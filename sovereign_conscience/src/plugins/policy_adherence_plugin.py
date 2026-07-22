import threading
import time
import re
from urllib.parse import urlparse
from datetime import datetime, timedelta
import urllib.robotparser
import requests
from medusa.src.tool_crawler.plugin_base import EnrichmentPluginBase
import os
import pickle

class PolicyAdherencePlugin(EnrichmentPluginBase):
    """
    Plugin for enforcing robots.txt and crawl-delay policy adherence.
    Caches rules per domain and provides a check_url_policy method.
    Thread-safe and robust to network errors. Persists cache and last_access across restarts.
    """
    CACHE_FILE = 'robots_cache.pkl'
    ACCESS_FILE = 'robots_last_access.pkl'

    def __init__(self, config=None, robots_ttl_hours=24):
        super().__init__(config)
        self.robots_cache = self._load_pickle(self.CACHE_FILE) or {}
        self.last_access = self._load_pickle(self.ACCESS_FILE) or {}
        self.robots_ttl = timedelta(hours=robots_ttl_hours)
        self.cache_lock = threading.Lock()
        self.default_politeness_delay = config.get('default_politeness_delay', 3) if config else 3

    def _save_pickle(self, obj, filename):
        """Persist a dict to disk using pickle."""
        try:
            with open(filename, 'wb') as f:
                pickle.dump(obj, f)
        except Exception:
            pass

    def _load_pickle(self, filename):
        """Load a dict from disk using pickle."""
        if os.path.exists(filename):
            try:
                with open(filename, 'rb') as f:
                    return pickle.load(f)
            except Exception:
                return None
        return None

    def _update_and_persist_cache(self):
        self._save_pickle(self.robots_cache, self.CACHE_FILE)
        self._save_pickle(self.last_access, self.ACCESS_FILE)

    def supported_enrichment_types(self):
        return []  # Not an enrichment plugin, but keeps interface

    def _fetch_and_parse_robots(self, domain, user_agent):
        """Fetch and parse robots.txt for a domain, return (parser, crawl_delay)."""
        robots_url = f"http://{domain}/robots.txt"
        parser = urllib.robotparser.RobotFileParser()
        crawl_delay = self.default_politeness_delay
        try:
            resp = requests.get(robots_url, timeout=10)
            if resp.status_code == 200:
                parser.parse(resp.text.splitlines())
                # Try to extract Crawl-delay for this user-agent
                lines = resp.text.splitlines()
                ua = user_agent.lower()
                found_ua = False
                for line in lines:
                    if line.lower().startswith('user-agent:'):
                        found_ua = ua in line.lower()
                    elif found_ua and line.lower().startswith('crawl-delay:'):
                        try:
                            crawl_delay = int(float(line.split(':', 1)[1].strip()))
                        except Exception:
                            pass
                        break
            else:
                parser.parse([])  # Empty rules
        except Exception as e:
            parser.parse([])
        return parser, crawl_delay

    def check_url_policy(self, url, user_agent, politeness_delay=None):
        """
        Check robots.txt and crawl-delay for the given URL and user-agent.
        Returns dict: { 'allowed': bool, 'reason': str, 'crawl_delay': int, 'restricted_until': datetime or None, 'rules': ... }
        """
        domain = urlparse(url).netloc
        now = datetime.now()
        politeness_delay = politeness_delay or self.default_politeness_delay
        with self.cache_lock:
            cache_entry = self.robots_cache.get(domain)
            if (not cache_entry) or (now - cache_entry['last_fetched'] > self.robots_ttl):
                parser, crawl_delay = self._fetch_and_parse_robots(domain, user_agent)
                self.robots_cache[domain] = {
                    'parser': parser,
                    'crawl_delay': crawl_delay,
                    'last_fetched': now
                }
                self._update_and_persist_cache()
            else:
                parser = cache_entry['parser']
                crawl_delay = cache_entry['crawl_delay']
            allowed = parser.can_fetch(user_agent, url)
            reason = 'allowed' if allowed else 'disallowed_by_robots'
            # --- Enforce crawl-delay ---
            last = self.last_access.get(domain)
            restricted_until = None
            if last:
                next_allowed = last + timedelta(seconds=crawl_delay)
                if now < next_allowed:
                    allowed = False
                    reason = 'crawl_delay'
                    restricted_until = next_allowed
            # --- Update last access if allowed ---
            if allowed:
                self.last_access[domain] = now
                self._update_and_persist_cache()
            # For debug/audit, expose rules summary
            rules = {
                'user_agent': user_agent,
                'crawl_delay': crawl_delay,
                'last_fetched': self.robots_cache[domain]['last_fetched'].isoformat(),
                'parser_repr': str(parser)
            }
            return {
                'allowed': allowed,
                'reason': reason,
                'crawl_delay': crawl_delay,
                'restricted_until': restricted_until,
                'rules': rules
            } 