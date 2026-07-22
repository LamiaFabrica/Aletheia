#!/usr/bin/env python3
"""
Nmap analyzer module for Medusa project.
Processes Nmap scan results and integrates with AI models for analysis.
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
import json
from pathlib import Path
import nmap
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from medusa.src.ai_models import AIModelManager
from medusa.src.database import Database
from medusa.src.visualization import ScanVisualizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NmapAnalyzer:
    """Analyzes Nmap scan results using AI models."""
    
    def __init__(self, model_dir: str = "models", db_path: str = "medusa.db"):
        self.ai_manager = AIModelManager(model_dir)
        self.db_manager = Database()
        self.visualizer = ScanVisualizer()
    
    def parse_nmap_xml(self, xml_file: str) -> List[Dict]:
        """Parse Nmap XML output file."""
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            scan_results = []
            for host in root.findall('host'):
                host_data = {
                    'ip': host.find('address').get('addr'),
                    'mac': host.find('address').get('addrtype') == 'mac' and host.find('address').get('addr'),
                    'status': host.find('status').get('state'),
                    'ports': []
                }
                
                for port in host.findall('.//port'):
                    port_data = {
                        'port': int(port.get('portid')),
                        'protocol': port.get('protocol'),
                        'state': port.find('state').get('state'),
                        'service': port.find('service').get('name') if port.find('service') is not None else 'unknown',
                        'version': port.find('service').get('version') if port.find('service') is not None else '',
                        'product': port.find('service').get('product') if port.find('service') is not None else ''
                    }
                    host_data['ports'].append(port_data)
                
                scan_results.append(host_data)
            
            return scan_results
            
        except Exception as e:
            logger.error(f"Error parsing Nmap XML: {e}")
            raise
    
    def analyze_scan(self, xml_file: str, generate_report: bool = True) -> Dict:
        """Analyze Nmap scan results using AI models."""
        # Parse scan results
        scan_results = self.parse_nmap_xml(xml_file)
        
        # Analyze each port
        for host in scan_results:
            for port in host['ports']:
                # Predict risk score
                risk_score = self.ai_manager.predict_risk(port)
                port['risk_score'] = risk_score
                
                # Detect anomalies
                is_anomaly, anomaly_score = self.ai_manager.detect_anomaly(port)
                port['is_anomaly'] = is_anomaly
                port['anomaly_score'] = anomaly_score
                
                # Add risk details
                port['risk_details'] = {
                    'service_risk': self._get_service_risk(port['service']),
                    'port_risk': self._get_port_risk(port['port']),
                    'version_risk': self._get_version_risk(port['version'])
                }
        
        # Save results to database
        self.db_manager.add_scan_result({
            'target': xml_file,
            'total_hosts': len(scan_results),
            'total_ports': sum(len(host['ports']) for host in scan_results),
            'high_risk_ports': sum(1 for host in scan_results 
                                 for port in host['ports']
                                 if port['risk_score'] > 0.7),
            'average_risk_score': sum(port['risk_score'] for host in scan_results 
                                    for port in host['ports']) / 
                                sum(len(host['ports']) for host in scan_results),
            'hosts': scan_results
        })
        
        # Generate report if requested
        if generate_report:
            report_dir = Path('reports') / datetime.now().strftime("%Y%m%d_%H%M%S")
            report_dir.mkdir(parents=True, exist_ok=True)
            
            self.visualizer.save_summary_report(
                scan_results,
                str(report_dir / 'summary.json')
            )
        
        return {
            'scan_results': scan_results,
            'summary': self.visualizer.generate_summary_stats(scan_results)
        }
    
    def _get_service_risk(self, service: str) -> float:
        """Get base risk score for a service."""
        high_risk_services = {
            'ftp': 0.8, 'telnet': 0.9, 'smtp': 0.7,
            'http': 0.6, 'https': 0.5, 'ssh': 0.4,
            'rdp': 0.8, 'vnc': 0.8, 'mysql': 0.7,
            'postgresql': 0.7, 'mongodb': 0.7,
            'redis': 0.7, 'elasticsearch': 0.7
        }
        return high_risk_services.get(service.lower(), 0.3)
    
    def _get_port_risk(self, port: int) -> float:
        """Get base risk score for a port."""
        high_risk_ports = {
            21: 0.8, 22: 0.4, 23: 0.9, 25: 0.7,
            80: 0.6, 443: 0.5, 3306: 0.7, 3389: 0.8,
            5432: 0.7, 27017: 0.7, 6379: 0.7, 9200: 0.7
        }
        return high_risk_ports.get(port, 0.3)
    
    def _get_version_risk(self, version: str) -> float:
        """Get risk score based on version information."""
        if not version:
            return 0.5  # Unknown version is medium risk
        
        # Check for old versions
        old_versions = ['1.0', '2.0', '3.0', '4.0', '5.0']
        if any(v in version for v in old_versions):
            return 0.8
        
        # Check for development versions
        if any(x in version.lower() for x in ['dev', 'alpha', 'beta', 'rc']):
            return 0.7
        
        return 0.4  # Default risk for known recent versions
    
    def run_scan(self, target: str, ports: str = None, 
                arguments: str = "-sV -sS -O") -> Dict:
        """Run Nmap scan and analyze results."""
        try:
            # Initialize Nmap scanner
            scanner = nmap.PortScanner()
            
            # Run scan
            logger.info(f"Running Nmap scan on {target}")
            scanner.scan(target, ports, arguments)
            
            # Save raw XML output
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            xml_file = f"scans/scan_{timestamp}.xml"
            Path('scans').mkdir(exist_ok=True)
            
            with open(xml_file, 'w') as f:
                f.write(scanner.get_nmap_last_output())
            
            # Analyze results
            return self.analyze_scan(xml_file)
            
        except Exception as e:
            logger.error(f"Error running Nmap scan: {e}")
            raise 