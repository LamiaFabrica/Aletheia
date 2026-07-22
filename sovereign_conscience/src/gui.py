#!/usr/bin/env python3
"""
GUI interface for Medusa project.
Provides an intuitive user interface for Nmap scan analysis.
"""

import os
import sys
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
from datetime import datetime
import webbrowser
from typing import Dict, List
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
import pandas as pd
import numpy as np

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from medusa.src.nmap_analyzer import NmapAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VisualizationTab(ttk.Frame):
    """Tab for displaying various visualizations of scan results."""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        # Create control panel
        self.control_frame = ttk.Frame(self)
        self.control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Chart type selection
        ttk.Label(self.control_frame, text="Chart Type:").pack(side=tk.LEFT, padx=5)
        self.chart_type = tk.StringVar(value="risk_distribution")
        chart_types = [
            ("Risk Distribution", "risk_distribution"),
            ("Service Distribution", "service_distribution"),
            ("Port Heatmap", "port_heatmap"),
            ("Risk by Service", "risk_by_service"),
            ("Anomaly Detection", "anomaly_detection"),
            ("Host Risk Comparison", "host_risk"),
            ("Version Analysis", "version_analysis"),
            ("Time Series", "time_series")
        ]
        self.chart_menu = ttk.OptionMenu(self.control_frame, self.chart_type,
                                       chart_types[0][1], *[t[1] for t in chart_types],
                                       command=self._update_chart)
        self.chart_menu.pack(side=tk.LEFT, padx=5)
        
        # Chart options
        self.options_frame = ttk.Frame(self)
        self.options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create figure and canvas
        self.figure = plt.Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Initialize empty data
        self.data = None
    
    def update_data(self, results: Dict):
        """Update visualization data."""
        self.data = results
        self._update_chart()
    
    def _update_chart(self, *args):
        """Update the current chart."""
        if not self.data:
            return
        
        self.figure.clear()
        
        # Get chart type
        chart_type = self.chart_type.get()
        
        # Create appropriate visualization
        if chart_type == "risk_distribution":
            self._plot_risk_distribution()
        elif chart_type == "service_distribution":
            self._plot_service_distribution()
        elif chart_type == "port_heatmap":
            self._plot_port_heatmap()
        elif chart_type == "risk_by_service":
            self._plot_risk_by_service()
        elif chart_type == "anomaly_detection":
            self._plot_anomaly_detection()
        elif chart_type == "host_risk":
            self._plot_host_risk()
        elif chart_type == "version_analysis":
            self._plot_version_analysis()
        elif chart_type == "time_series":
            self._plot_time_series()
        
        # Update canvas
        self.canvas.draw()
    
    def _plot_risk_distribution(self):
        """Plot distribution of risk scores."""
        ax = self.figure.add_subplot(111)
        
        # Collect risk scores
        risk_scores = []
        for host in self.data['scan_results']:
            for port in host['ports']:
                if 'risk_score' in port:
                    risk_scores.append(port['risk_score'])
        
        # Create histogram
        sns.histplot(risk_scores, bins=20, ax=ax)
        ax.set_title("Distribution of Risk Scores")
        ax.set_xlabel("Risk Score")
        ax.set_ylabel("Count")
    
    def _plot_service_distribution(self):
        """Plot distribution of services."""
        ax = self.figure.add_subplot(111)
        
        # Collect service counts
        services = {}
        for host in self.data['scan_results']:
            for port in host['ports']:
                service = port['service']
                services[service] = services.get(service, 0) + 1
        
        # Create bar plot
        services_df = pd.DataFrame(list(services.items()), columns=['Service', 'Count'])
        services_df = services_df.sort_values('Count', ascending=False)
        
        sns.barplot(data=services_df, x='Service', y='Count', ax=ax)
        ax.set_title("Service Distribution")
        ax.set_xlabel("Service")
        ax.set_ylabel("Count")
        plt.xticks(rotation=45, ha='right')
    
    def _plot_port_heatmap(self):
        """Plot port heatmap."""
        ax = self.figure.add_subplot(111)
        
        # Create port matrix
        ports = set()
        hosts = []
        for host in self.data['scan_results']:
            host_ports = set()
            for port in host['ports']:
                if port['state'] == 'open':
                    ports.add(port['port'])
                    host_ports.add(port['port'])
            hosts.append(host_ports)
        
        # Create heatmap data
        port_list = sorted(list(ports))
        heatmap_data = np.zeros((len(hosts), len(port_list)))
        
        for i, host_ports in enumerate(hosts):
            for j, port in enumerate(port_list):
                if port in host_ports:
                    heatmap_data[i, j] = 1
        
        # Plot heatmap
        sns.heatmap(heatmap_data, ax=ax, cmap='YlOrRd',
                   xticklabels=port_list, yticklabels=False)
        ax.set_title("Port Heatmap")
        ax.set_xlabel("Port")
    
    def _plot_risk_by_service(self):
        """Plot risk scores by service."""
        ax = self.figure.add_subplot(111)
        
        # Collect risk scores by service
        service_risks = {}
        for host in self.data['scan_results']:
            for port in host['ports']:
                if 'risk_score' in port:
                    service = port['service']
                    if service not in service_risks:
                        service_risks[service] = []
                    service_risks[service].append(port['risk_score'])
        
        # Create box plot
        data = []
        labels = []
        for service, risks in service_risks.items():
            data.append(risks)
            labels.append(service)
        
        ax.boxplot(data, labels=labels)
        ax.set_title("Risk Scores by Service")
        ax.set_xlabel("Service")
        ax.set_ylabel("Risk Score")
        plt.xticks(rotation=45, ha='right')
    
    def _plot_anomaly_detection(self):
        """Plot anomaly detection results."""
        ax = self.figure.add_subplot(111)
        
        # Collect anomaly scores
        normal_scores = []
        anomaly_scores = []
        for host in self.data['scan_results']:
            for port in host['ports']:
                if 'anomaly_score' in port:
                    if port.get('is_anomaly', False):
                        anomaly_scores.append(port['anomaly_score'])
                    else:
                        normal_scores.append(port['anomaly_score'])
        
        # Create scatter plot
        ax.scatter(range(len(normal_scores)), normal_scores,
                  label='Normal', alpha=0.5)
        ax.scatter(range(len(normal_scores),
                        len(normal_scores) + len(anomaly_scores)),
                  anomaly_scores, label='Anomaly', color='red', alpha=0.5)
        
        ax.set_title("Anomaly Detection Results")
        ax.set_xlabel("Port Index")
        ax.set_ylabel("Anomaly Score")
        ax.legend()
    
    def _plot_host_risk(self):
        """Plot risk comparison between hosts."""
        ax = self.figure.add_subplot(111)
        
        # Calculate average risk per host
        host_risks = []
        host_ips = []
        for host in self.data['scan_results']:
            risks = [p.get('risk_score', 0) for p in host['ports']]
            if risks:
                host_risks.append(sum(risks) / len(risks))
                host_ips.append(host['ip'])
        
        # Create bar plot
        ax.bar(range(len(host_risks)), host_risks)
        ax.set_title("Average Risk Score by Host")
        ax.set_xlabel("Host")
        ax.set_ylabel("Average Risk Score")
        ax.set_xticks(range(len(host_ips)))
        ax.set_xticklabels(host_ips, rotation=45, ha='right')
    
    def _plot_version_analysis(self):
        """Plot version analysis."""
        ax = self.figure.add_subplot(111)
        
        # Collect version information
        versions = {}
        for host in self.data['scan_results']:
            for port in host['ports']:
                if 'version' in port and port['version']:
                    service = port['service']
                    if service not in versions:
                        versions[service] = {}
                    version = port['version']
                    versions[service][version] = versions[service].get(version, 0) + 1
        
        # Create stacked bar plot
        services = list(versions.keys())
        version_counts = {}
        
        for service in services:
            for version, count in versions[service].items():
                if version not in version_counts:
                    version_counts[version] = [0] * len(services)
                version_counts[version][services.index(service)] = count
        
        bottom = np.zeros(len(services))
        for version, counts in version_counts.items():
            ax.bar(services, counts, bottom=bottom, label=version)
            bottom += counts
        
        ax.set_title("Version Distribution by Service")
        ax.set_xlabel("Service")
        ax.set_ylabel("Count")
        plt.xticks(rotation=45, ha='right')
        ax.legend()
    
    def _plot_time_series(self):
        """Plot time series of scan results."""
        ax = self.figure.add_subplot(111)
        
        # Simulate time series data (replace with actual data if available)
        times = pd.date_range(start='2024-01-01', periods=10, freq='D')
        risk_scores = np.random.normal(0.5, 0.1, 10)
        
        # Create line plot
        ax.plot(times, risk_scores, marker='o')
        ax.set_title("Risk Score Trend Over Time")
        ax.set_xlabel("Time")
        ax.set_ylabel("Average Risk Score")
        plt.xticks(rotation=45, ha='right')

