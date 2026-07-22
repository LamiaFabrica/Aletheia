# medusa/src/tool_crawler/orchestrator.py

from enum import Enum, auto
from threading import Event
from typing import List, Dict, Any
import json
from datetime import datetime, timedelta
from medusa.src.tool_crawler.fetcher import ToolFetcher
from medusa.src.tool_crawler.parsers.plugins.BinMan_RubbishRecycler import BinMan_RubbishRecycler
from medusa.src.tool_crawler.normalizer import ToolDataNormalizer
from medusa.src.tool_crawler.db_writer import ToolDBWriter
from medusa.src.tool_crawler.logger import ToolLogger
from medusa.src.tool_crawler.parsers.parser_plugin_manager import ParserPluginManager
from urllib.parse import urlparse
import threading
import time
import re

class OrchestratorState(Enum):
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()

class ToolCrawlerOrchestrator:
    """
    Orchestrator for Medusa's dynamic, database-driven tool crawl queue and plugin system.
    Integrates with crawl_history for incremental crawling, campaign linkage, and robust error handling.
    """
    def __init__(self, db_conn, socketio, reschedule_days=90):
        self.db_conn = db_conn
        self.logger = ToolLogger(socketio)
        self.fetcher = ToolFetcher()
        self.fetcher.orchestrator_logger = self.logger
        self.normalizer = ToolDataNormalizer()
        self.db_writer = ToolDBWriter(db_conn, orchestrator_logger=self.logger)
        self.parser_manager = ParserPluginManager()
        self.state = OrchestratorState.IDLE
        self.control_event = Event()
        self.control_event.set()
        self.reschedule_days = reschedule_days
        # Focused crawling config (can be replaced by campaign profile)
        self.focused_crawl_config = {
            'keywords': ['docs', 'manual', 'usage', 'reference', 'api'],
            'url_patterns': [r'/docs', r'/manual', r'/reference', r'\.pdf$', r'\.md$'],
            'domain_whitelist': [],
            'domain_blacklist': [],
            'weights': {
                'anchor': 3,
                'url': 2,
                'meta': 1,
                'proximity': 1,
                'domain': 1
            }
        }

    def load_crawl_queue(self):
        """
        Loads tools to crawl from crawler_tool_queue, prioritizing by focus_score DESC, then priority DESC, then id ASC.
        Returns a list of dicts.
        """
        try:
        with self.db_conn.get_cursor() as cur:
            cur.execute("""
                    SELECT id, tool_name, target_url, status, completion_percentage, force_recrawl_flag, parser_hint, source_campaign_id, focus_score
                FROM crawler_tool_queue
                WHERE status != 'completed' OR force_recrawl_flag = TRUE
                    ORDER BY focus_score DESC, priority DESC, id ASC
            """)
            rows = cur.fetchall()
                self.logger.log_event("ORCHESTRATOR_QUEUE_LOADED", {"queue_length": len(rows)}, severity="INFO", message=f"Queue loaded with {len(rows)} items.")
            return [dict(row) for row in rows]
        except Exception as e:
            self.logger.log_event("ORCHESTRATOR_QUEUE_LOAD_ERROR", {"error": str(e)}, severity="ERROR", message="Failed to load crawl queue.")
            return []

    def update_tool_status(self, cur, tool_id, status, completion, last_crawled_at=None, force_recrawl_flag=False):
        try:
            next_scheduled_crawl_at = None
            if status in ['completed', 'error']:
                # Schedule next crawl using configurable interval
                next_scheduled_crawl_at = datetime.utcnow() + timedelta(days=self.reschedule_days)
            cur.execute("""
                UPDATE crawler_tool_queue
                SET status = %s, completion_percentage = %s, last_crawled_at = %s, force_recrawl_flag = %s, next_scheduled_crawl_at = %s
                WHERE id = %s
            """, (status, completion, last_crawled_at or datetime.utcnow(), False, next_scheduled_crawl_at, tool_id))
            self.logger.log_event("ORCHESTRATOR_TOOL_STATUS_UPDATED", {"tool_id": tool_id, "status": status}, severity="INFO", message=f"Tool status updated to {status}.")
        except Exception as e:
            self.logger.log_event("ORCHESTRATOR_STATUS_UPDATE_ERROR", {"tool_id": tool_id, "error": str(e)}, severity="ERROR", message="Failed to update tool status.")
            raise

    def check_completion(self, normalized_tool):
        """
        Returns percent of required fields present and non-empty in normalized_tool['tool'].
        For now, just checks a basic set of fields.
        """
        required = [
            'tool_name', 'description', 'category', 'official_site_url',
            'supported_os', 'tags', 'license', 'version', 'dependencies'
        ]
        tool = normalized_tool['tool']
        present = sum(1 for k in required if tool.get(k))
        return int(100 * present / len(required))

    def select_parser(self, parser_hint=None):
        """
        Select a parser plugin by name (parser_hint) or use the first enabled parser.
        """
        enabled_parsers = self.parser_manager.get_enabled_parsers()
        if parser_hint and parser_hint in enabled_parsers:
            return enabled_parsers[parser_hint]
        # Default: return the first enabled parser
        if enabled_parsers:
            return next(iter(enabled_parsers.values()))
        # Log and abort if no parser is available
        raise RuntimeError("No enabled parser plugins available! All crawls will fail. Check /api/plugins/parsers/status for details.")

    def crawl_all(self):
            queue = self.load_crawl_queue()
            self.logger.log_event("ORCHESTRATOR_QUEUE_LOADED", {"queue_length": len(queue)}, severity="INFO", message=f"Queue loaded with {len(queue)} items.")
            for job in queue:
                if self.state == 'stopped':
                    self.logger.log_event("ORCHESTRATOR_STOPPED", {}, severity="INFO", message="Crawl stopped by operator.")
                break
            self.control_event.wait()
            self.crawl_job(job)

    def search_for_manual(self, tool_name):
        """
        Stub for future integration: Use DuckDuckGo or another search engine to find the best doc/manual URL.
        """
        pass

    def run(self):
        """
        Persistent main loop for orchestrator operation. Manages state transitions and background operation.
        Should be started in a background thread by web_server.py.
        """
        import threading
        self.logger.log_event("ORCHESTRATOR_RUN_START", {}, severity="INFO", message="Orchestrator main loop starting.")
        while True:
            if self.state == OrchestratorState.STOPPED:
                self.logger.log_event("ORCHESTRATOR_STOPPED", {}, severity="INFO", message="Orchestrator stopped. Exiting main loop.")
                break
            elif self.state == OrchestratorState.PAUSED:
                self.logger.log_event("ORCHESTRATOR_PAUSED", {}, severity="INFO", message="Orchestrator paused. Waiting...")
                self.control_event.wait()  # Block until resumed
                continue
            elif self.state == OrchestratorState.RUNNING:
                self.logger.log_event("ORCHESTRATOR_RUNNING", {}, severity="INFO", message="Orchestrator running. Starting crawl_all().")
                try:
                    self.crawl_all()
                except Exception as e:
                    self.logger.log_event("ORCHESTRATOR_RUN_ERROR", {"error": str(e)}, severity="ERROR", message="Error in crawl_all().")
                # After crawl_all, check state again
                if self.state == OrchestratorState.RUNNING:
                    self.state = OrchestratorState.IDLE
                    self.logger.log_event("ORCHESTRATOR_IDLE", {}, severity="INFO", message="Orchestrator finished crawl_all, now idle.")
            elif self.state == OrchestratorState.IDLE:
                self.control_event.wait(timeout=1)  # Wait for state change
            elif self.state == OrchestratorState.STOPPING:
                self.logger.log_event("ORCHESTRATOR_STOPPING", {}, severity="INFO", message="Orchestrator stopping.")
                self.state = OrchestratorState.STOPPED
            else:
                self.logger.log_event("ORCHESTRATOR_UNKNOWN_STATE", {"state": str(self.state)}, severity="WARNING", message="Unknown orchestrator state.")
                self.state = OrchestratorState.IDLE

    def get_state(self):
        """Return the current orchestrator state as a string."""
        return self.state.name

    def is_running(self):
        """Return True if orchestrator is in RUNNING state."""
        return self.state == OrchestratorState.RUNNING

    def retry_with_backoff(self, func, max_retries=3, base_delay=2, *args, **kwargs):
        """
        Retry a function with exponential backoff on failure.
        """
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.logger.log_event("ORCHESTRATOR_RETRY", {"attempt": attempt+1, "error": str(e)}, severity="WARNING", message=f"Retrying after error: {e}")
                time.sleep(base_delay * (2 ** attempt))
        raise Exception(f"Failed after {max_retries} retries.")

    def crawl_incremental(self, since_timestamp=None, filter_func=None):
        """
        Crawl only tools updated since a given timestamp or matching a filter function.
        """
        queue = self.load_crawl_queue()
        if since_timestamp:
            queue = [job for job in queue if job.get('last_updated_timestamp') and job['last_updated_timestamp'] > since_timestamp]
        if filter_func:
            queue = [job for job in queue if filter_func(job)]
        self.logger.log_event("ORCHESTRATOR_INCREMENTAL_CRAWL", {"queue_length": len(queue)}, severity="INFO", message="Starting incremental/focused crawl.")
        for job in queue:
            self.crawl_job(job)

    def prioritize_parsers(self, parser_hint=None):
        """
        Rank/select parsers based on plugin metadata or past success.
        """
        enabled_parsers = self.parser_manager.get_enabled_parsers()
        # Example: prioritize by a 'priority' attribute or past success rate
        ranked = sorted(enabled_parsers.values(), key=lambda p: getattr(p, 'priority', 0), reverse=True)
        if parser_hint:
            for parser in ranked:
                if getattr(parser, 'name', None) == parser_hint:
                    return parser
        return ranked[0] if ranked else None

    def crawl_job(self, job):
        """
        Crawl a single job with retry logic and error handling, fully integrated with crawl_history for incremental crawling.
        Ensures true atomicity: only one commit at the end, one rollback on error.
        """
        try:
            with self.db_conn.get_cursor() as cur:
                self.update_tool_status(cur, job['id'], 'running', 0, force_recrawl_flag=job.get('force_recrawl_flag', False))
                try:
                    parser = self.parser_manager.get_enabled_parsers().get(job.get('parser_hint')) or next(iter(self.parser_manager.get_enabled_parsers().values()))
                    print(f"[ORCH_DIAG] crawl_job: tool_name={job.get('tool_name')}, parser_hint={job.get('parser_hint')}, selected_parser={getattr(parser, 'name', type(parser).__name__)}")
                except Exception as e:
                    self.logger.log_event("ORCHESTRATOR_NO_PARSER", {"job_id": job['id'], "tool_name": job['tool_name']}, severity="ERROR", message=str(e))
                    self.update_tool_status(cur, job['id'], 'error_no_parser', 0)
                    return  # No commit here; will be committed at the end if no error
                # --- Crawl History: Read previous crawl state ---
                crawl_history = None
                previous_etag = None
                previous_last_modified = None
                previous_content_hash = None
                try:
                    cur.execute("""
                        SELECT last_etag, last_modified_header, content_hash, consecutive_errors
                        FROM crawl_history WHERE url = %s
                    """, (job['target_url'],))
                    row = cur.fetchone()
                    if row:
                        previous_etag = row[0]
                        previous_last_modified = row[1]
                        previous_content_hash = row[2]
                        consecutive_errors = row[3] or 0
                    else:
                        consecutive_errors = 0
                except Exception as e:
                    self.logger.log_event("ORCHESTRATOR_CRAWL_HISTORY_READ_ERROR", {"url": job['target_url'], "error": str(e)}, severity="ERROR", message="Failed to read crawl_history.")
                    previous_etag = previous_last_modified = previous_content_hash = None
                    consecutive_errors = 0
                # --- Fetch with incremental crawling ---
                fetch_result = self.fetcher.fetch({
                    'url': job['target_url'],
                    'crawl_id': job['id'],
                    'source_campaign_id': job.get('source_campaign_id'),
                    'previous_etag': previous_etag,
                    'previous_last_modified': previous_last_modified,
                    'previous_content_hash': previous_content_hash
                })
                fetch_status = fetch_result.get('status', '')
                now = datetime.utcnow()
                # --- Crawl History: Write/update after fetch ---
                if fetch_status == '304_not_modified':
                    # Only update last_crawled_at, reset consecutive_errors
                    cur.execute("""
                        UPDATE crawl_history SET last_crawled_at = %s, consecutive_errors = 0
                        WHERE url = %s
                    """, (now, fetch_result.get('final_url', job['target_url'])))
                    self.logger.log_event("ORCHESTRATOR_CRAWL_HISTORY_UPDATE_304", {"url": fetch_result.get('final_url', job['target_url'])}, severity="INFO", message="Crawl history updated for 304.")
                    self.update_tool_status(cur, job['id'], 'completed', 100, last_crawled_at=now)
                    return  # No commit here; will be committed at the end if no error
                elif fetch_status in ('200', '200_js_rendered') or fetch_status.startswith('200'):
                    # Insert or update crawl_history with all fields
                    headers = fetch_result.get('headers', {})
                    etag = headers.get('ETag') or headers.get('etag')
                    last_modified = headers.get('Last-Modified') or headers.get('last-modified')
                    cur.execute("""
                        INSERT INTO crawl_history (url, domain, last_crawled_at, last_etag, last_modified_header, content_hash, last_http_status_code, redirect_chain_json, consecutive_errors, source_campaign_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s)
                        ON CONFLICT (url) DO UPDATE SET
                            domain = EXCLUDED.domain,
                            last_crawled_at = EXCLUDED.last_crawled_at,
                            last_etag = EXCLUDED.last_etag,
                            last_modified_header = EXCLUDED.last_modified_header,
                            content_hash = EXCLUDED.content_hash,
                            last_http_status_code = EXCLUDED.last_http_status_code,
                            redirect_chain_json = EXCLUDED.redirect_chain_json,
                            consecutive_errors = 0,
                            source_campaign_id = EXCLUDED.source_campaign_id
                    """,
                    (
                        fetch_result.get('final_url', job['target_url']),
                        urlparse(fetch_result.get('final_url', job['target_url'])).netloc,
                        now,
                        etag,
                        last_modified,
                        fetch_result.get('content_hash'),
                        int(fetch_result.get('status', '200').split('_')[0]),
                        json.dumps(fetch_result.get('redirect_chain_json')) if fetch_result.get('redirect_chain_json') is not None else None,
                        job.get('source_campaign_id')
                    ))
                    self.logger.log_event("ORCHESTRATOR_CRAWL_HISTORY_UPSERT_200", {"url": fetch_result.get('final_url', job['target_url'])}, severity="INFO", message="Crawl history upserted for 200.")
                    # Proceed to parse/normalize/write
                elif fetch_status in ('disallowed_by_policy', 'delayed_by_policy'):
                    # Do not update crawl_history, just log and update tool status
                    self.update_tool_status(cur, job['id'], fetch_status, 0)
                    return  # No commit here; will be committed at the end if no error
                elif fetch_status.startswith('error'):
                    # Increment consecutive_errors
                    cur.execute("""
                        INSERT INTO crawl_history (url, domain, last_crawled_at, last_http_status_code, consecutive_errors, source_campaign_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (url) DO UPDATE SET
                            last_crawled_at = EXCLUDED.last_crawled_at,
                            last_http_status_code = EXCLUDED.last_http_status_code,
                            consecutive_errors = crawl_history.consecutive_errors + 1,
                            source_campaign_id = EXCLUDED.source_campaign_id
                    """,
                    (
                        fetch_result.get('final_url', job['target_url']),
                        urlparse(fetch_result.get('final_url', job['target_url'])).netloc,
                        now,
                        int(fetch_result.get('status', '0').split('_')[-1]) if '_' in fetch_result.get('status', '') else 0,
                        consecutive_errors + 1,
                        job.get('source_campaign_id')
                    ))
                    self.logger.log_event("ORCHESTRATOR_CRAWL_HISTORY_ERROR", {"url": fetch_result.get('final_url', job['target_url']), "status": fetch_status}, severity="WARNING", message="Crawl history updated for error.")
                    self.update_tool_status(cur, job['id'], 'error_fetch', 0)
                    return  # No commit here; will be committed at the end if no error
                # --- Parse and normalize ---
                try:
                    normalized_tool_data = parser.parse(fetch_result)
                except Exception as e:
                    self.logger.log_event("ORCHESTRATOR_PARSE_ERROR", {"job_id": job['id'], "error": str(e)}, severity="ERROR", message="Parser failed after fetch.")
                    self.update_tool_status(cur, job['id'], 'error_parse', 0)
                    return  # No commit here; will be committed at the end if no error
                write_result = self.db_writer.write(normalized_tool_data, plugin_name=parser.__class__.__name__, cur=cur)
                if write_result.get('status') == 'filtered':
                    self.update_tool_status(cur, job['id'], 'filtered', 100)
                    return  # No commit here; will be committed at the end if no error
                elif write_result.get('status') == 'failed':
                    self.update_tool_status(cur, job['id'], 'error_write', 0)
                    return  # No commit here; will be committed at the end if no error
                # When inserting discovered URLs, compute focus_score
                discovered_urls = normalized_tool_data.get('discovered_urls', [])
                for url in discovered_urls:
                    try:
                        # For MVP, anchor_text/meta/referrer_score are not available; use None/0
                        focus_score, _ = self.score_discovered_url(url)
                        cur.execute(
                            "INSERT INTO crawler_tool_queue (tool_name, target_url, status, next_scheduled_crawl_at, focus_score) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                            (job['tool_name'], url, 'pending', datetime.utcnow() + timedelta(days=self.reschedule_days), focus_score)
                        )
                    except Exception as e:
                        self.logger.log_event("ORCHESTRATOR_DISCOVERED_URL_ERROR", {"url": url, "error": str(e)}, severity="WARNING", message="Failed to add discovered URL.")
                self.update_tool_status(cur, job['id'], 'completed', 100)
                # --- Only one commit at the end of all successful operations ---
                self.db_conn.commit()
        except Exception as e:
            self.logger.log_event("ORCHESTRATOR_TOOL_ERROR", {"job_id": job['id'], "error": str(e)}, severity="ERROR", message="Error processing tool.")
            try:
                self.db_conn.rollback()
            except Exception as rollback_exc:
                self.logger.log_event("ORCHESTRATOR_ROLLBACK_ERROR", {"error": str(rollback_exc)}, severity="CRITICAL", message="Rollback failed.")

    def pause(self):
        """Pause the orchestrator (for UI control)."""
        self.state = OrchestratorState.PAUSED
        self.control_event.clear()
        self.logger.log_event("ORCHESTRATOR_PAUSED", {}, severity="INFO", message="Crawl paused by operator.")

    def resume(self):
        """Resume the orchestrator (for UI control)."""
        self.state = OrchestratorState.RUNNING
        self.control_event.set()
        self.logger.log_event("ORCHESTRATOR_RESUMED", {}, severity="INFO", message="Crawl resumed by operator.")

    def stop(self):
        """Stop the orchestrator gracefully (for UI control)."""
        self.state = OrchestratorState.STOPPED
        self.control_event.set()
        self.logger.log_event("ORCHESTRATOR_STOPPED", {}, severity="INFO", message="Crawl stopped by operator.")

    def set_state(self, new_state: OrchestratorState):
        """
        Centralized state transition logic. Logs, emits events, and handles cleanup.
        """
        prev_state = self.state
        if new_state == OrchestratorState.PAUSED:
            self.pause()
        elif new_state == OrchestratorState.RUNNING:
            self.resume()
        elif new_state == OrchestratorState.STOPPED:
            self.stop()
        else:
            self.logger.log_event("ORCHESTRATOR_STATE_ERROR", {"state": new_state}, severity="WARNING", message="Unknown state requested.")
        self.logger.log_event("ORCHESTRATOR_STATE_CHANGE", {"from": prev_state.name, "to": new_state.name}, severity="INFO", message=f"State changed from {prev_state.name} to {new_state.name}.")

    # --- Focused crawling scoring function ---
    def score_discovered_url(self, url, anchor_text=None, meta=None, referrer_score=0, config=None):
        """
        Compute a focus_score for a discovered URL based on heuristics and config.
        - anchor_text: text of the link
        - meta: dict of metadata from the source page
        - referrer_score: focus_score of the referring page (proximity)
        - config: config dict (defaults to self.focused_crawl_config)
        Returns: (score, breakdown_dict)
        """
        config = config or self.focused_crawl_config
        weights = config['weights']
        # Anchor text keyword match
        anchor_match = 0
        if anchor_text:
            for kw in config['keywords']:
                if kw.lower() in anchor_text.lower():
                    anchor_match = 1
                    break
        # URL pattern match
        url_match = 0
        for pat in config['url_patterns']:
            if re.search(pat, url, re.IGNORECASE):
                url_match = 1
                break
        # Metadata match (simple: any keyword in meta fields)
        meta_match = 0
        if meta:
            for v in meta.values():
                for kw in config['keywords']:
                    if kw.lower() in str(v).lower():
                        meta_match = 1
                        break
        # Proximity (normalized: 0-1)
        proximity = min(max(referrer_score, 0), 1)
        # Domain whitelist/blacklist
        domain_score = 0
        domain = urlparse(url).netloc
        if config['domain_whitelist'] and domain in config['domain_whitelist']:
            domain_score = 1
        elif config['domain_blacklist'] and domain in config['domain_blacklist']:
            domain_score = -1
        # Weighted sum
        score = (
            weights['anchor'] * anchor_match +
            weights['url'] * url_match +
            weights['meta'] * meta_match +
            weights['proximity'] * proximity +
            weights['domain'] * domain_score
        )
        # Normalize (optional: divide by sum of positive weights)
        max_score = sum([v for v in weights.values() if v > 0])
        norm_score = score / max_score if max_score else 0
        breakdown = {
            'anchor': anchor_match,
            'url': url_match,
            'meta': meta_match,
            'proximity': proximity,
            'domain': domain_score,
            'weights': weights.copy(),
            'raw_score': score,
            'norm_score': norm_score
        }
        self.logger.log_event(
            'FOCUSED_CRAWL_SCORE',
            {'url': url, 'breakdown': breakdown, 'config': config},
            severity='DEBUG',
            message=f"Focused crawl score for {url}: {norm_score:.2f} (raw: {score})"
        )
        return norm_score, breakdown

# To use:
# orchestrator = ToolCrawlerOrchestrator(db_conn, socketio)
# orchestrator.crawl_all() 