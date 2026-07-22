"""
Companion script for Medusa project.
Provides CLI interface for interacting with scan results and database.
"""

import argparse
import logging
from datetime import datetime
from typing import Optional
from database import Database
from nmap_analyzer import NmapAnalyzer
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def format_timestamp(timestamp: datetime) -> str:
    """Format timestamp for display."""
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def display_scan_summary(scan):
    """Display summary of a scan."""
    logger.info("\nScan Summary:")
    logger.info("=" * 50)
    logger.info(f"Scan ID: {scan.id}")
    logger.info(f"Date: {format_timestamp(scan.scan_date)}")
    logger.info(f"Target: {scan.target}")
    logger.info(f"Total Hosts: {scan.total_hosts}")
    logger.info(f"Total Ports: {scan.total_ports}")
    logger.info(f"High Risk Ports: {scan.high_risk_ports}")
    logger.info(f"Average Risk Score: {scan.average_risk_score:.2f}")

def display_high_risk_findings(ports):
    """Display high-risk port findings."""
    if not ports:
        logger.info("\nNo high-risk ports found.")
        return

    logger.info("\nHigh Risk Findings:")
    logger.info("=" * 50)
    for port in ports:
        logger.info(f"Host: {port.host.ip}")
        logger.info(f"Port: {port.port}/{port.protocol}")
        logger.info(f"Service: {port.service}")
        if port.version:
            logger.info(f"Version: {port.version}")
        logger.info(f"Risk Score: {port.risk_score:.2f}")
        logger.info("-" * 30)

def list_recent_scans(db_manager: Database, limit: int = 10):
    """List recent scans."""
    scans = db_manager.get_recent_scans(limit)
    if not scans:
        logger.info("No scans found in database.")
        return

    logger.info("\nRecent Scans:")
    logger.info("=" * 50)
    for scan in scans:
        logger.info(f"ID: {scan.id} | Date: {format_timestamp(scan.scan_date)} | Target: {scan.target}")

def analyze_new_scan(xml_file: str, target: Optional[str] = None):
    """Analyze a new Nmap scan and save results."""
    try:
        analyzer = NmapAnalyzer()
        results_df = analyzer.analyze_scan(xml_file, target)
        
        # Display results
        logger.info("\nAnalysis Results:")
        logger.info("=" * 50)
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        print(results_df.to_string())
        
    except Exception as e:
        logger.error(f"Error analyzing scan: {e}")

def main():
    parser = argparse.ArgumentParser(description="Medusa Companion - Nmap Analysis Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List scans command
    list_parser = subparsers.add_parser("list", help="List recent scans")
    list_parser.add_argument("--limit", type=int, default=10, help="Number of scans to list")

    # Show scan command
    show_parser = subparsers.add_parser("show", help="Show scan details")
    show_parser.add_argument("scan_id", type=int, help="ID of the scan to show")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a new Nmap scan")
    analyze_parser.add_argument("xml_file", help="Path to Nmap XML output file")
    analyze_parser.add_argument("--target", help="Target that was scanned")

    args = parser.parse_args()
    db_manager = Database()

    try:
        if args.command == "list":
            list_recent_scans(db_manager, args.limit)
        elif args.command == "show":
            scan = db_manager.get_scan(args.scan_id)
            if scan:
                display_scan_summary(scan)
                high_risk_ports = db_manager.get_high_risk_ports(args.scan_id)
                display_high_risk_findings(high_risk_ports)
            else:
                logger.error(f"Scan with ID {args.scan_id} not found")
        elif args.command == "analyze":
            analyze_new_scan(args.xml_file, args.target)
        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        del db_manager

if __name__ == "__main__":
    main() 