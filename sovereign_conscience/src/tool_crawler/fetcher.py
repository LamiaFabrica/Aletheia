# medusa/src/tool_crawler/fetcher.py

import time
import requests
import logging
import hashlib
import json
from typing import Dict, Any, Optional, Tuple
from collections import OrderedDict
from functools import wraps
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

class LRUCacheWithTTL:
    """
    Simple in-memory LRU cache with TTL support for fetcher responses.
    """
    def __init__(self, max_size=128, ttl=300):
        self.max_size = max_size
        self.ttl = ttl  # seconds
        self.cache = OrderedDict()  # key: (value, expire_time)

    def get(self, key):
        now = time.time()
        if key in self.cache:
            value, expire = self.cache[key]
            if expire is None or expire > now:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                return value
            else:
                # Expired
                del self.cache[key]
        return None

    def set(self, key, value):
        expire = time.time() + self.ttl if self.ttl else None
        self.cache[key] = (value, expire)
        self.cache.move_to_end(key)
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def clear(self):
        self.cache.clear()

    def stats(self):
        now = time.time()
        valid = sum(1 for v, e in self.cache.values() if e is None or e > now)
        return {
            'max_size': self.max_size,
            'ttl': self.ttl,
            'current_size': len(self.cache),
            'valid_entries': valid
        }

