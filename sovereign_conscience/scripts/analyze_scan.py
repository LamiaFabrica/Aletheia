#!/usr/bin/env python3
"""
Command-line interface for Nmap scan analysis.
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.nmap_analyzer import NmapAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Analyze Nmap scan results')
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--xml', type=str, help='Path to Nmap XML file')
    input_group.add_argument('--target', type=str, help='Target to scan')
    
    # Scan options
    parser.add_argument('--ports', type=str, default=None,
                       help='Ports to scan (e.g., "1-1000" or "22,80,443")')
    parser.add_argument('--arguments', type=str, default="-sV -sS -O",
                       help='Nmap scan arguments')
    
    # Output options
    parser.add_argument('--output-dir', type=str, default="reports",
                       help='Directory for output reports')
    parser.add_argument('--no-report', action='store_true',
                       help='Skip report generation')
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    
    try:
        # Initialize analyzer
        analyzer = NmapAnalyzer()
        
        # Process scan
        if args.xml:
            logger.info(f"Analyzing Nmap XML file: {args.xml}")
            results = analyzer.analyze_scan(args.xml, not args.no_report)
        else:
            logger.info(f"Running Nmap scan on target: {args.target}")
            results = analyzer.run_scan(args.target, args.ports, args.arguments)
        
        # Print summary
        summary = results['summary']
        print("\nScan Analysis Summary:")
        print(f"Total Hosts: {summary['total_hosts']}")
        print(f"Total Ports: {summary['total_ports']}")
        print(f"Open Ports: {summary['open_ports']}")
        print(f"Anomalies Detected: {summary['anomalies']}")
        print(f"Average Risk Score: {summary['avg_risk_score']:.2f}")
        print(f"High Risk Ports: {summary['high_risk_ports']}")
        
        if not args.no_report:
            print(f"\nDetailed report generated in: {args.output_dir}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 