#!/usr/bin/env python3
"""
Script to run the Medusa GUI interface.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.gui import MedusaGUI

def main():
    """Run the Medusa GUI."""
    app = MedusaGUI()
    app.run()

if __name__ == "__main__":
    main() 