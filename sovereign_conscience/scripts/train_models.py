#!/usr/bin/env python3
"""
Training script for Medusa AI models.
Trains risk assessment and anomaly detection models using historical scan data.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict
import argparse
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nmap_analyzer import NmapAnalyzer
from src.visualization import ScanVisualizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_training_data(data_dir: str) -> List[Dict]:
    """Load historical scan data from JSON files."""
    training_data = []
    
    for filename in os.listdir(data_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(data_dir, filename)
            try:
                with open(file_path, 'r') as f:
                    scan_data = json.load(f)
                    training_data.append(scan_data)
                logger.info(f"Loaded {filename}")
            except Exception as e:
                logger.error(f"Error loading {filename}: {str(e)}")
    
    return training_data

def main():
    parser = argparse.ArgumentParser(description='Train Medusa AI models')
    parser.add_argument('--data-dir', type=str, required=True,
                      help='Directory containing historical scan data')
    parser.add_argument('--epochs', type=int, default=100,
                      help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=32,
                      help='Training batch size')
    parser.add_argument('--output-dir', type=str, default='models',
                      help='Directory to save trained models')
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    try:
        # Load training data
        logger.info(f"Loading training data from {args.data_dir}")
        training_data = load_training_data(args.data_dir)
        
        if not training_data:
            logger.error("No training data found!")
            sys.exit(1)
        
        logger.info(f"Loaded {len(training_data)} scan results")
        
        # Initialize analyzer and train models
        analyzer = NmapAnalyzer()
        
        logger.info("Starting model training...")
        analyzer.train_models(training_data, epochs=args.epochs)
        
        # Generate training report
        logger.info("Generating training report...")
        visualizer = ScanVisualizer(output_dir=os.path.join(args.output_dir, 'training_reports'))
        
        # Create a combined dataset for visualization
        combined_data = {
            'scan_date': datetime.now().isoformat(),
            'total_hosts': sum(len(scan['hosts']) for scan in training_data),
            'total_ports': sum(
                len(port)
                for scan in training_data
                for host in scan['hosts']
                for port in host['ports']
            ),
            'high_risk_ports': sum(
                1
                for scan in training_data
                for host in scan['hosts']
                for port in host['ports']
                if port.get('risk_score', 0) > 0.7
            ),
            'hosts': [
                host
                for scan in training_data
                for host in scan['hosts']
            ]
        }
        
        report_path = visualizer.generate_summary_report(combined_data)
        logger.info(f"Training report generated: {report_path}")
        
        logger.info("Training completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during training: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main() 