class ResultsNotebook(ttk.Notebook):
    """Tabbed interface for displaying scan results."""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        # Create tabs
        self.summary_tab = ttk.Frame(self)
        self.hosts_tab = ttk.Frame(self)
        self.ports_tab = ttk.Frame(self)
        self.risks_tab = ttk.Frame(self)
        self.visualization_tab = VisualizationTab(self)
        
        self.add(self.summary_tab, text="Summary")
        self.add(self.hosts_tab, text="Hosts")
        self.add(self.ports_tab, text="Ports")
        self.add(self.risks_tab, text="Risks")
        self.add(self.visualization_tab, text="Visualizations")
        
        # Initialize tab contents
        self._init_summary_tab()
        self._init_hosts_tab()
        self._init_ports_tab()
        self._init_risks_tab()
    
    def _init_summary_tab(self):
        """Initialize summary tab with key metrics."""
        # Summary text
        self.summary_text = tk.Text(self.summary_tab, height=10, width=60, wrap=tk.WORD)
        self.summary_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.summary_tab, orient=tk.VERTICAL,
                                command=self.summary_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.summary_text['yscrollcommand'] = scrollbar.set
    
    def _init_hosts_tab(self):
        """Initialize hosts tab with host information."""
        # Create treeview for hosts
        columns = ('IP', 'Status', 'OS', 'Open Ports', 'Risk Score')
        self.hosts_tree = ttk.Treeview(self.hosts_tab, columns=columns, show='headings')
        
        # Configure columns
        for col in columns:
            self.hosts_tree.heading(col, text=col)
            self.hosts_tree.column(col, width=100)
        
        # Add scrollbars
        y_scroll = ttk.Scrollbar(self.hosts_tab, orient=tk.VERTICAL,
                               command=self.hosts_tree.yview)
        x_scroll = ttk.Scrollbar(self.hosts_tab, orient=tk.HORIZONTAL,
                               command=self.hosts_tree.xview)
        self.hosts_tree.configure(yscrollcommand=y_scroll.set,
                                xscrollcommand=x_scroll.set)
        
        # Pack widgets
        self.hosts_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _init_ports_tab(self):
        """Initialize ports tab with port information."""
        # Create treeview for ports
        columns = ('Host', 'Port', 'Service', 'State', 'Version', 'Risk')
        self.ports_tree = ttk.Treeview(self.ports_tab, columns=columns, show='headings')
        
        # Configure columns
        for col in columns:
            self.ports_tree.heading(col, text=col)
            self.ports_tree.column(col, width=100)
        
        # Add scrollbars
        y_scroll = ttk.Scrollbar(self.ports_tab, orient=tk.VERTICAL,
                               command=self.ports_tree.yview)
        x_scroll = ttk.Scrollbar(self.ports_tab, orient=tk.HORIZONTAL,
                               command=self.ports_tree.xview)
        self.ports_tree.configure(yscrollcommand=y_scroll.set,
                                xscrollcommand=x_scroll.set)
        
        # Pack widgets
        self.ports_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _init_risks_tab(self):
        """Initialize risks tab with risk information."""
        # Create treeview for risks
        columns = ('Host', 'Port', 'Service', 'Risk Score', 'Anomaly', 'Details')
        self.risks_tree = ttk.Treeview(self.risks_tab, columns=columns, show='headings')
        
        # Configure columns
        for col in columns:
            self.risks_tree.heading(col, text=col)
            self.risks_tree.column(col, width=100)
        
        # Add scrollbars
        y_scroll = ttk.Scrollbar(self.risks_tab, orient=tk.VERTICAL,
                               command=self.risks_tree.yview)
        x_scroll = ttk.Scrollbar(self.risks_tab, orient=tk.HORIZONTAL,
                               command=self.risks_tree.xview)
        self.risks_tree.configure(yscrollcommand=y_scroll.set,
                                xscrollcommand=x_scroll.set)
        
        # Pack widgets
        self.risks_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
    
    def update_results(self, results: Dict):
        """Update all tabs with scan results."""
        self._update_summary(results)
        self._update_hosts(results)
        self._update_ports(results)
        self._update_risks(results)
        self.visualization_tab.update_data(results)
    
    def _update_summary(self, results: Dict):
        """Update summary tab with key metrics."""
        summary = results['summary']
        
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(tk.END, "Scan Analysis Summary\n")
        self.summary_text.insert(tk.END, "=" * 50 + "\n\n")
        
        # General statistics
        self.summary_text.insert(tk.END, "General Statistics:\n")
        self.summary_text.insert(tk.END, f"• Total Hosts: {summary['total_hosts']}\n")
        self.summary_text.insert(tk.END, f"• Total Ports: {summary['total_ports']}\n")
        self.summary_text.insert(tk.END, f"• Open Ports: {summary['open_ports']}\n\n")
        
        # Risk assessment
        self.summary_text.insert(tk.END, "Risk Assessment:\n")
        self.summary_text.insert(tk.END, f"• Average Risk Score: {summary['avg_risk_score']:.2f}\n")
        self.summary_text.insert(tk.END, f"• High Risk Ports: {summary['high_risk_ports']}\n")
        self.summary_text.insert(tk.END, f"• Anomalies Detected: {summary['anomalies']}\n\n")
        
        # Service distribution
        self.summary_text.insert(tk.END, "Service Distribution:\n")
        for service, count in summary.get('service_distribution', {}).items():
            self.summary_text.insert(tk.END, f"• {service}: {count}\n")
    
    def _update_hosts(self, results: Dict):
        """Update hosts tab with host information."""
        # Clear existing items
        for item in self.hosts_tree.get_children():
            self.hosts_tree.delete(item)
        
        # Add host information
        for host in results['scan_results']:
            open_ports = len([p for p in host['ports'] if p['state'] == 'open'])
            avg_risk = sum(p.get('risk_score', 0) for p in host['ports']) / len(host['ports']) if host['ports'] else 0
            
            self.hosts_tree.insert('', tk.END, values=(
                host['ip'],
                host['status'],
                host.get('os', 'Unknown'),
                open_ports,
                f"{avg_risk:.2f}"
            ))
    
    def _update_ports(self, results: Dict):
        """Update ports tab with port information."""
        # Clear existing items
        for item in self.ports_tree.get_children():
            self.ports_tree.delete(item)
        
        # Add port information
        for host in results['scan_results']:
            for port in host['ports']:
                self.ports_tree.insert('', tk.END, values=(
                    host['ip'],
                    port['port'],
                    port['service'],
                    port['state'],
                    port.get('version', ''),
                    f"{port.get('risk_score', 0):.2f}"
                ))
    
    def _update_risks(self, results: Dict):
        """Update risks tab with risk information."""
        # Clear existing items
        for item in self.risks_tree.get_children():
            self.risks_tree.delete(item)
        
        # Add risk information
        for host in results['scan_results']:
            for port in host['ports']:
                if port.get('risk_score', 0) > 0.5 or port.get('is_anomaly', False):
                    risk_details = port.get('risk_details', {})
                    details = ", ".join(f"{k}: {v:.2f}" for k, v in risk_details.items())
                    
                    self.risks_tree.insert('', tk.END, values=(
                        host['ip'],
                        port['port'],
                        port['service'],
                        f"{port.get('risk_score', 0):.2f}",
                        "Yes" if port.get('is_anomaly', False) else "No",
                        details
                    ))

