# medusa/src/tool_crawler/db_writer.py

import hashlib
import base64
import logging
import json
from typing import Dict, Any, List, Optional
from cryptography.fernet import Fernet
import random
import string
from datetime import datetime
from medusa.src.plugins.antigumf_plugin import AntiGumfPlugin

# --- Helper to remove NUL bytes from strings ---
def remove_null_bytes(s, field_name=None, logger=None):
    if isinstance(s, str):
        if '\x00' in s or '\u0000' in s or chr(0) in s:
            msg = f"[DATA_HYGIENE] NUL byte detected and removed from field '{field_name or '?'}'"
            if logger:
                logger.warning(msg)
            else:
                print(msg)
        return s.replace('\x00', '').replace('\u0000', '').replace(chr(0), '')
    return s

# --- Helper to recursively sanitize all strings in dicts/lists ---
def sanitize_for_db(obj, field_name=None, logger=None):
    if isinstance(obj, str):
        return remove_null_bytes(obj, field_name=field_name, logger=logger)
    elif isinstance(obj, list):
        return [sanitize_for_db(v, field_name=field_name, logger=logger) for v in obj]
    elif isinstance(obj, dict):
        return {k: sanitize_for_db(v, field_name=k, logger=logger) for k, v in obj.items()}
    else:
        return obj

