from medusa.src.tool_crawler.enrichment_plugins.plugin_base import EnrichmentPluginBase
import re
import time
from urllib.parse import urlparse
from datetime import datetime, timedelta

class PolicyAdherencePlugin(EnrichmentPluginBase):
    """
    Plugin for enforcing robots.txt and crawl-delay policy adherence.
    Caches rules per domain and provides a check_url_policy method.
    """
    def __init__(self, config=None):
        super().__init__(config)
        self.robots_cache = {}  # domain -> {rules, crawl_delay, last_fetched}
        self.last_access = {}   # domain -> last access timestamp

    def supported_enrichment_types(self):
        return []  # Not an enrichment plugin, but keeps interface

    def check_url_policy(self, url, user_agent, politeness_delay=3):
        """
        Check robots.txt and crawl-delay for the given URL and user-agent.
        Returns dict: { 'allowed': bool, 'reason': str, 'crawl_delay': int, 'restricted_until': datetime or None, 'rules': ... }
        """
        domain = urlparse(url).netloc
        now = datetime.now()
        # --- Stub: Fetch and parse robots.txt (replace with real logic) ---
        # For now, allow all, crawl_delay = politeness_delay
        rules = {'User-agent': user_agent, 'Disallow': [], 'Allow': ['*'], 'Crawl-delay': politeness_delay}
        crawl_delay = politeness_delay
        allowed = True
        reason = 'allowed (stub)'
        restricted_until = None
        # --- Enforce crawl-delay ---
        last = self.last_access.get(domain)
        if last:
            next_allowed = last + timedelta(seconds=crawl_delay)
            if now < next_allowed:
                allowed = False
                reason = 'crawl_delay'
                restricted_until = next_allowed
        # --- Update last access if allowed ---
        if allowed:
            self.last_access[domain] = now
        return {
            'allowed': allowed,
            'reason': reason,
            'crawl_delay': crawl_delay,
            'restricted_until': restricted_until,
            'rules': rules
        } 