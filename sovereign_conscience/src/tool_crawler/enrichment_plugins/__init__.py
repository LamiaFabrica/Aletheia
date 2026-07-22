# medusa/src/tool_crawler/enrichment_plugins/__init__.py
# This file marks the enrichment_plugins directory as a Python package for plugin discovery. 

import logging
import time

class PluginManager:
    def __init__(self):
        self.plugins = {}
        self.plugin_health = {}
        self.plugin_logs = {}
        self.plugin_versions = {}
        self.plugin_last_reload = {}
        self.plugin_last_error = {}
        self.load_plugins()

    def load_plugins(self):
        # Discover and load all plugins
        # ... existing code ...
        pass

    def get_all_plugin_health(self):
        # Return health for all plugins
        return {
            name: {
                'status': self.plugin_health.get(name, 'unknown'),
                'last_error': self.plugin_last_error.get(name),
                'last_reload': self.plugin_last_reload.get(name),
                'version': self.plugin_versions.get(name)
            }
            for name in self.plugins
        }

    def get_plugin_logs(self, name):
        return self.plugin_logs.get(name, [])

    def get_plugin_version(self, name):
        return self.plugin_versions.get(name, 'unknown')

    def enable_plugin(self, name):
        # ... enable logic ...
        self.plugin_health[name] = 'enabled'
        self.plugin_last_reload[name] = time.time()
        self.plugin_last_error[name] = None

    def disable_plugin(self, name):
        # ... disable logic ...
        self.plugin_health[name] = 'disabled'
        self.plugin_last_reload[name] = time.time()
        self.plugin_last_error[name] = None

    def reload_plugin(self, name):
        # ... reload logic ...
        self.plugin_health[name] = 'reloaded'
        self.plugin_last_reload[name] = time.time()
        self.plugin_last_error[name] = None

    def get_plugin_update(self, name):
        # Stub for update check
        return {'update_available': False, 'message': 'Update check not implemented yet.'}

plugin_manager = PluginManager() 