class ToolDBWriter:
    """
    Handles all database writes for the tool extraction crawler.
    Supports multi-table inserts/updates, deduplication, medusa_id generation, batch operations, and error handling.
    Encrypts only sensitive fields as per the security policy.
    
    Encryption Policy:
    - Only sensitive fields are encrypted: description, installation_instructions, usage_summary, license, authors_maintainers, source_code_url, binary_download_url, logo_url, raw_extracted_data.
    - Metadata fields (categories, tags, supported_os) are stored in plaintext for search/filtering.
    - See DATA_RELATIONSHIPS.md and DB_Field_Mapping.md for details.
    """
    def __init__(self, db_connection, orchestrator_logger=None):
        self.db = db_connection
        self.logger = logging.getLogger("ToolDBWriter")
        self.orchestrator_logger = orchestrator_logger
        # --- Integrate AntiGumf ---
        self.antigumf = AntiGumfPlugin(self.db)

    def encrypt(self, value: Any, field_name=None) -> str:
        if value is None:
            return None
        return self.db._encrypt(remove_null_bytes(str(value), field_name=field_name, logger=self.logger))

    def log(self, level, msg, **kwargs):
        if level == 'warning':
            self.logger.warning(msg)
        elif level == 'error':
            self.logger.error(msg)
        else:
            self.logger.info(msg)
        if self.orchestrator_logger:
            self.orchestrator_logger.log_event(f"dbwriter_{level}", {"message": msg, **kwargs})

    def canonicalize_content(self, content):
        return content.strip().lower() if content else ''

    def write(self, normalized_tool_data: Dict[str, Any], plugin_name: str = None, cur: Optional[Any] = None) -> dict:
        """
        Inserts or updates tool data across all relevant tables and join tables.
        Handles deduplication, medusa_id, and transactional integrity.
        Encrypts only sensitive fields as per policy.
        Returns a dict with medusa_id, status, child_counts, and error (if any).
        """
        self.log('debug', '[DBW] write() received normalized_tool_data', normalized_tool_data=normalized_tool_data)
        external_cursor_provided = cur is not None
        result = {"medusa_id": None, "status": None, "child_counts": {}, "error": None}
        try:
            if external_cursor_provided:
                self.log('debug', f"[DBWriter] Write called with cur: Provided")
                self._perform_write_operations(cur, normalized_tool_data, plugin_name, result)
            else:
                self.log('debug', f"[DBWriter] Write called with cur: Not Provided")
                with self.db.get_cursor() as own_cur:
                    self._perform_write_operations(own_cur, normalized_tool_data, plugin_name, result)
                    if hasattr(self.db, 'conn'):
                        self.db.conn.commit()
            result['status'] = result.get('status', 'success')
            tool_name = normalized_tool_data.get('tool', {}).get('tool_name', '?')
            medusa_id = normalized_tool_data.get('tool', {}).get('medusa_id', '?')
            self.log('info', f"[DBWriter] Write successful for {tool_name}", medusa_id=medusa_id, result_status=result['status'])
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log('error', f"Exception: {e}\n{tb}")
            if not external_cursor_provided and hasattr(self.db, 'conn'):
                try:
                    self.db.conn.rollback()
                    self.log('info', f"[DBWriter] Rollback successful for {tool_name} due to error.", medusa_id=medusa_id)
                except Exception as rollback_exc:
                    self.log('error', f"[DBWriter] Further error during rollback: {rollback_exc}", medusa_id=medusa_id)
            try:
                if self.orchestrator_logger:
                    self.orchestrator_logger.log_event("db_write_error", {"error": str(e), "traceback": tb})
            except Exception:
                pass
            result["status"] = "failed"
            result["error"] = str(e)
        self.log('info', f"Write result: {result}")
        return result

    def _perform_write_operations(self, cur, normalized_tool_data, plugin_name, result):
        # Move all DB logic from write() here, using cur for all DB ops. Raise exceptions on error.
        # Input validation
        if not isinstance(normalized_tool_data, dict) or 'tool' not in normalized_tool_data or not isinstance(normalized_tool_data['tool'], dict):
            self.log('error', "Invalid input: normalized_tool_data must be a dict with a 'tool' dict")
            result.update({"status": "failed", "error": "Invalid input structure"})
            raise Exception("Invalid input structure")
        if 'medusa_id' not in normalized_tool_data['tool']:
            self.log('error', "Missing medusa_id in tool data")
            result.update({"status": "failed", "error": "Missing medusa_id"})
            raise Exception("Missing medusa_id")
        # --- Enhanced logging around AntiGumf.filter ---
        try:
            self.log('debug', '[DBW] About to call AntiGumf.filter', tool_data=normalized_tool_data['tool'])
            antigumf_result = self.antigumf.filter(normalized_tool_data['tool'])
            self.log('debug', '[DBW] AntiGumf.filter result', antigumf_result=antigumf_result)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log('error', f"Exception in AntiGumf.filter: {e}\n{tb}")
            if self.orchestrator_logger:
                self.orchestrator_logger.log_event("dbwriter_antigumf_filter_error", {"error": str(e), "traceback": tb})
            result['status'] = 'failed'
            result['error'] = f"AntiGumf.filter: {e}"
            raise
        if antigumf_result['result'] != 'allowed':
            msg = f"[AntiGumf] Tool '{normalized_tool_data['tool'].get('tool_name')}' blocked: {antigumf_result}"
            self.log('warning', msg)
            result['status'] = 'filtered'
            result['error'] = antigumf_result
            return
        medusa_id = normalized_tool_data['tool']['medusa_id']
        result["medusa_id"] = medusa_id
        # --- Enhanced logging around sanitize_for_db ---
        try:
            self.log('debug', '[DBW] About to sanitize tool data')
            tool_data_map = sanitize_for_db(normalized_tool_data['tool'], logger=self.logger)
            self.log('debug', '[DBW] Tool data sanitized', tool_data_map=tool_data_map)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log('error', f"Exception in sanitize_for_db: {e}\n{tb}")
            if self.orchestrator_logger:
                self.orchestrator_logger.log_event("dbwriter_sanitize_error", {"error": str(e), "traceback": tb})
            result['status'] = 'failed'
            result['error'] = f"sanitize_for_db: {e}"
            raise
        if plugin_name:
            tool_data_map['last_enriched_by'] = plugin_name
            tool_data_map['last_enriched_at'] = datetime.utcnow().isoformat()
        # --- Enhanced logging around _upsert_main_tool ---
        try:
            self.log('debug', '[DBW] About to call _upsert_main_tool')
            tool_id = self._upsert_main_tool(cur, tool_data_map, medusa_id)
            self.log('debug', '[DBW] _upsert_main_tool returned', tool_id=tool_id)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log('error', f"Exception in _upsert_main_tool: {e}\n{tb}")
            if self.orchestrator_logger:
                self.orchestrator_logger.log_event("dbwriter_upsert_main_tool_error", {"error": str(e), "traceback": tb})
            result['status'] = 'failed'
            result['error'] = f"_upsert_main_tool: {e}"
            raise
        result["status"] = "updated"
        page = normalized_tool_data.get('page')
        if page and page.get('url') and page.get('title'):
            try:
                self.log('debug', '[DBW] Calling _upsert_page')
                self._upsert_page(cur, page)
                self.log('debug', '[DBW] _upsert_page succeeded')
            except Exception as e:
                self.log('warning', f"Failed to upsert page: {e}")
        # --- Enhanced logging around AntiGumf._cross_source_consistency ---
        try:
            self.log('debug', '[DBW] About to call AntiGumf._cross_source_consistency')
            self.antigumf._cross_source_consistency(tool_data_map)
            self.log('debug', '[DBW] AntiGumf._cross_source_consistency succeeded')
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log('error', f"Exception in AntiGumf._cross_source_consistency: {e}\n{tb}")
            if self.orchestrator_logger:
                self.orchestrator_logger.log_event("dbwriter_antigumf_cross_source_error", {"error": str(e), "traceback": tb})
        self.log('debug', '[DBW] Calling _process_related_vulns')
        rv_count = self._process_related_vulns(cur, tool_id, normalized_tool_data.get('related_vulnerabilities', []))
        self.log('debug', '[DBW] _process_related_vulns returned', rv_count=rv_count)
        self.log('debug', '[DBW] Calling _process_commands')
        cmd_count = self._process_commands(cur, tool_id, normalized_tool_data.get('commands', []))
        self.log('debug', '[DBW] _process_commands returned', cmd_count=cmd_count)
        self.log('debug', '[DBW] Calling _process_modules')
        mod_count = self._process_modules(cur, tool_id, normalized_tool_data.get('modules', []))
        self.log('debug', '[DBW] _process_modules returned', mod_count=mod_count)
        self.log('debug', '[DBW] Calling _process_workflows')
        wf_count = self._process_workflows(cur, tool_id, normalized_tool_data.get('workflows', []))
        self.log('debug', '[DBW] _process_workflows returned', wf_count=wf_count)
        self.log('debug', '[DBW] Calling _process_troubleshooting')
        t_count = self._process_troubleshooting(cur, tool_id, normalized_tool_data.get('troubleshooting', []))
        self.log('debug', '[DBW] _process_troubleshooting returned', t_count=t_count)
        self.log('debug', '[DBW] Calling _process_external_links')
        l_count = self._process_external_links(cur, tool_id, normalized_tool_data.get('external_links', []), medusa_id)
        self.log('debug', '[DBW] _process_external_links returned', l_count=l_count)
        self.log('debug', '[DBW] Calling _process_supported_os')
        os_count = self._process_supported_os(cur, tool_id, tool_data_map.get('supported_os', []))
        self.log('debug', '[DBW] _process_supported_os returned', os_count=os_count)
        result["child_counts"] = {
            "related_vulnerabilities": rv_count,
            "commands": cmd_count,
            "modules": mod_count,
            "workflows": wf_count,
            "troubleshooting": t_count,
            "external_links": l_count,
            "supported_os": os_count
        }

    def _upsert_main_tool(self, cur, tool_data_map, medusa_id):
        enc = self.encrypt
        tool_insert = (
            medusa_id,
            tool_data_map['tool_name'],
            enc(tool_data_map.get('description')),
            tool_data_map.get('categories'),  # plaintext
            enc(tool_data_map.get('website')),
            tool_data_map.get('version'),
            tool_data_map.get('tags'),  # plaintext
            enc(tool_data_map.get('installation_instructions')),
            enc(tool_data_map.get('usage_summary')),
            enc(tool_data_map.get('license')),
            enc(tool_data_map.get('authors_maintainers')),
            tool_data_map.get('supported_os'),  # plaintext
            enc(tool_data_map.get('source_code_url')),
            enc(tool_data_map.get('binary_download_url')),
            enc(tool_data_map.get('logo_url')),
            tool_data_map.get('data_sensitivity_level'),
            tool_data_map.get('first_seen_timestamp'),
            tool_data_map.get('last_updated_timestamp'),
            enc(tool_data_map.get('source_url')),
            tool_data_map.get('parser_plugin_name'),
            enc(str(tool_data_map.get('raw_extracted_data'))),
            tool_data_map.get('encryption_key_id')
        )
        self.log('debug', f"Main tool insert params: {tool_insert}")
        cur.execute("""
            INSERT INTO tools (
                medusa_id, tool_name, description, categories, website, version, tags, installation_instructions, usage_summary, license, authors_maintainers, supported_os, source_code_url, binary_download_url, logo_url, data_sensitivity_level, first_seen_timestamp, last_updated_timestamp, source_url, parser_plugin_name, raw_extracted_data, encryption_key_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (medusa_id) DO UPDATE SET
                tool_name=EXCLUDED.tool_name,
                description=EXCLUDED.description,
                categories=EXCLUDED.categories,
                website=EXCLUDED.website,
                version=EXCLUDED.version,
                tags=EXCLUDED.tags,
                installation_instructions=EXCLUDED.installation_instructions,
                usage_summary=EXCLUDED.usage_summary,
                license=EXCLUDED.license,
                authors_maintainers=EXCLUDED.authors_maintainers,
                supported_os=EXCLUDED.supported_os,
                source_code_url=EXCLUDED.source_code_url,
                binary_download_url=EXCLUDED.binary_download_url,
                logo_url=EXCLUDED.logo_url,
                data_sensitivity_level=EXCLUDED.data_sensitivity_level,
                first_seen_timestamp=EXCLUDED.first_seen_timestamp,
                last_updated_timestamp=EXCLUDED.last_updated_timestamp,
                source_url=EXCLUDED.source_url,
                parser_plugin_name=EXCLUDED.parser_plugin_name,
                raw_extracted_data=EXCLUDED.raw_extracted_data,
                encryption_key_id=EXCLUDED.encryption_key_id,
                updated_at=NOW()
            RETURNING id
        """, tool_insert)
        row = cur.fetchone()
        if row is None:
            cur.execute("SELECT id FROM tools WHERE medusa_id = %s", (medusa_id,))
            row = cur.fetchone()
        if row is None:
            raise Exception("No row returned from tools table")
        tool_id = row['id'] if isinstance(row, dict) and 'id' in row else row[0]
        self.log('info', f"Main tool record written: id={tool_id}")
        return tool_id

    def _upsert_page(self, cur, page):
        page = sanitize_for_db(page, logger=self.logger)
        mde_id = page.get('mde_id')
        if not mde_id:
            mde_id = 'MDE_PAGE_' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            page['mde_id'] = mde_id
        entity_type = page.get('entity_type', 'tool_doc')
        if isinstance(entity_type, str):
            entity_type = [entity_type]
        elif entity_type is None:
            entity_type = ['tool_doc']
        content = page.get('content', '')
        content = remove_null_bytes(content, field_name='content', logger=self.logger)
        page['content'] = content
        content_hash = hashlib.sha256(self.canonicalize_content(content).encode('utf-8')).hexdigest()
        page['content_hash'] = content_hash
        cur.execute("""
            INSERT INTO pages (mde_id, url, title, summary, content, entity_type, content_hash, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (url) DO UPDATE SET
                title=EXCLUDED.title,
                summary=EXCLUDED.summary,
                content=EXCLUDED.content,
                entity_type=EXCLUDED.entity_type,
                content_hash=EXCLUDED.content_hash,
                updated_at=NOW()
        """, (
            mde_id,
            page['url'],
            page['title'],
            page.get('description', ''),
            content,
            entity_type,
            content_hash
        ))
        self.log('info', f"Page upserted for URL: {page['url']}")

    def _process_related_vulns(self, cur, tool_id, related_vulns):
        count = 0
        for rv in related_vulns:
            try:
                rv = sanitize_for_db(rv, logger=self.logger)
                if not rv.get('vulnerability_ref'):
                    self.log('warning', f"Skipping related_vulnerability with missing ref for tool_id {tool_id}")
                    continue
                cur.execute("""
                    INSERT INTO tool_related_vulnerabilities (tool_id, vulnerability_ref, reference_type)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (tool_id, rv['vulnerability_ref'], rv['reference_type']))
                self.log('info', f"Inserted related_vulnerability: {rv['vulnerability_ref']} for tool_id {tool_id}")
                count += 1
            except Exception as e:
                self.log('warning', f"Failed to insert related_vulnerability: {e}")
        return count

    def _process_commands(self, cur, tool_id, commands):
        count = 0
        for c in commands:
            try:
                c = sanitize_for_db(c, logger=self.logger)
                if not c.get('name'):
                    self.log('warning', f"Skipping command with missing name for tool_id {tool_id}")
                    continue
                cur.execute("""
                    INSERT INTO tool_commands (tool_id, name, description, syntax)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tool_id, name) DO UPDATE SET
                        description=COALESCE(NULLIF(EXCLUDED.description, ''), tool_commands.description),
                        syntax=COALESCE(NULLIF(EXCLUDED.syntax, ''), tool_commands.syntax),
                        updated_at=NOW()
                """, (tool_id, c['name'], self.encrypt(c.get('description')), self.encrypt(c.get('syntax'))))
                self.log('info', f"Inserted/updated command: {c['name']} for tool_id {tool_id}")
                # PATCH: Insert/update options/flags/variables
                cur.execute("SELECT id FROM tool_commands WHERE tool_id = %s AND name = %s", (tool_id, c['name']))
                cmd_row = cur.fetchone()
                if not cmd_row:
                    self.log('warning', f"No command_id found for command {c['name']} (tool_id {tool_id})")
                    continue
                cmd_id = cmd_row[0]
                for o in c.get('options', []):
                    try:
                        if not o.get('name'):
                            self.log('warning', f"Skipping command_option with missing name for command_id {cmd_id}")
                            continue
                        opt_type = o.get('type')
                        if opt_type is None:
                            if o.get('required') is False and not o.get('default') and not o.get('example'):
                                opt_type = 'flag'
                            elif o.get('name').startswith('<') and o.get('name').endswith('>'):
                                opt_type = 'variable'
                            else:
                                opt_type = 'option'
                        for k, v in o.items():
                            if isinstance(v, str):
                                o[k] = remove_null_bytes(v, field_name=k, logger=self.logger)
                        cur.execute("""
                            INSERT INTO tool_command_options (command_id, name, description, required, type, default, example)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (command_id, name) DO UPDATE SET
                                description=COALESCE(NULLIF(EXCLUDED.description, ''), tool_command_options.description),
                                required=COALESCE(EXCLUDED.required, tool_command_options.required),
                                type=COALESCE(NULLIF(EXCLUDED.type, ''), tool_command_options.type),
                                default=COALESCE(NULLIF(EXCLUDED.default, ''), tool_command_options.default),
                                example=COALESCE(NULLIF(EXCLUDED.example, ''), tool_command_options.example),
                                updated_at=NOW()
                        """, (cmd_id, o['name'], self.encrypt(o.get('description')), o.get('required'), opt_type, o.get('default'), self.encrypt(o.get('example'))))
                        self.log('info', f"Inserted/updated command_option: {o['name']} for command_id {cmd_id}")
                    except Exception as e:
                        self.log('warning', f"Failed to insert command_option: {e}")
                ex_values = [(tool_id, self.encrypt(ex)) for ex in c.get('examples', []) if ex]
                if ex_values:
                    try:
                        cur.executemany("""
                            INSERT INTO tool_examples (tool_id, example)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING
                        """, ex_values)
                        self.log('info', f"Inserted {len(ex_values)} command examples for tool_id {tool_id}")
                    except Exception as e:
                        self.log('warning', f"Failed to insert command examples: {e}")
                count += 1
            except Exception as e:
                self.log('warning', f"Failed to insert command: {e}")
        return count

    def _process_modules(self, cur, tool_id, modules):
        count = 0
        for m in modules:
            try:
                if not m.get('name'):
                    self.log('warning', f"Skipping module with missing name for tool_id {tool_id}")
                    continue
                cur.execute("""
                    INSERT INTO tool_modules (tool_id, name, type, description)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tool_id, name) DO UPDATE SET
                        type=EXCLUDED.type,
                        description=EXCLUDED.description,
                        updated_at=NOW()
                """, (tool_id, m['name'], m.get('type'), self.encrypt(m.get('description'))))
                self.log('info', f"Inserted/updated module: {m['name']} for tool_id {tool_id}")
                cur.execute("SELECT id FROM tool_modules WHERE tool_id = %s AND name = %s", (tool_id, m['name']))
                mod_row = cur.fetchone()
                if not mod_row:
                    self.log('warning', f"No module_id found for module {m['name']} (tool_id {tool_id})")
                    continue
                mod_id = mod_row[0]
                opt_values = []
                for o in m.get('options', []):
                    try:
                        if not o.get('name'):
                            self.log('warning', f"Skipping module_option with missing name for module_id {mod_id}")
                            continue
                        for k, v in o.items():
                            if isinstance(v, str):
                                o[k] = remove_null_bytes(v, field_name=k, logger=self.logger)
                        opt_values.append((mod_id, o['name'], self.encrypt(o.get('description')), o.get('required'), o.get('type'), o.get('default'), self.encrypt(o.get('example'))))
                    except Exception as e:
                        self.log('warning', f"Failed to prepare module_option: {e}")
                if opt_values:
                    try:
                        cur.executemany("""
                            INSERT INTO tool_module_options (module_id, name, description, required, type, default, example)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (module_id, name) DO UPDATE SET
                                description=EXCLUDED.description,
                                required=EXCLUDED.required,
                                type=EXCLUDED.type,
                                default=EXCLUDED.default,
                                example=EXCLUDED.example,
                                updated_at=NOW()
                        """, opt_values)
                        self.log('info', f"Inserted/updated {len(opt_values)} module_options for module_id {mod_id}")
                    except Exception as e:
                        self.log('warning', f"Failed to insert module_options: {e}")
                ex_values = [(tool_id, self.encrypt(ex)) for ex in m.get('examples', []) if ex]
                if ex_values:
                    try:
                        cur.executemany("""
                            INSERT INTO tool_examples (tool_id, example)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING
                        """, ex_values)
                        self.log('info', f"Inserted {len(ex_values)} module examples for tool_id {tool_id}")
                    except Exception as e:
                        self.log('warning', f"Failed to insert module examples: {e}")
                count += 1
            except Exception as e:
                self.log('warning', f"Failed to insert module: {e}")
        return count

    def _process_workflows(self, cur, tool_id, workflows):
        count = 0
        for wf in workflows:
            try:
                if not wf.get('name'):
                    continue
                cur.execute("""
                    INSERT INTO tool_workflows (tool_id, name)
                    VALUES (%s, %s)
                    ON CONFLICT (tool_id, name) DO UPDATE SET name=EXCLUDED.name, updated_at=NOW()
                """, (tool_id, wf['name']))
                self.log('info', f"Inserted/updated workflow: {wf['name']} for tool_id {tool_id}")
                cur.execute("SELECT id FROM tool_workflows WHERE tool_id = %s AND name = %s", (tool_id, wf['name']))
                wf_row = cur.fetchone()
                if not wf_row:
                    self.log('warning', f"No workflow_id found for workflow {wf['name']} (tool_id {tool_id})")
                    continue
                wf_id = wf_row[0]
                step_values = [(wf_id, i+1, self.encrypt(step)) for i, step in enumerate(wf.get('steps', [])) if step]
                if step_values:
                    try:
                        cur.executemany("""
                            INSERT INTO tool_workflow_steps (workflow_id, step_number, step_text)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (workflow_id, step_number) DO UPDATE SET step_text=EXCLUDED.step_text, updated_at=NOW()
                        """, step_values)
                        self.log('info', f"Inserted/updated {len(step_values)} workflow_steps for workflow_id {wf_id}")
                    except Exception as e:
                        self.log('warning', f"Failed to insert workflow_steps: {e}")
                count += 1
            except Exception as e:
                self.log('warning', f"Failed to insert workflow: {e}")
        return count

    def _process_troubleshooting(self, cur, tool_id, troubleshooting):
        count = 0
        t_values = [(tool_id, self.encrypt(t['issue']), self.encrypt(t['solution'])) for t in troubleshooting if t.get('issue')]
        if t_values:
            try:
                cur.executemany("""
                    INSERT INTO tool_troubleshooting (tool_id, issue, solution)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, t_values)
                self.log('info', f"Inserted {len(t_values)} troubleshooting records for tool_id {tool_id}")
                count = len(t_values)
            except Exception as e:
                self.log('warning', f"Failed to insert troubleshooting records: {e}")
        return count

    def _process_external_links(self, cur, tool_id, links, medusa_id):
        count = 0
        l_values = []
        for l in links:
            try:
                if isinstance(l, str):
                    link_url = l
                    link_title = None
                    parent_mde_id = medusa_id
                elif isinstance(l, dict):
                    link_url = l.get('link') or l.get('url')
                    link_title = l.get('title')
                    parent_mde_id = l.get('parent_mde_id', medusa_id)
                else:
                    continue
                if not link_title:
                    link_title = None
                if isinstance(l, dict):
                    for k, v in l.items():
                        if isinstance(v, str):
                            l[k] = remove_null_bytes(v, field_name=k, logger=self.logger)
                elif isinstance(l, str):
                    l = remove_null_bytes(l, field_name='external_link', logger=self.logger)
                l_values.append((tool_id, link_url, link_title, parent_mde_id))
            except Exception as e:
                self.log('warning', f"Failed to prepare external_link: {e}")
        if l_values:
            try:
                cur.executemany("""
                    INSERT INTO tool_external_links (tool_id, link, title, parent_mde_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tool_id, link) DO UPDATE SET
                        title=COALESCE(NULLIF(EXCLUDED.title, ''), tool_external_links.title),
                        parent_mde_id=COALESCE(NULLIF(EXCLUDED.parent_mde_id, ''), tool_external_links.parent_mde_id),
                        updated_at=NOW()
                """, l_values)
                self.log('info', f"Inserted/updated {len(l_values)} external links for tool_id {tool_id}")
                count = len(l_values)
            except Exception as e:
                self.log('warning', f"Failed to insert external links: {e}")
        return count

    def _process_supported_os(self, cur, tool_id, supported_os_list):
        count = 0
        for os_entry in supported_os_list:
            try:
                if isinstance(os_entry, str):
                    os_name = os_entry
                    os_version = None
                    min_version = None
                    max_version = None
                elif isinstance(os_entry, dict):
                    os_name = os_entry.get('name')
                    os_version = os_entry.get('version')
                    min_version = os_entry.get('min_version')
                    max_version = os_entry.get('max_version')
                else:
                    continue
                cur.execute("SELECT os_id FROM operating_systems WHERE os_name = %s AND (version = %s OR version IS NULL)", (os_name, os_version))
                row = cur.fetchone()
                if not row:
                    cur.execute("INSERT INTO operating_systems (os_name, version) VALUES (%s, %s) RETURNING os_id", (os_name, os_version))
                    os_id = cur.fetchone()[0]
                else:
                    os_id = row[0]
                cur.execute("""
                    INSERT INTO tool_supported_os (tool_id, os_id, min_version, max_version)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tool_id, os_id) DO UPDATE SET
                        min_version=COALESCE(NULLIF(EXCLUDED.min_version, ''), tool_supported_os.min_version),
                        max_version=COALESCE(NULLIF(EXCLUDED.max_version, ''), tool_supported_os.max_version)
                """, (tool_id, os_id, min_version, max_version))
                self.log('info', f"Linked tool_id {tool_id} to OS {os_name} (os_id={os_id}) version={os_version} min={min_version} max={max_version}")
                count += 1
            except Exception as e:
                self.log('warning', f"Failed to insert supported_os: {e}")
        return count

    def generate_medusa_id(self, tool_name: str, source_url: str) -> str:
        """
        Generates a deterministic medusa_id as MD5(tool_name + canonical_source_url).
        Handles None for tool_name and source_url.
        """
        tool_name = (tool_name or '').strip().lower()
        base = (tool_name + (source_url or '')).encode('utf-8')
        return hashlib.md5(base).hexdigest()

    def batch_write(self, items, cur=None):
        """
        Batch insert or update for a list of normalized tool data items.
        """
        # Implement batch DB logic here
        pass

    def rollback(self, cur=None):
        """
        Rollback the current transaction.
        """
        if cur:
            cur.connection.rollback()

    def manage_join_tables(self, cur, join_data):
        """
        Manage join tables for many-to-many relationships.
        """
        # Implement join table management logic here
        pass

    # TODO: Add methods for batch operations, rollback, and join table management as needed. 