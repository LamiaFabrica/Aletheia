#!/usr/bin/env python3
"""
Database module for Medusa project.
Manages the knowledge base and scan results storage using a local flat-file JSON backend.
"""

import os
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from cryptography.fernet import Fernet, InvalidToken

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        """Initialize the local flat-file database."""
        # Setup local data directory
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.fernet = None
        self._initialize()
    
    def _initialize(self):
        """Initialize database encryption."""
        key = os.getenv('MEDUSA_KEY')
        if not key:
            key = Fernet.generate_key()
            os.environ['MEDUSA_KEY'] = key.decode()
            logger.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            logger.warning("! MEDUSA_KEY not found in environment. A new EPIC encryption key has been generated. !")
            logger.warning("! This key is process-local and will be lost on application restart.                 !")
            logger.warning("! PREVIOUSLY ENCRYPTED DATA WILL BE UNDECRYPTABLE IF THE APP RESTARTS.               !")
            logger.warning(f"! Set MEDUSA_KEY in your environment or a .env file: MEDUSA_KEY='{key.decode()}'      !")
            logger.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        self.fernet = Fernet(key if isinstance(key, bytes) else key.encode())

    # --- Flat File Helpers ---
    def _read_table(self, table_name: str) -> List[Dict]:
        """Read a JSON array from disk."""
        filepath = os.path.join(self.data_dir, f"{table_name}.json")
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

    def _write_table(self, table_name: str, data: List[Dict]):
        """Write a JSON array to disk."""
        filepath = os.path.join(self.data_dir, f"{table_name}.json")
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

    def _encrypt(self, data: str) -> str:
        """Encrypt data using Fernet."""
        return self.fernet.encrypt(data.encode()).decode()

    def _decrypt(self, data: str) -> str:
        """Decrypt data using Fernet."""
        return self.fernet.decrypt(data.encode()).decode()

    # --- Knowledge Base ---
    def add_knowledge(self, knowledge: Dict) -> None:
        """Add a knowledge entry to the flat-file database."""
        table = self._read_table('knowledge')
        
        # Encrypt sensitive data
        encrypted_content = self._encrypt(knowledge['content'])
        
        entry = {
            'id': str(uuid.uuid4()),
            'title': knowledge.get('title', ''),
            'content': encrypted_content,
            'source': knowledge.get('source', ''),
            'type': knowledge.get('type', ''),
            'timestamp': knowledge.get('timestamp', datetime.now().isoformat()),
            'encrypted': True
        }
        
        table.append(entry)
        self._write_table('knowledge', table)

    def get_knowledge(self, category=None):
        """Fetch knowledge entries, optionally filtered by category."""
        table = self._read_table('knowledge')
        if category:
            table = [entry for entry in table if entry.get('type') == category]
            
        # Sort by timestamp desc
        table.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        entries = []
        for entry in table:
            # Decrypt if needed
            if entry.get('encrypted'):
                try:
                    entry['content'] = self._decrypt(entry['content'])
                except Exception:
                    entry['content'] = '[Content unavailable]'
            
            entry['url'] = entry.get('url') or entry.get('source') or ''
            entry.pop('encrypted', None)
            entries.append(entry)
            
        return entries

    # --- Scans ---
    def add_scan_result(self, scan: Dict) -> str:
        """Add a scan result to the flat-file database."""
        table = self._read_table('scan_results')
        
        results_str = json.dumps(scan.get('results', {})) if scan.get('results') else None
        encrypted_results = self._encrypt(results_str) if results_str else None
        
        scan_id = str(uuid.uuid4())
        entry = {
            'id': scan_id,
            'target': scan.get('target', ''),
            'scan_type': scan.get('scan_type', ''),
            'ports': scan.get('ports'),
            'status': scan.get('status', ''),
            'start_time': scan.get('start_time', datetime.now().isoformat()),
            'end_time': scan.get('end_time'),
            'results': encrypted_results,
            'encrypted': bool(encrypted_results)
        }
        
        table.append(entry)
        self._write_table('scan_results', table)
        return scan_id

    def get_scan_results(self) -> List[Dict]:
        """Get all scan results from the database."""
        table = self._read_table('scan_results')
        
        results = []
        for scan in table:
            if scan.get('encrypted') and scan.get('results'):
                try:
                    scan['results'] = json.loads(self._decrypt(scan['results']))
                except InvalidToken:
                    scan['results'] = {"error": "[DECRYPTION ERROR - INVALID TOKEN]"}
                except Exception:
                    scan['results'] = {"error": "[DECRYPTION ERROR - UNKNOWN]"}
            results.append(scan)
            
        return results

    def delete_scan(self, scan_id: str) -> None:
        """Delete a scan result from the database."""
        table = self._read_table('scan_results')
        table = [scan for scan in table if scan.get('id') != scan_id]
        self._write_table('scan_results', table)

    # --- Training History ---
    def add_training_record(self, training: Dict) -> str:
        table = self._read_table('training_history')
        encrypted_data = self._encrypt(training.get('training_data', ''))
        
        record_id = str(uuid.uuid4())
        record = {
            'id': record_id,
            'model_type': training.get('model_type', ''),
            'training_data': encrypted_data,
            'start_date': training.get('start_date'),
            'end_date': training.get('end_date'),
            'status': training.get('status', ''),
            'start_time': training.get('start_time', datetime.now().isoformat()),
            'end_time': training.get('end_time'),
            'accuracy': training.get('accuracy'),
            'encrypted': True
        }
        
        table.append(record)
        self._write_table('training_history', table)
        return record_id

    def get_training_history(self) -> List[Dict]:
        table = self._read_table('training_history')
        history = []
        for record in table:
            if record.get('encrypted'):
                try:
                    record['training_data'] = self._decrypt(record['training_data'])
                except Exception:
                    record['training_data'] = '[DECRYPTION ERROR]'
            history.append(record)
        return history

    def delete_model(self, model_id: str) -> None:
        table = self._read_table('training_history')
        table = [record for record in table if record.get('id') != model_id]
        self._write_table('training_history', table)

    # --- Analytics & Dashboard Aggregations (Mocked for flat file) ---
    def get_risk_distribution(self) -> Dict:
        table = self._read_table('scan_results')
        dist = {}
        for scan in table:
            status = scan.get('status')
            dist[status] = dist.get(status, 0) + 1
        return dist

    def get_port_usage(self) -> Dict:
        table = self._read_table('scan_results')
        dist = {}
        for scan in table:
            ports = scan.get('ports')
            if ports:
                dist[ports] = dist.get(ports, 0) + 1
        return dist

    def get_vulnerability_trends(self) -> Dict:
        return {}

    def get_service_distribution(self) -> Dict:
        table = self._read_table('scan_results')
        dist = {}
        for scan in table:
            stype = scan.get('scan_type')
            if stype:
                dist[stype] = dist.get(stype, 0) + 1
        return dist

    def get_risk_score_timeline(self) -> Dict:
        return {}

    # --- Settings ---
    def update_settings(self, settings: Dict) -> None:
        table = self._read_table('settings')
        
        # Convert list of dicts to dict for easy update
        settings_dict = {item['key']: item for item in table}
        
        for key, value in settings.items():
            encrypted_value = self._encrypt(str(value))
            settings_dict[key] = {
                'key': key,
                'value': encrypted_value,
                'encrypted': True
            }
            
        self._write_table('settings', list(settings_dict.values()))

    def get_settings(self) -> Dict:
        table = self._read_table('settings')
        settings = {}
        for row in table:
            if row.get('encrypted'):
                try:
                    settings[row['key']] = self._decrypt(row['value'])
                except Exception:
                    settings[row['key']] = '[DECRYPTION ERROR]'
            else:
                settings[row['key']] = row.get('value')
        return settings

    # --- Server Connectivity ---
    def is_connected(self) -> bool:
        """Always return true for local file storage."""
        return True

    def close(self):
        pass
    
    def reconnect(self):
        pass

    # --- Crawler API Stubs ---
    def get_tools(self, limit=5):
        return []

    def ensure_urls_scraped_table(self):
        pass

    def url_scraped_recently(self, url, days=1):
        return False

    def domain_scrape_count_today(self, domain):
        return 0

    def insert_scraped_url(self, url, crawl_id, status, data_size, error_message=None, content=None):
        pass

    def update_scraped_url(self, url, status=None, data_size=None, error_message=None, content=None):
        pass

    def get_ollama_language(self):
        return self.get_settings().get('ollama_language', 'en')

    def set_ollama_language(self, lang):
        self.update_settings({'ollama_language': lang})

    def get_ollama_model(self):
        return self.get_settings().get('ollama_model', '')