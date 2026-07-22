import os
import importlib
import inspect
import traceback
from typing import Dict, Type, Any, Optional
# Robust import for EnrichmentPluginBase
try:
    from .plugin_base import EnrichmentPluginBase
except ImportError:
    try:
        from medusa.src.tool_crawler.enrichment_plugins.plugin_base import EnrichmentPluginBase
    except ImportError:
        try:
            from src.tool_crawler.enrichment_plugins.plugin_base import EnrichmentPluginBase
        except ImportError:
            import sys, os, importlib
            plugin_base_path = os.path.join(os.path.dirname(__file__), 'plugin_base.py')
            sys.path.append(os.path.dirname(plugin_base_path))
            EnrichmentPluginBase = importlib.import_module('plugin_base').EnrichmentPluginBase

class EnrichmentPluginManager:
    """
    Auto-discovers, loads, and manages all enrichment plugins (subclasses of EnrichmentPluginBase) in the enrichment_plugins directory.
    Tracks status (enabled/disabled/invalid), error details, last_modified, version, description.
    """
    def __init__(self, plugin_dir=None):
        base_dir = os.path.dirname(__file__)
        self.plugin_dir = plugin_dir or base_dir
        self.plugins: Dict[str, Dict[str, Any]] = {}
        self._discover_plugins()

    def _get_plugin_metadata(self, name, obj, module, fname):
        file_path = os.path.join(self.plugin_dir, fname)
        last_modified = os.path.getmtime(file_path) if os.path.exists(file_path) else None
        version = getattr(obj, '__version__', None)
        description = obj.__doc__.strip() if obj.__doc__ else ''
        module_path = module.__name__ if module else None
        return {
            'name': name,
            'class': obj,
            'instance': obj(),
            'enabled': True,
            'status': 'loaded',
            'error': None,
            'last_modified': last_modified,
            'version': version,
            'module_path': module_path,
            'description': description,
            'file_path': file_path
        }

    def _discover_plugins(self):
        self.plugins.clear()
        for fname in os.listdir(self.plugin_dir):
            if fname.startswith('_') or not fname.endswith('.py') or fname == 'plugin_base.py' or fname == os.path.basename(__file__):
                continue
            import importlib.util
            import sys
            file_path = os.path.join(self.plugin_dir, fname)
            module_name = fname[:-3]
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                else:
                    raise ImportError(f"Could not load spec for {fname}")
                found = False
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, EnrichmentPluginBase) and obj is not EnrichmentPluginBase:
                        found = True
                        if name not in self.plugins:
                            self.plugins[name] = self._get_plugin_metadata(name, obj, module, fname)
                if not found:
                    self.plugins[fname] = {
                        'name': fname,
                        'class': None,
                        'instance': None,
                        'enabled': False,
                        'status': 'invalid',
                        'error': 'No valid EnrichmentPluginBase subclass found',
                        'last_modified': os.path.getmtime(os.path.join(self.plugin_dir, fname)),
                        'version': None,
                        'module_path': module_name,
                        'description': '',
                        'file_path': os.path.join(self.plugin_dir, fname)
                    }
            except Exception as e:
                tb = traceback.format_exc()
                print(f"[ENRICHMENT_PLUGIN_MANAGER_DIAG] Failed to load plugin {fname}: {e}\n{tb}")
                self.plugins[fname] = {
                    'name': fname,
                    'class': None,
                    'instance': None,
                    'enabled': False,
                    'status': 'failed_to_load',
                    'error': f'{e}\n{tb}',
                    'last_modified': os.path.getmtime(os.path.join(self.plugin_dir, fname)) if os.path.exists(os.path.join(self.plugin_dir, fname)) else None,
                    'version': None,
                    'module_path': module_name,
                    'description': '',
                    'file_path': os.path.join(self.plugin_dir, fname)
                }
        print("[ENRICHMENT_PLUGIN_MANAGER_DIAG] Discovered enrichment plugins:")
        for name, plugin in self.plugins.items():
            print(f"  - {name}: enabled={plugin.get('enabled')}, status={plugin.get('status')}, error={plugin.get('error')}")

    def list_plugins(self):
        """Return a list of all discovered enrichment plugins and their metadata."""
        return [
            {k: v for k, v in meta.items() if k != 'class' and k != 'instance'}
            for meta in self.plugins.values()
        ]

    def get_enabled_plugins(self):
        """Return a dict of enabled enrichment plugin instances: {name: instance, ...}"""
        return {name: meta['instance'] for name, meta in self.plugins.items() if meta['enabled'] and meta['instance'] and meta['status'] in ('loaded', 'enabled')}

    def reload_plugins(self):
        for fname, meta in self.plugins.items():
            if meta.get('module_path') and meta['status'] in ('loaded', 'enabled'):
                try:
                    importlib.reload(importlib.import_module(meta['module_path']))
                except Exception:
                    pass
        self._discover_plugins()

    def get_all_plugin_health(self):
        """Return health status for all enrichment plugins."""
        health = {}
        for name, meta in self.plugins.items():
            health[name] = {
                'status': meta.get('status', 'unknown'),
                'last_error': meta.get('error'),
                'last_reload': meta.get('last_modified'),
                'version': meta.get('version'),
            }
        return health 