#!/usr/bin/env python3
"""
Web server for Medusa project.
Provides a web-based interface for controlling the crawler and managing training data collection.
"""
from dotenv import load_dotenv
load_dotenv()
import os
import sys
import logging
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash, send_from_directory, Response, copy_current_request_context, stream_with_context, current_app
from flask_socketio import SocketIO
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import threading
from pathlib import Path
import json
from datetime import datetime, timedelta, timezone
import webbrowser
from typing import Dict, Optional
from flask import abort
from threading import Event
import psutil
import torch
# Robust import for Database
try:
    from medusa.src.database import Database
except ImportError as e:
    print("\n[IMPORT ERROR] Could not import Database. Make sure to run this script from the project root using:\n    python -m medusa.src.web_server\nError details:", e)
    sys.exit(1)
from logging.handlers import RotatingFileHandler
import traceback
import time
from flask import current_app
import enum
from psycopg import sql as psql
import uuid
from cryptography.fernet import Fernet, InvalidToken
import io
import csv
import requests
import subprocess
from medusa.src.plugins.antigumf_plugin import AntiGumfPlugin
from flask import Blueprint, request, jsonify
from medusa.src.tool_crawler.orchestrator import ToolCrawlerOrchestrator
import psycopg
import psycopg.errors
from psycopg.rows import dict_row
import signal

def admin_required(f):
      # TEMP: Pass-through decorator for testing
      return f

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from medusa.src.crawler import SecurityCrawler
from medusa.src.auth import User
from medusa.src.tool_crawler.orchestrator import ToolCrawlerOrchestrator
# Robust import for EnrichmentPluginManager
try:
    from medusa.src.tool_crawler.enrichment_plugins.enrichment_plugin_manager import EnrichmentPluginManager
except ImportError:
    try:
        from src.tool_crawler.enrichment_plugins.enrichment_plugin_manager import EnrichmentPluginManager
    except ImportError:
        try:
            from .tool_crawler.enrichment_plugins.enrichment_plugin_manager import EnrichmentPluginManager
        except ImportError:
            import sys, os, importlib
            sys.path.append(os.path.join(os.path.dirname(__file__), 'tool_crawler', 'enrichment_plugins'))
            EnrichmentPluginManager = importlib.import_module('enrichment_plugin_manager').EnrichmentPluginManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Set a fixed secret key for session management
app.secret_key = 'b7f8e2c9a1d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Patch: Custom unauthorized handler for API endpoints
@login_manager.unauthorized_handler
def unauthorized_callback():
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Unauthorized'}), 401
    return redirect(url_for('login', next=request.path))

# Initialize crawler
crawler = SecurityCrawler()

# Store active crawls and their stop events
active_crawls: Dict[str, Dict] = {}
crawl_stop_events: Dict[str, Event] = {}
crawl_pause_events: Dict[str, Event] = {}

CRAWL_STATE_FILE = 'active_crawls.json'

activity_log = []

db = Database()

# Initialize orchestrator and attach to app for global access
if not hasattr(app, 'orchestrator'):
    # MODIFICATION: ToolCrawlerOrchestrator now uses db._encrypt via ToolDBWriter.
    # No explicit encryption key needs to be passed here.
    app.orchestrator = ToolCrawlerOrchestrator(db, socketio=socketio) # MODIFIED

# Load settings from config.json if it exists
import json
config_path = 'config.json'
try:
    with open(config_path, 'r') as f:
        config_data = json.load(f)
        db.update_settings(config_data)
        logger.info(f"Loaded settings from {config_path} and updated database settings.")
except FileNotFoundError:
    logger.info(f"No config.json found, using default settings.")
except Exception as e:
    logger.error(f"Error loading config.json: {e}")

# Add these globals near the top
medusa_running = False
current_task = 'Idle'

# Add a global list to track running AI training tasks (threads, processes, etc.)
running_training_tasks = []

# Logging toggles
VERBOSE_LOGGING = os.environ.get('MEDUSA_VERBOSE_LOGGING', '1') == '1'
ERROR_LOGGING = os.environ.get('MEDUSA_ERROR_LOGGING', '1') == '1'

# Enhanced logging setup
class DevelopmentLogger:
    def __init__(self):
        self.log_dir = 'logs'
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Main log files
        self.verbose_log = os.path.join(self.log_dir, 'medusa_verbose.log')
        self.error_log = os.path.join(self.log_dir, 'medusa_error.log')
        self.performance_log = os.path.join(self.log_dir, 'medusa_performance.log')
        self.page_tracking_log = os.path.join(self.log_dir, 'medusa_page_tracking.log')
        
        # Setup handlers
        self.setup_handlers()
        
        # Track page loads and errors
        self.page_loads = {}
        self.errors = []
        self.performance_metrics = {}
        
    def setup_handlers(self):
        # Verbose logging
        verbose_handler = RotatingFileHandler(
            self.verbose_log, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        verbose_handler.setLevel(logging.INFO)
        verbose_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s'
        ))
        
        # Error logging
        error_handler = RotatingFileHandler(
            self.error_log,
            maxBytes=10*1024*1024,
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s\n%(pathname)s:%(lineno)d\n%(message)s'
        ))
        
        # Performance logging
        perf_handler = RotatingFileHandler(
            self.performance_log,
            maxBytes=10*1024*1024,
            backupCount=5
        )
        perf_handler.setLevel(logging.INFO)
        perf_handler.setFormatter(logging.Formatter(
            '%(asctime)s [PERFORMANCE] %(message)s'
        ))
        
        # Page tracking logging
        page_handler = RotatingFileHandler(
            self.page_tracking_log,
            maxBytes=10*1024*1024,
            backupCount=5
        )
        page_handler.setLevel(logging.INFO)
        page_handler.setFormatter(logging.Formatter(
            '%(asctime)s [PAGE] %(message)s'
        ))
        
        # Add handlers to logger
        logger = logging.getLogger()
        logger.addHandler(verbose_handler)
        logger.addHandler(error_handler)
        logger.addHandler(perf_handler)
        logger.addHandler(page_handler)
        
    def log_page_load(self, page, duration, user_agent, ip):
        """Log page load with timing and user info"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'page': page,
            'duration': duration,
            'user_agent': user_agent,
            'ip': ip
        }
        self.page_loads[page] = entry
        logging.info(f"Page Load: {json.dumps(entry)}")
        
    def log_error(self, error, context=None):
        """Log error with full stack trace and context"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'error': str(error),
            'traceback': traceback.format_exc(),
            'context': context
        }
        self.errors.append(entry)
        logging.error(f"Error: {json.dumps(entry)}")
        
    def log_performance(self, operation, duration, details=None):
        """Log performance metrics"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'duration': duration,
            'details': details
        }
        self.performance_metrics[operation] = entry
        logging.info(f"Performance: {json.dumps(entry)}")
        
    def get_recent_errors(self, hours=24):
        """Get errors from the last 24 hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [e for e in self.errors if datetime.fromisoformat(e['timestamp']) > cutoff]
        
    def get_page_stats(self):
        """Get page load statistics"""
        return self.page_loads
        
    def get_performance_stats(self):
        """Get performance statistics"""
        return self.performance_metrics
        
    def clear_logs(self):
        """Clear all logs"""
        self.page_loads.clear()
        self.errors.clear()
        self.performance_metrics.clear()
        for log_file in [self.verbose_log, self.error_log, self.performance_log, self.page_tracking_log]:
            if os.path.exists(log_file):
                with open(log_file, 'w') as f:
                    f.write('')

# Initialize development logger
dev_logger = DevelopmentLogger()

# Add middleware for request timing
@app.before_request
def before_request():
    request.start_time = time.time()

@app.after_request
def after_request(response):
    if hasattr(request, 'start_time'):
        duration = time.time() - request.start_time
        dev_logger.log_performance(
            'request',
            duration,
            {
                'path': request.path,
                'method': request.method,
                'status': response.status_code
            }
        )
    return response

# Add error handler
@app.errorhandler(Exception)
def handle_exception(e):
    # Always pass extra data as keyword arguments, not as a dict positional argument
    log_event(
        event_type="CRAWLER_ERROR_INTERNAL",
        message=f"CRITICAL CRAWLER ERROR: {str(e)}",
        severity="CRITICAL",
        component="FlaskApp",
        error_message=str(e),
        stack_trace_snippet=traceback.format_exc(limit=3),
    )
    dev_logger.log_error(e, {
        'path': request.path,
        'method': request.method,
        'args': request.args,
        'form': request.form,
        'json': request.get_json(silent=True)
    })
    return jsonify({'error': str(e)}), 500

# Add page tracking
@app.after_request
def track_page(response):
    if request.path.startswith('/'):
        duration = time.time() - request.start_time
        dev_logger.log_page_load(
            request.path,
            duration,
            request.user_agent.string,
            request.remote_addr
        )
    return response