class MedusaGUI:
    """Main GUI window for Medusa."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Medusa - Security Analysis Tool")
        self.root.geometry("1000x800")
        
        # Initialize analyzer
        self.analyzer = NmapAnalyzer()
        
        # Create main container
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create widgets
        self._create_widgets()
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
    
    def _create_widgets(self):
        """Create and arrange GUI widgets."""
        # Target input
        ttk.Label(self.main_frame, text="Target:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.target_var = tk.StringVar()
        self.target_entry = ttk.Entry(self.main_frame, textvariable=self.target_var, width=40)
        self.target_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Port range input
        ttk.Label(self.main_frame, text="Ports:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.ports_var = tk.StringVar(value="1-1000")
        self.ports_entry = ttk.Entry(self.main_frame, textvariable=self.ports_var, width=40)
        self.ports_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Scan options
        ttk.Label(self.main_frame, text="Scan Options:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.options_frame = ttk.Frame(self.main_frame)
        self.options_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Service detection
        self.service_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.options_frame, text="Service Detection (-sV)",
                       variable=self.service_var).grid(row=0, column=0, sticky=tk.W)
        
        # OS detection
        self.os_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.options_frame, text="OS Detection (-O)",
                       variable=self.os_var).grid(row=0, column=1, sticky=tk.W)
        
        # XML file input
        ttk.Label(self.main_frame, text="Or load XML:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.xml_frame = ttk.Frame(self.main_frame)
        self.xml_frame.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)
        
        self.xml_var = tk.StringVar()
        self.xml_entry = ttk.Entry(self.xml_frame, textvariable=self.xml_var, width=30)
        self.xml_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.browse_btn = ttk.Button(self.xml_frame, text="Browse", command=self._browse_xml)
        self.browse_btn.grid(row=0, column=1, padx=5)
        
        # Action buttons
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        self.scan_btn = ttk.Button(self.button_frame, text="Run Scan",
                                 command=self._run_scan)
        self.scan_btn.grid(row=0, column=0, padx=5)
        
        self.analyze_btn = ttk.Button(self.button_frame, text="Analyze XML",
                                    command=self._analyze_xml)
        self.analyze_btn.grid(row=0, column=1, padx=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self.main_frame, length=300,
                                      mode='indeterminate',
                                      variable=self.progress_var)
        self.progress.grid(row=5, column=0, columnspan=2, pady=10)
        
        # Status label
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(self.main_frame, textvariable=self.status_var)
        self.status_label.grid(row=6, column=0, columnspan=2, pady=5)
        
        # Results notebook
        self.results_notebook = ResultsNotebook(self.main_frame)
        self.results_notebook.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # View report button
        self.report_btn = ttk.Button(self.main_frame, text="View Report",
                                   command=self._view_report, state=tk.DISABLED)
        self.report_btn.grid(row=8, column=0, columnspan=2, pady=10)
    
    def _browse_xml(self):
        """Open file dialog to select XML file."""
        filename = filedialog.askopenfilename(
            title="Select Nmap XML file",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
        if filename:
            self.xml_var.set(filename)
    
    def _get_scan_arguments(self) -> str:
        """Get Nmap scan arguments based on selected options."""
        args = []
        if self.service_var.get():
            args.append("-sV")
        if self.os_var.get():
            args.append("-O")
        return " ".join(args) if args else "-sV -sS -O"
    
    def _run_scan(self):
        """Run Nmap scan in a separate thread."""
        target = self.target_var.get().strip()
        if not target:
            messagebox.showerror("Error", "Please enter a target")
            return
        
        self._start_progress("Running scan...")
        
        def scan_thread():
            try:
                results = self.analyzer.run_scan(
                    target,
                    self.ports_var.get(),
                    self._get_scan_arguments()
                )
                self._show_results(results)
                self._stop_progress("Scan completed")
            except Exception as e:
                self._stop_progress(f"Error: {str(e)}")
                messagebox.showerror("Error", str(e))
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def _analyze_xml(self):
        """Analyze XML file in a separate thread."""
        xml_file = self.xml_var.get().strip()
        if not xml_file:
            messagebox.showerror("Error", "Please select an XML file")
            return
        
        self._start_progress("Analyzing scan results...")
        
        def analyze_thread():
            try:
                results = self.analyzer.analyze_scan(xml_file)
                self._show_results(results)
                self._stop_progress("Analysis completed")
            except Exception as e:
                self._stop_progress(f"Error: {str(e)}")
                messagebox.showerror("Error", str(e))
        
        threading.Thread(target=analyze_thread, daemon=True).start()
    
    def _show_results(self, results: Dict):
        """Display scan results in the notebook."""
        self.results_notebook.update_results(results)
        self.report_btn.config(state=tk.NORMAL)
    
    def _view_report(self):
        """Open the generated report in the default web browser."""
        report_dir = Path('reports') / datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / 'interactive_report.html'
        
        if report_file.exists():
            webbrowser.open(f'file://{report_file.absolute()}')
        else:
            messagebox.showinfo("Info", "No report available yet")
    
    def _start_progress(self, message: str):
        """Start progress bar and update status."""
        self.progress.start()
        self.status_var.set(message)
        self.scan_btn.config(state=tk.DISABLED)
        self.analyze_btn.config(state=tk.DISABLED)
    
    def _stop_progress(self, message: str):
        """Stop progress bar and update status."""
        self.progress.stop()
        self.status_var.set(message)
        self.scan_btn.config(state=tk.NORMAL)
        self.analyze_btn.config(state=tk.NORMAL)
    
    def run(self):
        """Start the GUI main loop."""
        self.root.mainloop()

def main():
    """Main function."""
    app = MedusaGUI()
    app.run()

if __name__ == "__main__":
    main() 