#!/usr/bin/env python3
"""
Security crawler for Medusa project.
Collects security information from various sources to feed Medusa's knowledge base.
"""

import os
import sys
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
from datetime import datetime, timedelta
import threading
from typing import Dict, List, Optional, Set, Any
import re
from threading import Event
import psutil
from collections import deque
import time
import atexit
import enum
from medusa.src.tool_crawler.plugin_base import EnrichmentPluginBase, PluginConfig
from langdetect import detect as lang_detect

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from medusa.src.database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CrawlerState(enum.Enum):
    IDLE = 'idle'
    RUNNING = 'running'
    PAUSED = 'paused'
    STOPPED = 'stopped'
    COMPLETED = 'completed'
    FAILED = 'failed'
    ERROR_LIMIT = 'error_limit'
    EXHAUSTED = 'exhausted'

class SecurityCrawler:
    def __init__(self):
        """Initialize the security crawler."""
        self.db = Database()
        self.visited_urls: Set[str] = set()
        self.session = requests.Session()
        self._load_settings()
        self.indefinite_mode = False
        self.max_consecutive_errors = 10
        self.consecutive_errors = 0
        self.state_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'indefinite_crawl_state.json')
        self.resume_state = False
        self._load_indefinite_settings()
        
        # Define source URLs
        self.sources = {
            'nmap': {
                'url': 'https://nmap.org/docs.html',
                'type': 'documentation'
            },
            'cve': {
                'url': 'https://cve.mitre.org/data/downloads/allitems.html',
                'type': 'vulnerabilities'
            },
            'owasp': {
                'url': 'https://owasp.org/www-project-top-ten/',
                'type': 'best_practices'
            },
            'iana': {
                'url': 'https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml',
                'type': 'ports'
            }
        }

        self.current_task = None
        self.processing_queue = deque(maxlen=10)
        self.recent_activities = deque(maxlen=50)
        self._lock = threading.Lock()
        self.enrichment_plugins = self._load_enrichment_plugins()

        atexit.register(self.save_indefinite_state)

    def _load_settings(self):
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            crawler_settings = config.get('crawler_settings', {})
            self.user_agent = crawler_settings.get('user_agent', 'MedusaCrawler/1.0 (+https://github.com/yourusername/medusa)')
            self.politeness_delay = int(crawler_settings.get('politeness_delay', 3))
            self.indefinite_mode = bool(crawler_settings.get('indefinite_mode', False))
            self.max_consecutive_errors = int(crawler_settings.get('max_consecutive_errors', 10))
        else:
            self.user_agent = 'MedusaCrawler/1.0 (+https://github.com/yourusername/medusa)'
            self.politeness_delay = 3
            self.indefinite_mode = False
            self.max_consecutive_errors = 10
        self.session.headers.update({'User-Agent': self.user_agent})

    def _load_indefinite_settings(self):
        # On startup, if indefinite mode is enabled and state file exists, load state
        if self.indefinite_mode and os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                self.visited_urls = set(state.get('visited_urls', []))
                self.consecutive_errors = state.get('consecutive_errors', 0)
                self.resume_state = True
                self._indefinite_queue = state.get('queue', [])
                self._indefinite_results = state.get('results', None)
                # Optionally: emit log event for auto-resume
                print('[Indefinite Mode] Auto-resume: loaded crawl state.')
            except Exception as e:
                print(f'[Indefinite Mode] Failed to load crawl state: {e}')
                self.resume_state = False
                self._indefinite_queue = []
                self._indefinite_results = None
        else:
            self.resume_state = False
            self._indefinite_queue = []
            self._indefinite_results = None

    def save_indefinite_state(self):
        if not self.indefinite_mode:
            return
        try:
            state = {
                'visited_urls': list(self.visited_urls),
                'consecutive_errors': self.consecutive_errors,
                'queue': getattr(self, '_indefinite_queue', []),
                'results': getattr(self, '_indefinite_results', None)
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f)
        except Exception as e:
            print(f'[Indefinite Mode] Failed to save crawl state: {e}')

    def crawl_source(self, source: str, max_depth: int = 3, max_pages: int = 1000, 
                    stop_event: Optional[Event] = None, pause_event: Optional[Event] = None, is_custom: bool = False) -> Dict:
        """
        Crawl a documentation source up to max_depth (or unlimited if max_depth=None or 0).
        """
        self._load_settings()  # Reload settings before each crawl
        self.consecutive_errors = 0
        if is_custom:
            start_url = source
            source_type = 'custom'
        else:
            if source not in self.sources:
                raise ValueError(f"Unknown source: {source}")
            start_url = self.sources[source]['url']
            source_type = self.sources[source]['type']
        # Indefinite mode: restore state if available
        if self.indefinite_mode and self.resume_state and self._indefinite_results:
            results = self._indefinite_results
            queue = deque(self._indefinite_queue)
            self.resume_state = False
            print('[Indefinite Mode] Resuming crawl from saved state.')
        else:
            self.visited_urls.clear()
            results = {
                'source': source,
                'type': source_type,
                'start_time': datetime.now().isoformat(),
                'pages_crawled': 0,
                'knowledge_gained': 0
            }
            queue = deque([start_url])
        try:
            # Interpret max_depth=0 or None as unlimited
            unlimited_depth = max_depth is None or max_depth == 0
            if self.indefinite_mode:
                self._crawl_indefinite(queue, max_depth, max_pages, stop_event, pause_event, results, unlimited_depth)
            else:
                self._crawl_url(start_url, max_depth, max_pages, stop_event, pause_event, results, unlimited_depth=unlimited_depth)
        except Exception as e:
            logger.error(f"Error crawling {source}: {e}")
            results['error'] = str(e)
        results['end_time'] = datetime.now().isoformat()
        self.save_indefinite_state()
        return results

    def _crawl_indefinite(self, queue: deque, max_depth: int, max_pages: int, stop_event: Optional[Event], pause_event: Optional[Event], results: Dict, unlimited_depth: bool = False):
        """
        Indefinite crawl mode, up to max_depth (or unlimited if unlimited_depth=True).
        """
        while queue:
            url, *rest = queue.popleft() if isinstance(queue[0], (list, tuple)) else (queue.popleft(),)
            if stop_event and stop_event.is_set():
                break
            while pause_event and pause_event.is_set():
                time.sleep(0.5)
            if url in self.visited_urls:
                continue
            self.visited_urls.add(url)
            results['pages_crawled'] += 1
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                # Extract info
                if results['type'] == 'documentation':
                    self._extract_documentation(soup, url, results)
                elif results['type'] == 'vulnerabilities':
                    self._extract_vulnerabilities(soup, url, results)
                elif results['type'] == 'best_practices':
                    self._extract_best_practices(soup, url, results)
                elif results['type'] == 'ports':
                    self._extract_port_info(soup, url, results)
                else:
                    self._extract_general_info(soup, url, results)
                # --- Enrichment: run plugins and live update DB ---
                mde_id = url  # For now, use URL as mde_id; can be improved for entity-centric crawls
                core_entity_data = {'name': soup.title.string if soup.title else url, 'description': '', 'summary': '', 'content': soup.get_text()[:500]}
                self._enrich_page(response.text, url, results['type'], mde_id, core_entity_data)
                # Find new links
                if max_depth > 0 or unlimited_depth:
                    for link in soup.find_all('a', href=True):
                        next_url = urljoin(url, link['href'])
                        if self._should_follow_link(next_url, url) and next_url not in self.visited_urls:
                            queue.append((next_url,))
                self.consecutive_errors = 0
            except Exception as e:
                logger.error(f"Error crawling {url}: {e}")
                self.consecutive_errors += 1
                if self.consecutive_errors >= self.max_consecutive_errors:
                    logger.error(f"[Indefinite Mode] Max consecutive errors reached ({self.max_consecutive_errors}). Stopping crawl.")
                    results['error'] = f"Max consecutive errors reached: {self.max_consecutive_errors}"
                    self.save_indefinite_state()
                    return
            # Save state after each page
            self._indefinite_queue = list(queue)
            self._indefinite_results = results
            self.save_indefinite_state()
            time.sleep(self.politeness_delay)
        # If queue is empty, crawl is exhausted
        print('[Indefinite Mode] Crawl exhausted: all reachable pages visited.')
        self._indefinite_queue = []
        self._indefinite_results = None
        self.save_indefinite_state()

    def _crawl_url(self, url: str, max_depth: int, max_pages: int, 
                  stop_event: Optional[Event], pause_event: Optional[Event], results: Dict, depth: int = 0, unlimited_depth: bool = False) -> None:
        """
        Crawl a single URL, recursing up to max_depth (or unlimited if unlimited_depth=True).
        """
        if stop_event and stop_event.is_set():
            return
        # PAUSE SUPPORT
        while pause_event and pause_event.is_set():
            time.sleep(0.5)
        if url in self.visited_urls or results['pages_crawled'] >= max_pages:
            return
        self.visited_urls.add(url)
        results['pages_crawled'] += 1
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            # Extract security information based on source type
            if results['type'] == 'documentation':
                self._extract_documentation(soup, url, results)
            elif results['type'] == 'vulnerabilities':
                self._extract_vulnerabilities(soup, url, results)
            elif results['type'] == 'best_practices':
                self._extract_best_practices(soup, url, results)
            elif results['type'] == 'ports':
                self._extract_port_info(soup, url, results)
            else:
                self._extract_general_info(soup, url, results)
            # --- Enrichment: run plugins and live update DB ---
            mde_id = url  # For now, use URL as mde_id; can be improved for entity-centric crawls
            core_entity_data = {'name': soup.title.string if soup.title else url, 'description': '', 'summary': '', 'content': soup.get_text()[:500]}
            self._enrich_page(response.text, url, results['type'], mde_id, core_entity_data)
            # Follow links if not at max depth
            if not unlimited_depth and depth < max_depth:
                for link in soup.find_all('a', href=True):
                    next_url = urljoin(url, link['href'])
                    if self._should_follow_link(next_url, url):
                        # PAUSE SUPPORT
                        while pause_event and pause_event.is_set():
                            time.sleep(0.5)
                        time.sleep(self.politeness_delay)
                        self._crawl_url(next_url, max_depth, max_pages, stop_event, pause_event, results, depth + 1, unlimited_depth)
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
    
    def _should_follow_link(self, url: str, base_url: str) -> bool:
        """Determine if a link should be followed."""
        try:
            parsed_url = urlparse(url)
            parsed_base = urlparse(base_url)
            
            # Only follow links from the same domain
            if parsed_url.netloc and parsed_url.netloc != parsed_base.netloc:
                return False
            
            # Skip non-HTML resources
            if any(url.endswith(ext) for ext in ['.pdf', '.zip', '.tar.gz', '.jpg', '.png']):
                    return False
            
            return True
        except:
            return False
    
    def _extract_documentation(self, soup: BeautifulSoup, url: str, results: Dict) -> None:
        """Extract security documentation information."""
        # Extract headings and their content
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4']):
            content = []
            for sibling in heading.next_siblings:
                if sibling.name in ['h1', 'h2', 'h3', 'h4']:
                    break
                if sibling.string:
                    content.append(sibling.string.strip())
            
            if content:
                knowledge = {
                    'title': heading.get_text().strip(),
                    'content': ' '.join(content),
                    'source': url,
                    'type': 'documentation',
                    'timestamp': datetime.now().isoformat()
                }
                self.db.add_knowledge(knowledge)
                results['knowledge_gained'] += 1

    def _extract_vulnerabilities(self, soup: BeautifulSoup, url: str, results: Dict) -> None:
        """Extract vulnerability information."""
        # Look for CVE entries
        cve_pattern = re.compile(r'CVE-\d{4}-\d{4,}')
        for text in soup.stripped_strings:
            if cve_pattern.search(text):
                knowledge = {
                    'title': f"Vulnerability: {cve_pattern.search(text).group()}",
                'content': text,
                    'source': url,
                    'type': 'vulnerability',
                    'timestamp': datetime.now().isoformat()
                }
                self.db.add_knowledge(knowledge)
                results['knowledge_gained'] += 1

    def _extract_best_practices(self, soup: BeautifulSoup, url: str, results: Dict) -> None:
        """Extract security best practices."""
        # Look for best practice sections
        for section in soup.find_all(['div', 'section'], class_=lambda x: x and 'best-practice' in x.lower()):
            title = section.find(['h1', 'h2', 'h3', 'h4'])
            if title:
                knowledge = {
                    'title': title.get_text().strip(),
                    'content': section.get_text().strip(),
                    'source': url,
                    'type': 'best_practice',
                    'timestamp': datetime.now().isoformat()
                }
                self.db.add_knowledge(knowledge)
                results['knowledge_gained'] += 1
    
    def _extract_port_info(self, soup: BeautifulSoup, url: str, results: Dict) -> None:
        """Extract port and service information."""
        # Look for port tables
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    port = cells[0].get_text().strip()
                    service = cells[1].get_text().strip()
                    if port.isdigit():
                        knowledge = {
                            'title': f"Port {port}: {service}",
                            'content': row.get_text().strip(),
                            'source': url,
                            'type': 'port_info',
                            'timestamp': datetime.now().isoformat()
                        }
                        self.db.add_knowledge(knowledge)
                        results['knowledge_gained'] += 1

    def _extract_general_info(self, soup: BeautifulSoup, url: str, results: Dict) -> None:
        """Extract general security information."""
        # Extract main content
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
        if main_content:
            knowledge = {
                'title': soup.title.string if soup.title else url,
                'content': main_content.get_text().strip(),
                'source': url,
                'type': 'general',
                'timestamp': datetime.now().isoformat()
            }
            self.db.add_knowledge(knowledge)
            results['knowledge_gained'] += 1

    def process_medusa_message(self, message: str) -> str:
        """
        Process a message through Medusa's core.
        
        Args:
            message: The message to process
            
        Returns:
            Medusa's response
        """
        # TODO: Implement Medusa's core processing
        # This will be where Medusa's AI processes the message
        # using the knowledge gained from crawling
        return "I am still learning. Please teach me more about security."

    def get_medusa_core_status(self) -> str:
        """Get Medusa's core status."""
        # TODO: Implement actual status check
        return "active"

    def get_medusa_learning_status(self) -> str:
        """Get Medusa's learning system status."""
        # TODO: Implement actual status check
        return "learning"

    def get_medusa_decision_status(self) -> str:
        """Get Medusa's decision-making system status."""
        # TODO: Implement actual status check
        return "active"

    def get_knowledge(self, category: Optional[str] = None) -> List[Dict]:
        """Get knowledge entries from the database."""
        return self.db.get_knowledge(category)
    
    def get_scan_results(self) -> List[Dict]:
        """Get scan results from the database."""
        return self.db.get_scan_results()

    def start_scan(self, target: str, scan_type: str, ports: Optional[str] = None) -> Dict:
        """Start a new security scan (stub)."""
        # Integrate with actual scanner here
        return {
            'id': 1,
            'target': target,
            'scan_type': scan_type,
            'ports': ports,
            'status': 'running',
            'start_time': datetime.now().isoformat()
        }

    def delete_scan(self, scan_id: int) -> None:
        """Delete a scan result."""
        self.db.delete_scan(scan_id)

    def get_training_history(self) -> List[Dict]:
        """Get Medusa's training history."""
        return self.db.get_training_history()

    def train_model(self, model_type: str, training_data: str, 
                   start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict:
        """Start training a new model (stub)."""
        # Integrate with actual model training here
        return {
            'id': 1,
            'model_type': model_type,
            'training_data': training_data,
            'start_date': start_date,
            'end_date': end_date,
            'status': 'training',
            'start_time': datetime.now().isoformat()
        }

    def delete_model(self, model_id: int) -> None:
        """Delete a model."""
        self.db.delete_model(model_id)

    def get_risk_distribution(self) -> Dict:
        """Get risk distribution data."""
        return self.db.get_risk_distribution()

    def get_port_usage(self) -> Dict:
        """Get port usage data."""
        return self.db.get_port_usage()

    def get_vulnerability_trends(self) -> Dict:
        """Get vulnerability trends data."""
        return self.db.get_vulnerability_trends()
    
    def get_service_distribution(self) -> Dict:
        """Get service distribution data."""
        return self.db.get_service_distribution()

    def get_risk_score_timeline(self) -> Dict:
        """Get risk score timeline data."""
        return self.db.get_risk_score_timeline()

    def get_database_status(self) -> str:
        """Get database connection status."""
        return "connected" if self.db.is_connected() else "disconnected"

    def get_model_status(self) -> str:
        """Get model training status (stub)."""
        return "active"

    def get_resource_status(self) -> str:
        """Get system resource status (stub)."""
        return "normal"

    def update_database_settings(self, settings: Dict) -> None:
        """Update database settings."""
        self.db.update_settings(settings)

    def update_security_settings(self, settings: Dict) -> None:
        """Update security settings (stub)."""
        pass

    def update_ai_settings(self, settings: Dict) -> None:
        """Update AI model settings (stub)."""
        pass

    def get_current_task(self) -> Optional[str]:
        """Get the current task being processed."""
        with self._lock:
            return self.current_task
            
    def get_processing_queue(self) -> List[str]:
        """Get the current processing queue."""
        with self._lock:
            return list(self.processing_queue)
            
    def get_recent_activities(self) -> List[Dict[str, Any]]:
        """Get recent activities."""
        with self._lock:
            return list(self.recent_activities)
    
    def get_knowledge_count(self) -> int:
        """Get total number of knowledge entries."""
        try:
            return len(self.get_knowledge())
        except Exception:
            return 0
            
    def get_recent_knowledge_updates(self) -> int:
        """Get number of recent knowledge updates."""
        try:
            recent_time = datetime.now() - timedelta(hours=24)
            updates = [k for k in self.get_knowledge() 
                      if datetime.fromisoformat(k.get('timestamp', '')) > recent_time]
            return len(updates)
        except Exception:
            return 0
            
    def get_knowledge_categories(self) -> Dict[str, int]:
        """Get count of knowledge entries by category."""
        try:
            categories = {}
            for entry in self.get_knowledge():
                category = entry.get('category', 'unknown')
                categories[category] = categories.get(category, 0) + 1
            return categories
        except Exception:
            return {}
            
    def get_training_sessions_count(self) -> int:
        """Get total number of training sessions."""
        try:
            return len(self.get_training_history())
        except Exception:
            return 0
            
    def get_last_training_time(self) -> str:
        """Get timestamp of last training session."""
        try:
            history = self.get_training_history()
            if history:
                return history[-1].get('timestamp', '')
            return ''
        except Exception:
            return ''
            
    def get_model_accuracy(self) -> float:
        """Get current model accuracy."""
        try:
            history = self.get_training_history()
            if history:
                return float(history[-1].get('accuracy', 0))
            return 0.0
        except Exception:
            return 0.0
            
    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        try:
            return psutil.cpu_percent()
        except Exception:
            return 0.0
            
    def get_memory_usage(self) -> float:
        """Get current memory usage percentage."""
        try:
            return psutil.virtual_memory().percent
        except Exception:
            return 0.0
            
    def get_active_threads(self) -> int:
        """Get number of active threads."""
        try:
            return threading.active_count()
        except Exception:
            return 0
            
    def add_activity(self, description: str):
        """Add a new activity to the recent activities list."""
        with self._lock:
            self.recent_activities.append({
                'timestamp': datetime.now().isoformat(),
                'description': description
            })
            
    def set_current_task(self, task: Optional[str]):
        """Set the current task being processed."""
        with self._lock:
            self.current_task = task
            if task:
                self.add_activity(f"Started task: {task}")
            else:
                self.add_activity("Task completed")
                
    def add_to_queue(self, task: str):
        """Add a task to the processing queue."""
        with self._lock:
            self.processing_queue.append(task)
            self.add_activity(f"Added to queue: {task}")

    def set_state(self, state, extra=None):
        prev = getattr(self, '_state', None)
        self._state = state
        logger.info(f"Crawler state changed from {prev} to {state}")
        # Optionally: emit event or callback here
        # e.g., if hasattr(self, 'on_state_change'): self.on_state_change(state, prev, extra) 

    def _load_enrichment_plugins(self):
        """Dynamically load plugins from tool_crawler/plugins/ (stub)."""
        # Implement dynamic plugin loading here
        return []

    def _enrich_page(self, page_content, url, entity_type, mde_id, core_entity_data):
        """
        Run all enabled enrichment plugins on the page and insert results into pages_* tables.
        Bulletproof: validate, deduplicate, filter, and route low-confidence data to review queue.
        """
        plugin_config = PluginConfig()  # TODO: Load real config per plugin
        for plugin in self.enrichment_plugins:
            for enrich_type in plugin.supported_enrichment_types():
                try:
                    extractor = getattr(plugin, f'extract_{enrich_type}', None)
                    if not extractor:
                        continue
                    results = extractor(page_content, url, entity_type, mde_id, core_entity_data, plugin_config)
                    for item in results:
                        # --- Bulletproofing ---
                        # 1. Schema validation
                        if not self._validate_enrichment_schema(item, enrich_type):
                            self._log_enrichment('invalid_schema', item, enrich_type, plugin)
                            continue
                        # 2. Deduplication (by URL, post ID, etc.)
                        if self._is_duplicate_enrichment(item, enrich_type, mde_id):
                            self._log_enrichment('duplicate', item, enrich_type, plugin)
                            continue
                        # 3. Language detection (English only for now)
                        text = item.get('title') or item.get('description_snippet') or item.get('comment_summary') or ''
                        try:
                            if text and lang_detect(text) != 'en':
                                self._log_enrichment('non_english', item, enrich_type, plugin)
                                continue
                        except Exception:
                            pass
                        # 4. Relevance scoring (simple keyword/heuristic for now)
                        if not self._is_relevant_enrichment(item, core_entity_data):
                            self._log_enrichment('irrelevant', item, enrich_type, plugin)
                            continue
                        # 5. Confidence threshold
                        if item.get('extraction_confidence', 0) < 0.6:
                            self._route_to_review_queue(item, enrich_type, plugin)
                            continue
                        # 6. Insert into DB
                        self._insert_enrichment(item, enrich_type, mde_id, entity_type, core_entity_data)
                        self._log_enrichment('inserted', item, enrich_type, plugin)
                except Exception as e:
                    self._log_enrichment('plugin_error', {'error': str(e)}, enrich_type, plugin)

    def _validate_enrichment_schema(self, item, enrich_type):
        """Strict schema checks per enrich_type (stub)."""
        # Implement schema validation logic here
        return True if item.get('specific_source_url') else False

    def _is_duplicate_enrichment(self, item, enrich_type, mde_id):
        """Check DB for existing entry with same canonical URL/post ID for this mde_id (stub)."""
        # Implement duplicate check logic here
        return False

    def _is_relevant_enrichment(self, item, core_entity_data):
        # Simple keyword-based relevance for now
        keywords = [core_entity_data.get('name',''), core_entity_data.get('description','')]
        text = (item.get('title') or '') + ' ' + (item.get('description_snippet') or '')
        for kw in keywords:
            if kw and re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE):
                return True
        return False

    def _route_to_review_queue(self, item, enrich_type, plugin):
        """Add to review queue for operator moderation (stub)."""
        # Implement review queue logic here
        pass

    def _insert_enrichment(self, item, enrich_type, mde_id, entity_type=None, core_entity_data=None):
        """
        Insert enrichment data into the correct pages_* table, linking to the parent page by page_id.
        Handles: videos, geo_location, related_links, related_socials.
        """
        import traceback
        try:
            page_id = self._get_or_create_page_id(mde_id, entity_type, core_entity_data)
            print(f"[ENRICHMENT_DIAG] Attempting insert: enrich_type={enrich_type}, page_id={page_id}, item={json.dumps(item, default=str)[:1000]}")
            log_event = None
            try:
                from src.web_server import log_event as global_log_event
                log_event = global_log_event
            except Exception:
                pass
            if enrich_type == 'videos':
                sql = '''INSERT INTO pages_video_content (page_id, video_url, title, description_snippet, uploader, platform, video_id, embed_code, added_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())'''
                params = (
                    page_id,
                    item.get('video_url'),
                    item.get('title'),
                    item.get('description_snippet'),
                    item.get('uploader'),
                    item.get('platform'),
                    item.get('video_id'),
                    item.get('embed_code'),
                )
            elif enrich_type == 'geo_location':
                sql = '''INSERT INTO pages_geo_location (page_id, latitude, longitude, location_description, source_of_geo_info, notes, added_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())'''
                params = (
                    page_id,
                    item.get('latitude'),
                    item.get('longitude'),
                    item.get('location_description'),
                    item.get('source_of_geo_info'),
                    item.get('notes'),
                )
            elif enrich_type == 'related_links':
                sql = '''INSERT INTO pages_related_links (page_id, link_type, url, title, description, added_at) VALUES (%s, %s, %s, %s, %s, NOW())'''
                params = (
                    page_id,
                    item.get('link_type'),
                    item.get('url'),
                    item.get('title'),
                    item.get('description'),
                )
            elif enrich_type == 'related_socials':
                sql = '''INSERT INTO pages_related_socials (page_id, platform, author_handle, comment_summary, mde_id, url, timestamp, comment) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'''
                params = (
                    page_id,
                    item.get('platform'),
                    item.get('author_handle'),
                    item.get('comment_summary'),
                    item.get('mde_id'),
                    item.get('url'),
                    item.get('timestamp'),
                    item.get('comment'),
                )
            else:
                raise ValueError(f"Unknown enrichment type: {enrich_type}")
            print(f"[ENRICHMENT_DIAG] SQL: {sql}\nParams: {params}")
            if log_event:
                log_event("enrichment_insert_attempt", {"enrich_type": enrich_type, "page_id": page_id, "item": item, "sql": sql, "params": params})
            self.db.cursor.execute(sql, params)
            self.db.conn.commit()
            print(f"[ENRICHMENT_DIAG] Insert successful for enrich_type={enrich_type}, page_id={page_id}")
            if log_event:
                log_event("enrichment_insert_success", {"enrich_type": enrich_type, "page_id": page_id, "item": item})
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[ENRICHMENT_INSERT_ERROR] {enrich_type}: {e}\n{tb}")
            if log_event:
                log_event("enrichment_insert_error", {"enrich_type": enrich_type, "error": str(e), "traceback": tb, "item": item})
            self.db.conn.rollback() 