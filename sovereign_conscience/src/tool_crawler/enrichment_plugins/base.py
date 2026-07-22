import json
from datetime import datetime

class EnrichmentPluginBase:
    def __init__(self, plugin_name):
        self.plugin_name = plugin_name

    def log_enrichment(self, db, table, record_id, changes):
        # changes: dict of {field: (old_value, new_value)}
        details = {
            'plugin': self.plugin_name,
            'fields_changed': list(changes.keys()),
            'changes': changes,
            'timestamp': datetime.utcnow().isoformat()
        }
        try:
            db.execute(
                "INSERT INTO kb_audit_log (action, table_name, record_id, user_name, details, timestamp) VALUES (%s, %s, %s, %s, %s, %s)",
                ('enrichment', table, record_id, self.plugin_name, json.dumps(details), datetime.utcnow())
            )
        except Exception as e:
            try:
                if hasattr(db, 'conn'):
                    db.conn.rollback()
            except Exception as rollback_exc:
                print(f"[EnrichmentPluginBase] Rollback failed: {rollback_exc}")
            print(f"[EnrichmentPluginBase] ERROR in log_enrichment: {e}")

    # All enrichment plugins should call self.log_enrichment after making changes 