# medusa/src/tool_crawler/normalizer.py

from typing import Dict, Any, List
import re
import logging
from datetime import datetime
from medusa.src.tool_crawler.utils import remove_null_bytes

class NormalizationError(Exception):
    pass

class ToolDataNormalizer:
    """
    Cleans and standardizes raw tool data extracted by parsers.
    Applies normalization rules, handles missing/messy data, and enforces schema for DB insertion.
    """
    def __init__(self, normalization_rules: Dict[str, Any] = None, orchestrator_logger=None):
        self.normalization_rules = normalization_rules or {}
        self.logger = logging.getLogger("ToolDataNormalizer")
        self.orchestrator_logger = orchestrator_logger
        # TODO: Load or define normalization rules (e.g., OS name mapping, tag cleaning)

    def log(self, level, msg, **kwargs):
        # Log to both local logger and orchestrator logger if available
        if level == 'warning':
            self.logger.warning(msg)
        elif level == 'error':
            self.logger.error(msg)
        else:
            self.logger.info(msg)
        if self.orchestrator_logger:
            self.orchestrator_logger.log_event(f"normalizer_{level}", {"message": msg, **kwargs})

    def _normalize_timestamp(self, timestamp_str: Any, field_name: str, tool_name: str) -> str | None:
        if not timestamp_str or not isinstance(timestamp_str, str):
            if timestamp_str is not None and timestamp_str != "":
                 self.log('warning', f"Invalid type for {field_name}: {timestamp_str} (type: {type(timestamp_str)}). Using current UTC time.", field=field_name, tool=tool_name)
                 return datetime.utcnow().isoformat()
            return None

        timestamp_str = timestamp_str.strip()
        if not timestamp_str:
            return None

        # Handle specific known invalid string values explicitly
        if timestamp_str.lower() == "on":
            self.log('warning', f"Invalid timestamp value {timestamp_str} for {field_name}. Using current UTC time.", field=field_name, tool=tool_name)
            return datetime.utcnow().isoformat()

        # Attempt to parse common datetime formats
        # Add more formats here if commonly encountered from parsers
        common_formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO 8601 with Z
            "%Y-%m-%dT%H:%M:%SZ",     # ISO 8601 without microseconds, with Z
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%B %d, %Y",             # e.g., "March 15, 2023"
            "%b %d, %Y",              # e.g., "Mar 15, 2023"
            "%d %B %Y",              # e.g., "15 March 2023"
            "%d %b %Y",               # e.g., "15 Mar 2023"
        ]

        for fmt in common_formats:
            try:
                dt_obj = datetime.strptime(timestamp_str, fmt)
                return dt_obj.isoformat()
            except ValueError:
                continue
        
        # If all parsing attempts fail
        self.log('warning', f"Could not parse timestamp {timestamp_str} for {field_name}. Using current UTC time.", field=field_name, tool=tool_name)
        return datetime.utcnow().isoformat()

    def normalize(self, raw_tool_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalizes raw tool data to match the new DB schema.
        Handles missing fields, cleans text, standardizes values, and flags data quality issues.
        Returns a dict with keys for each normalized table.
        """
        if not isinstance(raw_tool_data, dict):
            self.log('error', 'Input to normalize() is not a dict', input_type=str(type(raw_tool_data)))
            return {'error': 'Input to normalize() is not a dict', 'input_type': str(type(raw_tool_data))}
        try:
            # Canonical schema fields
            canonical_fields = [
                'medusa_id', 'tool_name', 'description', 'website', 'version', 'categories', 'tags',
                'installation_instructions', 'usage_summary', 'license', 'authors_maintainers',
                'supported_os', 'source_code_url', 'binary_download_url', 'logo_url',
                'data_sensitivity_level', 'first_seen_timestamp', 'last_updated_timestamp',
                'source_url', 'parser_plugin_name', 'raw_extracted_data', 'encryption_key_id'
            ]
            # Required fields
            required_fields = ['medusa_id', 'tool_name']
            # Start normalization
            tool = {}
            # --- Required fields ---
            tool_name = (raw_tool_data.get('tool_name') or '').strip()
            if not tool_name:
                self.log('error', "Required field 'tool_name' missing", field='tool_name', source=raw_tool_data.get('source_url'))
            tool['tool_name'] = tool_name
            # medusa_id: generate if not present
            medusa_id = raw_tool_data.get('medusa_id')
            if not medusa_id and tool_name:
                import hashlib
                medusa_id = hashlib.md5((tool_name.lower() + (raw_tool_data.get('source_url') or '')).encode('utf-8')).hexdigest()
                self.log('info', "Generated medusa_id from tool_name and source_url", field='medusa_id', value=medusa_id)
            if not medusa_id:
                self.log('error', "Required field 'medusa_id' missing", field='medusa_id', source=raw_tool_data.get('source_url'))
            tool['medusa_id'] = medusa_id
            # --- Highly desirable/optional fields ---
            def get_field(field, fallback=None, clean=None, std=None, placeholder=None):
                val = raw_tool_data.get(field)
                if val is None or (isinstance(val, str) and not val.strip()):
                    self.log('warning', f"Field '{field}' not found", field=field, tool=tool_name)
                    val = placeholder if placeholder is not None else fallback
                if clean and val:
                    val = clean(val)
                if std and val:
                    val = std(val)
                return val
            # Description
            tool['description'] = get_field('description', placeholder="No description available")
            # Website (homepage): always use official_site_url or website, never documentation_url or page URL
            homepage = raw_tool_data.get('official_site_url') or raw_tool_data.get('website')
            # If homepage is missing but documentation_url is present, do NOT use documentation_url as website
            tool['website'] = homepage
            # Installation instructions (robust mapping)
            tool['installation_instructions'] = (
                raw_tool_data.get('installation_instructions') or
                raw_tool_data.get('installation_details') or
                raw_tool_data.get('install_instructions') or
                None
            )
            if not tool['installation_instructions']:
                self.log('warning', "Missing installation instructions after all fallbacks", field='installation_instructions', tool=tool_name)
            # Usage summary (robust mapping)
            tool['usage_summary'] = (
                raw_tool_data.get('usage_summary') or
                raw_tool_data.get('common_use_cases') or
                raw_tool_data.get('usage') or
                None
            )
            if not tool['usage_summary']:
                self.log('warning', "Missing usage summary after all fallbacks", field='usage_summary', tool=tool_name)
            # License (robust mapping)
            tool['license'] = (
                raw_tool_data.get('license') or
                raw_tool_data.get('licence') or
                None
            )
            if not tool['license']:
                self.log('warning', "Missing license after all fallbacks", field='license', tool=tool_name)
            # Version (robust mapping)
            tool['version'] = (
                raw_tool_data.get('version') or
                raw_tool_data.get('tool_version') or
                None
            )
            if not tool['version']:
                self.log('warning', "Missing version after all fallbacks", field='version', tool=tool_name)
            # Categories (robust mapping)
            cats = (
                raw_tool_data.get('categories') or
                raw_tool_data.get('category') or
                raw_tool_data.get('tool_categories') or
                []
            )
            if isinstance(cats, str):
                cats = [c.strip() for c in cats.split(',') if c.strip()]
            tool['categories'] = [str(c).strip() for c in cats if c]
            if not tool['categories']:
                self.log('warning', "Missing categories after all fallbacks", field='categories', tool=tool_name)
            # Tags (robust mapping)
            tags = (
                raw_tool_data.get('tags') or
                raw_tool_data.get('tool_tags') or
                []
            )
            if isinstance(tags, str):
                tags = [t.strip().lower() for t in tags.split(',') if t.strip()]
            elif isinstance(tags, list):
                tags = [str(t).strip().lower() for t in tags if t]
            else:
                tags = []
            tool['tags'] = tags
            if not tool['tags']:
                self.log('warning', "Missing tags after all fallbacks", field='tags', tool=tool_name)
            # Authors/Maintainers
            tool['authors_maintainers'] = get_field('authors_maintainers')
            # Supported OS (standardize)
            oses = raw_tool_data.get('supported_os') or []
            tool['supported_os'] = [str(o).strip() for o in oses if o]
            # Source code URL
            tool['source_code_url'] = get_field('source_code_url')
            # Binary download URL
            tool['binary_download_url'] = get_field('binary_download_url')
            # Logo URL
            tool['logo_url'] = get_field('logo_url')
            # Data sensitivity level
            tool['data_sensitivity_level'] = get_field('data_sensitivity_level')
            # Timestamps
            raw_first_seen = raw_tool_data.get('first_seen_timestamp')
            raw_last_updated = raw_tool_data.get('last_updated_timestamp', raw_tool_data.get('last_updated'))

            tool['first_seen_timestamp'] = self._normalize_timestamp(raw_first_seen, 'first_seen_timestamp', tool_name)
            tool['last_updated_timestamp'] = self._normalize_timestamp(raw_last_updated, 'last_updated_timestamp', tool_name)
            
            # If first_seen is still None, try to use last_updated if available and valid, or current time
            if tool['first_seen_timestamp'] is None:
                if tool['last_updated_timestamp']:
                     tool['first_seen_timestamp'] = tool['last_updated_timestamp']
                     self.log('info', f"Setting 'first_seen_timestamp' to 'last_updated_timestamp' as it was None.", field='first_seen_timestamp', tool=tool_name)
                else:
                     tool['first_seen_timestamp'] = datetime.utcnow().isoformat()
                     self.log('info', f"Setting 'first_seen_timestamp' to current UTC time as it was None.", field='first_seen_timestamp', tool=tool_name)

            # If last_updated is still None, set it to first_seen (which is now guaranteed to be set)
            if tool['last_updated_timestamp'] is None:
                tool['last_updated_timestamp'] = tool['first_seen_timestamp']
                self.log('info', f"Setting 'last_updated_timestamp' to 'first_seen_timestamp' as it was None.", field='last_updated_timestamp', tool=tool_name)

            # Source URL
            tool['source_url'] = get_field('source_url')
            # Parser plugin name
            tool['parser_plugin_name'] = get_field('parser_plugin_name', fallback=raw_tool_data.get('parser_hint'))
            # Raw extracted data (for audit/debug)
            tool['raw_extracted_data'] = raw_tool_data
            # Encryption key id
            tool['encryption_key_id'] = get_field('encryption_key_id')
            # After all field assignments, sanitize all string fields in tool dict
            for k, v in tool.items():
                if isinstance(v, str):
                    tool[k] = remove_null_bytes(v, field_name=k, logger=self.logger)
            # --- Related/child tables ---
            # Related vulnerabilities
            related_vulns = self._normalize_related_vulns(raw_tool_data.get('related_vulnerabilities', []))
            # Commands
            commands = self._normalize_commands(raw_tool_data.get('commands', []))
            # Modules
            modules = self._normalize_modules(raw_tool_data.get('modules', []))
            # Examples
            examples = raw_tool_data.get('practical_examples', []) or []
            # Workflows
            workflows = self._normalize_workflows(raw_tool_data.get('workflows', []))
            # Troubleshooting
            troubleshooting = self._normalize_troubleshooting(raw_tool_data.get('troubleshooting', []))
            # External links
            external_links = self._normalize_external_links(raw_tool_data.get('external_links', []))
            # Page data
            page = None
            if 'page_data' in raw_tool_data:
                page = raw_tool_data['page_data']
                for k, v in page.items():
                    if isinstance(v, str):
                        page[k] = remove_null_bytes(v, field_name=k, logger=self.logger)
            # --- Gold standard fields for completeness ---
            gold_fields = [
                'website', 'version', 'license', 'categories', 'tags', 'supported_os', 'usage_summary', 'installation_instructions'
            ]
            # Attempt enrichment from raw_extracted_data if missing
            raw_content = ''
            if isinstance(tool.get('raw_extracted_data'), dict):
                raw_content = tool['raw_extracted_data'].get('content', '') or ''
            elif isinstance(tool.get('raw_extracted_data'), str):
                raw_content = tool['raw_extracted_data']
            enrichment_performed = self._enrich_tool_fields_from_raw_content(tool, raw_content)
            # Calculate data_quality_score
            present = 0
            for f in gold_fields:
                v = tool.get(f)
                if isinstance(v, list):
                    if v and any(v):
                        present += 1
                elif v:
                    present += 1
            tool['data_quality_score'] = round(100 * present / len(gold_fields), 1)
            # Compute quality rank
            def get_quality_rank(score):
                if score >= 95:
                    return 'S'
                elif score >= 90:
                    return 'A'
                elif score >= 80:
                    return 'B'
                elif score >= 70:
                    return 'C'
                elif score >= 60:
                    return 'D'
                else:
                    return 'F'
            tool['quality_rank'] = get_quality_rank(tool['data_quality_score'])
            # Log missing fields
            for f in gold_fields:
                v = tool.get(f)
                if (isinstance(v, list) and (not v or not any(v))) or (not isinstance(v, list) and not v):
                    self.log('warning', f"Gold standard field missing after enrichment: {f}", field=f, tool=tool_name)
            # Log the final normalized tool data
            if hasattr(self, 'logger'):
                self.logger.log_event('NORMALIZER_OUTPUT', {'normalized_tool_data': {
                    'tool': tool,
                    'related_vulnerabilities': related_vulns,
                    'commands': commands,
                    'modules': modules,
                    'examples': examples,
                    'workflows': workflows,
                    'troubleshooting': troubleshooting,
                    'external_links': external_links,
                    'page': page
                }}, severity='DEBUG', message='Normalizer output for tool.')
            return {
                'tool': tool,
                'related_vulnerabilities': related_vulns,
                'commands': commands,
                'modules': modules,
                'examples': examples,
                'workflows': workflows,
                'troubleshooting': troubleshooting,
                'external_links': external_links,
                'page': page
            }
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log('error', f'Exception in normalize: {e}', traceback=tb)
            return {'error': str(e), 'traceback': tb}

    def _normalize_option(self, opt: Dict[str, Any]) -> Dict[str, Any]:
        # Standardize option fields and types
        return {
            'name': opt.get('name'),
            'description': opt.get('description'),
            'required': bool(opt.get('required', False)),
            'type': opt.get('type', 'string'),
            'default': opt.get('default'),
            'example': opt.get('example')
        }

    def _normalize_related_vulns(self, related_vulns):
        if not isinstance(related_vulns, list):
            self.log('warning', 'related_vulnerabilities is not a list', input_type=str(type(related_vulns)))
            related_vulns = []
        result = []
        for ref in related_vulns:
            if not isinstance(ref, str):
                self.log('warning', 'related_vulnerability ref is not a string', value=ref)
                continue
            ref_type = 'CVE' if ref.startswith('CVE-') else ('CWE' if ref.startswith('CWE-') else 'OTHER')
            rv = {'vulnerability_ref': ref, 'reference_type': ref_type}
            for k, v in rv.items():
                if isinstance(v, str):
                    rv[k] = remove_null_bytes(v, field_name=k, logger=self.logger)
            result.append(rv)
        return result

    def _normalize_commands(self, commands):
        if not isinstance(commands, list):
            self.log('warning', 'commands is not a list', input_type=str(type(commands)))
            commands = []
        result = []
        for cmd in commands:
            if not isinstance(cmd, dict):
                self.log('warning', 'command is not a dict', value=cmd)
                continue
            c = {
                'name': cmd.get('name'),
                'description': cmd.get('description'),
                'syntax': cmd.get('syntax'),
                'options': [self._normalize_option(opt) for opt in cmd.get('options', []) if isinstance(opt, dict)],
                'examples': cmd.get('examples', []) if isinstance(cmd.get('examples', []), list) else []
            }
            for k, v in c.items():
                if isinstance(v, str):
                    c[k] = remove_null_bytes(v, field_name=k, logger=self.logger)
            c['examples'] = [remove_null_bytes(ex, field_name='example', logger=self.logger) for ex in c.get('examples', [])]
            for o in c['options']:
                for ok, ov in o.items():
                    if isinstance(ov, str):
                        o[ok] = remove_null_bytes(ov, field_name=ok, logger=self.logger)
            result.append(c)
        return result

    def _normalize_modules(self, modules):
        if not isinstance(modules, list):
            self.log('warning', 'modules is not a list', input_type=str(type(modules)))
            modules = []
        result = []
        for mod in modules:
            if not isinstance(mod, dict):
                self.log('warning', 'module is not a dict', value=mod)
                continue
            m = {
                'name': mod.get('name'),
                'type': mod.get('type'),
                'description': mod.get('description'),
                'options': [self._normalize_option(opt) for opt in mod.get('options', []) if isinstance(opt, dict)],
                'examples': mod.get('examples', []) if isinstance(mod.get('examples', []), list) else []
            }
            for k, v in m.items():
                if isinstance(v, str):
                    m[k] = remove_null_bytes(v, field_name=k, logger=self.logger)
            m['examples'] = [remove_null_bytes(ex, field_name='example', logger=self.logger) for ex in m.get('examples', [])]
            for o in m['options']:
                for ok, ov in o.items():
                    if isinstance(ov, str):
                        o[ok] = remove_null_bytes(ov, field_name=ok, logger=self.logger)
            result.append(m)
        return result

    def _normalize_workflows(self, workflows):
        if not isinstance(workflows, list):
            self.log('warning', 'workflows is not a list', input_type=str(type(workflows)))
            workflows = []
        result = []
        for wf in workflows:
            if not isinstance(wf, dict):
                self.log('warning', 'workflow is not a dict', value=wf)
                continue
            w = {'name': wf.get('name'), 'steps': wf.get('steps', []) if isinstance(wf.get('steps', []), list) else []}
            for k, v in w.items():
                if isinstance(v, str):
                    w[k] = remove_null_bytes(v, field_name=k, logger=self.logger)
            w['steps'] = [remove_null_bytes(step, field_name='step', logger=self.logger) for step in w.get('steps', [])]
            result.append(w)
        return result

    def _normalize_troubleshooting(self, troubleshooting):
        if not isinstance(troubleshooting, list):
            self.log('warning', 'troubleshooting is not a list', input_type=str(type(troubleshooting)))
            troubleshooting = []
        result = []
        for t in troubleshooting:
            if not isinstance(t, dict):
                self.log('warning', 'troubleshooting entry is not a dict', value=t)
                continue
            tr = {'issue': t.get('issue'), 'solution': t.get('solution')}
            for k, v in tr.items():
                if isinstance(v, str):
                    tr[k] = remove_null_bytes(v, field_name=k, logger=self.logger)
            result.append(tr)
        return result

    def _normalize_external_links(self, external_links):
        if not isinstance(external_links, list):
            self.log('warning', 'external_links is not a list', input_type=str(type(external_links)))
            external_links = []
        result = []
        for l in external_links:
            if isinstance(l, dict):
                for k, v in l.items():
                    if isinstance(v, str):
                        l[k] = remove_null_bytes(v, field_name=k, logger=self.logger)
                result.append(l)
            elif isinstance(l, str):
                result.append(remove_null_bytes(l, field_name='external_link', logger=self.logger))
            else:
                self.log('warning', 'external_link entry is not a dict or str', value=l)
        return result

    def _enrich_tool_fields_from_raw_content(self, tool, raw_content):
        import re
        enrichment_performed = False
        # License
        if not tool.get('license') and raw_content:
            m = re.search(r'License[:\s]+([\w\-\.]+)', raw_content, re.I)
            if m:
                tool['license'] = m.group(1)
                enrichment_performed = True
                self.log('info', f"Field 'license' enriched from raw_content with value: {tool['license']}", field='license', value=tool['license'])
        # Version
        if not tool.get('version') and raw_content:
            m = re.search(r'Version[:\s]+([\w\.\-]+)', raw_content, re.I)
            if m:
                tool['version'] = m.group(1)
                enrichment_performed = True
                self.log('info', f"Field 'version' enriched from raw_content with value: {tool['version']}", field='version', value=tool['version'])
        # Supported OS
        if (not tool.get('supported_os') or not any(tool.get('supported_os'))) and raw_content:
            os_matches = re.findall(r'(Windows|Linux|macOS|Unix|BSD|Android|iOS)', raw_content, re.I)
            if os_matches:
                tool['supported_os'] = list(set([o.capitalize() for o in os_matches]))
                enrichment_performed = True
                self.log('info', f"Field 'supported_os' enriched from raw_content with value: {tool['supported_os']}", field='supported_os', value=tool['supported_os'])
        # Categories/Tags
        if (not tool.get('categories') or not any(tool.get('categories'))) and raw_content:
            cat_match = re.search(r'Category[:\s]+([\w\s,\-/]+)', raw_content, re.I)
            if cat_match:
                tool['categories'] = [c.strip() for c in cat_match.group(1).split(',') if c.strip()]
                enrichment_performed = True
                self.log('info', f"Field 'categories' enriched from raw_content with value: {tool['categories']}", field='categories', value=tool['categories'])
        if (not tool.get('tags') or not any(tool.get('tags'))) and raw_content:
            tag_match = re.search(r'Tags?[:\s]+([\w\s,\-/]+)', raw_content, re.I)
            if tag_match:
                tool['tags'] = [t.strip().lower() for t in tag_match.group(1).split(',') if t.strip()]
                enrichment_performed = True
                self.log('info', f"Field 'tags' enriched from raw_content with value: {tool['tags']}", field='tags', value=tool['tags'])
        # Usage summary
        if not tool.get('usage_summary') and raw_content:
            usage_match = re.search(r'Usage[:\s]+(.+?)(?:\n|$)', raw_content, re.I)
            if usage_match:
                tool['usage_summary'] = usage_match.group(1).strip()
                enrichment_performed = True
                self.log('info', f"Field 'usage_summary' enriched from raw_content with value: {tool['usage_summary']}", field='usage_summary', value=tool['usage_summary'])
        # Installation instructions
        if not tool.get('installation_instructions') and raw_content:
            install_match = re.search(r'Install(?:ation)?[:\s]+(.+?)(?:\n|$)', raw_content, re.I)
            if install_match:
                tool['installation_instructions'] = install_match.group(1).strip()
                enrichment_performed = True
                self.log('info', f"Field 'installation_instructions' enriched from raw_content with value: {tool['installation_instructions']}", field='installation_instructions', value=tool['installation_instructions'])
        # Set enrichment fields if enrichment was performed
        if enrichment_performed:
            tool['last_enriched_by'] = tool.get('parser_plugin_name') or 'normalizer_regex'
            tool['last_enriched_at'] = datetime.utcnow().isoformat()
        return enrichment_performed

    # TODO: Add methods for rule updates, data quality checks, and schema enforcement. 