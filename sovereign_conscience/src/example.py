"""
Example script demonstrating how to use the Nmap XML Analyzer.
"""

import os
from nmap_analyzer import NmapAnalyzer
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def display_risk_summary(summary: dict):
    """Display risk summary in a formatted way."""
    logger.info("\nRisk Summary:")
    logger.info("=" * 50)
    logger.info(f"Total Hosts Scanned: {summary['total_hosts']}")
    logger.info(f"Total Ports Found: {summary['total_ports']}")
    logger.info(f"High Risk Ports: {summary['high_risk_ports']}")
    logger.info(f"Average Risk Score: {summary['average_risk_score']:.2f}")

def display_high_risk_findings(df: pd.DataFrame):
    """Display high-risk findings in a formatted way."""
    high_risk = df[df['risk_score'] >= 0.7]
    if not high_risk.empty:
        logger.info("\nHigh Risk Findings:")
        logger.info("=" * 50)
        for _, row in high_risk.iterrows():
            logger.info(f"IP: {row['ip']}")
            logger.info(f"Port: {row['port']}/{row['protocol']}")
            logger.info(f"Service: {row['service']}")
            if row['version']:
                logger.info(f"Version: {row['version']}")
            logger.info(f"Risk Score: {row['risk_score']:.2f}")
            logger.info("-" * 30)

def main():
    # Initialize the analyzer
    analyzer = NmapAnalyzer()
    
    # Example Nmap XML file path
    xml_file = "data/sample_scan.xml"
    
    try:
        # Analyze the scan
        logger.info(f"Analyzing Nmap scan from {xml_file}")
        results_df = analyzer.analyze_scan(xml_file)
        
        # Get risk summary
        risk_summary = analyzer.get_risk_summary(results_df)
        display_risk_summary(risk_summary)
        
        # Display high-risk findings
        display_high_risk_findings(results_df)
        
        # Display all results
        logger.info("\nAll Scan Results:")
        logger.info("=" * 50)
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        print(results_df.to_string())
        
    except FileNotFoundError:
        logger.error(f"Error: Nmap XML file not found at {xml_file}")
        logger.info("Please run an Nmap scan with XML output (-oX) and place the file in the data directory.")
    except Exception as e:
        logger.error(f"Error analyzing scan: {e}")

if __name__ == "__main__":
    main() 