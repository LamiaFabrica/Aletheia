#!/usr/bin/env python3
"""
User interface module for Medusa project.
Provides natural language interaction with the crawler and AI models.
"""

import os
import sys
import logging
import argparse
from typing import Dict, List, Optional, Tuple
import json
from datetime import datetime
import re
from pathlib import Path
import difflib
from colorama import init, Fore, Style

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.collect_training_data import SecurityDocCrawler
from medusa.src.nmap_analyzer import NmapAnalyzer
from medusa.src.ai_models import AIModelManager
from medusa.src.language_guard import enforce_english

# Initialize colorama for colored output
init()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MedusaInterface:
    """Provides a natural language interface for Medusa."""
    
    def __init__(self):
        self.crawler = None
        self.analyzer = NmapAnalyzer()
        self.ai_manager = AIModelManager()
        
        # Command patterns for natural language processing
        self.command_patterns = {
            'crawl': [
                r'crawl\s+(.+?)(?:\s+docs)?$',
                r'learn\s+from\s+(.+?)(?:\s+docs)?$',
                r'gather\s+info\s+from\s+(.+?)(?:\s+docs)?$'
            ],
            'analyze': [
                r'analyze\s+(.+?)$',
                r'check\s+(.+?)$',
                r'scan\s+(.+?)$',
                r'look\s+at\s+(.+?)$'
            ],
            'train': [
                r'train\s+(?:models|ai|system)?$',
                r'learn\s+(?:from|with)\s+data$',
                r'update\s+(?:models|ai|system)$'
            ],
            'status': [
                r'status$',
                r'what\s+do\s+you\s+know$',
                r'show\s+knowledge$',
                r'what\s+have\s+you\s+learned$'
            ],
            'help': [
                r'help$',
                r'what\s+can\s+you\s+do$',
                r'commands$',
                r'options$'
            ],
            'quit': [
                r'quit$',
                r'exit$',
                r'bye$',
                r'goodbye$'
            ]
        }
        
        # Command handlers
        self.commands = {
            'crawl': self._handle_crawl,
            'analyze': self._handle_analyze,
            'train': self._handle_train,
            'help': self._handle_help,
            'status': self._handle_status,
            'quit': self._handle_quit
        }
        
        # Load existing knowledge base if available
        self.knowledge_base = self._load_knowledge_base()
        
        # Command history
        self.history: List[str] = []
    
    def _load_knowledge_base(self) -> Dict:
        """Load existing knowledge base from files."""
        knowledge_base = {
            'scan_examples': [],
            'security_concepts': [],
            'tool_usage': [],
            'best_practices': []
        }
        
        training_dir = Path('training_data')
        if training_dir.exists():
            for category in knowledge_base.keys():
                for file in training_dir.glob(f'{category}_*.json'):
                    try:
                        with open(file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            knowledge_base[category].extend(data)
                    except Exception as e:
                        logger.error(f"Error loading {file}: {str(e)}")
        
        return knowledge_base
    
    def _find_best_match(self, command: str) -> Tuple[str, float]:
        """Find the best matching command using fuzzy matching."""
        best_match = None
        best_score = 0
        
        for cmd, patterns in self.command_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, command.lower())
                if match:
                    score = difflib.SequenceMatcher(None, command.lower(), pattern).ratio()
                    if score > best_score:
                        best_score = score
                        best_match = cmd
        
        return best_match, best_score
    
    def _handle_crawl(self, args: List[str]) -> str:
        """Handle crawl command."""
        if not args:
            return f"{Fore.YELLOW}Please specify what to crawl. Example: 'crawl kali docs'{Style.RESET_ALL}"
        
        target = ' '.join(args).lower()
        
        # Initialize crawler if not already done
        if not self.crawler:
            self.crawler = SecurityDocCrawler()
        
        # Map natural language to specific sources
        source_mapping = {
            'kali': 'kali_docs',
            'nmap': 'nmap_docs',
            'security': 'security_trails',
            'hacktricks': 'hacktricks',
            'pentest': 'pentest_wiki',
            'offensive': 'offensive_security',
            'all': 'all'
        }
        
        # Find matching source
        source = None
        for key, value in source_mapping.items():
            if key in target:
                source = value
                break
        
        if not source:
            return f"{Fore.YELLOW}I don't understand which documentation to crawl. Try: kali, nmap, security, hacktricks, pentest, offensive, or all{Style.RESET_ALL}"
        
        try:
            print(f"{Fore.CYAN}Starting to crawl {source} documentation...{Style.RESET_ALL}")
            
            if source == 'all':
                for name, url in self.crawler.seed_urls.items():
                    print(f"{Fore.CYAN}Crawling {name} from {url}...{Style.RESET_ALL}")
                    self.crawler.crawl_page(url)
            else:
                url = self.crawler.seed_urls[source]
                print(f"{Fore.CYAN}Crawling {source} from {url}...{Style.RESET_ALL}")
                self.crawler.crawl_page(url)
            
            # Save and update knowledge base
            self.crawler.save_knowledge_base()
            self.knowledge_base = self._load_knowledge_base()
            
            return f"{Fore.GREEN}Successfully crawled {source} documentation. New knowledge has been added to the database.{Style.RESET_ALL}"
            
        except Exception as e:
            return f"{Fore.RED}Error during crawling: {str(e)}{Style.RESET_ALL}"
    
    def _handle_analyze(self, args: List[str]) -> str:
        """Handle analyze command."""
        if not args:
            return f"{Fore.YELLOW}Please specify what to analyze. Example: 'analyze scan results.xml'{Style.RESET_ALL}"
        
        target = ' '.join(args)
        
        try:
            if target.endswith('.xml'):
                print(f"{Fore.CYAN}Analyzing {target}...{Style.RESET_ALL}")
                # Analyze Nmap scan results
                results = self.analyzer.analyze_scan(target)
                return f"{Fore.GREEN}Analysis complete. Found {results['total_hosts']} hosts with {results['total_ports']} ports.{Style.RESET_ALL}"
            else:
                return f"{Fore.YELLOW}I can only analyze Nmap XML files at the moment.{Style.RESET_ALL}"
                
        except Exception as e:
            return f"{Fore.RED}Error during analysis: {str(e)}{Style.RESET_ALL}"
    
    def _handle_train(self, args: List[str]) -> str:
        """Handle train command."""
        try:
            print(f"{Fore.CYAN}Training models using collected knowledge...{Style.RESET_ALL}")
            # Train models using collected knowledge
            self.analyzer.train_models()
            return f"{Fore.GREEN}Models have been trained successfully using the collected knowledge.{Style.RESET_ALL}"
            
        except Exception as e:
            return f"{Fore.RED}Error during training: {str(e)}{Style.RESET_ALL}"
    
    def _handle_help(self, args: List[str]) -> str:
        """Handle help command."""
        help_text = f"""
{Fore.CYAN}Available commands:{Style.RESET_ALL}
- {Fore.GREEN}crawl [source]{Style.RESET_ALL}: Crawl documentation (kali, nmap, security, hacktricks, pentest, offensive, or all)
- {Fore.GREEN}analyze [file]{Style.RESET_ALL}: Analyze Nmap scan results
- {Fore.GREEN}train{Style.RESET_ALL}: Train AI models using collected knowledge
- {Fore.GREEN}status{Style.RESET_ALL}: Show current knowledge base status
- {Fore.GREEN}help{Style.RESET_ALL}: Show this help message
- {Fore.GREEN}quit{Style.RESET_ALL}: Exit the program

{Fore.CYAN}Examples:{Style.RESET_ALL}
- "crawl kali docs"
- "learn from nmap documentation"
- "analyze scan_results.xml"
- "check my scan results"
- "train models"
- "what do you know?"
"""
        return help_text
    
    def _handle_status(self, args: List[str]) -> str:
        """Handle status command."""
        status = f"{Fore.CYAN}Knowledge Base Status:{Style.RESET_ALL}\n"
        for category, data in self.knowledge_base.items():
            status += f"- {Fore.GREEN}{category}{Style.RESET_ALL}: {len(data)} entries\n"
        return status
    
    def _handle_quit(self, args: List[str]) -> str:
        """Handle quit command."""
        print(f"\n{Fore.CYAN}Goodbye! Thank you for using Medusa.{Style.RESET_ALL}")
        sys.exit(0)
    
    def process_command(self, command: str) -> str:
        """Process a natural language command."""
        # English-only enforcement
        if rejection := enforce_english(command):
            return f"{Fore.RED}{rejection}{Style.RESET_ALL}"

        # Add to history
        self.history.append(command)

        # Find best matching command
        cmd, score = self._find_best_match(command)
        
        if cmd and score > 0.6:  # Threshold for matching
            # Extract arguments
            args = command.split()[1:] if cmd in ['crawl', 'analyze'] else []
            return self.commands[cmd](args)
        else:
            return f"{Fore.YELLOW}I'm not sure what you mean. Type 'help' for available commands.{Style.RESET_ALL}"

def main():
    parser = argparse.ArgumentParser(description='Medusa Interface')
    parser.add_argument('--interactive', action='store_true',
                      help='Run in interactive mode')
    args = parser.parse_args()
    
    interface = MedusaInterface()
    
    if args.interactive:
        print(f"{Fore.CYAN}Welcome to Medusa Interface!{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Type 'help' for available commands.{Style.RESET_ALL}")
        
        while True:
            try:
                command = input(f"\n{Fore.GREEN}Medusa>{Style.RESET_ALL} ").strip()
                if command:
                    response = interface.process_command(command)
                    print(response)
            except KeyboardInterrupt:
                print(f"\n{Fore.CYAN}Goodbye! Thank you for using Medusa.{Style.RESET_ALL}")
                break
            except Exception as e:
                print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
    else:
        # Process single command from command line
        command = ' '.join(sys.argv[1:])
        if command:
            response = interface.process_command(command)
            print(response)
        else:
            print(f"{Fore.YELLOW}Please provide a command. Use --interactive for interactive mode.{Style.RESET_ALL}")

if __name__ == '__main__':
    main() 