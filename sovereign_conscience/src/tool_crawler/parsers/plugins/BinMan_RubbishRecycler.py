from medusa.src.tool_crawler.parsers.base_parser import BaseToolParser
import logging
from bs4 import BeautifulSoup
import re

class BinMan_RubbishRecycler(BaseToolParser):
    """
    Parser for Nmap docs. Extracts real fields for Nmap from https://nmap.org/docs.html.
    """
    def __init__(self):
        super().__init__()
        self.name = "BinMan_RubbishRecycler"
        self.description = "Parser that extracts real Nmap fields from HTML."
        self.logger = logging.getLogger("BinMan_RubbishRecycler")

    def can_parse(self, fetch_result):
        content = fetch_result.get('content', '')
        url = fetch_result.get('final_url', fetch_result.get('url', ''))
        self.logger.debug(f"[BINMAN_DIAG] can_parse called for URL: {url}, content length: {len(content)}")
        # Only parse nmap.org/docs.html
        return (
            bool(content and isinstance(content, str) and '<html' in content.lower()) and
            ('nmap.org/docs.html' in url)
        )

    def parse(self, fetch_result):
        content = fetch_result.get('content', '')
        url = fetch_result.get('final_url', fetch_result.get('url', ''))
        self.logger.debug(f"[BINMAN_DIAG] parse called for URL: {url}, content length: {len(content)}")
        soup = BeautifulSoup(content, 'html.parser')
        # Extract title/description
        title = soup.title.string.strip() if soup.title and soup.title.string else 'Nmap'
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        description = desc_tag['content'].strip() if desc_tag and desc_tag.get('content') else None
        # Fallback: try to extract a meaningful description from the main content
        if not description:
            h1 = soup.find('h1')
            if h1 and h1.get_text():
                description = h1.get_text().strip()
            else:
                # Try to find the first <p> after the main heading
                main_p = soup.find('p')
                if main_p and main_p.get_text():
                    description = main_p.get_text().strip()
        if not description:
            description = "Nmap is a free and open source network scanner."
        # Try to extract version from page text
        version = None
        for tag in soup.find_all(['b', 'strong', 'p']):
            txt = tag.get_text()
            if txt and 'version' in txt.lower() and 'nmap' in txt.lower():
                m = re.search(r'Nmap[\s\w\-]*([0-9]+\.[0-9]+(\.[0-9]+)?)', txt)
                if m:
                    version = m.group(1)
                    break
        # Try to extract license from the page (look for "License" or "Public Source License")
        license_text = None
        for a in soup.find_all('a', href=True):
            if 'license' in a.get('href', '').lower() or 'license' in a.get_text().lower():
                license_text = a.get_text().strip()
                break
        if not license_text:
            # Fallback: look for text mentioning "license" in the page
            for tag in soup.find_all(['p', 'li', 'a']):
                if 'license' in tag.get_text().lower():
                    license_text = tag.get_text().strip()
                    break
        # Categories and tags (hardcoded for Nmap)
        categories = ['Network Scanner', 'Security Auditing']
        tags = ['network', 'port scanner', 'security', 'nmap']
        # Supported OS (from docs, Nmap runs on many OSes)
        supported_os = ['Windows', 'Linux', 'macOS', 'FreeBSD', 'OpenBSD', 'NetBSD', 'Solaris', 'HP-UX', 'Amiga']
        # Source code URL (look for a link to GitHub or source)
        source_code_url = None
        for a in soup.find_all('a', href=True):
            if 'github.com/nmap' in a['href']:
                source_code_url = a['href']
                break
        if not source_code_url:
            # Fallback: official download/source page
            source_code_url = 'https://nmap.org/download.html'
        # Official site URL
        official_site_url = 'https://nmap.org'
        # Documentation URL
        documentation_url = url
        tool_dict = {
            'tool_name': 'Nmap',
            'description': description,
            'official_site_url': official_site_url,
            'documentation_url': documentation_url,
            'categories': categories,
            'tags': tags,
            'version': version,
            'license': license_text,
            'supported_os': supported_os,
            'source_code_url': source_code_url,
            'source_url': url
        }
        page_dict = {
            'url': url,
            'title': title,
            'content': content
        }
        result = {
            'tool': tool_dict,
            'page': page_dict,
            'related_vulnerabilities': [],
            'commands': [],
            'modules': [],
            'workflows': [],
            'troubleshooting': [],
            'external_links': [],
            'supported_os': supported_os
        }
        self.logger.info(f"[BinMan_RubbishRecycler] Parsed Nmap data: {result}")
        return result 