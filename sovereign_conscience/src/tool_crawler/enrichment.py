# medusa/src/tool_crawler/enrichment.py

import logging
from typing import Dict, Any
from .enrichment_plugins.enrichment_plugin_manager import EnrichmentPluginManager

class ToolDataEnrichment:
    """
    Optional enrichment stage for advanced AI/NLP processing.
    Supports NER, CVE linking, summarization, topic modeling, and other intelligence features.
    Designed as a pluggable post-normalization pipeline stage.
    """
    def __init__(self, nlp_models: Dict[str, Any] = None, db_connection=None):
        self.logger = logging.getLogger("ToolDataEnrichment")
        self.nlp_models = nlp_models or {}
        self.db_connection = db_connection
        self.plugin_manager = EnrichmentPluginManager()
        self.logger.info("[ENRICHMENT] Attempting to load enrichment plugins...")
        try:
            enabled_plugins = self.plugin_manager.get_enabled_plugins()
            if enabled_plugins:
                for name, plugin_instance in enabled_plugins.items():
                    try:
                        types = plugin_instance.supported_enrichment_types()
                        self.logger.info(f"  - Loaded: {name}: types={types}")
                    except Exception as e_plugin:
                        self.logger.error(f"  - Failed to get supported_enrichment_types from plugin {name}: {e_plugin}")
            else:
                self.logger.info("  - No enabled enrichment plugins found.")
        except Exception as e_manager:
            self.logger.error(f"[ENRICHMENT] Error listing enrichment plugins from manager: {e_manager}")
        # TODO: Load or initialize AI/NLP models (NER, summarization, etc.)

    def list_plugins(self):
        return self.plugin_manager.list_plugins()

    def enrich(self, normalized_tool_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applies AI/NLP enrichment to normalized tool data.
        Iterates enabled plugins, applies those that match, merges results, and logs errors.
        """
        enriched_data = normalized_tool_data.copy()
        errors = []
        for name, plugin in self.plugin_manager.get_enabled_plugins().items():
            try:
                types = plugin.supported_enrichment_types()
                # For now, assume all plugins are applicable; in future, check types vs data
                if hasattr(plugin, 'enrich_data'):
                    self.logger.info(f"[ENRICHMENT] Running plugin: {name}")
                    result = plugin.enrich_data(enriched_data, self.nlp_models, self.db_connection)
                    if result:
                        enriched_data.update(result)
            except Exception as e:
                self.logger.error(f"[ENRICHMENT] Plugin {name} failed: {e}")
                errors.append({"plugin": name, "error": str(e)})
        if errors:
            enriched_data['enrichment_errors'] = errors
        return enriched_data

    # TODO: Add methods for model management, enrichment configuration, and error handling.

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("ToolDataEnrichment")
    logger.info("[ENRICHMENT] Standalone plugin health check:")
    enrichment = ToolDataEnrichment()
    for plugin in enrichment.list_plugins():
        try:
            types = getattr(plugin.get('instance'), 'supported_enrichment_types', lambda: [])() if plugin.get('instance') else []
            logger.info(f"  - {plugin['name']}: status={plugin['status']}, enabled={plugin['enabled']}, error={plugin['error']}, types={types}")
        except Exception as e:
            logger.error(f"  - {plugin['name']}: status={plugin['status']}, enabled={plugin['enabled']}, error={plugin['error']}, types=ERROR: {e}") 