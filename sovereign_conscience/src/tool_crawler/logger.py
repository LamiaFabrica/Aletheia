# medusa/src/tool_crawler/logger.py

import logging
import os
from typing import Dict, Any

# These will be set by web_server.py
VERBOSE_LOGGING = os.environ.get('MEDUSA_VERBOSE_LOGGING', '1') == '1'
UI_LOGGING = True

class ToolLogger:
    """
    Structured logger for the tool extraction crawler.
    Logs all pipeline stages (fetch, parse, normalize, write) using structured events for UI, file, and console.
    Integrates with log_event for SocketIO/UI logging.
    If log_to_file is True, logs will also be written to a dedicated file via a FileHandler.
    NOTE: Never insert medusa_id into medusa_activity_log; only use allowed columns. DB persistence is handled by backend log_event, not here.
    """
    def __init__(self, socketio=None, log_to_file: bool = True, log_to_console: bool = None, log_to_ui: bool = None, logfile_path: str = 'tool_crawler.log'):
        self.socketio = socketio
        self.log_to_file = log_to_file
        self.log_to_console = VERBOSE_LOGGING if log_to_console is None else log_to_console
        self.log_to_ui = UI_LOGGING if log_to_ui is None else log_to_ui
        self.logger = logging.getLogger('ToolLogger')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
        if self.log_to_file:
            file_handler = logging.FileHandler(logfile_path)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        if self.log_to_console:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            self.logger.addHandler(stream_handler)

    def update_logging_toggles(self, verbose: bool, ui: bool):
        self.log_to_console = verbose
        self.log_to_ui = ui

    def log_event(self, event_type: str, data: dict = None, severity: str = "INFO", message: str = ""):
        """
        Emits a structured event for a given pipeline stage to SocketIO for UI, and optionally logs to file/console.
        NOTE: This does NOT write to medusa_activity_log directly; only the backend log_event does DB persistence.
        Bulletproof: data is always a plain dict.
        """
        import datetime
        import types
        import collections.abc
        # Bulletproof: ensure data is a plain dict
        if data is None:
            data = {}
        elif isinstance(data, dict):
            pass
        elif hasattr(data, 'items') and callable(data.items):
            try:
                data = dict(data)
            except Exception:
                data = {"_raw": str(data)}
        elif isinstance(data, (list, tuple, set, types.GeneratorType, collections.abc.Generator)):
            data = {"_raw": str(list(data))}
        else:
            data = {"_raw": str(data)}
        event = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "event_type": event_type,
            "severity": severity,
            "message": message,
        }
        event.update(data)
        # Emit to UI if enabled
        if getattr(self, 'log_to_ui', True) and self.socketio:
            self.socketio.emit("new_log_entry", event)
        # Log to console/file using standard logger
        log_message = f"[{event_type}] {message}"
        if data:
            log_message += f" | Data: {str(data)[:200]}"  # Truncate for console/file logs
        if severity.upper() == "ERROR":
            self.logger.error(log_message)
        elif severity.upper() == "WARNING":
            self.logger.warning(log_message)
        elif severity.upper() == "DEBUG":
            self.logger.debug(log_message)
        else:
            self.logger.info(log_message)
        # --- Persist to medusa_activity_log via global log_event ---
        try:
            from src.web_server import log_event as global_log_event
            global_log_event(event_type, message, severity=severity, **data)
        except Exception as e:
            self.logger.error(f"[ToolLogger] Failed to persist event to medusa_activity_log: {e}")
        return event

    def log(self, stage: str, data: Dict[str, Any], severity: str = "INFO", message: str = ""):
        """
        Logs a structured event for a given pipeline stage.
        This is a wrapper for log_event with a standardized event_type.
        """
        event_type = f"STAGE_{stage.upper()}"
        return self.log_event(event_type, data, severity, message)

    # TODO: Add methods for log formatting, severity filtering, and UI event emission. 