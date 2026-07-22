import logging
from datetime import datetime
from medusa.src.tool_crawler.enrichment_plugins.plugin_base import EnrichmentPluginBase

class AuditKBAgentPlugin(EnrichmentPluginBase):
    """
    Plugin for Medusa AI Command Center: audits the knowledge base, queue, and crawler.
    Only acts if the 'ai_command_center_enabled' system setting is True.
    """
    name = "AuditKBAgent"
    type = "enrichment"
    version = "0.1"
    description = "AI agent for auditing and testing Medusa's knowledge base, queue, and crawler."

    def __init__(self, medusa_app=None, db=None, logger=None):
        super().__init__()
        self.medusa_app = medusa_app
        self.db = db
        self.logger = logger or logging.getLogger(__name__)

    def is_enabled(self):
        # Check system setting (should be in DB/settings)
        if self.db:
            settings = self.db.get_settings()
            return settings.get('ai_command_center_enabled', False)
        return False

    def run_audit(self, user=None):
        if not self.is_enabled():
            self.logger.warning("AuditKBAgentPlugin: AI Command Center is disabled. No action taken.")
            return {'status': 'disabled', 'message': 'AI Command Center is disabled.'}
        # Example: audit the tools table
        try:
            tools = self.db.get_tools(limit=5) if self.db else []
            result = {
                'timestamp': datetime.now().isoformat(),
                'tools_sample': tools,
                'status': 'success',
                'message': f'Audited {len(tools)} tools.'
            }
            if self.logger:
                self.logger.info(f"AuditKBAgentPlugin: {result['message']}")
            # Optionally log to Medusa activity log
            if hasattr(self.medusa_app, 'log_event'):
                self.medusa_app.log_event(
                    event_type="AI_COMMAND_AUDIT",
                    message=result['message'],
                    user=user,
                    data=result
                )
            return result
        except Exception as e:
            self.logger.error(f"AuditKBAgentPlugin error: {e}")
            return {'status': 'error', 'message': str(e)}

    def supported_enrichment_types(self):
        return [] 