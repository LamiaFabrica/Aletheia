import os
import sys
import json
import logging
from datetime import datetime

# Ensure medusa package is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INPUT_FILE = 'kali_core_tools_knowledge.json'

def main():
    db = Database()
    if not os.path.exists(INPUT_FILE):
        logger.error(f"Input file {INPUT_FILE} not found.")
        return
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    imported = 0
    skipped = 0
    for entry in data:
        # Prepare knowledge entry for DB
        knowledge = {
            'title': entry.get('tool_name', entry.get('title', 'Untitled')),
            'content': entry.get('description', entry.get('content', '')),
            'source': entry.get('source_url', entry.get('source', 'unknown')),
            'type': 'tool_usage',
            'timestamp': entry.get('date_crawled', datetime.utcnow().isoformat())
        }
        # Check for duplicate (by title+source)
        existing = [k for k in db.get_knowledge('tool_usage') if k['title'] == knowledge['title'] and k['source'] == knowledge['source']]
        if existing:
            skipped += 1
            continue
        try:
            db.add_knowledge(knowledge)
            imported += 1
        except Exception as e:
            logger.error(f"Failed to import {knowledge['title']}: {e}")
            skipped += 1
    logger.info(f"Import complete. Imported: {imported}, Skipped: {skipped}")

if __name__ == "__main__":
    main() 