class ToolFetcher:
    """
    Handles all network requests for the tool extraction crawler.
    Supports robots.txt, configurable user-agent, politeness, retries, JS rendering, caching, and session management.
    Enforces robots.txt and crawl-delay via PolicyAdherencePlugin if provided.
    DB logging is now handled by the orchestrator, not directly here.

    Session Management (F2.12):
    - Uses requests.Session() for all HTTP requests to enable cookie persistence, connection pooling, and better handling of sites that require sessions.
    - Each ToolFetcher instance maintains its own session (future: can be extended for per-domain session isolation).
    - Custom session headers can be provided via the session_headers argument.

    Caching (MVP):
    - In-memory LRU cache with TTL for static fetches (not JS-rendered fetches).
    - Configurable cache size and TTL.
    - Methods for cache stats and manual invalidation.
    - Prepares for future pluggable cache backends.
    """
    def __init__(self, user_agent: str = None, politeness_delay: float = 1.0, cache_enabled: bool = False, cache_size: int = 128, cache_ttl: int = 300, request_timeout: float = 15.0, robots_policy_plugin=None, js_rendering_enabled: bool = False, js_domains: list = None, js_timeout: float = 15.0, session_headers: Optional[dict] = None):
        self.user_agent = user_agent or 'MedusaCrawler/1.0'
        self.politeness_delay = politeness_delay
        self.cache_enabled = cache_enabled
        self.cache_size = cache_size
        self.cache_ttl = cache_ttl
        self.request_timeout = request_timeout
        self.robots_policy_plugin = robots_policy_plugin  # For robots.txt checks
        self.logger = logging.getLogger("ToolFetcher")
        self.session = requests.Session()  # Session management for HTTP requests
        if session_headers:
            self.session.headers.update(session_headers)
        self.js_rendering_enabled = js_rendering_enabled
        self.js_domains = js_domains or []  # List of domains to force JS rendering
        self.js_timeout = js_timeout
        self.js_renderer = None  # Playwright is used directly
        self.per_domain_sessions = None  # Not implemented yet
        # In-memory LRU cache with TTL for static fetches
        self.cache = LRUCacheWithTTL(max_size=cache_size, ttl=cache_ttl) if cache_enabled else None
        # TODO: Add support for disk/redis cache backends in future

    def _make_cache_key(self, url: str, headers: dict = None, params: dict = None) -> str:
        # Normalize cache key: URL + sorted headers + sorted params
        key = url
        if headers:
            key += '|' + '|'.join(f'{k}:{v}' for k, v in sorted(headers.items()))
        if params:
            key += '|' + '|'.join(f'{k}:{v}' for k, v in sorted(params.items()))
        return key

    def render_js_with_playwright(self, url: str, wait_selector: str = None, timeout: float = None) -> str:
        """
        Fetches and renders a page using Playwright (Chromium headless).
        Optionally waits for a selector before extracting HTML.
        Returns the rendered HTML as a string.
        """
        timeout = timeout or self.js_timeout
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=self.user_agent)
                page = context.new_page()
                page.goto(url, timeout=int(timeout * 1000))
                if wait_selector:
                    page.wait_for_selector(wait_selector, timeout=int(timeout * 1000))
                else:
                    page.wait_for_load_state('networkidle', timeout=int(timeout * 1000))
                html = page.content()
                page.close()
                context.close()
                browser.close()
                return html
        except PlaywrightTimeoutError as e:
            self.logger.error(f"Playwright timeout for {url}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Playwright error for {url}: {e}")
            raise

    def fetch(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetches a URL or resource as specified in source_config.
        Returns a dict with content, headers, status, final_url, error, data_size, crawl_id, content_hash, and redirect_chain_json.
        Implements incremental crawling: conditional GETs, 304 handling, content hashing, redirect chain, and correct politeness delay.
        """
        url = source_config.get('url')
        crawl_id = source_config.get('crawl_id')
        previous_etag = source_config.get('previous_etag')
        previous_last_modified = source_config.get('previous_last_modified')
        headers = {'User-Agent': self.user_agent}
        if previous_etag:
            headers['If-None-Match'] = previous_etag
        if previous_last_modified:
            headers['If-Modified-Since'] = previous_last_modified
        log_data = {"url": url, "user_agent": self.user_agent, "politeness_delay": self.politeness_delay}
        if hasattr(self, 'orchestrator_logger') and self.orchestrator_logger:
            self.orchestrator_logger.log_event("FETCH_ATTEMPT", log_data, severity="DEBUG", message=f"About to fetch URL: {url}")
        else:
            self.logger.debug(f"[FETCH_ATTEMPT] URL: {url}, User-Agent: {self.user_agent}, Delay: {self.politeness_delay}s")
        # --- robots.txt and crawl-delay enforcement ---
        crawl_delay = self.politeness_delay
        if self.robots_policy_plugin:
            policy = self.robots_policy_plugin.check_url_policy(url, self.user_agent, politeness_delay=self.politeness_delay)
            crawl_delay = policy.get('crawl_delay', self.politeness_delay)
            if not policy['allowed']:
                if policy['reason'] == 'disallowed_by_robots':
                    msg = f"Fetch disallowed by robots.txt for URL: {url}"
                    if hasattr(self, 'orchestrator_logger') and self.orchestrator_logger:
                        self.orchestrator_logger.log_event("FETCH_POLICY_BLOCKED", {"url": url, "policy": policy}, severity="WARNING", message=msg)
                    else:
                        self.logger.warning(msg)
                    return {
                        'content': None,
                        'headers': {},
                        'status': 'disallowed_by_policy',
                        'final_url': url,
                        'error': 'Disallowed by robots.txt',
                        'data_size': 0,
                        'crawl_id': crawl_id,
                        'policy': policy,
                        'content_hash': None,
                        'redirect_chain_json': None
                    }
                elif policy['reason'] == 'crawl_delay':
                    msg = f"Fetch delayed by crawl-delay policy for URL: {url} until {policy['restricted_until']}"
                    if hasattr(self, 'orchestrator_logger') and self.orchestrator_logger:
                        self.orchestrator_logger.log_event("FETCH_POLICY_DELAYED", {"url": url, "policy": policy}, severity="INFO", message=msg)
                    else:
                        self.logger.info(msg)
                    return {
                        'content': None,
                        'headers': {},
                        'status': 'delayed_by_policy',
                        'final_url': url,
                        'error': f"Crawl-delay in effect until {policy['restricted_until']}",
                        'data_size': 0,
                        'crawl_id': crawl_id,
                        'policy': policy,
                        'content_hash': None,
                        'redirect_chain_json': None
                    }
        # --- End robots.txt/crawl-delay enforcement ---
        status = None
        content = None
        error_message = None
        data_size = 0
        resp = None
        content_hash = None
        redirect_chain_json = None
        # --- JS Rendering decision ---
        use_js = self.js_rendering_enabled or (self.js_domains and any(domain in url for domain in self.js_domains))
        self.logger.debug(f"[FETCH] use_js={use_js} js_rendering_enabled={self.js_rendering_enabled} js_domains={self.js_domains} url={url}")
        if use_js:
            try:
                self.logger.info(f"[FETCH] Using Playwright JS rendering for {url}")
                time.sleep(crawl_delay)
                content = self.render_js_with_playwright(url)
                status = '200_js_rendered'
                data_size = len(content.encode('utf-8')) if content else 0
                # Content hash for JS
                content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest() if content else None
                # Playwright does not expose redirect chain; placeholder only
                redirect_chain_json = json.dumps([{'url': url, 'status_code': 200}])
                return {
                    'content': content,
                    'headers': {},
                    'status': status,
                    'final_url': url,
                    'error': None,
                    'data_size': data_size,
                    'crawl_id': crawl_id,
                    'content_hash': content_hash,
                    'redirect_chain_json': redirect_chain_json
                }
            except Exception as e:
                self.logger.error(f"JS rendering failed for {url}: {e}. Falling back to static fetch.")
                # Fallback to static fetch below
        # --- Static fetch ---
        cache_key = self._make_cache_key(url, headers)
        if self.cache_enabled and self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                self.logger.info(f"[CACHE HIT] {url}")
                return cached.copy()  # Return a copy to avoid mutation
        try:
            self.logger.info(f"[FETCH] Using static fetch for {url}")
            time.sleep(crawl_delay)
            resp = self.session.get(url, headers=headers, timeout=self.request_timeout, allow_redirects=True)
            # --- 304 Not Modified Handling ---
            if resp.status_code == 304:
                status = '304_not_modified'
                self.logger.info(f"[FETCH_RESULT] URL: {url} status: {status} (Not Modified)")
                # If cache enabled, refresh TTL
                if self.cache_enabled and self.cache is not None:
                    cached = self.cache.get(cache_key)
                    if cached is not None:
                        self.cache.set(cache_key, cached)
                return {
                    'content': None,
                    'headers': dict(resp.headers),
                    'status': status,
                    'final_url': resp.url,
                    'error': None,
                    'data_size': 0,
                    'crawl_id': crawl_id,
                    'content_hash': None,
                    'redirect_chain_json': json.dumps([
                        {'url': r.url, 'status_code': r.status_code} for r in resp.history
                    ] + [{'url': resp.url, 'status_code': resp.status_code}]) if resp.history else json.dumps([{'url': resp.url, 'status_code': resp.status_code}])
                }
            resp.raise_for_status()
            content = resp.text
            status = str(resp.status_code)
            data_size = len(resp.content)
            # Content hash for static fetch
            content_hash = hashlib.sha256(resp.content).hexdigest() if resp.content else None
            # Redirect chain reporting
            if resp.history:
                redirect_chain_json = json.dumps([
                    {'url': r.url, 'status_code': r.status_code} for r in resp.history
                ] + [{'url': resp.url, 'status_code': resp.status_code}])
            else:
                redirect_chain_json = json.dumps([{'url': resp.url, 'status_code': resp.status_code}])
        except requests.exceptions.Timeout:
            status = 'error_timeout'
            error_message = "Request timed out"
        except requests.exceptions.ConnectionError:
            status = 'error_connection'
            error_message = "Connection error"
        except requests.exceptions.HTTPError as e_http:
            status = f'error_http_{getattr(e_http.response, 'status_code', 'unknown')}'
            error_message = str(e_http)
        except requests.exceptions.TooManyRedirects:
            status = 'error_redirects'
            error_message = "Too many redirects"
        except Exception as e:
            status = 'error_generic'
            error_message = str(e)
        log_result = {
            'url': url,
            'status': status,
            'error': error_message,
            'data_size': data_size,
            'crawl_id': crawl_id
        }
        if hasattr(self, 'orchestrator_logger') and self.orchestrator_logger:
            self.orchestrator_logger.log_event("FETCH_RESULT", log_result, severity="INFO" if status and 'error' not in status else "ERROR", message=f"Fetch result for URL: {url}")
        else:
            if status and 'error' not in status:
                self.logger.info(f"[FETCH_RESULT] URL: {url} status: {status} size: {data_size}")
            else:
                self.logger.error(f"[FETCH_RESULT] URL: {url} status: {status} error: {error_message}")
        result = {
            'content': content,
            'headers': dict(resp.headers) if resp and status and 'error' not in status else {},
            'status': status,
            'final_url': resp.url if resp and status and 'error' not in status else url,
            'error': error_message,
            'data_size': data_size,
            'crawl_id': crawl_id,
            'content_hash': content_hash,
            'redirect_chain_json': redirect_chain_json
        }
        if self.cache_enabled and self.cache is not None and status and 'error' not in status:
            self.cache.set(cache_key, result.copy())
        return result

    def cache_stats(self):
        """Return cache statistics (if enabled)."""
        if self.cache_enabled and self.cache:
            return self.cache.stats()
        return None

    def clear_cache(self):
        """Clear the in-memory cache (if enabled)."""
        if self.cache_enabled and self.cache:
            self.cache.clear()

    def adaptive_politeness(self, domain: str) -> float:
        """Stub for adaptive politeness delay logic."""
        # Implement adaptive delay logic here
        return self.politeness_delay

    def render_js(self, url: str) -> str:
        """Stub for JS rendering logic."""
        # Integrate with a headless browser if needed
        return ""

    def close(self):
        """Close the session and cleanup."""
        self.session.close()
    # TODO: Add methods for robots.txt checking (using robots_policy_plugin), adaptive politeness, retry logic, session management, JS rendering, and caching. 