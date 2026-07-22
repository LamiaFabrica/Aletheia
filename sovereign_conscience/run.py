#!/usr/bin/env python3
"""
Run script for Medusa web server.
"""

import os
import sys
import logging
from src.web_server import main

if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('medusa.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Ensure MEDUSA_KEY is set
    if not os.getenv('MEDUSA_KEY'):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        os.environ['MEDUSA_KEY'] = key
        logging.info("Generated new MEDUSA_KEY")
    
    # Start the server
    main() 