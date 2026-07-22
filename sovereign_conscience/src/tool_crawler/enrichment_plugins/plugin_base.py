import abc

class PluginConfig:
    """Base config for plugins. Extend as needed for API keys, keywords, etc."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class EnrichmentPluginBase(abc.ABC):
    """Base class for Medusa enrichment plugins."""
    def __init__(self, config: PluginConfig = None):
        self.config = config or PluginConfig()

    @abc.abstractmethod
    def supported_enrichment_types(self):
        """Return a list of supported enrichment types (e.g., ['links', 'videos', 'socials', 'geo'])."""
        pass

    def extract_links(self, page_content, url, entity_type, mde_id, core_entity_data, plugin_config):
        """Extract related links. Return list of dicts with extraction_confidence, specific_source_url, etc."""
        return []

    def extract_socials(self, page_content, url, entity_type, mde_id, core_entity_data, plugin_config):
        """Extract related social posts. Return list of dicts with extraction_confidence, specific_source_url, etc."""
        return []

    def extract_videos(self, page_content, url, entity_type, mde_id, core_entity_data, plugin_config):
        """Extract related videos. Return list of dicts with extraction_confidence, specific_source_url, etc."""
        return []

    def extract_geo(self, page_content, url, entity_type, mde_id, core_entity_data, plugin_config):
        """Extract geo-location data. Return list of dicts with extraction_confidence, specific_source_url, etc."""
        return [] 