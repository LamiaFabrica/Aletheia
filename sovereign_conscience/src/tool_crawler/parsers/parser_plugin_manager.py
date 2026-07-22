import os
import importlib
import inspect
import traceback
from typing import Dict, Type, Any, Optional
from medusa.src.tool_crawler.parsers.base_parser import BaseToolParser

class ParserPluginManager:
    """
    Auto-discovers, loads, and manages all parser plugins (subclasses of BaseToolParser) in the parsers directory.
    Tracks status (enabled/disabled/invalid), error details, last_modified, version, description, and default parser.
    """
    def __init__(self, plugin_dir=None):
        # Always use the plugins subdirectory for parser plugins
        base_dir = os.path.dirname(__file__)
        plugins_dir = os.path.join(base_dir, 'plugins')
        self.plugin_dir = plugin_dir or plugins_dir
        self.plugins: Dict[str, Dict[str, Any]] = {}  # name -> metadata dict
        self.default_parser: Optional[str] = None
        self._discover_plugins()

    def _get_plugin_metadata(self, name, obj, module, fname):
        # Get last modified time
        file_path = os.path.join(self.plugin_dir, fname)
        last_modified = os.path.getmtime(file_path) if os.path.exists(file_path) else None
        # Try to get version and description
        version = getattr(obj, '__version__', None)
        description = obj.__doc__.strip() if obj.__doc__ else ''
        module_path = module.__name__ if module else None
        return {
            'name': name,
            'class': obj,
            'instance': obj(),
            'enabled': True,  # Default to enabled; can be changed via API
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
        print(f"[PLUGIN_MANAGER_DIAG] Scanning plugin_dir: {self.plugin_dir}")
        all_files = os.listdir(self.plugin_dir)
        print(f"[PLUGIN_MANAGER_DIAG] Files in plugin_dir: {all_files}")
        for fname in all_files:
            if fname.startswith('_') or not fname.endswith('.py') or fname == 'base_parser.py' or fname == os.path.basename(__file__):
                continue
            module_name = f"src.tool_crawler.parsers.plugins.{fname[:-3]}"
            try:
                if module_name in globals():
                    module = importlib.reload(globals()[module_name])
                else:
                    module = importlib.import_module(module_name)
                found = False
                print(f"[PLUGIN_MANAGER_DIAG] Inspecting module: {module_name}")
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    print(f"[PLUGIN_MANAGER_DIAG] Found class: {name}, issubclass: {issubclass(obj, BaseToolParser) if obj is not BaseToolParser else False}")
                    if issubclass(obj, BaseToolParser) and obj is not BaseToolParser:
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
                        'error': 'No valid BaseToolParser subclass found',
                        'last_modified': os.path.getmtime(os.path.join(self.plugin_dir, fname)),
                        'version': None,
                        'module_path': module_name,
                        'description': '',
                        'file_path': os.path.join(self.plugin_dir, fname)
                    }
            except Exception as e:
                tb = traceback.format_exc()
                print(f"[PLUGIN_MANAGER_DIAG] Failed to load plugin {fname}: {e}\n{tb}")
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
        print("[PLUGIN_MANAGER_DIAG] Discovered plugins:")
        for name, plugin in self.plugins.items():
            print(f"  - {name}: enabled={plugin.get('enabled')}, status={plugin.get('status')}, error={plugin.get('error')}")
        enabled = [name for name, plugin in self.plugins.items() if plugin['enabled']]
        print(f"[PLUGIN_MANAGER_DIAG] Enabled plugins after discovery: {enabled}")
        self.default_parser = enabled[0] if enabled else None
        # NOTE: No direct logging here to avoid circular imports. The orchestrator or web server should log plugin errors/status after initialization.

    def list_plugins(self):
        """Return a list of all discovered parser plugins and their metadata."""
        return [
            {k: v for k, v in meta.items() if k != 'class' and k != 'instance'}
            for meta in self.plugins.values()
        ]

    def enable_plugin(self, name):
        if name in self.plugins and self.plugins[name]['status'] == 'loaded':
            self.plugins[name]['enabled'] = True
            self.plugins[name]['status'] = 'enabled'
            return True
        return False

    def disable_plugin(self, name, override=False):
        if name == self.default_parser and not override:
            return False  # Prevent disabling default parser unless override
        if name in self.plugins and self.plugins[name]['status'] in ('loaded', 'enabled'):
            self.plugins[name]['enabled'] = False
            self.plugins[name]['status'] = 'disabled'
            return True
        return False

    def get_status(self, name):
        if name in self.plugins:
            meta = self.plugins[name]
            return {k: v for k, v in meta.items() if k != 'class' and k != 'instance'}
        return None

    def get_enabled_parsers(self):
        """Return a dict of enabled parser plugin instances: {name: instance, ...}"""
        enabled = {name: meta['instance'] for name, meta in self.plugins.items() if meta['enabled'] and meta['instance'] and meta['status'] in ('loaded', 'enabled')}
        print(f"[PLUGIN_MANAGER_DIAG] get_enabled_parsers called. Enabled: {list(enabled.keys())}")
        return enabled

    def reload_plugins(self):
        """Re-scan the directory and reload all plugins (for hot-reload support)."""
        for fname, meta in self.plugins.items():
            if meta.get('module_path') and meta['status'] in ('loaded', 'enabled'):
                try:
                    importlib.reload(importlib.import_module(meta['module_path']))
                except Exception:
                    pass  # Ignore reload errors here; will be caught in _discover_plugins
        self._discover_plugins()

    def set_default_parser(self, name):
        if name in self.plugins and self.plugins[name]['status'] in ('loaded', 'enabled'):
            self.default_parser = name
            return True
        return False

    def get_default_parser(self):
        return self.default_parser 