# Add API endpoint to get logs
@app.route('/api/system/logs', methods=['GET'])
@login_required
def get_logs():
    """Get recent logs for debugging"""
    if current_user.get_id() != 'Roylepython':
        abort(403)
    try:
        hours = request.args.get('hours', 24, type=int)
        return jsonify({
            'errors': dev_logger.get_recent_errors(hours),
            'page_stats': dev_logger.get_page_stats(),
            'performance': dev_logger.get_performance_stats()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Add API endpoint to clear logs
@app.route('/api/system/logs/clear', methods=['POST'])
@login_required
def clear_logs():
    """Clear all logs"""
    if current_user.get_id() != 'Roylepython':
        abort(403)
    try:
        dev_logger.clear_logs()
        return jsonify({'status': 'logs cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def save_crawl_state():
    with open(CRAWL_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(active_crawls, f, indent=2)

def load_crawl_state():
    if os.path.exists(CRAWL_STATE_FILE):
        with open(CRAWL_STATE_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                active_crawls.update(data)
            except Exception:
                pass

@login_manager.user_loader
def load_user(username):
    return User.get(username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.get(username)
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    """Render main page."""
    return render_template('index.html')

@app.route('/api/crawl', methods=['POST'])
@login_required
def start_crawl():
    global medusa_running, current_task
    print("[/api/crawl] Endpoint hit (diagnostic)")
    logger.info("[/api/crawl] Endpoint hit (diagnostic)")
    try:
        db.cursor.execute('SELECT * FROM crawler_tool_queue WHERE status = %s', ('pending',))
        pending_jobs = db.cursor.fetchall()
        logger.info(f"[DIAGNOSTIC] Pending jobs in crawler_tool_queue: {len(pending_jobs)}")
        for job in pending_jobs:
            logger.info(f"[DIAGNOSTIC] Pending job: {job}")
    except Exception as e:
        logger.error(f"[DIAGNOSTIC] Failed to fetch pending jobs: {e}")
    data = request.get_json(silent=True) or {}
    # --- PATCH: Ensure orchestrator is always initialized ---
    if not hasattr(app, 'orchestrator') or app.orchestrator is None:
        logger.warning("[PATCH] app.orchestrator was missing; re-initializing now.")
        try:
            app.orchestrator = ToolCrawlerOrchestrator(db, socketio=socketio)
            logger.info("[PATCH] app.orchestrator re-initialized successfully.")
        except Exception as e:
            logger.error(f"[PATCH] Failed to re-initialize orchestrator: {e}")
            return jsonify({'error': 'Orchestrator not initialized and could not be created.'}), 500
    try:
        @copy_current_request_context
        def crawl_thread():
            global medusa_running, current_task
            print("[/api/crawl] Crawl thread started (diagnostic)")
            logger.info("[/api/crawl] Crawl thread started (diagnostic)")
            medusa_running = True
            current_task = 'Crawling'
            socketio.emit('crawler_status_update', {'system_state': 'RUNNING', 'timestamp': datetime.now().isoformat()})
            try:
                print("[/api/crawl] Calling orchestrator.crawl_all() (diagnostic)")
                logger.info("[/api/crawl] Calling orchestrator.crawl_all() (diagnostic)")
                # DIAGNOSTIC: Prepare payload for logging
                log_payload_start = {"stage": "crawl_all_start"}
                print(f"[DIAG] log_event payload for start: {log_payload_start}")
                app.orchestrator.logger.log_event(
                    event_type="ORCHESTRATOR_LIFECYCLE",
                    message="Orchestrator crawl_all() starting from /api/crawl endpoint.",
                    severity="INFO",
                    data=log_payload_start
                )
                try:
                    app.orchestrator.crawl_all()
                except Exception as e:
                    import traceback
                    print(f"[DIAG] Exception in crawl_all: {e}")
                    traceback.print_exc()
                    raise
                print("[/api/crawl] Orchestrator finished (diagnostic)")
                logger.info("[/api/crawl] Orchestrator finished (diagnostic)")
                # DIAGNOSTIC: Prepare payload for logging
                log_payload_end = {"stage": "crawl_all_end"}
                print(f"[DIAG] log_event payload for end: {log_payload_end}")
                app.orchestrator.logger.log_event(
                    event_type="ORCHESTRATOR_LIFECYCLE",
                    message="Orchestrator crawl_all() finished from /api/crawl endpoint.",
                    severity="INFO",
                    data=log_payload_end
                )
                socketio.emit('crawl_complete', {'status': 'completed'})
            except Exception as e:
                print(f"[/api/crawl] Error during crawl: {e}")
                import traceback
                traceback.print_exc()
                logger.error(f"Error during crawl: {e}")
                socketio.emit('crawl_error', {'error': str(e)})
            finally:
                medusa_running = False
                current_task = None
                socketio.emit('crawler_status_update', {'system_state': 'IDLE', 'timestamp': datetime.now().isoformat()})
        import threading
        thread = threading.Thread(target=crawl_thread)
        thread.daemon = True
        thread.start()
        print("[/api/crawl] Crawl thread launched (diagnostic)")
        logger.info("[/api/crawl] Crawl thread launched (diagnostic)")
        return jsonify({'status': 'started'})
    except Exception as e:
        print(f"[/api/crawl] Threading failed, running crawl_all() directly: {e}")
        logger.error(f"Threading failed, running crawl_all() directly: {e}")
        try:
            app.orchestrator.crawl_all()
            return jsonify({'status': 'started_direct'})
        except Exception as e2:
            print(f"[/api/crawl] Direct crawl_all() failed: {e2}")
            logger.error(f"Direct crawl_all() failed: {e2}")
            return jsonify({'error': str(e2)}), 500

# --- PATCH: Add /api/crawler/start as an alias for /api/crawl ---
@app.route('/api/crawler/start', methods=['POST'])
@login_required
def start_crawler_alias():
    return start_crawl()

@app.route('/api/crawl/test-direct', methods=['POST'])
@login_required
def test_crawl_direct():
    print("[/api/crawl/test-direct] Called (diagnostic)")
    logger.info("[/api/crawl/test-direct] Called (diagnostic)")
    if not hasattr(app, 'orchestrator') or app.orchestrator is None:
        print("[/api/crawl/test-direct] FATAL: app.orchestrator is not set!")
        logger.error("[/api/crawl/test-direct] FATAL: app.orchestrator is not set!")
        return jsonify({'error': 'Orchestrator not initialized'}), 500
    try:
        app.orchestrator.crawl_all()
        return jsonify({'status': 'started_direct'})
    except Exception as e:
        print(f"[/api/crawl/test-direct] Direct crawl_all() failed: {e}")
        logger.error(f"Direct crawl_all() failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/crawl/<crawl_id>', methods=['GET'])
@login_required
def get_crawl_status(crawl_id):
    """Get status of a crawl."""
    if crawl_id not in active_crawls:
        return jsonify({'error': 'Crawl not found'}), 404
    
    return jsonify(active_crawls[crawl_id])

@app.route('/api/crawls', methods=['GET'])
@login_required
def list_crawls():
    """List all crawls."""
    return jsonify(list(active_crawls.items()))

@app.route('/api/sources', methods=['GET'])
@login_required
def list_sources():
    """List available crawl sources."""
    sources = {
        'nmap': {
            'name': 'Nmap Documentation',
            'description': 'Official Nmap documentation and service information',
            'category': 'services'
        },
        'cve': {
            'name': 'CVE Database',
            'description': 'Common Vulnerabilities and Exposures database',
            'category': 'vulnerabilities'
        },
        'owasp': {
            'name': 'OWASP Top 10',
            'description': 'OWASP security best practices and vulnerabilities',
            'category': 'best_practices'
        },
        'iana': {
            'name': 'IANA Port Numbers',
            'description': 'Official port number assignments and services',
            'category': 'ports'
        }
    }
    return jsonify(sources)

@app.route('/api/crawl/<crawl_id>/stop', methods=['POST'])
@login_required
def stop_crawl(crawl_id):
    """Stop a running crawl."""
    if crawl_id not in active_crawls:
        return jsonify({'error': 'Crawl not found'}), 404
    if active_crawls[crawl_id]['status'] != 'running':
        return jsonify({'error': 'Crawl is not running'}), 400
    stop_event = crawl_stop_events.get(crawl_id)
    if stop_event:
        stop_event.set()
        set_crawl_status(crawl_id, CrawlStatus.STOPPED)
        return jsonify({'status': 'stopped'})
    return jsonify({'error': 'Stop event not found'}), 500

@app.route('/api/crawl/<crawl_id>/remove', methods=['POST'])
@login_required
def remove_crawl(crawl_id):
    """Remove a crawl from the list."""
    if crawl_id not in active_crawls:
        return jsonify({'error': 'Crawl not found'}), 404
    active_crawls.pop(crawl_id, None)
    crawl_stop_events.pop(crawl_id, None)
    socketio.emit('crawl_removed', {'crawl_id': crawl_id})
    save_crawl_state()
    return jsonify({'status': 'removed'})

@app.route('/crawler')
@login_required
def crawler_page():
    """Render crawler control page."""
    return render_template('crawler.html')

@app.route('/scan-results')
@login_required
def scan_results_page():
    """Render scan results page."""
    return render_template('scan_results.html')

@app.route('/knowledge')
@login_required
def knowledge_page():
    """Render knowledge base page."""
    return render_template('knowledge_base.html')

@app.route('/ai-models')
@login_required
def ai_models_page():
    """Render AI models management page."""
    return render_template('ai_models.html')

@app.route('/visualization')
@login_required
def visualization_page():
    """Render visualization page."""
    return render_template('visualization.html')

@app.route('/system')
@login_required
def system_page():
    """Render system configuration page."""
    return render_template('system.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """Redirect /dashboard to the main dashboard at / (index.html)"""
    return redirect(url_for('index'))

@app.route('/api/scan-results', methods=['GET'])
@login_required
def get_scan_results():
    """Get all scan results."""
    try:
        results = crawler.get_scan_results()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scan', methods=['POST'])
@login_required
def start_scan():
    """Start a new scan."""
    if not medusa_running:
        return jsonify({'error': 'Medusa is not running'}), 403
    data = request.json
    try:
        result = crawler.start_scan(
            target=data.get('target'),
            scan_type=data.get('scan_type'),
            ports=data.get('ports')
        )
        activity_log.append({
            'timestamp': datetime.now().isoformat(),
            'description': f"Started scan: {data.get('target')} ({data.get('scan_type')})"
        })
        # Optionally, log scan completion if result indicates success
        if result.get('status') == 'completed':
            activity_log.append({
                'timestamp': datetime.now().isoformat(),
                'description': f"Completed scan: {data.get('target')} ({data.get('scan_type')})"
            })
        return jsonify(result)
    except Exception as e:
        activity_log.append({
            'timestamp': datetime.now().isoformat(),
            'description': f"Scan error: {data.get('target')} - {str(e)}"
        })
        return jsonify({'error': str(e)}), 500

@app.route('/api/scan/<int:scan_id>', methods=['DELETE'])
@login_required
def delete_scan(scan_id):
    """Delete a scan result."""
    try:
        crawler.delete_scan(scan_id)
        return jsonify({'status': 'deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge', methods=['GET'])
@login_required
def get_knowledge():
    try:
        knowledge = crawler.get_knowledge() or []
        return jsonify({'status': 'success', 'knowledge': knowledge})
    except Exception as e:
        logger.error(f"Error in get_knowledge: {e}")
        return jsonify({'status': 'error', 'knowledge': [], 'error': str(e)}), 500

@app.route('/api/knowledge/<category>', methods=['GET'])
@login_required
def get_knowledge_by_category(category):
    """Get knowledge entries by category."""
    try:
        knowledge = crawler.get_knowledge(category)
        return jsonify(knowledge)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/training-history', methods=['GET'])
@login_required
def get_training_history():
    """Get AI model training history."""
    try:
        history = crawler.get_training_history()
        return jsonify(history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/train', methods=['POST'])
@login_required
def train_model():
    """Start training a new AI model."""
    data = request.json
    try:
        result = crawler.train_model(
            model_type=data.get('model_type'),
            training_data=data.get('training_data'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date')
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/model/<int:model_id>', methods=['DELETE'])
@login_required
def delete_model(model_id):
    """Delete an AI model."""
    try:
        crawler.delete_model(model_id)
        return jsonify({'status': 'deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/visualization/data', methods=['GET'])
@login_required
def get_visualization_data():
    """Get data for visualization charts."""
    try:
        data = {
            'risk_distribution': crawler.get_risk_distribution(),
            'port_usage': crawler.get_port_usage(),
            'vulnerability_trends': crawler.get_vulnerability_trends(),
            'service_distribution': crawler.get_service_distribution(),
            'risk_score_timeline': crawler.get_risk_score_timeline()
        }
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/status', methods=['GET'])
@login_required
def get_system_status():
    """Get system status information."""
    try:
        status = {
            'database': crawler.get_database_status(),
            'models': crawler.get_model_status(),
            'resources': crawler.get_resource_status()
        }
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/database', methods=['GET'])
@login_required
def get_database_settings():
    try:
        settings = db.get_settings()
        return jsonify({
            'db_type': settings.get('db_type', 'postgresql'),
            'db_host': settings.get('db_host', 'localhost'),
            'db_port': settings.get('db_port', '5432'),
            'db_name': settings.get('db_name', 'medusa'),
            'db_user': settings.get('db_user', 'medusa'),
            'db_password': settings.get('db_password', '')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/database', methods=['POST'])
@login_required
def update_database_settings():
    data = request.json
    try:
        db.update_settings(data)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/security', methods=['POST'])
@login_required
def update_security_settings():
    """Update security settings."""
    data = request.json
    try:
        crawler.update_security_settings(data)
        return jsonify({'status': 'updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/ai', methods=['POST'])
@login_required
def update_ai_settings():
    """Update AI model settings."""
    data = request.json
    try:
        crawler.update_ai_settings(data)
        return jsonify({'status': 'updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/medusa/activity')
@login_required
def get_medusa_activity():
    try:
        global current_task, medusa_running
        cpu_usage = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        gpu_stats = {
            'utilization': 0,
            'memory_used': 0,
            'device_name': 'Not Available',
            'cuda_version': 'Not Available'
        }
        if torch.cuda.is_available():
            gpu_stats.update({
                'utilization': torch.cuda.utilization(),
                'memory_used': (torch.cuda.memory_allocated() / torch.cuda.max_memory_allocated()) * 100 if torch.cuda.max_memory_allocated() else 0,
                'device_name': torch.cuda.get_device_name(0),
                'cuda_version': torch.version.cuda
            })
        if not medusa_running:
            status = 'Stopped'
        elif active_crawls:
            status = 'Processing'
        else:
            status = 'Idle'
        recent_activities = []
        for activity in reversed(activity_log[-10:]):
            recent_activities.append({
                'timestamp': activity.get('timestamp', ''),
                'description': activity.get('description', '')
            })
        try:
            knowledge_entries = db.get_knowledge() or []
        except Exception as e:
            logger.error(f"Error fetching knowledge for activity: {e}")
            knowledge_entries = []
        knowledge_stats = {
            'total_entries': len(knowledge_entries),
            'recent_updates': len([k for k in knowledge_entries if k.get('timestamp') and (datetime.now() - datetime.fromisoformat(k.get('timestamp','1970-01-01'))).days < 7]),
            'categories': {}
        }
        for entry in knowledge_entries:
            category = entry.get('type', 'Unknown')
            knowledge_stats['categories'][category] = knowledge_stats['categories'].get(category, 0) + 1
        processing_queue = list(active_crawls.keys())
        learning_stats = {
            'total_training_sessions': 0,
            'last_training': '',
            'accuracy': 0
        }
        return jsonify({
            'current_task': status,
            'system_stats': {
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'active_threads': len(active_crawls)
            },
            'gpu_stats': gpu_stats,
            'recent_activities': recent_activities,
            'knowledge_stats': knowledge_stats,
            'processing_queue': processing_queue,
            'learning_stats': learning_stats
        })
    except Exception as e:
        logger.error(f"Error getting Medusa activity: {e}")
        return jsonify({
            'current_task': 'Idle',
            'system_stats': {
                'cpu_usage': 0,
                'memory_usage': 0,
                'active_threads': 0
            },
            'gpu_stats': {
                'utilization': 0,
                'memory_used': 0,
                'device_name': 'Not Available',
                'cuda_version': 'Not Available'
            },
            'learning_stats': {
                'total_training_sessions': 0,
                'last_training': '',
                'accuracy': 0
            },
            'recent_activities': [],
            'knowledge_stats': {
                'total_entries': 0,
                'recent_updates': 0,
                'categories': {}
            },
            'processing_queue': [],
            'error': str(e)
        }), 200

@app.route('/api/medusa/chat', methods=['POST'])
@login_required
def medusa_chat():
    """Handle communication with Medusa."""
    data = request.json
    message = data.get('message')

    if not message:
        return jsonify({'error': 'Message is required'}), 400

    # English-only enforcement
    from medusa.src.language_guard import enforce_english
    if rejection := enforce_english(message):
        return jsonify({'error': rejection}), 422

    try:
        # Process message through Medusa's core
        response = crawler.process_medusa_message(message)
        return jsonify({'response': response})
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/medusa/status', methods=['GET'])
@login_required
def medusa_status():
    """Get Medusa's current status."""
    try:
        status = {
            'core': crawler.get_medusa_core_status(),
            'learning': crawler.get_medusa_learning_status(),
            'decision': crawler.get_medusa_decision_status()
        }
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting Medusa status: {e}")
        return jsonify({'error': str(e)}), 500

# Helper function to check if there are jobs to process
def has_jobs_to_process():
    # Implement your logic here. For now, always return False (no jobs)
    return False

@app.route('/api/medusa/start', methods=['POST'])
@login_required
def start_medusa():
    global medusa_running, current_task
    if current_user.get_id() != 'Roylepython':
        abort(403)
    medusa_running = True
    current_task = 'Idle'
    logger.info('Medusa started by admin.')
    return jsonify({'status': 'started', 'current_task': current_task})

@app.route('/api/medusa/stop', methods=['POST'])
@login_required
def stop_medusa():
    global medusa_running, current_task, running_training_tasks
    if current_user.get_id() != 'Roylepython':
        abort(403)
    try:
        # Stop all running AI training tasks
        for task in running_training_tasks:
            try:
                if hasattr(task, 'stop'):
                    task.stop()
                    logger.info(f'Stopped AI training task: {task}')
                elif hasattr(task, 'terminate'):
                    task.terminate()
                    logger.info(f'Terminated AI training process: {task}')
                elif hasattr(task, 'cancel'):
                    task.cancel()
                    logger.info(f'Cancelled AI training job: {task}')
            except Exception as e:
                logger.error(f'Error stopping training task: {e}')
        running_training_tasks.clear()
        medusa_running = False
        current_task = 'Idle'  # Always set to Idle on stop
        # --- PATCH: Also turn off AI Command Center toggle ---
        db.update_settings({'ai_command_center_enabled': False})
        logger.info('Medusa stopped by admin. Initiating kill switch.')
        def shutdown():
            import time
            time.sleep(0.5)  # Give the response time to go out
            os._exit(0)
        threading.Thread(target=shutdown).start()
        return jsonify({'status': 'stopped', 'current_task': current_task, 'message': 'Medusa backend is shutting down.'})
    except Exception as e:
        logger.error(f'Error stopping Medusa: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/medusa/restart', methods=['POST'])
@login_required
def restart_medusa():
    global medusa_running, current_task
    if current_user.get_id() != 'Roylepython':
        abort(403)
    medusa_running = False
    medusa_running = True
    current_task = 'Idle'
    logger.info('Medusa restarted by admin.')
    return jsonify({'status': 'restarted', 'current_task': current_task})

def open_browser():
    """Open web browser to the application."""
    webbrowser.open('http://localhost:5000')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

_browser_opened = False

def main():
    global _browser_opened
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' and not _browser_opened:
        threading.Timer(1.5, open_browser).start()
        _browser_opened = True
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)

# On startup, load crawl state and resume any running crawls
load_crawl_state()
for crawl_id, crawl in list(active_crawls.items()):
    if crawl.get('status') == 'running':
        # Resume crawl in a new thread
        stop_event = Event()
        pause_event = Event()
        crawl_stop_events[crawl_id] = stop_event
        crawl_pause_events[crawl_id] = pause_event
        def resume_thread(crawl_id=crawl_id, crawl=crawl):
            try:
                results = crawler.crawl_source(
                    crawl.get('source'),
                    crawl.get('max_depth', 3),
                    crawl.get('max_pages', 1000),
                    stop_event=stop_event,
                    pause_event=pause_event
                )
                if stop_event.is_set():
                    set_crawl_status(crawl_id, CrawlStatus.STOPPED)
                    return
                # Convert results to dict if needed
                safe_results = dict(results) if hasattr(results, 'items') and not isinstance(results, dict) else results
                set_crawl_status(crawl_id, CrawlStatus.COMPLETED, {'results': safe_results})
                socketio.emit('crawl_complete', {
                    'crawl_id': crawl_id,
                    'status': 'completed',
                    'results': safe_results
                })
                log_event(
                    event_type="CRAWL_JOB_COMPLETED",
                    message=f"Crawl job {crawl_id} completed. Processed: {safe_results.get('pages_crawled', 0)} URLs, Found: {safe_results.get('knowledge_gained', 0)} new items, Errors: {safe_results.get('errors_this_job', 0)}.",
                    job_id=crawl_id,
                    total_urls_processed=safe_results.get('pages_crawled', 0),
                    new_kb_items_identified=safe_results.get('knowledge_gained', 0),
                    errors_encountered=safe_results.get('errors_this_job', 0),
                    emit_status=True
                )
                save_crawl_state()
            except Exception as e:
                set_crawl_status(crawl_id, CrawlStatus.FAILED, {'error': str(e)})
                socketio.emit('crawl_error', {
                    'crawl_id': crawl_id,
                    'error': str(e)
                })
                log_event(
                    event_type="CRAWL_JOB_ERROR_LIMIT_REACHED",
                    message=f"Crawl job {crawl_id} reached error limit. Error: {str(e)}",
                    job_id=crawl_id,
                    error_message=str(e),
                    emit_status=True
                )
                save_crawl_state()
        thread = threading.Thread(target=resume_thread)
        thread.daemon = True
        thread.start()

@app.route('/api/system/check-schema', methods=['POST'])
@login_required
def check_and_repair_schema():
    try:
        # Call the database's _create_tables method to ensure all tables exist
        db._create_tables()
        # Optionally, check encryption for sensitive fields
        # (Assume db._encrypt and db._decrypt use Fernet/AES-256)
        # Check a sample value
        test_value = 'test_secret'
        encrypted = db._encrypt(test_value)
        decrypted = db._decrypt(encrypted)
        encryption_ok = (decrypted == test_value)
        return jsonify({
            'status': 'ok',
            'schema_checked': True,
            'encryption_ok': encryption_ok,
            'encryption_method': 'Fernet (AES-256)'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/api/system/ollama-model', methods=['POST'])
@login_required
def save_ollama_model():
    data = request.json
    model = data.get('model')
    if not model:
        return jsonify({'error': 'No model specified'}), 400
    try:
        db.update_settings({'ollama_model': model})
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/ollama-model', methods=['GET'])
@login_required
def get_ollama_model():
    try:
        settings = db.get_settings()
        model = settings.get('ollama_model', '')
        return jsonify({'model': model})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/resources', methods=['GET'])
@login_required
def get_system_resources():
    """
    Returns JSON:
    {
        'cpu_usage': <system-wide percent>,
        'cpu_per_core': [<core0>, <core1>, ...],
        'process_cpu': <percent for Medusa process>,
        'memory_usage': <system percent>,
        'gpu_stats': { ... }
    }
    """
    try:
        import os
        # Sample per-core CPU usage once
        cpu_per_core = psutil.cpu_percent(interval=0.5, percpu=True)
        # Compute system-wide CPU usage as the average of per-core values
        cpu_usage = sum(cpu_per_core) / len(cpu_per_core) if cpu_per_core else 0
        process = psutil.Process(os.getpid())
        process_cpu = process.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        gpu_stats = {
            'utilization': 0,
            'memory_used': 0,
            'device_name': 'Not Available',
            'cuda_version': 'Not Available'
        }
        if torch.cuda.is_available():
            gpu_stats.update({
                'utilization': torch.cuda.utilization(),
                'memory_used': (torch.cuda.memory_allocated() / torch.cuda.max_memory_allocated()) * 100 if torch.cuda.max_memory_allocated() else 0,
                'device_name': torch.cuda.get_device_name(0),
                'cuda_version': torch.version.cuda
            })
        return jsonify({
            'cpu_usage': cpu_usage,
            'cpu_per_core': cpu_per_core,
            'process_cpu': process_cpu,
            'memory_usage': memory_usage,
            'gpu_stats': gpu_stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found_error(error):
    app.logger.warning(f"404 Not Found: {request.path}")
    return ("<h1>404 Not Found</h1><p>The requested URL was not found on the server.</p>", 404)

def load_crawler_settings():
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get('crawler_settings', {
            'user_agent': 'MedusaCrawler/1.0 (+https://github.com/yourusername/medusa)',
            'politeness_delay': 3
        })
    return {
        'user_agent': 'MedusaCrawler/1.0 (+https://github.com/yourusername/medusa)',
        'politeness_delay': 3
    }

def save_crawler_settings(settings):
    config = {}
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    config['crawler_settings'] = settings
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

@app.route('/api/crawler/settings', methods=['GET'])
@login_required
def get_crawler_settings():
    settings = load_crawler_settings()
    return jsonify(settings)

@app.route('/api/crawler/settings', methods=['POST'])
@login_required
def set_crawler_settings():
    data = request.json
    user_agent = data.get('user_agent', 'MedusaCrawler/1.0 (+https://github.com/yourusername/medusa)')
    try:
        politeness_delay = int(data.get('politeness_delay', 3))
    except Exception:
        politeness_delay = 3
    settings = {
        'user_agent': user_agent,
        'politeness_delay': politeness_delay
    }
    save_crawler_settings(settings)
    return jsonify({'status': 'updated'})

@app.route('/api/crawler/stats', methods=['GET'])
@login_required
def get_crawler_stats():
    try:
        db.cursor.execute('SELECT * FROM crawler_tool_queue WHERE status IN (%s, %s)', ('pending', 'running'))
        queue_jobs = db.cursor.fetchall() or []
        queue_size = len(queue_jobs)
        queue_list = queue_jobs

        db.cursor.execute('SELECT * FROM crawler_tool_queue WHERE status IN (%s, %s) ORDER BY id DESC LIMIT 1', ('running', 'completed'))
        current_job = db.cursor.fetchone()
        if not current_job:
            db.cursor.execute('SELECT * FROM crawler_tool_queue ORDER BY id DESC LIMIT 1')
            current_job = db.cursor.fetchone()
        current_job = current_job or {}

        db.cursor.execute('SELECT COUNT(*) as count FROM crawler_tool_queue')
        total_jobs_row = db.cursor.fetchone()
        total_jobs = total_jobs_row['count'] if total_jobs_row and 'count' in total_jobs_row else 0

        total_urls = 0  # TODO: update if you track URLs elsewhere

        db.cursor.execute('SELECT COUNT(*) as total_kb FROM knowledge')
        total_kb_row = db.cursor.fetchone()
        total_kb = total_kb_row['total_kb'] if total_kb_row and 'total_kb' in total_kb_row else 0

        db.cursor.execute('SELECT COUNT(*) as total_errors FROM crawler_tool_queue WHERE status = %s', ('failed',))
        total_errors_row = db.cursor.fetchone()
        total_errors = total_errors_row['total_errors'] if total_errors_row and 'total_errors' in total_errors_row else 0

        last_error = None
        db.cursor.execute('SELECT * FROM crawler_tool_queue WHERE status = %s ORDER BY id DESC LIMIT 1', ('failed',))
        failed_job = db.cursor.fetchone()
        if failed_job:
            last_error = {
                'timestamp': str(failed_job.get('updated_at', '')),
                'message': failed_job.get('error', 'Unknown error'),
                'type': 'JobFailed'
            }
        else:
            # Defensive: check if activity_log exists and is iterable
            if 'activity_log' in globals() and hasattr(activity_log, '__iter__'):
                for entry in reversed(activity_log):
                    if 'error' in entry.get('description', '').lower():
                        last_error = {
                            'timestamp': entry.get('timestamp'),
                            'message': entry.get('description'),
                            'type': 'GeneralError'
                        }
                        break

        return jsonify({
            'system_state': 'RUNNING' if any(j.get('status') == 'running' for j in queue_jobs) else ('IDLE' if queue_size == 0 else 'PENDING'),
            'queue_size': queue_size,
            'queue_list': queue_list,
            'current_job': current_job,
            'historical_stats': {
                'total_crawl_jobs_run': total_jobs,
                'total_urls_crawled_ever': total_urls,
                'total_kb_items_added_ever': total_kb,
                'total_errors_encountered_ever': total_errors
            },
            'last_error_details': last_error
        })
    except Exception as e:
        db.conn.rollback()
        logger.error(f"Error in get_crawler_stats: {e}")
        return jsonify({
            'system_state': 'IDLE',
            'queue_size': 0,
            'queue_list': [],
            'current_job': {},
            'historical_stats': {},
            'last_error_details': None,
            'error': str(e)
        }), 200

@app.route('/api/crawler/core-settings', methods=['GET'])
@login_required
def get_crawler_core_settings():
    # Load from config.json
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        settings = config.get('crawler_settings', {})
    else:
        settings = {}
    # Provide sensible defaults
    return jsonify({
        'user_agent': settings.get('user_agent', 'MedusaCrawler/1.0 (+https://github.com/yourusername/medusa)'),
        'politeness_delay': settings.get('politeness_delay', 3),
        'max_depth': settings.get('max_depth', 3),
        'scope': settings.get('scope', 'domain')
    })

@app.route('/api/crawler/core-settings', methods=['POST'])
@login_required
def set_crawler_core_settings():
    data = request.json
    # Validate
    user_agent = data.get('user_agent', 'MedusaCrawler/1.0 (+https://github.com/yourusername/medusa)')
    try:
        politeness_delay = int(data.get('politeness_delay', 3))
        if politeness_delay < 1 or politeness_delay > 60:
            raise ValueError
    except Exception:
        return jsonify({'error': 'Politeness delay must be an integer between 1 and 60.'}), 400
    try:
        max_depth = int(data.get('max_depth', 3))
        if max_depth < 1 or max_depth > 10:
            raise ValueError
    except Exception:
        return jsonify({'error': 'Crawl depth must be an integer between 1 and 10.'}), 400
    scope = data.get('scope', 'domain')
    if scope not in ['domain', 'subdomains', 'all']:
        return jsonify({'error': 'Scope must be one of: domain, subdomains, all.'}), 400
    # Save to config.json
    config = {}
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    if 'crawler_settings' not in config:
        config['crawler_settings'] = {}
    config['crawler_settings'].update({
        'user_agent': user_agent,
        'politeness_delay': politeness_delay,
        'max_depth': max_depth,
        'scope': scope
    })
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    return jsonify({'status': 'updated'})

@app.route('/api/crawler/filter-settings', methods=['GET'])
@login_required
def get_crawler_filter_settings():
    # Load from config.json
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        settings = config.get('crawler_settings', {})
    else:
        settings = {}
    return jsonify({
        'include_patterns': settings.get('include_patterns', ''),
        'exclude_patterns': settings.get('exclude_patterns', '')
    })

@app.route('/api/crawler/filter-settings', methods=['POST'])
@login_required
def set_crawler_filter_settings():
    data = request.json
    include_patterns = data.get('include_patterns', '').strip()
    exclude_patterns = data.get('exclude_patterns', '').strip()
    # Optionally validate regex (warn, but don't block on error)
    import re
    for pattern in include_patterns.splitlines():
        if pattern.strip():
            try:
                re.compile(pattern.strip())
            except Exception:
                return jsonify({'error': f'Invalid include pattern: {pattern}'}), 400
    for pattern in exclude_patterns.splitlines():
        if pattern.strip():
            try:
                re.compile(pattern.strip())
            except Exception:
                return jsonify({'error': f'Invalid exclude pattern: {pattern}'}), 400
    # Save to config.json
    config = {}
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    if 'crawler_settings' not in config:
        config['crawler_settings'] = {}
    config['crawler_settings'].update({
        'include_patterns': include_patterns,
        'exclude_patterns': exclude_patterns
    })
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    return jsonify({'status': 'updated'})

@app.route('/api/crawl/<crawl_id>/pause', methods=['POST'])
@login_required
def pause_crawl(crawl_id):
    """Pause a running crawl."""
    if crawl_id not in active_crawls:
        return jsonify({'error': 'Crawl not found'}), 404
    if active_crawls[crawl_id]['status'] != 'running':
        return jsonify({'error': 'Crawl is not running'}), 400
    pause_event = crawl_pause_events.get(crawl_id)
    if pause_event:
        pause_event.set()
        set_crawl_status(crawl_id, CrawlStatus.PAUSED)
        return jsonify({'status': 'paused'})
    return jsonify({'error': 'Pause event not found'}), 500

@app.route('/api/crawl/<crawl_id>/resume', methods=['POST'])
@login_required
def resume_crawl(crawl_id):
    """Resume a paused crawl."""
    if crawl_id not in active_crawls:
        return jsonify({'error': 'Crawl not found'}), 404
    if active_crawls[crawl_id]['status'] != 'paused':
        return jsonify({'error': 'Crawl is not paused'}), 400
    pause_event = crawl_pause_events.get(crawl_id)
    if pause_event:
        pause_event.clear()
        set_crawl_status(crawl_id, CrawlStatus.RUNNING)
        return jsonify({'status': 'resumed'})
    return jsonify({'error': 'Pause event not found'}), 500

# --- SocketIO Emit Helpers ---
def emit_log_entry(entry):
    socketio.emit('new_log_entry', entry)

def emit_crawler_status():
    # Reuse logic from get_crawler_stats
    if not medusa_running:
        system_state = "IDLE"
    elif any(c['status'] == 'running' for c in active_crawls.values()):
        system_state = "RUNNING"
    elif any(c['status'] == 'paused' for c in active_crawls.values()):
        system_state = "PAUSED"
    elif any(c['status'] == 'failed' for c in active_crawls.values()):
        system_state = "ERROR"
    else:
        system_state = "IDLE"
    current_job = None
    for job_id, job in active_crawls.items():
        if job['status'] == 'running':
            current_job = {
                'job_id': job_id,
                'status': job['status'],
                'progress': job.get('results', {}).get('pages_crawled', 0) / max(1, job.get('max_pages', 1000)),
                'message': f"Crawling page {job.get('results', {}).get('pages_crawled', 0)} of {job.get('max_pages', 1000)}"
            }
            break
    socketio.emit('crawler_status_update', {
        'system_state': system_state,
        'current_job': current_job,
        'timestamp': datetime.now().isoformat()
    })

# --- SocketIO Log Event Helper ---
ACTIVITY_LOG_MAX = 500

def log_event(event_type, message, severity="INFO", job_id=None, user=None, emit_status=False, **kwargs):
    """
    Bulletproof log_event: recursively sanitizes all kwargs to ensure all values are serializable and dicts are plain dicts.
    """
    def sanitize(val):
        # Recursively sanitize values
        if hasattr(val, 'items') and callable(val.items) and not isinstance(val, dict):
            try:
                return {k: sanitize(v) for k, v in dict(val).items()}
            except Exception:
                return str(val)
        elif isinstance(val, dict):
            return {k: sanitize(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [sanitize(v) for v in val]
        elif isinstance(val, tuple):
            return tuple(sanitize(v) for v in val)
        elif isinstance(val, (str, int, float, bool, type(None))):
            return val
        else:
            return str(val)
    logger.info(f"[log_event DIAG] event_type={event_type!r} message={message!r} severity={severity!r} job_id={job_id!r} user={user!r} emit_status={emit_status!r} kwargs_type={type(kwargs)} kwargs={kwargs}")
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "severity": severity,
        "message": message,
    }
    if job_id:
        entry["job_id"] = job_id
    if user:
        entry["user"] = user
    # Recursively sanitize all kwargs
    safe_kwargs = {str(k): sanitize(v) for k, v in kwargs.items()}
    logger.info(f"[log_event DIAG] sanitized kwargs: {safe_kwargs}")
    try:
        entry.update(safe_kwargs)
    except Exception as e:
        logger.error(f"[log_event] entry.update failed: {e} | safe_kwargs={safe_kwargs}")
        return entry
    activity_log.append(entry)
    if len(activity_log) > ACTIVITY_LOG_MAX:
        activity_log.pop(0)
    socketio.emit("new_log_entry", entry)
    if emit_status:
        emit_crawler_status()
    # --- Persistent DB logging ---
    try:
        timestamp = entry.get("timestamp")
        event_type_val = entry.get("event_type")
        severity_val = entry.get("severity")
        message_val = entry.get("message")
        job_id_val = entry.get("job_id")
        username_val = entry.get("user")
        data_fields = dict(entry)
        for k in ["timestamp", "event_type", "severity", "message", "job_id", "user"]:
            data_fields.pop(k, None)
        try:
            cursor = db.get_cursor()
            cursor.execute(
                """
                INSERT INTO medusa_activity_log (timestamp, event_type, severity, message, job_id, username, data) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    timestamp,
                    event_type_val,
                    severity_val,
                    message_val,
                    job_id_val,
                    username_val,
                    json.dumps(data_fields) if data_fields else None
                )
            )
            db.conn.commit()
        except Exception as e:
            logger.error(f"[log_event] DB insert failed, attempting reconnect: {e}")
            db.reconnect()
            try:
                cursor = db.get_cursor()
                cursor.execute(
                    """
                    INSERT INTO medusa_activity_log (timestamp, event_type, severity, message, job_id, username, data) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        timestamp,
                        event_type_val,
                        severity_val,
                        message_val,
                        job_id_val,
                        username_val,
                        json.dumps(data_fields) if data_fields else None
                    )
                )
                db.conn.commit()
            except Exception as e2:
                logger.error(f"[log_event] Failed to persist log entry to medusa_activity_log after reconnect: {e2}")
    except Exception as e:
        logger.error(f"[log_event] Unexpected error in DB logging: {e}")
    return entry

class CrawlStatus(enum.Enum):
    IDLE = 'idle'
    RUNNING = 'running'
    PAUSED = 'paused'
    STOPPED = 'stopped'
    COMPLETED = 'completed'
    FAILED = 'failed'
    ERROR_LIMIT = 'error_limit'
    EXHAUSTED = 'exhausted'

def set_crawl_status(crawl_id, status, extra=None):
    if crawl_id not in active_crawls:
        return
    prev_status = active_crawls[crawl_id].get('status')
    active_crawls[crawl_id]['status'] = status.value if isinstance(status, CrawlStatus) else status
    # Log transition
    if isinstance(extra, dict):
        safe_extra = {}
        for k, v in extra.items():
            if hasattr(v, 'items') and not isinstance(v, dict):
                safe_extra[k] = dict(v)
            elif isinstance(v, list) and v and hasattr(v[0], 'items'):
                safe_extra[k] = [dict(i) for i in v]
            else:
                safe_extra[k] = str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
        log_event(
            event_type="CRAWL_STATUS_CHANGE",
            message=f"Crawl {crawl_id} status changed from {prev_status} to {status}",
            job_id=crawl_id,
            emit_status=True,
            **safe_extra
        )
    else:
        log_event(
            event_type="CRAWL_STATUS_CHANGE",
            message=f"Crawl {crawl_id} status changed from {prev_status} to {status}",
            job_id=crawl_id,
            emit_status=True
        )
    # Emit SocketIO event
    socketio.emit('crawl_status_update', {'crawl_id': crawl_id, 'status': status.value if isinstance(status, CrawlStatus) else status})
    save_crawl_state()

# --- Crawler Tool Queue Management API ---
@app.route('/api/crawler/queue', methods=['GET'])
@login_required
def get_crawler_queue():
    import traceback
    try:
        with db.get_cursor() as cur: # Use 'with' statement
            try:
                cur.execute('SELECT COUNT(*) FROM public.crawler_tool_queue')
                row = cur.fetchone()
                row_count = row['count'] if row else 0
            except Exception as e:
                tb = traceback.format_exc()
                # Log the error, but don't necessarily stop if the main query can proceed
                log_event('CRAWLER_QUEUE_ERROR', f'Failed to fetch row count from crawler_tool_queue: {e}', error_details=str(e), traceback=tb, severity='WARNING')
                # If count fails, we might still be able to get jobs, or set row_count to indicate an issue.
                row_count = -1 # Indicate error in count

            # If we get here, the table is accessible or count query failed but we proceed
            cur.execute('SELECT * FROM public.crawler_tool_queue ORDER BY priority DESC, id ASC LIMIT 100') # Added priority sorting
            jobs = cur.fetchall() or []
        return jsonify({'status': 'success', 'row_count': row_count, 'queue': jobs})
    except Exception as e:
        # db.conn.rollback() # Should be handled by 'with' if an exception escapes it.
        tb = traceback.format_exc()
        log_event('CRAWLER_QUEUE_ERROR', f'Unexpected error in get_crawler_queue: {e}', error_details=str(e), traceback=tb, severity='ERROR')
        return jsonify({'status': 'error', 'error': str(e), 'traceback': tb}), 500

@app.route('/api/crawler/queue', methods=['POST'])
@login_required
def add_crawler_queue():
    try:
        data = request.get_json(force=True)
        tool_name = data.get('tool_name')
        target_url = data.get('target_url')
        parser_hint = data.get('parser_hint')
        priority = data.get('priority', 0)
        if not tool_name or not target_url:
            log_event('CRAWLER_QUEUE_ERROR', 'Add job failed: tool_name and target_url required', severity='WARNING', data=data)
            return jsonify({'status': 'error', 'error': 'tool_name and target_url required'}), 400
        
        with db.get_cursor() as cur:
            # PATCH: Prevent duplicate queue entries
            duplicate_check_query = '''
                SELECT id, status FROM crawler_tool_queue WHERE tool_name = %s AND target_url = %s AND status NOT IN ('completed', 'error')
            '''
            cur.execute(duplicate_check_query, (tool_name, target_url))
            existing = cur.fetchone()
            if existing:
                return jsonify({'status': 'exists', 'id': existing['id'], 'message': 'Job already in queue', 'status_existing': existing['status'], 'duplicate_check_query': duplicate_check_query}), 200
            # PATCH: Use correct field name completion_percentage
            cur.execute('''
                INSERT INTO crawler_tool_queue 
                    (tool_name, target_url, status, completion_percentage, force_recrawl_flag, last_crawled_at, priority, parser_hint) 
                VALUES (%s, %s, %s, %s, %s, NULL, %s, %s) 
                RETURNING id
            ''', (tool_name, target_url, 'queued', 0, False, priority, parser_hint))
            id_row = cur.fetchone()
            if id_row and id_row['id'] is not None:
                new_id = id_row['id']
                log_event('CRAWLER_QUEUE_ADD', f'Added job {tool_name} ({target_url})', severity='INFO', user=current_user.get_id(), data={'id': new_id, 'tool_data': data})
                return jsonify({'status': 'success', 'id': new_id}), 201
            else:
                log_event('CRAWLER_QUEUE_ERROR', f'Add job failed for {tool_name}: RETURNING id gave no result or None.', severity='ERROR', data=data)
                return jsonify({'status': 'error', 'error': 'Failed to retrieve ID after insert, operation likely rolled back.'}), 500
    except Exception as e:
        tb_str = traceback.format_exc()
        log_event('CRAWLER_QUEUE_ERROR', f'Error adding job: {str(e)}', severity='ERROR', error_details=str(e), traceback=tb_str)
        return jsonify({'status': 'error', 'error': str(e), 'traceback': tb_str}), 500

@app.route('/api/crawler/queue/<int:job_id>', methods=['DELETE'])
@login_required
def delete_crawler_queue(job_id):
    try:
        db.cursor.execute('DELETE FROM crawler_tool_queue WHERE id = %s RETURNING id', (job_id,))
        deleted = db.cursor.fetchone()
        db.conn.commit()
        if deleted:
            log_event('CRAWLER_QUEUE_DELETE', f'Deleted job {job_id}', severity='INFO', user=current_user.get_id())
            return jsonify({'status': 'success', 'id': job_id})
        else:
            return jsonify({'status': 'error', 'error': 'Job not found'}), 404
    except Exception as e:
        log_event('CRAWLER_QUEUE_ERROR', f'Error deleting job: {e}', severity='ERROR')
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/api/crawler/queue/<int:job_id>', methods=['PATCH'])
@login_required
def update_crawler_queue(job_id):
    try:
        data = request.get_json(force=True)
        fields = []
        values = []
        for key in ['tool_name', 'target_url', 'status', 'completion_perc', 'force_recrawl_flag', 'last_crawled_at', 'priority', 'parser_hint']:
            if key in data:
                fields.append(f"{key} = %s")
                values.append(data[key])
        if not fields:
            return jsonify({'status': 'error', 'error': 'No fields to update'}), 400
        values.append(job_id)
        db.cursor.execute(f'UPDATE crawler_tool_queue SET {", ".join(fields)} WHERE id = %s RETURNING id', tuple(values))
        updated = db.cursor.fetchone()
        db.conn.commit()
        if updated:
            log_event('CRAWLER_QUEUE_UPDATE', f'Updated job {job_id}', severity='INFO', user=current_user.get_id(), data=data)
            return jsonify({'status': 'success', 'id': job_id})
        else:
            return jsonify({'status': 'error', 'error': 'Job not found'}), 404
    except Exception as e:
        log_event('CRAWLER_QUEUE_ERROR', f'Error updating job: {e}', severity='ERROR')
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/api/crawler/queue/<int:tool_id>/recrawl', methods=['PUT'])
@login_required
def force_recrawl_tool(tool_id):
    try:
        db.cursor.execute('UPDATE crawler_tool_queue SET force_recrawl_flag = TRUE, status = \'pending\' WHERE id = %s RETURNING *', (tool_id,))
        db.conn.commit()
        updated = db.cursor.fetchone()
        if not updated:
            return jsonify({'status': 'fail', 'data': {'id': 'Tool not found'}}), 404
        return jsonify({'status': 'success', 'data': updated})
    except Exception as e:
        db.conn.rollback()
        logger.error(f"Error setting force_recrawl_flag: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/crawler/queue/<int:tool_id>/edit', methods=['PUT'])
@login_required
def edit_tool_in_queue(tool_id):
    data = request.get_json()
    fields = []
    values = []
    for field in ['target_url', 'parser_hint', 'priority']:
        if field in data:
            fields.append(psql.Identifier(field))
            values.append(data[field])
    if not fields:
        return jsonify({'status': 'fail', 'data': {'fields': 'No updatable fields provided'}}), 400
    try:
        set_clause = psql.SQL(', ').join([
            psql.SQL('{} = %s').format(f) for f in fields
        ])
        query = psql.SQL('UPDATE crawler_tool_queue SET {} WHERE id = %s RETURNING *').format(set_clause)
        db.cursor.execute(query, values + [tool_id])
        db.conn.commit()
        updated = db.cursor.fetchone()
        if not updated:
            return jsonify({'status': 'fail', 'data': {'id': 'Tool not found'}}), 404
        return jsonify({'status': 'success', 'data': updated})
    except Exception as e:
        db.conn.rollback()
        logger.error(f"Error editing tool in queue: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/crawler/queue/<int:tool_id>', methods=['DELETE'])
@login_required
def delete_tool_from_queue(tool_id):
    try:
        db.cursor.execute('DELETE FROM crawler_tool_queue WHERE id = %s RETURNING *', (tool_id,))
        db.conn.commit()
        deleted = db.cursor.fetchone()
        if not deleted:
            return jsonify({'status': 'fail', 'data': {'id': 'Tool not found'}}), 404
        return jsonify({'status': 'success', 'data': deleted})
    except Exception as e:
        db.conn.rollback()
        logger.error(f"Error deleting tool from queue: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/crawler/queue/<int:tool_queue_id>', methods=['DELETE'])
@login_required
def remove_tool_from_queue(tool_queue_id):
    db.cursor.execute('DELETE FROM crawler_tool_queue WHERE id = %s RETURNING id', (tool_queue_id,))
    deleted = db.cursor.fetchone()
    db.conn.commit()
    if not deleted:
        logger.warning(f"Attempted to remove non-existent tool_queue_id {tool_queue_id}")
        return jsonify({'status': 'fail', 'message': 'Tool not found', 'id': tool_queue_id}), 404
    logger.info(f"Removed tool_queue_id {tool_queue_id} from queue")
    return jsonify({'status': 'removed', 'id': tool_queue_id})

# --- End Crawler Tool Queue Management API ---

# --- Crawler Plugin Management API (Admin Only) ---
@app.route('/api/admin/crawler/plugins', methods=['GET'])
@login_required
def list_plugins():
    if current_user.get_id() != 'Roylepython':
        abort(403)
    try:
        db.cursor.execute('SELECT * FROM crawler_plugins ORDER BY id ASC')
        plugins = db.cursor.fetchall()
        return jsonify({'status': 'success', 'data': plugins})
    except Exception as e:
        logger.error(f"Error listing plugins: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/crawler/plugins', methods=['POST'])
@login_required
def add_plugin():
    if current_user.get_id() != 'Roylepython':
        abort(403)
    data = request.get_json()
    plugin_name = data.get('plugin_name')
    plugin_type = data.get('plugin_type')
    module_path = data.get('module_path')
    status = data.get('status', 'inactive')
    version = data.get('version')
    description = data.get('description')
    # Only allow module_path in allowed directory
    allowed_prefix = 'tool_crawler.parsers.'
    if not module_path or not module_path.startswith(allowed_prefix):
        return jsonify({'status': 'fail', 'data': {'module_path': 'Module path must start with tool_crawler.parsers.'}}), 400
    try:
        db.cursor.execute(
            'INSERT INTO crawler_plugins (plugin_name, plugin_type, module_path, status, version, description) VALUES (%s, %s, %s, %s, %s, %s) RETURNING *',
            (plugin_name, plugin_type, module_path, status, version, description)
        )
        db.conn.commit()
        new_plugin = db.cursor.fetchone()
        # Always convert DB row to dict before logging
        log_event('PLUGIN_ADDED', f'Plugin {plugin_name} added by {current_user.get_id()}', user=current_user.get_id(), plugin=dict(new_plugin) if new_plugin else None)
        return jsonify({'status': 'success', 'data': new_plugin}), 201
    except Exception as e:
        logger.error(f"Error adding plugin: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/crawler/plugins/<int:plugin_id>', methods=['PUT'])
@login_required
def update_plugin(plugin_id):
    if current_user.get_id() != 'Roylepython':
        abort(403)
    data = request.get_json()
    fields = []
    values = []
    allowed_fields = ['plugin_name', 'plugin_type', 'module_path', 'status', 'version', 'description']
    allowed_prefix = 'tool_crawler.parsers.'
    for field in allowed_fields:
        if field in data:
            if field == 'module_path' and not data[field].startswith(allowed_prefix):
                return jsonify({'status': 'fail', 'data': {'module_path': 'Module path must start with tool_crawler.parsers.'}}), 400
            fields.append(psql.Identifier(field))
            values.append(data[field])
    if not fields:
        return jsonify({'status': 'fail', 'data': {'fields': 'No updatable fields provided'}}), 400
    try:
        set_clause = psql.SQL(', ').join([
            psql.SQL('{} = %s').format(f) for f in fields
        ])
        query = psql.SQL('UPDATE crawler_plugins SET {} WHERE id = %s RETURNING *').format(set_clause)
        db.cursor.execute(query, values + [plugin_id])
        db.conn.commit()
        updated = db.cursor.fetchone()
        if not updated:
            return jsonify({'status': 'fail', 'data': {'id': 'Plugin not found'}}), 404
        # Always convert DB row to dict before logging
        log_event('PLUGIN_UPDATED', f'Plugin {plugin_id} updated by {current_user.get_id()}', user=current_user.get_id(), plugin=dict(updated) if updated else None)
        return jsonify({'status': 'success', 'data': updated})
    except Exception as e:
        logger.error(f"Error updating plugin: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/crawler/plugins/<int:plugin_id>', methods=['DELETE'])
@login_required
def delete_plugin(plugin_id):
    if current_user.get_id() != 'Roylepython':
        abort(403)
    confirm = request.args.get('confirm')
    if confirm != 'true':
        return jsonify({'status': 'fail', 'data': {'confirm': 'Set confirm=true to delete'}}), 400
    try:
        db.cursor.execute('DELETE FROM crawler_plugins WHERE id = %s RETURNING *', (plugin_id,))
        db.conn.commit()
        deleted = db.cursor.fetchone()
        if not deleted:
            return jsonify({'status': 'fail', 'data': {'id': 'Plugin not found'}}), 404
        # Always convert DB row to dict before logging
        log_event('PLUGIN_DELETED', f'Plugin {plugin_id} deleted by {current_user.get_id()}', user=current_user.get_id(), plugin=dict(deleted) if deleted else None)
        return jsonify({'status': 'success', 'data': deleted})
    except Exception as e:
        logger.error(f"Error deleting plugin: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
# --- End Crawler Plugin Management API ---

@app.route('/crawler-admin')
@login_required
def crawler_admin_page():
    if current_user.get_id() != 'Roylepython':
        abort(403)
    return render_template('crawler_admin.html', page='crawler_admin')

@app.route('/admin/knowledge_base_ui')
@login_required
def knowledge_base_ui_page():
    if current_user.get_id() != 'Roylepython':
        abort(403)
    return render_template('admin/knowledge_base_ui.html', page='knowledge_base_ui')

@app.route('/api/admin/db/health', methods=['GET'])
@login_required
def db_health():
    if current_user.get_id() != 'Roylepython':
        abort(403)
    # Define gold standard tables and columns
    gold_tables = {
        'knowledge': 7,
        'scan_results': 9,
        'training_history': 9,
        'settings': 3,
        'vulnerabilities': 16,
        'tools': 5,
        'urls_scraped': 7,
        'pages': 10,
        'pages_related_links': 7,
        'pages_related_socials': 9,
        'pages_video_content': 10,
        'pages_geo_location': 8
    }
    results = []
    for table, expected_cols in gold_tables.items():
        try:
            db.cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,))
            cols = db.cursor.fetchall()
            col_count = len(cols)
            db.cursor.execute(f"SELECT COUNT(*) FROM {table}")
            row_count = db.cursor.fetchone()['count']
            if col_count == expected_cols:
                status = 'healthy'
                details = ''
            elif col_count >= expected_cols - 1:
                status = 'warning'
                details = f"Expected {expected_cols} columns, found {col_count}."
            else:
                status = 'danger'
                details = f"Table missing columns (expected {expected_cols}, found {col_count})"
        except Exception as e:
            status = 'danger'
            col_count = 0
            row_count = 0
            details = f"Error: {str(e)}"
        results.append({
            'name': table,
            'status': status,
            'columns': col_count,
            'rows': row_count,
            'details': details
        })
    return jsonify({'status': 'success', 'data': results})

@app.route('/api/admin/db/audit', methods=['POST'])
@login_required
def db_audit():
    if current_user.get_id() != 'Roylepython':
        abort(403)
    def generate():
        gold_tables = ['knowledge', 'scan_results', 'training_history', 'settings', 'vulnerabilities', 'tools', 'urls_scraped', 'pages', 'pages_related_links', 'pages_related_socials', 'pages_video_content', 'pages_geo_location']
        yield 'Starting schema audit...\n'
        for t in gold_tables:
            yield f'Checking table: {t}... '
            try:
                db.cursor.execute(f"SELECT 1 FROM {t} LIMIT 1")
                yield 'OK\n'
            except Exception as e:
                yield f'MISSING or ERROR: {str(e)}\n'
        yield 'Ensuring all tables/columns exist...\n'
        db._create_tables()
        yield 'Schema creation/repair attempted.\n'
        # Optionally, check columns again
        for t in gold_tables:
            db.cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = %s", (t,))
            cols = db.cursor.fetchall()
            yield f'{t}: {len(cols)} columns\n'
        yield 'Audit complete.\n'
    return Response(generate(), mimetype='text/plain')

@app.route('/api/admin/db/table_columns/<table>', methods=['GET'])
@login_required
def db_table_columns(table):
    if current_user.get_id() != 'Roylepython':
        abort(403)
    try:
        db.cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position", (table,))
        cols = db.cursor.fetchall()
        return jsonify({'status': 'success', 'columns': cols})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/db/table_sample/<table>', methods=['GET'])
@login_required
def db_table_sample(table):
    if current_user.get_id() != 'Roylepython':
        abort(403)
    try:
        db.cursor.execute(f'SELECT * FROM {table} LIMIT 10')
        rows = db.cursor.fetchall()
        return jsonify({'status': 'success', 'rows': rows})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/activity_log', methods=['GET'])
@login_required
def get_activity_log():
    if current_user.get_id() != 'Roylepython':
        abort(403)
    # Query params: severity, event_type, job_id, medusa_id, username, start, end, search, page, page_size
    severity = request.args.getlist('severity')
    event_type = request.args.get('event_type')
    job_id = request.args.get('job_id')
    medusa_id = request.args.get('medusa_id')
    username = request.args.get('username')
    start = request.args.get('start')  # ISO8601 string
    end = request.args.get('end')      # ISO8601 string
    search = request.args.get('search', '').strip().lower()
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 50))
    # Build WHERE clause
    where = []
    values = []
    if severity:
        where.append(f"severity = ANY(%s)")
        values.append(severity)
    if event_type:
        where.append("event_type = %s")
        values.append(event_type)
    if job_id:
        where.append("job_id = %s")
        values.append(job_id)
    if medusa_id:
        where.append("medusa_id = %s")
        values.append(medusa_id)
    if username:
        where.append("username = %s")
        values.append(username)
    if start:
        where.append("timestamp >= %s")
        values.append(start)
    if end:
        where.append("timestamp <= %s")
        values.append(end)
    if search:
        # Search in message, event_type, and data JSONB
        where.append("(LOWER(message) LIKE %s OR LOWER(event_type) LIKE %s OR (data IS NOT NULL AND data::text ILIKE %s))")
        values.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    where_clause = f"WHERE {' AND '.join(where)}" if where else ''
    # Count query
    count_sql = f"SELECT COUNT(*) as count FROM medusa_activity_log {where_clause}"
    try:
        db.cursor.execute(count_sql, values)
        count_row = db.cursor.fetchone()
        if count_row is None:
            logger.error("[activity_log] COUNT query returned None. SQL: %s | values: %s", count_sql, values)
            return jsonify({'status': 'error', 'message': 'COUNT query failed'}), 500
        total = count_row['count']
    except Exception as e:
        logger.error(f"[activity_log] COUNT query failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    # Data query
    offset = (page - 1) * page_size
    data_sql = f"SELECT * FROM medusa_activity_log {where_clause} ORDER BY timestamp DESC LIMIT %s OFFSET %s"
    db.cursor.execute(data_sql, values + [page_size, offset])
    rows = db.cursor.fetchall()
    log_entries = []
    for row in rows:
        entry = dict(row)
        data = entry.get('data')
        if data:
            try:
                data = json.loads(data)
            except Exception:
                data = None
        if isinstance(data, dict):
            for k, v in data.items():
                if k not in entry:
                    entry[k] = v
        log_entries.append(entry)
    return jsonify({'status': 'success', 'data': log_entries, 'total': total})

@app.route('/api/admin/db/search/<table>', methods=['GET'])
@login_required
def db_search_table(table):
    """
    Unified, secure, and fast search endpoint for the knowledge base.
    Supports: knowledge, tools, vulnerabilities (CVE)
    Query params:
      - search: free text (ILIKE, FTS-ready)
      - column filters: e.g., cve_id, category, etc.
      - page, page_size
      - sort (column, asc/desc)
      - date/numeric range filters (e.g., date_published_from, date_published_to, cvss_v3_base_score_min, ...)
    Returns: { status, total, page, page_size, rows }
    Only accessible to admin/operator.
    """
    if current_user.get_id() != 'Roylepython':
        abort(403)
    allowed_tables = {
        'knowledge': ['id', 'title', 'content', 'source', 'type', 'timestamp'],
        'tools': [
            'id', 'tool_name', 'description', 'medusa_id',
            'category', 'official_site_url', 'documentation_url', 'source_code_url',
            'supported_os', 'tags', 'license', 'version', 'last_updated',
            'dependencies', 'extraction_confidence', 'source_url',
            'extraction_timestamp', 'created_at', 'updated_at'
        ],
        'vulnerabilities': [
            'medusa_id', 'cve_id', 'state', 'assigner_short_name', 'date_published', 'date_updated',
            'description', 'cvss_v3_base_score', 'cvss_v3_vector', 'cvss_v3_severity',
            'affected_products', 'problem_types', 'references', 'raw_json', 'created_at', 'updated_at'
        ]
    }
    if table not in allowed_tables:
        return jsonify({'status': 'error', 'message': 'Table not allowed'}), 400
    columns = allowed_tables[table]
    # --- Parse query params ---
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 50))
    sort = request.args.get('sort', columns[0])
    sort_dir = request.args.get('sort_dir', 'asc').lower()
    # Column filters
    filters = []
    values = []
    for col in columns:
        val = request.args.get(col)
        if val:
            filters.append(psql.SQL('{} = %s').format(psql.Identifier(col)))
            values.append(val)
    # Date/numeric range filters (for vulnerabilities)
    if table == 'vulnerabilities':
        for rng in [('date_published', 'date_published_from', '>='), ('date_published', 'date_published_to', '<='),
                    ('cvss_v3_base_score', 'cvss_v3_base_score_min', '>='), ('cvss_v3_base_score', 'cvss_v3_base_score_max', '<=')]:
            col, param, op = rng
            val = request.args.get(param)
            if val:
                filters.append(psql.SQL('{} {} %s').format(psql.Identifier(col), psql.SQL(op)))
                values.append(val)
    # Free text search (ILIKE for now, FTS-ready)
    if search:
        search_clauses = []
        # Iterate over the columns defined in allowed_tables for the current table
        current_table_columns = allowed_tables.get(table, []) # Get columns for the current table
        for col in current_table_columns:
            if table == 'tools':
                # For the 'tools' table, only search in 'tool_name' and 'description'
                if col == 'tool_name':
                    search_clauses.append(psql.SQL('{} ILIKE %s').format(psql.Identifier('tool_name')))
                    values.append(f'%{search}%')
                elif col == 'description':
                    search_clauses.append(psql.SQL('{} ILIKE %s').format(psql.Identifier('description')))
                    values.append(f'%{search}%')
            elif col in ['description', 'content', 'title', 'name']: # Original check for other tables/columns
                # For other tables, use their respective text-based columns
                search_clauses.append(psql.SQL('{} ILIKE %s').format(psql.Identifier(col)))
                values.append(f'%{search}%')
        if search_clauses:
            filters.append(psql.SQL('(') + psql.SQL(' OR ').join(search_clauses) + psql.SQL(')'))
    # --- Build query ---
    where_clause = psql.SQL('WHERE ') + psql.SQL(' AND ').join(filters) if filters else psql.SQL('')
    sort_col = sort if sort in columns else columns[0]
    sort_dir_sql = psql.SQL('ASC') if sort_dir == 'asc' else psql.SQL('DESC')
    # Count query
    count_query = psql.SQL('SELECT COUNT(*) FROM {} ').format(psql.Identifier(table)) + where_clause
    db.cursor.execute(count_query, values)
    total = db.cursor.fetchone()['count']
    # Data query
    offset = (page - 1) * page_size
    data_query = (
        psql.SQL('SELECT {} FROM {} ').format(
            psql.SQL(', ').join([psql.Identifier(c) for c in columns]),
            psql.Identifier(table)
        ) +
        where_clause +
        psql.SQL(' ORDER BY {} {} LIMIT %s OFFSET %s').format(psql.Identifier(sort_col), sort_dir_sql)
    )
    db.cursor.execute(data_query, values + [page_size, offset])
    rows = db.cursor.fetchall()

    # MODIFIED - Start of decryption logic for 'tools' table
    if table == 'tools':
        decrypted_rows = []
        fields_to_decrypt = [
            'tool_name', 'description', 'official_site_url', 
            'documentation_url', 'source_code_url', 'license', 'source_url'
        ]
        array_fields_to_decrypt = ['category', 'supported_os', 'tags', 'dependencies']
        for row_dict in rows: # Assuming rows are dicts
            new_row = dict(row_dict) # Make a mutable copy
            for field in fields_to_decrypt:
                if new_row.get(field) and isinstance(new_row[field], str): # Check if field exists and is a string
                    try:
                        new_row[field] = db._decrypt(new_row[field])
                    except InvalidToken:
                        logger.warning(f"TOOLS DECRYPTION FAILED (InvalidToken) for field '{field}', ID {new_row.get('id')}. Key mismatch or data corruption suspected.")
                        new_row[field] = '[DECRYPTION ERROR - INVALID TOKEN]'
                    except Exception as e:
                        logger.error(f"Error decrypting field {field} for tool ID {new_row.get('id')}: {e}")
                        new_row[field] = f'[DECRYPTION ERROR - {type(e).__name__}]'
            for field in array_fields_to_decrypt:
                if new_row.get(field) and isinstance(new_row[field], list):
                    decrypted_array = []
                    for item in new_row[field]:
                        if isinstance(item, str):
                            try:
                                decrypted_array.append(db._decrypt(item))
                            except InvalidToken:
                                logger.warning(f"TOOLS DECRYPTION FAILED (InvalidToken) for item in array field '{field}', ID {new_row.get('id')}. Key mismatch or data corruption suspected.")
                                decrypted_array.append('[DECRYPTION ERROR - INVALID TOKEN]')
                            except Exception as e:
                                logger.error(f"Error decrypting item in array field {field} for tool ID {new_row.get('id')}: {e}")
                                decrypted_array.append(f'[DECRYPTION ERROR - {type(e).__name__}]')
                        else:
                            decrypted_array.append(item) # Keep non-string items as is
                    new_row[field] = decrypted_array
            decrypted_rows.append(new_row)
        rows = decrypted_rows
    # MODIFIED - End of decryption logic

    return jsonify({
        'status': 'success',
        'total': total,
        'page': page,
        'page_size': page_size,
        'rows': rows
    })

@app.route('/kb/<entity_type>/<entity_id>')
@login_required
def kb_entity_detail(entity_type, entity_id):
    # Fetch all data for the entity (tools, vulnerabilities, MDE_)
    # For now, just pass entity_type and entity_id; template will fetch via JS
    return render_template('kb_entity_detail.html', entity_type=entity_type, entity_id=entity_id)

@app.route('/api/kb/entity/<entity_type>/<entity_id>', methods=['GET'])
@login_required
def api_kb_entity_detail(entity_type, entity_id):
    # Fetch all fields for the entity, plus related links, notes, media
    # For now, just return stub data
    # TODO: Implement real DB lookups and joins
    data = {
        'entity_type': entity_type,
        'entity_id': entity_id,
        'fields': {'name': entity_id, 'description': 'Example description', 'severity': 'HIGH'},
        'related_links': [],
        'remediation': 'Patch or mitigate as described.',
        'notes': [],
        'media': [],
    }
    return jsonify({'status': 'success', 'entity': data})

@app.route('/api/kb/entity/<entity_type>/<entity_id>/report', methods=['POST'])
@login_required
def api_kb_entity_report(entity_type, entity_id):
    # Add to scraping queue as class 2 (operator-requested, non-urgent)
    # TODO: Integrate with real crawl queue and priority system
    # For now, just log the request and pretend to queue it
    request_time = datetime.now(timezone.utc).isoformat()
    queue_class = 2  # 1 = urgent/client/internal, 2 = operator-requested, 3 = low-priority
    # FIXED: Only pass extra data as keyword arguments to log_event
    log_event(
        event_type="ENTITY_REPORT_REQUESTED",
        message=f"Entity {entity_type}:{entity_id} requested for crawl (class {queue_class}) by {current_user.get_id()}.",
        severity="INFO",
        entity_type=str(entity_type),
        entity_id=str(entity_id),
        queue_class=str(queue_class),
        request_time=str(request_time),
        user=str(current_user.get_id())
    )
    # In real logic: insert into crawl queue with class/priority
    return jsonify({'status': 'success', 'message': f'Entity queued for crawl as class {queue_class} (operator-requested, non-urgent).', 'queue_class': queue_class})

# --- Parser Plugin Management API ---
@app.route('/api/plugins/parsers', methods=['GET'])
@login_required
def list_parser_plugins():
    try:
        plugins = app.orchestrator.parser_manager.list_plugins()
        return jsonify({'status': 'success', 'data': plugins})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/plugins/parsers/<plugin_name>/enable', methods=['POST'])
@login_required
def enable_parser_plugin(plugin_name):
    try:
        meta = app.orchestrator.parser_manager.get_status(plugin_name)
        if not meta:
            return jsonify({'status': 'fail', 'message': f'Plugin {plugin_name} not found'}), 404
        if meta['status'] not in ('loaded', 'enabled', 'disabled'):
            return jsonify({'status': 'fail', 'message': f'Plugin {plugin_name} cannot be enabled (status: {meta["status"]})', 'data': meta}), 400
        if meta['enabled']:
            return jsonify({'status': 'success', 'message': f'Plugin {plugin_name} already enabled', 'data': meta})
        app.orchestrator.parser_manager.enable_plugin(plugin_name)
        meta = app.orchestrator.parser_manager.get_status(plugin_name)
        return jsonify({'status': 'success', 'message': f'Plugin {plugin_name} enabled', 'data': meta})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/plugins/parsers/<plugin_name>/disable', methods=['POST'])
@login_required
def disable_parser_plugin(plugin_name):
    try:
        meta = app.orchestrator.parser_manager.get_status(plugin_name)
        if not meta:
            return jsonify({'status': 'fail', 'message': f'Plugin {plugin_name} not found'}), 404
        override = request.args.get('override', 'false').lower() == 'true'
        default_parser = app.orchestrator.parser_manager.get_default_parser()
        if plugin_name == default_parser and not override:
            return jsonify({'status': 'fail', 'message': f'Cannot disable the default parser ({plugin_name}) unless override=true is set.', 'data': meta}), 400
        if not meta['enabled']:
            return jsonify({'status': 'success', 'message': f'Plugin {plugin_name} already disabled', 'data': meta})
        app.orchestrator.parser_manager.disable_plugin(plugin_name, override=override)
        meta = app.orchestrator.parser_manager.get_status(plugin_name)
        return jsonify({'status': 'success', 'message': f'Plugin {plugin_name} disabled', 'data': meta})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/plugins/parsers/<plugin_name>/status', methods=['GET'])
@login_required
def parser_plugin_status(plugin_name):
    try:
        meta = app.orchestrator.parser_manager.get_status(plugin_name)
        if meta:
            return jsonify({'status': 'success', 'data': meta})
        else:
            return jsonify({'status': 'fail', 'message': f'Plugin {plugin_name} not found'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/plugins/parsers/reload', methods=['POST'])
@login_required
def reload_parser_plugins():
    try:
        app.orchestrator.parser_manager.reload_plugins()
        plugins = app.orchestrator.parser_manager.list_plugins()
        return jsonify({
            'status': 'success',
            'message': 'Parser plugins reloaded. Note: Reload only affects new jobs. Running jobs keep their parser instance. If a plugin fails to reload, see its error field.',
            'data': plugins
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/plugins/parsers/default', methods=['GET'])
@login_required
def get_default_parser():
    try:
        default_parser = app.orchestrator.parser_manager.get_default_parser()
        if not default_parser:
            return jsonify({'status': 'success', 'data': None, 'message': 'No default parser set.'})
        meta = app.orchestrator.parser_manager.get_status(default_parser)
        return jsonify({'status': 'success', 'data': meta})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/plugins/parsers/default', methods=['POST'])
@login_required
def set_default_parser():
    try:
        data = request.get_json() or {}
        name = data.get('name')
        if not name:
            return jsonify({'status': 'fail', 'message': 'Missing parser name in request.'}), 400
        ok = app.orchestrator.parser_manager.set_default_parser(name)
        if ok:
            meta = app.orchestrator.parser_manager.get_status(name)
            return jsonify({'status': 'success', 'message': f'Default parser set to {name}', 'data': meta})
        else:
            return jsonify({'status': 'fail', 'message': f'Parser {name} not found or not loadable.'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/plugins/parsers/byfile/<filename>', methods=['GET'])
@login_required
def parser_plugin_by_file(filename):
    try:
        # filename should be the .py file, e.g. kali_docs_parser.py
        for meta in app.orchestrator.parser_manager.plugins.values():
            if meta.get('file_path', '').endswith(filename):
                return jsonify({'status': 'success', 'data': {k: v for k, v in meta.items() if k != 'class' and k != 'instance'}})
        return jsonify({'status': 'fail', 'message': f'No plugin found for file {filename}'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
# --- End Parser Plugin Management API ---

# --- Logging Settings API ---
VERBOSE_LOGGING = True
UI_LOGGING = True

@app.route('/api/system/logging', methods=['GET'])
@login_required
def get_logging_settings():
    try:
        settings = db.get_settings()
        return jsonify({
            'verbose_logging': settings.get('verbose_logging', VERBOSE_LOGGING),
            'ui_logging': settings.get('ui_logging', UI_LOGGING)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/logging', methods=['POST'])
@login_required
def set_logging_settings():
    data = request.json
    global VERBOSE_LOGGING, UI_LOGGING
    try:
        VERBOSE_LOGGING = bool(data.get('verbose_logging', True))
        UI_LOGGING = bool(data.get('ui_logging', True))
        # Persist to DB
        db.update_settings({'verbose_logging': VERBOSE_LOGGING, 'ui_logging': UI_LOGGING})
        # Update orchestrator logger in real time
        if hasattr(app, 'orchestrator') and hasattr(app.orchestrator, 'logger'):
            app.orchestrator.logger.log_to_console = VERBOSE_LOGGING
            app.orchestrator.logger.log_to_ui = UI_LOGGING
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- GLOBAL POST LOGGER FOR DIAGNOSTICS ---
@app.before_request
def log_all_post_requests():
    if request.method == 'POST':
        try:
            logger.info("[POST] %s %s", request.path, request.get_json(silent=True))
        except Exception as e:
            logger.error("[POST] %s (payload logging failed: %s)", request.path, str(e))

@app.route('/api/logs/tail', methods=['GET'])
@login_required
def tail_logs():
    if current_user.get_id() != 'Roylepython':
        abort(403)
    lines = int(request.args.get('lines', 100))
    try:
        db.cursor.execute('''
            SELECT timestamp, event_type, severity, message, job_id, username, data
            FROM medusa_activity_log
            ORDER BY timestamp DESC
            LIMIT %s
        ''', (lines,))
        rows = db.cursor.fetchall()
        # Convert to dicts and reverse for chronological order
        logs = [dict(row) for row in reversed(rows)]
        return jsonify({'status': 'success', 'lines': logs})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/plugins/parsers/status', methods=['GET'])
@login_required
def get_parser_plugin_status():
    try:
        plugins = app.orchestrator.parser_manager.list_plugins()
        enabled = [p for p in plugins if p.get('enabled') and p.get('status') in ('loaded', 'enabled')]
        if not enabled:
            from src.web_server import log_event
            log_event(
                event_type="PLUGIN_CRITICAL_ERROR",
                message="No enabled parser plugins available! All crawls will fail.",
                severity="CRITICAL"
            )
            return jsonify({'status': 'error', 'message': 'No enabled parser plugins available! All crawls will fail.', 'plugins': plugins}), 500
        return jsonify({'status': 'success', 'plugins': plugins})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def safe_get_crawler_stats():
    import traceback
    try:
        with db.get_cursor() as cur: # Use 'with' statement
            try:
                cur.execute('SELECT * FROM crawler_tool_queue WHERE status IN (%s, %s)', ('pending', 'running'))
                queue_jobs = cur.fetchall() or []
                queue_size = len(queue_jobs)
            except Exception as e:
                tb = traceback.format_exc()
                log_event('CRAWLER_STATS_ERROR', f'Failed to fetch queue jobs: {e}', error_details=str(e), traceback=tb, severity='ERROR') # Changed severity to ERROR
                # Return an error structure that the frontend might expect or can handle
                return jsonify({
                    'status': 'error', 
                    'system_state': 'ERROR',
                    'queue_size': -1, 
                    'error': f'Failed to fetch queue jobs: {e}', 
                    'traceback': tb
                }), 503 # Use 503 for service unavailable / backend DB error

            # Add more defensive fetches as needed...
            # These should also be wrapped in try-except if they are critical or prone to fail
            try:
                cur.execute('SELECT * FROM crawler_tool_queue WHERE status IN (%s, %s) ORDER BY id DESC LIMIT 1', ('running', 'completed'))
                current_job_row = cur.fetchone()
                if not current_job_row:
                    cur.execute('SELECT * FROM crawler_tool_queue ORDER BY id DESC LIMIT 1')
                    current_job_row = cur.fetchone()
                current_job = dict(current_job_row) if current_job_row else {}
            except Exception as e:
                log_event('CRAWLER_STATS_ERROR', f'Failed to fetch current_job: {e}', severity='WARNING')
                current_job = {'error': 'failed to fetch'}

            try:
                cur.execute('SELECT COUNT(*) as count FROM crawler_tool_queue')
                total_jobs_row = cur.fetchone()
                total_jobs = total_jobs_row['count'] if total_jobs_row and 'count' in total_jobs_row else 0
            except Exception as e:
                log_event('CRAWLER_STATS_ERROR', f'Failed to fetch total_jobs_count: {e}', severity='WARNING')
                total_jobs = -1 # Indicate error

            total_urls = 0  # Placeholder, as noted in original code

            try:
                cur.execute('SELECT COUNT(*) as total_kb FROM knowledge')
                total_kb_row = cur.fetchone()
                total_kb = total_kb_row['total_kb'] if total_kb_row and 'total_kb' in total_kb_row else 0
            except Exception as e:
                log_event('CRAWLER_STATS_ERROR', f'Failed to fetch total_kb_count: {e}', severity='WARNING')
                total_kb = -1 # Indicate error

            try:
                cur.execute('SELECT COUNT(*) as total_errors FROM crawler_tool_queue WHERE status = %s', ('failed',))
                total_errors_row = cur.fetchone()
                total_errors = total_errors_row['total_errors'] if total_errors_row and 'total_errors' in total_errors_row else 0
            except Exception as e:
                log_event('CRAWLER_STATS_ERROR', f'Failed to fetch total_errors_count: {e}', severity='WARNING')
                total_errors = -1 # Indicate error

            last_error = None
            try:
                cur.execute('SELECT * FROM crawler_tool_queue WHERE status = %s ORDER BY id DESC LIMIT 1', ('failed',))
                failed_job = cur.fetchone()
                if failed_job:
                    last_error = {
                        'timestamp': str(failed_job.get('updated_at', '')),
                        'message': failed_job.get('error', 'Unknown error'), # Assuming 'error' column exists
                        'type': 'JobFailed',
                        'job_id': failed_job.get('id')
                    }
            except Exception as e:
                log_event('CRAWLER_STATS_ERROR', f'Failed to fetch last_error_job: {e}', severity='WARNING')
                last_error = {'message': 'failed to fetch last error', 'type': 'SystemError'}
        
        # If execution reaches here, the primary queue_jobs fetch was successful.
        return jsonify({
            'status': 'ok', # Overall status is ok if we got this far
            'system_state': 'RUNNING' if any(j.get('status') == 'running' for j in queue_jobs) else ('IDLE' if queue_size == 0 else 'PENDING'),
            'queue_size': queue_size,
            'queue_list': [dict(j) for j in queue_jobs], # Ensure jobs are dicts
            'current_job': current_job,
            'historical_stats': {
                'total_crawl_jobs_run': total_jobs,
                'total_urls_crawled_ever': total_urls,
                'total_kb_items_added_ever': total_kb,
                'total_errors_encountered_ever': total_errors
            },
            'last_error_details': last_error
        })

    except Exception as e:
        # This outer except block catches errors if db.get_cursor() itself fails, or other unexpected issues.
        tb = traceback.format_exc()
        log_event('CRAWLER_STATS_ERROR', f'Unexpected critical error in get_crawler_stats: {e}', error_details=str(e), traceback=tb, severity='CRITICAL')
        return jsonify({
            'status': 'error', 
            'system_state': 'ERROR', 
            'error': f'Unexpected critical error in get_crawler_stats: {e}', 
            'traceback': tb
        }), 500

# Replace the original get_crawler_stats with the safe version
app.view_functions['get_crawler_stats'] = safe_get_crawler_stats

# --- Admin CRUD API for Knowledge Base, Tools, Vulnerabilities ---
@app.route('/api/admin/db/<table>', methods=['POST'])
@login_required
def admin_create_entry(table):
    if current_user.get_id() != 'Roylepython':
        abort(403)
    allowed_tables = ['knowledge', 'tools', 'vulnerabilities']
    if table not in allowed_tables:
        return jsonify({'status': 'error', 'message': 'Table not allowed'}), 400
    data = request.get_json()
    try:
        cols = list(data.keys())
        vals = [data[c] for c in cols]
        insert_sql = psql.SQL('INSERT INTO {} ({}) VALUES ({}) RETURNING *').format(
            psql.Identifier(table),
            psql.SQL(', ').join(map(psql.Identifier, cols)),
            psql.SQL(', ').join(psql.Placeholder() * len(cols))
        )
        db.cursor.execute(insert_sql, vals)
        db.conn.commit()
        row = db.cursor.fetchone()
        return jsonify({'status': 'success', 'row': dict(row)})
    except Exception as e:
        db.conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/db/<table>/<int:row_id>', methods=['PUT'])
@login_required
def admin_update_entry(table, row_id):
    if current_user.get_id() != 'Roylepython':
        abort(403)
    allowed_tables = ['knowledge', 'tools', 'vulnerabilities']
    if table not in allowed_tables:
        return jsonify({'status': 'error', 'message': 'Table not allowed'}), 400
    data = request.get_json()
    try:
        cols = list(data.keys())
        vals = [data[c] for c in cols]
        set_clause = psql.SQL(', ').join([
            psql.SQL('{} = %s').format(psql.Identifier(c)) for c in cols
        ])
        update_sql = psql.SQL('UPDATE {} SET {} WHERE id = %s RETURNING *').format(
            psql.Identifier(table), set_clause
        )
        db.cursor.execute(update_sql, vals + [row_id])
        db.conn.commit()
        row = db.cursor.fetchone()
        return jsonify({'status': 'success', 'row': dict(row)})
    except Exception as e:
        db.conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/db/<table>/<int:row_id>', methods=['DELETE'])
@login_required
def admin_delete_entry(table, row_id):
    if current_user.get_id() != 'Roylepython':
        abort(403)
    allowed_tables = ['knowledge', 'tools', 'vulnerabilities']
    if table not in allowed_tables:
        return jsonify({'status': 'error', 'message': 'Table not allowed'}), 400
    try:
        del_sql = psql.SQL('DELETE FROM {} WHERE id = %s RETURNING *').format(psql.Identifier(table))
        db.cursor.execute(del_sql, [row_id])
        db.conn.commit()
        row = db.cursor.fetchone()
        return jsonify({'status': 'success', 'row': dict(row) if row else None})
    except Exception as e:
        db.conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- Export Endpoints ---
@app.route('/api/admin/db/export/<table>/<fmt>', methods=['GET'])
@login_required
def export_table(table, fmt):
    if current_user.get_id() != 'Roylepython':
        abort(403)
    allowed_tables = {
        'knowledge': ['id', 'title', 'content', 'source', 'type', 'timestamp'],
        'tools': ['id', 'name', 'description', 'medusa_id'],
        'vulnerabilities': [
            'medusa_id', 'cve_id', 'state', 'assigner_short_name', 'date_published', 'date_updated',
            'description', 'cvss_v3_base_score', 'cvss_v3_vector', 'cvss_v3_severity',
            'affected_products', 'problem_types', 'references', 'raw_json', 'created_at', 'updated_at'
        ]
    }
    if table not in allowed_tables:
        return jsonify({'status': 'error', 'message': 'Table not allowed'}), 400
    columns = allowed_tables[table]
    try:
        db.cursor.execute(psql.SQL('SELECT {} FROM {}').format(
            psql.SQL(', ').join([psql.Identifier(c) for c in columns]),
            psql.Identifier(table)
        ))
        rows = db.cursor.fetchall()
        if fmt == 'csv':
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))
            output.seek(0)
            return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name=f'{table}.csv')
        elif fmt == 'json':
            return jsonify({'status': 'success', 'rows': [dict(r) for r in rows]})
        else:
            return jsonify({'status': 'error', 'message': 'Format not supported'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/system/ai-command-center', methods=['GET'])
@login_required
def get_ai_command_center_setting():
    try:
        settings = db.get_settings()
        enabled = settings.get('ai_command_center_enabled', False)
        return jsonify({'enabled': enabled})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/ai-command-center', methods=['POST'])
@login_required
def set_ai_command_center_setting():
    data = request.get_json(force=True)
    enabled = bool(data.get('enabled', False))
    try:
        db.update_settings({'ai_command_center_enabled': enabled})
        return jsonify({'enabled': enabled})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Basic Administration API ---
@app.route('/api/system/ollama/language', methods=['GET', 'POST'])
@login_required
def ollama_language():
    if request.method == 'GET':
        settings = db.get_settings()
        return jsonify({'language': settings.get('ollama_language', 'en')})
    else:
        data = request.get_json(force=True)
        lang = data.get('language', 'en')
        db.update_settings({'ollama_language': lang})
        return jsonify({'status': 'ok', 'language': lang})

@app.route('/api/system/ollama/models', methods=['GET'])
@login_required
def ollama_models():
    try:
        import requests
        resp = requests.get('http://localhost:11434/api/tags', timeout=5)
        data = resp.json()
        return jsonify({'models': data.get('models', [])})
    except Exception as e:
        return jsonify({'models': [], 'error': str(e)})

@app.route('/api/system/ollama/model', methods=['GET', 'POST'])
@login_required
def ollama_model():
    if request.method == 'GET':
        settings = db.get_settings()
        return jsonify({'model': settings.get('ollama_model', '')})
    else:
        data = request.get_json(force=True)
        model = data.get('model', '')
        db.update_settings({'ollama_model': model})
        return jsonify({'status': 'ok', 'model': model})

@app.route('/api/system/startup', methods=['GET', 'POST'])
@login_required
def medusa_startup():
    if request.method == 'GET':
        settings = db.get_settings()
        return jsonify({
            'auto_start': settings.get('auto_start_medusa', False),
            'default_state': settings.get('default_system_state', 'idle')
        })
    else:
        data = request.get_json(force=True)
        db.update_settings({
            'auto_start_medusa': bool(data.get('auto_start', False)),
            'default_system_state': data.get('default_state', 'idle')
        })
        return jsonify({'status': 'ok'})

@app.route('/api/system/safemode', methods=['GET', 'POST'])
@login_required
def medusa_safemode():
    if request.method == 'GET':
        settings = db.get_settings()
        return jsonify({'safe_mode': settings.get('safe_mode', False)})
    else:
        data = request.get_json(force=True)
        db.update_settings({'safe_mode': bool(data.get('safe_mode', False))})
        return jsonify({'status': 'ok'})

@app.route('/api/system/quickaction', methods=['POST'])
@login_required
def medusa_quickaction():
    data = request.get_json(force=True)
    action = data.get('action')
    # Stubs for now
    if action == 'start':
        # TODO: Implement real start logic
        return jsonify({'status': 'started'})
    elif action == 'restart':
        # TODO: Implement real restart logic
        return jsonify({'status': 'restarted'})
    elif action == 'stop':
        # TODO: Implement real stop logic
        return jsonify({'status': 'stopped'})
    elif action == 'kill':
        # TODO: Implement real kill switch logic
        return jsonify({'status': 'killed'})
    else:
        return jsonify({'status': 'error', 'message': 'Unknown action'}), 400

# --- Database Management API ---
@app.route('/api/system/db/pg_status', methods=['GET'])
@login_required
def db_pg_status():
    try:
        import psycopg
        cur = db.conn.cursor()
        cur.execute('SELECT version()')
        version = cur.fetchone()[0]
        cur.execute('SELECT pg_postmaster_start_time()')
        uptime = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s', ('public',))
        table_count = cur.fetchone()[0]
        return jsonify({'status': 'ok', 'version': version, 'uptime': str(uptime), 'table_count': table_count})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

@app.route('/api/system/db/schema_audit', methods=['POST'])
@login_required
def db_schema_audit():
    # Stub: run schema audit, return progress/log
    return jsonify({'status': 'ok', 'output': 'Schema audit started (stub).'}), 202

@app.route('/api/system/db/backup', methods=['POST'])
@login_required
def db_backup():
    # Stub: run backup, return progress/log
    return jsonify({'status': 'ok', 'output': 'Backup started (stub).'}), 202

@app.route('/api/system/db/restore', methods=['POST'])
@login_required
def db_restore():
    # Stub: run restore, return progress/log
    return jsonify({'status': 'ok', 'output': 'Restore started (stub).'}), 202

@app.route('/api/system/db/console', methods=['POST'])
@login_required
def db_console():
    # Stub: run SQL, return output
    data = request.get_json(force=True)
    sql = data.get('sql', '')
    return jsonify({'status': 'ok', 'output': f'Executed: {sql} (stub)'})

# --- System Health API ---
@app.route('/api/system/health', methods=['GET', 'POST'])
@login_required
def system_health():
    if request.method == 'GET':
        import psutil
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        return jsonify({'cpu': cpu, 'memory': mem, 'disk': disk, 'status': 'ok'})
    else:
        # POST: repair/clear cache/recheck schema, etc.
        data = request.get_json(force=True)
        action = data.get('action')
        # Stub actions
        if action == 'repair':
            return jsonify({'status': 'ok', 'output': 'Repair started (stub).'}), 202
        elif action == 'clear_cache':
            return jsonify({'status': 'ok', 'output': 'Cache cleared (stub).'}), 202
        elif action == 'recheck_schema':
            return jsonify({'status': 'ok', 'output': 'Schema recheck started (stub).'}), 202
        else:
            return jsonify({'status': 'error', 'message': 'Unknown action'}), 400

@app.route('/api/plugins/enrichment/health', methods=['GET'])
@login_required
def plugin_health():
    # Return health status for all enrichment plugins
    try:
        health = plugin_manager.get_all_plugin_health()
        return jsonify(health)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/plugins/enrichment/logs/<plugin_name>', methods=['GET'])
@login_required
def plugin_logs(plugin_name):
    # Return logs/errors for a plugin
    try:
        logs = plugin_manager.get_plugin_logs(plugin_name)
        return jsonify({'logs': logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/plugins/enrichment/version/<plugin_name>', methods=['GET'])
@login_required
def plugin_version(plugin_name):
    try:
        version = plugin_manager.get_plugin_version(plugin_name)
        return jsonify({'version': version})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/plugins/enrichment/update/<plugin_name>', methods=['GET'])
@login_required
def plugin_update_check(plugin_name):
    # Stub: check for updates (future: check PyPI/git)
    return jsonify({'update_available': False, 'message': 'Update check not implemented yet.'})

plugin_manager = EnrichmentPluginManager()

@app.route('/api/plugins/enrichment/list', methods=['GET'])
@login_required
def list_enrichment_plugins():
    try:
        plugins = plugin_manager.list_plugins()
        return jsonify(plugins)
    except Exception as e:
        logger.error(f"Error in /api/plugins/enrichment/list: {e}")
        return jsonify({'error': str(e)}), 500

# --- PGADMIN 4 INTEGRATION ---
PGADMIN_URL = os.environ.get('PGADMIN_URL', 'http://localhost:5050')
PGADMIN_EMAIL = os.environ.get('PGADMIN_EMAIL', 'medusa@localhost')
PGADMIN_PASSWORD = os.environ.get('PGADMIN_PASSWORD', 'medusa123')

# Helper to launch pgAdmin 4 (Docker)
def launch_pgadmin():
    # Only launch if not already running
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(('localhost', 5050))
        s.close()
        return  # Already running
    except Exception:
        pass
    s.close()
    # Launch pgAdmin 4 Docker container
    cmd = [
        'docker', 'run', '--rm', '-d',
        '-p', '5050:80',
        '-e', f'PGADMIN_DEFAULT_EMAIL={PGADMIN_EMAIL}',
        '-e', f'PGADMIN_DEFAULT_PASSWORD={PGADMIN_PASSWORD}',
        '--name', 'medusa-pgadmin',
        'dpage/pgadmin4'
    ]
    subprocess.Popen(cmd)

@app.route('/db-admin', defaults={'path': ''})
@app.route('/db-admin/<path:path>')
@login_required
def proxy_pgadmin(path):
    launch_pgadmin()  # Ensure pgAdmin is running
    url = f"{PGADMIN_URL}/{path}"
    headers = {k: v for k, v in request.headers if k.lower() != 'host'}
    resp = requests.request(
        method=request.method,
        url=url,
        headers=headers,
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False,
        stream=True
    )
    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
    response = Response(stream_with_context(resp.iter_content(chunk_size=1024)), resp.status_code, headers)
    return response

# --- Category Management (Admin) ---
from flask import request

CATEGORIES = {
    'tools': [
        {'id': 1, 'name': 'Reconnaissance'},
        {'id': 2, 'name': 'Exploitation'},
        {'id': 3, 'name': 'Post-Exploitation'}
    ],
    'knowledge': [
        {'id': 1, 'name': 'Security Concepts'},
        {'id': 2, 'name': 'Scan Examples'},
        {'id': 3, 'name': 'Operator Tips'}
    ]
}

@app.route('/api/admin/categories/<cat_type>', methods=['GET'])
@login_required
def list_categories(cat_type):
    if current_user.get_id() != 'Roylepython':
        abort(403)
    return jsonify({'status': 'success', 'categories': CATEGORIES.get(cat_type, [])})

@app.route('/api/admin/categories/<cat_type>', methods=['POST'])
@login_required
def add_category(cat_type):
    if current_user.get_id() != 'Roylepython':
        abort(403)
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'status': 'error', 'message': 'Name required'}), 400
    new_id = max([c['id'] for c in CATEGORIES.get(cat_type, [])] or [0]) + 1
    cat = {'id': new_id, 'name': name}
    CATEGORIES.setdefault(cat_type, []).append(cat)
    return jsonify({'status': 'success', 'category': cat})

@app.route('/api/admin/categories/<cat_type>/<int:cat_id>', methods=['PUT'])
@login_required
def edit_category(cat_type, cat_id):
    if current_user.get_id() != 'Roylepython':
        abort(403)
    data = request.json
    name = data.get('name')
    cats = CATEGORIES.get(cat_type, [])
    for c in cats:
        if c['id'] == cat_id:
            c['name'] = name
            return jsonify({'status': 'success', 'category': c})
    return jsonify({'status': 'error', 'message': 'Not found'}), 404

@app.route('/api/admin/categories/<cat_type>/<int:cat_id>', methods=['DELETE'])
@login_required
def delete_category(cat_type, cat_id):
    if current_user.get_id() != 'Roylepython':
        abort(403)
    cats = CATEGORIES.get(cat_type, [])
    for i, c in enumerate(cats):
        if c['id'] == cat_id:
            cats.pop(i)
            return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Not found'}), 404

@app.route('/api/admin/categories/<cat_type>/<int:cat_id>/move', methods=['POST'])
@login_required
def move_category(cat_type, cat_id):
    if current_user.get_id() != 'Roylepython':
        abort(403)
    data = request.json
    direction = int(data.get('direction', 0))
    cats = CATEGORIES.get(cat_type, [])
    idx = next((i for i, c in enumerate(cats) if c['id'] == cat_id), None)
    if idx is None or direction == 0:
        return jsonify({'status': 'error', 'message': 'Not found'}), 404
    new_idx = idx + direction
    if new_idx < 0 or new_idx >= len(cats):
        return jsonify({'status': 'error', 'message': 'Out of bounds'}), 400
    cats[idx], cats[new_idx] = cats[new_idx], cats[idx]
    return jsonify({'status': 'success'})

# --- ANTI-GUMF CONTROL ENDPOINTS ---
from flask import Blueprint, request, jsonify
antigumf_api = Blueprint('antigumf_api', __name__)

# Assume antigumf_plugin is initialized and available as antigumf
# You may need to adjust this depending on your app structure
antigumf = None  # Will be set in app factory/init

def get_antigumf():
    global antigumf
    if antigumf is None:
        from medusa.src.plugins.antigumf_plugin import AntiGumfPlugin
        antigumf = AntiGumfPlugin(db=db)
    return antigumf

@antigumf_api.route('/api/antigumf/status', methods=['GET'])
@login_required
@admin_required
def antigumf_status():
    ag = get_antigumf()
    return jsonify(ag.get_status())

@antigumf_api.route('/api/antigumf/enable', methods=['POST'])
@login_required
@admin_required
def antigumf_enable():
    ag = get_antigumf()
    data = request.get_json(force=True)
    stage = data.get('stage')  # e.g., 'deduplication', 'fuzzy', 'relevance', or None for all
    enabled = data.get('enabled', True)
    ag.set_enabled(stage, enabled)
    return jsonify({'status': 'ok', 'stage': stage, 'enabled': enabled})

@antigumf_api.route('/api/antigumf/pause', methods=['POST'])
@login_required
@admin_required
def antigumf_pause():
    ag = get_antigumf()
    data = request.get_json(force=True)
    stage = data.get('stage')
    paused = data.get('paused', True)
    ag.set_paused(stage, paused)
    return jsonify({'status': 'ok', 'stage': stage, 'paused': paused})

@antigumf_api.route('/api/antigumf/threshold', methods=['POST'])
@login_required
@admin_required
def antigumf_threshold():
    ag = get_antigumf()
    data = request.get_json(force=True)
    stage = data.get('stage')
    threshold = data.get('threshold')
    ag.set_threshold(stage, threshold)
    return jsonify({'status': 'ok', 'stage': stage, 'threshold': threshold})

@antigumf_api.route('/api/antigumf/reload', methods=['POST'])
@login_required
@admin_required
def antigumf_reload():
    ag = get_antigumf()
    ag.load_all()
    return jsonify({'status': 'ok', 'reloaded': True})

@antigumf_api.route('/api/antigumf/reprocess', methods=['POST'])
@login_required
@admin_required
def antigumf_reprocess():
    ag = get_antigumf()
    data = request.get_json(force=True)
    item_id = data.get('item_id')
    result = ag.reprocess_item(item_id)
    return jsonify({'status': 'ok', 'result': result})

@antigumf_api.route('/api/antigumf/audit', methods=['GET'])
@login_required
@admin_required
def antigumf_audit():
    ag = get_antigumf()
    logs = ag.get_audit_log()
    return jsonify({'status': 'ok', 'audit_log': logs})

@antigumf_api.route('/api/antigumf/config/import', methods=['POST'])
@login_required
@admin_required
def antigumf_config_import():
    ag = get_antigumf()
    data = request.get_json(force=True)
    result = ag.import_config(data)
    return jsonify(result)

# Register blueprint in app factory/init
# app.register_blueprint(antigumf_api)

def admin_required(f):
    # TEMP: Pass-through decorator for testing
    return f

# Register the AntiGumf API Blueprint after app creation
app.register_blueprint(antigumf_api)

@app.route('/admin/antigumf_control')
@login_required
@admin_required
def antigumf_control_panel():
    return render_template('admin/antigumf_control.html')

# --- Campaign Profiles API (AI/Command Ready) ---
campaigns_api = Blueprint('campaigns_api', __name__)

def get_db_conn():
    # Replace with your DB connection logic
    return Database().get_conn()

def get_orchestrator():
    # Replace with your orchestrator singleton/factory
    return ToolCrawlerOrchestrator(db_conn=get_db_conn(), socketio=socketio)

@campaigns_api.route('/api/campaigns', methods=['GET'])
def list_campaigns():
    """List all campaign profiles."""
    try:
        with get_db_conn().cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, name, description, is_active, profile_json, created_at, updated_at FROM campaign_profiles ORDER BY id ASC")
            rows = cur.fetchall()
        return jsonify({'campaigns': rows}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@campaigns_api.route('/api/campaigns', methods=['POST'])
def create_campaign():
    """Create a new campaign profile."""
    data = request.get_json(force=True)
    required = ['name', 'profile_json']
    for r in required:
        if r not in data:
            return jsonify({'error': f'Missing required field: {r}'}), 400
    try:
        with get_db_conn().cursor() as cur:
            cur.execute("""
                INSERT INTO campaign_profiles (name, description, profile_json, is_active)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (data['name'], data.get('description'), psycopg.types.json.Jsonb(data['profile_json']), data.get('is_active', False)))
            campaign_id = cur.fetchone()[0]
            get_db_conn().commit()
        return jsonify({'id': campaign_id}), 201
    except psycopg.errors.UniqueViolation:
        return jsonify({'error': 'Campaign name must be unique'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@campaigns_api.route('/api/campaigns/<int:campaign_id>', methods=['PUT'])
def update_campaign(campaign_id):
    """Update a campaign profile."""
    data = request.get_json(force=True)
    try:
        with get_db_conn().cursor() as cur:
            cur.execute("""
                UPDATE campaign_profiles SET name=%s, description=%s, profile_json=%s, updated_at=NOW()
                WHERE id=%s
            """, (data.get('name'), data.get('description'), psycopg.types.json.Jsonb(data['profile_json']), campaign_id))
            get_db_conn().commit()
        return jsonify({'status': 'updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@campaigns_api.route('/api/campaigns/<int:campaign_id>', methods=['DELETE'])
def delete_campaign(campaign_id):
    """Delete a campaign profile."""
    try:
        with get_db_conn().cursor() as cur:
            cur.execute("DELETE FROM campaign_profiles WHERE id=%s", (campaign_id,))
            get_db_conn().commit()
        return jsonify({'status': 'deleted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@campaigns_api.route('/api/campaigns/<int:campaign_id>/activate', methods=['POST'])
def activate_campaign(campaign_id):
    """Activate a campaign profile (deactivate others)."""
    command_source = request.json.get('command_source', 'human')
    try:
        with get_db_conn().cursor() as cur:
            cur.execute("UPDATE campaign_profiles SET is_active=FALSE WHERE is_active=TRUE")
            cur.execute("UPDATE campaign_profiles SET is_active=TRUE WHERE id=%s", (campaign_id,))
            get_db_conn().commit()
        # Reload orchestrator config
        orchestrator = get_orchestrator()
        orchestrator.reload_campaign_profile()
        # Log activation source
        logger.info(f"Campaign {campaign_id} activated by {command_source}")
        return jsonify({'status': 'activated', 'id': campaign_id}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Medusa AI Command Endpoint ---
@campaigns_api.route('/api/command', methods=['POST'])
def medusa_command():
    """AI/Command endpoint for campaign management and orchestrator control."""
    data = request.get_json(force=True)
    command = data.get('command')
    command_source = data.get('command_source', 'AI')
    if command == 'activate_campaign':
        campaign_id = data.get('campaign_id')
        if not campaign_id:
            return jsonify({'error': 'Missing campaign_id'}), 400
        # Activate campaign
        with get_db_conn().cursor() as cur:
            cur.execute("UPDATE campaign_profiles SET is_active=FALSE WHERE is_active=TRUE")
            cur.execute("UPDATE campaign_profiles SET is_active=TRUE WHERE id=%s", (campaign_id,))
            get_db_conn().commit()
        orchestrator = get_orchestrator()
        orchestrator.reload_campaign_profile()
        logger.info(f"AI Command: Campaign {campaign_id} activated by {command_source}")
        return jsonify({'status': 'activated', 'id': campaign_id}), 200
    elif command == 'list_campaigns':
        with get_db_conn().cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, name, description, is_active FROM campaign_profiles ORDER BY id ASC")
            rows = cur.fetchall()
        return jsonify({'campaigns': rows}), 200
    elif command == 'get_active_campaign':
        with get_db_conn().cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, name, description, is_active, profile_json FROM campaign_profiles WHERE is_active=TRUE LIMIT 1")
            row = cur.fetchone()
        return jsonify({'active_campaign': row}), 200
    else:
        return jsonify({'error': 'Unknown command'}), 400

# Register blueprint
app.register_blueprint(campaigns_api)

# --- Orchestrator integration for campaign profile reload ---
# Add a method to ToolCrawlerOrchestrator to reload campaign profile from DB
# (This should be implemented in orchestrator.py)

if __name__ == '__main__':
    main() 