#!/usr/bin/env python3
"""
Script to collect training data using the security crawler.
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import List
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from urllib.parse import urljoin
import re
import time
from urllib.robotparser import RobotFileParser

# Ensure medusa package is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from medusa.models.tool_knowledge import ToolKnowledge, ToolExample, ToolOption, RelatedCVE, Directive

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from medusa.src.crawler import SecurityCrawler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of 21 core tools to crawl
CORE_TOOLS = [
    "Nmap", "Metasploit Framework", "Burp Suite", "Wireshark", "Aircrack-ng",
    "John the Ripper", "Hydra", "SQLMap", "Nessus", "Nikto", "Snort",
    "Zed Attack Proxy (ZAP)", "Maltego", "Gobuster", "THC-Hydra",
    "Social Engineering Toolkit (SET)", "Browser Exploitation Framework (BeEF)",
    "Empire", "Recon-ng", "VeraCrypt", "Cuckoo Sandbox"
]

KALI_TOOLS_URL = "https://www.kali.org/tools/"

USER_AGENT = "MedusaCrawler/1.0 (+https://github.com/yourusername/medusa)"
POLITENESS_DELAY = 3  # seconds between requests

# Helper to normalize tool names for matching
def normalize_name(name):
    return name.lower().replace("framework", "").replace("(zap)", "zap").replace("(set)", "set").replace("(beef)", "beef").replace(" ", "").replace("-", "")

def is_allowed_by_robots(url, user_agent=USER_AGENT):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        allowed = rp.can_fetch(user_agent, url)
        if not allowed:
            logger.info(f"Blocked by robots.txt: {url}")
        return allowed
    except Exception as e:
        logger.warning(f"robots.txt fetch failed for {robots_url}: {e}")
        # If robots.txt can't be fetched, default to allow
        return True

# Main crawler function
def crawl_kali_tools(core_tools):
    resp = requests.get(KALI_TOOLS_URL, headers={"User-Agent": USER_AGENT})
    soup = BeautifulSoup(resp.text, 'html.parser')
    tool_links = [a['href'] for a in soup.select('a.card-link') if a['href'].startswith('/tools/')]
    found_tools = []
    for link in tool_links:
        tool_url = urljoin(KALI_TOOLS_URL, link)
        if not is_allowed_by_robots(tool_url):
            continue
        time.sleep(POLITENESS_DELAY)
        tool_data = parse_tool_page(tool_url)
        if tool_data:
            for core_tool in core_tools:
                if normalize_name(core_tool) in normalize_name(tool_data['tool_name']):
                    found_tools.append(tool_data)
                    break
    return found_tools

def parse_tool_page(url):
    resp = requests.get(url, headers={"User-Agent": USER_AGENT})
    soup = BeautifulSoup(resp.text, 'html.parser')
    name = soup.find('h1').get_text(strip=True) if soup.find('h1') else None
    desc = soup.find('div', class_='tool-description')
    description = desc.get_text(strip=True) if desc else ""
    # GIGO: skip if no name or description
    if not name or not description:
        return None
    # Extract usage examples (look for code/pre blocks)
    examples = []
    for pre in soup.find_all('pre'):
        code = pre.get_text(strip=True)
        if code and len(code) < 500:
            examples.append(ToolExample(command=code, explanation="Example command from official docs. Review for safety before use."))
    # Extract common options/flags
    options = []
    for code in soup.find_all('code'):
        text = code.get_text()
        if re.match(r"^(-{1,2}\w+)", text):
            options.append(ToolOption(flag=text, description="Option/flag from docs. Add details as needed."))
    # Use cases and security notes
    use_cases = ["See official docs for safe usage."]
    security_notes = ["Never use tools on networks you do not own or have permission to test."]
    # Add a sample directive as a placeholder
    directives = [
        Directive(
            title="Basic Usage",
            description=f"See the official documentation for how to use {name} safely and effectively.",
            source=url,
            tags=["usage", "beginner"],
            last_verified=datetime.utcnow().strftime("%Y-%m-%d"),
            confidence=0.8
        )
    ]
    # Build ToolKnowledge object
    tool_knowledge = ToolKnowledge(
        tool_name=name,
        description=description,
        examples=examples,
        common_options=options,
        use_cases=use_cases,
        security_notes=security_notes,
        related_cves=[],  # To be filled in later
        directives=directives,
        source_url=url,
        date_crawled=datetime.utcnow().isoformat()
    )
    return tool_knowledge.__dict__

def main():
    logger.info("Crawling Kali tools for core tool knowledge...")
    tools_data = crawl_kali_tools(CORE_TOOLS)
    logger.info(f"Found {len(tools_data)} core tools.")
    # Output to JSON
    with open('kali_core_tools_knowledge.json', 'w', encoding='utf-8') as f:
        json.dump(tools_data, f, indent=2, ensure_ascii=False)
    logger.info("Output written to kali_core_tools_knowledge.json")

if __name__ == "__main__":
    main() 