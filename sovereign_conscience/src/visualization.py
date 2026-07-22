#!/usr/bin/env python3
"""
Visualization module for Medusa project.
Provides tools for analyzing and visualizing scan results and risk assessments.
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import json
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScanVisualizer:
    """Visualizes scan results and risk assessments."""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Set style for plots
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
    
    def plot_risk_distribution(self, scan_results: List[Dict], save_path: Optional[str] = None):
        """Plot distribution of risk scores."""
        risk_scores = [port.get('risk_score', 0) for host in scan_results 
                      for port in host.get('ports', [])]
        
        plt.figure(figsize=(10, 6))
        sns.histplot(risk_scores, bins=20, kde=True)
        plt.title('Distribution of Risk Scores')
        plt.xlabel('Risk Score')
        plt.ylabel('Count')
        
        if save_path:
            plt.savefig(save_path)
            plt.close()
        else:
            plt.show()
    
    def plot_service_risks(self, scan_results: List[Dict], save_path: Optional[str] = None):
        """Plot risk scores by service."""
        service_risks = {}
        for host in scan_results:
            for port in host.get('ports', []):
                service = port.get('service', 'unknown')
                risk = port.get('risk_score', 0)
                if service not in service_risks:
                    service_risks[service] = []
                service_risks[service].append(risk)
        
        # Calculate mean risk for each service
        service_means = {service: np.mean(risks) for service, risks in service_risks.items()}
        services = list(service_means.keys())
        means = list(service_means.values())
        
        plt.figure(figsize=(12, 6))
        sns.barplot(x=services, y=means)
        plt.title('Average Risk Score by Service')
        plt.xlabel('Service')
        plt.ylabel('Average Risk Score')
        plt.xticks(rotation=45, ha='right')
        
        if save_path:
            plt.savefig(save_path, bbox_inches='tight')
            plt.close()
        else:
            plt.show()
    
    def plot_anomaly_detection(self, scan_results: List[Dict], save_path: Optional[str] = None):
        """Plot anomaly detection results."""
        anomalies = []
        normal = []
        
        for host in scan_results:
            for port in host.get('ports', []):
                if port.get('is_anomaly', False):
                    anomalies.append(port)
                else:
                    normal.append(port)
        
        plt.figure(figsize=(10, 6))
        plt.scatter([p.get('port', 0) for p in normal],
                   [p.get('risk_score', 0) for p in normal],
                   label='Normal', alpha=0.6)
        plt.scatter([p.get('port', 0) for p in anomalies],
                   [p.get('risk_score', 0) for p in anomalies],
                   label='Anomaly', color='red', marker='x')
        
        plt.title('Port Anomaly Detection')
        plt.xlabel('Port Number')
        plt.ylabel('Risk Score')
        plt.legend()
        
        if save_path:
            plt.savefig(save_path)
            plt.close()
        else:
            plt.show()
    
    def generate_html_report(self, scan_results: List[Dict], output_file: str):
        """Generate interactive HTML report with Plotly."""
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Risk Score Distribution', 'Service Risk Analysis',
                          'Anomaly Detection', 'Top Risk Ports')
        )
        
        # Risk distribution
        risk_scores = [port.get('risk_score', 0) for host in scan_results 
                      for port in host.get('ports', [])]
        fig.add_trace(
            go.Histogram(x=risk_scores, name='Risk Distribution'),
            row=1, col=1
        )
        
        # Service risks
        service_risks = {}
        for host in scan_results:
            for port in host.get('ports', []):
                service = port.get('service', 'unknown')
                risk = port.get('risk_score', 0)
                if service not in service_risks:
                    service_risks[service] = []
                service_risks[service].append(risk)
        
        service_means = {service: np.mean(risks) for service, risks in service_risks.items()}
        fig.add_trace(
            go.Bar(x=list(service_means.keys()), y=list(service_means.values()),
                  name='Service Risks'),
            row=1, col=2
        )
        
        # Anomaly detection
        anomalies = []
        normal = []
        for host in scan_results:
            for port in host.get('ports', []):
                if port.get('is_anomaly', False):
                    anomalies.append(port)
                else:
                    normal.append(port)
        
        fig.add_trace(
            go.Scatter(x=[p.get('port', 0) for p in normal],
                      y=[p.get('risk_score', 0) for p in normal],
                      mode='markers', name='Normal'),
            row=2, col=1
        )
        fig.add_trace(
            go.Scatter(x=[p.get('port', 0) for p in anomalies],
                      y=[p.get('risk_score', 0) for p in anomalies],
                      mode='markers', name='Anomaly',
                      marker=dict(color='red', symbol='x')),
            row=2, col=1
        )
        
        # Top risk ports
        all_ports = []
        for host in scan_results:
            for port in host.get('ports', []):
                all_ports.append({
                    'port': port.get('port', 0),
                    'service': port.get('service', 'unknown'),
                    'risk': port.get('risk_score', 0)
                })
        
        top_ports = sorted(all_ports, key=lambda x: x['risk'], reverse=True)[:10]
        fig.add_trace(
            go.Bar(x=[f"{p['port']} ({p['service']})" for p in top_ports],
                  y=[p['risk'] for p in top_ports],
                  name='Top Risk Ports'),
            row=2, col=2
        )
        
        # Update layout
        fig.update_layout(
            height=1000,
            width=1200,
            title_text="Scan Analysis Report",
            showlegend=True
        )
        
        # Save as HTML
        fig.write_html(output_file)
        logger.info(f"Generated HTML report: {output_file}")
    
    def generate_summary_stats(self, scan_results: List[Dict]) -> Dict:
        """Generate summary statistics for scan results."""
        stats = {
            'total_hosts': len(scan_results),
            'total_ports': sum(len(host.get('ports', [])) for host in scan_results),
            'open_ports': sum(1 for host in scan_results 
                            for port in host.get('ports', [])
                            if port.get('state') == 'open'),
            'anomalies': sum(1 for host in scan_results 
                           for port in host.get('ports', [])
                           if port.get('is_anomaly', False)),
            'avg_risk_score': np.mean([port.get('risk_score', 0) for host in scan_results 
                                     for port in host.get('ports', [])]),
            'high_risk_ports': sum(1 for host in scan_results 
                                 for port in host.get('ports', [])
                                 if port.get('risk_score', 0) > 0.7)
        }
        
        return stats
    
    def save_summary_report(self, scan_results: List[Dict], output_file: str):
        """Save summary report with statistics and visualizations."""
        # Generate statistics
        stats = self.generate_summary_stats(scan_results)
        
        # Create report directory
        report_dir = Path(output_file).parent
        report_dir.mkdir(exist_ok=True)
        
        # Generate visualizations
        self.plot_risk_distribution(scan_results, 
                                  save_path=str(report_dir / 'risk_distribution.png'))
        self.plot_service_risks(scan_results, 
                               save_path=str(report_dir / 'service_risks.png'))
        self.plot_anomaly_detection(scan_results, 
                                  save_path=str(report_dir / 'anomalies.png'))
        
        # Generate HTML report
        self.generate_html_report(scan_results, 
                                str(report_dir / 'interactive_report.html'))
        
        # Save statistics
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'statistics': stats,
                'visualizations': {
                    'risk_distribution': 'risk_distribution.png',
                    'service_risks': 'service_risks.png',
                    'anomalies': 'anomalies.png',
                    'interactive_report': 'interactive_report.html'
                }
            }, f, indent=2)
        
        logger.info(f"Generated summary report: {output_file}") 