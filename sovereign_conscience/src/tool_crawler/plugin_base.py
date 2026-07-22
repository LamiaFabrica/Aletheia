import abc
from typing import Any, Dict, List

class PluginConfig:
    """Base config for plugins. Extend as needed for API keys, keywords, etc.
    For stricter config validation, consider using Pydantic or a subclass with explicit fields in the future.
    """
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class EnrichmentPluginBase(abc.ABC):
    """
    Base class for Medusa enrichment plugins.
    Concrete implementations must implement enrich_data(), and should handle their own exceptions gracefully (e.g., network errors, parsing errors) and log issues using Medusa's standard logging. They should aim to return an empty list or partial results in case of non-fatal errors, rather than letting exceptions propagate and potentially halt the entire enrichment pipeline.
    """
    def __init__(self, config: PluginConfig = None):
        self.config = config or PluginConfig()

    @abc.abstractmethod
    def supported_enrichment_types(self) -> List[str]:
        """Return a list of supported enrichment types (e.g., ['links', 'videos', 'socials', 'geo'])."""
        pass

    @abc.abstractmethod
    def enrich_data(self, data_to_enrich: Dict[str, Any], nlp_models: Dict[str, Any], db_connection: Any, **kwargs) -> Dict[str, Any]:
        """
        Main enrichment method called by the orchestrator (ToolDataEnrichment).
        The plugin should process the data_to_enrich and return a dictionary of new or updated fields to be merged into the main data record.
        Return an empty dict if no changes are made. Do NOT return the full data_to_enrich object.
        If the plugin needs to access the database, use the provided db_connection (or cursor) and follow transaction management best practices (do not commit if part of a larger transaction).
        """
        pass

    def extract_links(self, page_content: str, url: str, entity_type: str, mde_id: str, core_entity_data: Dict[str, Any], plugin_config: PluginConfig) -> List[Dict[str, Any]]:
        """
        Extract related links. Return list of dicts with extraction_confidence, specific_source_url, etc.
        core_entity_data: The normalized data structure for the tool/vulnerability (not raw parser output).
        plugin_config: An instance of PluginConfig or a subclass.
        Implementers should handle errors gracefully and log as appropriate.
        """
        return []

    def extract_socials(self, page_content: str, url: str, entity_type: str, mde_id: str, core_entity_data: Dict[str, Any], plugin_config: PluginConfig) -> List[Dict[str, Any]]:
        """
        Extract related social posts. Return list of dicts with extraction_confidence, specific_source_url, etc.
        core_entity_data: The normalized data structure for the tool/vulnerability (not raw parser output).
        plugin_config: An instance of PluginConfig or a subclass.
        Implementers should handle errors gracefully and log as appropriate.
        """
        return []

    def extract_videos(self, page_content: str, url: str, entity_type: str, mde_id: str, core_entity_data: Dict[str, Any], plugin_config: PluginConfig) -> List[Dict[str, Any]]:
        """
        Extract related videos. Return list of dicts with extraction_confidence, specific_source_url, etc.
        core_entity_data: The normalized data structure for the tool/vulnerability (not raw parser output).
        plugin_config: An instance of PluginConfig or a subclass.
        Implementers should handle errors gracefully and log as appropriate.
        """
        return []

    def extract_geo(self, page_content: str, url: str, entity_type: str, mde_id: str, core_entity_data: Dict[str, Any], plugin_config: PluginConfig) -> List[Dict[str, Any]]:
        """
        Extract geo-location data. Return list of dicts with extraction_confidence, specific_source_url, etc.
        core_entity_data: The normalized data structure for the tool/vulnerability (not raw parser output).
        plugin_config: An instance of PluginConfig or a subclass.
        Implementers should handle errors gracefully and log as appropriate.
        """
        return []

# If parser plugin base is not defined elsewhere, provide a stub for developer reference:
class BaseToolParser(abc.ABC):
    """
    Base class for Medusa parser plugins. Place in medusa/src/tool_crawler/parsers/plugins/ and inherit from BaseToolParser.
    Implement parse(self, content: str, url: str, **kwargs) -> List[Dict[str, Any]].
    """
    @abc.abstractmethod
    def parse(self, content: str, url: str, **kwargs) -> List[Dict[str, Any]]:
        pass 