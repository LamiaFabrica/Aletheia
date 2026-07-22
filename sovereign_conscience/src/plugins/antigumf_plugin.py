import logging
from typing import Any, Dict, List, Optional
import re
import json
import traceback

"""
AntiGumfPlugin: Medusa plugin for anti-gumf (data hygiene, deduplication, filtering, audit, and consistency checks).

MUST DO (next refactor):
- Refactor any large write/insert/update methods into smaller, private helpers.
- Ensure one logical transaction per tool write, with commit at the end of success (rely on Database wrapper or explicit commit/rollback as appropriate).
- Only encrypt fields that are truly sensitive; metadata fields (tool_name, categories, tags, supported_os) should be plaintext for search/filter.
- Replace all print() with self.log().
- Ensure all ON CONFLICT ... DO UPDATE statements set updated_at=NOW() where relevant.
- Add initial checks for the structure of normalized_tool_data in all entry points.
"""

class AntiGumfPlugin:
    def __init__(self, db):
        self.db = db
        self.enabled = True
        self.logger = logging.getLogger('AntiGumfPlugin')
        self.rules = []
        self.filters = []
        self.tags = []
        self.categories = []
        self.load_all()

    def load_all(self):
        try:
            self.rules = self._load_rules()
            self.filters = self._load_filters()
            self.tags = self._load_tags()
            self.categories = self._load_categories()
        except Exception as e:
            self.logger.error(f"[AntiGumf] Failed to load rules/filters: {e}")
            self.enabled = False

    def _load_rules(self) -> List[Dict[str, Any]]:
        try:
            self.db.cursor.execute("SELECT * FROM antigumf_rules WHERE enabled = TRUE ORDER BY priority ASC, id ASC")
            return self.db.cursor.fetchall()
        except Exception as e:
            self.logger.error(f"[AntiGumf] Error loading rules: {e}")
            return []

    def _load_filters(self) -> List[Dict[str, Any]]:
        try:
            self.db.cursor.execute("SELECT * FROM antigumf_filters WHERE enabled = TRUE")
            return self.db.cursor.fetchall()
        except Exception as e:
            self.logger.error(f"[AntiGumf] Error loading filters: {e}")
            return []

    def _load_tags(self) -> List[Dict[str, Any]]:
        try:
            self.db.cursor.execute("SELECT * FROM antigumf_tags WHERE enabled = TRUE")
            return self.db.cursor.fetchall()
        except Exception as e:
            self.logger.error(f"[AntiGumf] Error loading tags: {e}")
            return []

    def _load_categories(self) -> List[Dict[str, Any]]:
        try:
            self.db.cursor.execute("SELECT * FROM antigumf_categories WHERE enabled = TRUE")
            return self.db.cursor.fetchall()
        except Exception as e:
            self.logger.error(f"[AntiGumf] Error loading categories: {e}")
            return []

    def filter(self, record: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main entry point: filter a record. Returns a dict with result, reason, and any actions taken.
        """
        # Initial structure check
        self.logger.debug(f"[AntiGumf] filter() received record: {json.dumps(record, default=str)[:1000]}")
        if not isinstance(record, dict):
            self.logger.error("[AntiGumf] Input record is not a dict")
            return {"result": "error", "reason": "Input record is not a dict"}
        if not self.enabled:
            return {"result": "skipped", "reason": "AntiGumf disabled"}
        try:
            record = self._decrypt_if_needed(record)
            self.logger.debug(f"[AntiGumf] After decryption: {json.dumps(record, default=str)[:1000]}")
            try:
                result, reason, rule_id = self._apply_rules(record, context)
                self.logger.debug(f"[AntiGumf] _apply_rules result: {result}, reason: {reason}, rule_id: {rule_id}")
            except Exception as e:
                self.logger.error(f"[AntiGumf] Exception in _apply_rules: {e}", exc_info=True)
                raise
            try:
                dedup_result = self._deduplication(record)
                self.logger.debug(f"[AntiGumf] _deduplication result: {dedup_result}")
            except Exception as e:
                self.logger.error(f"[AntiGumf] Exception in _deduplication: {e}", exc_info=True)
                dedup_result = 'error'
            try:
                fuzzy_result = self._fuzzy_deduplication(record)
                self.logger.debug(f"[AntiGumf] _fuzzy_deduplication result: {fuzzy_result}")
            except Exception as e:
                self.logger.error(f"[AntiGumf] Exception in _fuzzy_deduplication: {e}", exc_info=True)
                fuzzy_result = 'error'
            try:
                relevance = self._relevance_score(record, context)
                self.logger.debug(f"[AntiGumf] _relevance_score result: {relevance}")
            except Exception as e:
                self.logger.error(f"[AntiGumf] Exception in _relevance_score: {e}", exc_info=True)
                relevance = 'error'
            try:
                self._log_audit_event(record, result, reason, rule_id, dedup_result, fuzzy_result, relevance)
            except Exception as e:
                self.logger.error(f"[AntiGumf] Exception in _log_audit_event: {e}", exc_info=True)
            if result == 'filtered' or dedup_result == 'duplicate' or fuzzy_result == 'near-duplicate' or relevance == 'low':
                try:
                    self._quarantine_record(record, reason or dedup_result or fuzzy_result or 'low relevance')
                except Exception as e:
                    self.logger.error(f"[AntiGumf] Exception in _quarantine_record: {e}", exc_info=True)
            self.logger.debug(f"[AntiGumf] filter() returning: result={result}, reason={reason}, dedup={dedup_result}, fuzzy={fuzzy_result}, relevance={relevance}")
            return {"result": result, "reason": reason, "rule_id": rule_id, "dedup": dedup_result, "fuzzy": fuzzy_result, "relevance": relevance}
        except Exception as e:
            self.logger.error(f"[AntiGumf] Filter error: {e}", exc_info=True)
            return {"result": "error", "reason": str(e)}

    def _decrypt_if_needed(self, record: Dict[str, Any]) -> Dict[str, Any]:
        # Stub: implement decryption logic as needed
        return record

    def _apply_rules(self, record: Dict[str, Any], context: Optional[Dict[str, Any]]) -> (str, str, Optional[int]):
        """
        Apply all rules to the record, supporting conditional logic and priorities.
        Returns (result, reason, rule_id) where result is 'allowed' or 'filtered'.
        Only uses columns that exist in the tools table for no_exact_match rules.
        """
        import json
        for rule in self.rules:
            field = rule.get('field')
            rule_type = rule.get('rule_type')
            value = rule.get('value')
            condition = rule.get('condition')
            action = rule.get('action', 'filter')
            logic_group = rule.get('logic_group')
            priority = rule.get('priority', 1)
            rule_id = rule.get('id')

            # Evaluate condition if present
            if condition and not self._evaluate_condition(condition, record):
                continue

            # Field-specific rule application
            field_value = record.get(field) if field != '*' else record
            if rule_type == 'regex' and field_value:
                if not re.match(value, str(field_value)):
                    return 'filtered', f"Field '{field}' failed regex: {value}", rule_id
            elif rule_type == 'min_length' and field_value:
                if len(str(field_value)) < int(value):
                    return 'filtered', f"Field '{field}' below min length {value}", rule_id
            elif rule_type == 'blacklist' and field_value:
                if str(field_value).lower() in [v.strip().lower() for v in value.split(',')]:
                    return 'filtered', f"Field '{field}' is blacklisted value", rule_id
            elif rule_type == 'unique' and field_value:
                # Check for uniqueness in DB
                self.db.cursor.execute(f"SELECT COUNT(*) FROM {rule['value']} WHERE {field} = %s", (field_value,))
                count = list(self.db.cursor.fetchone().values())[0]
                if count > 0:
                    return 'filtered', f"Duplicate value for '{field}'", rule_id
            elif rule_type == 'no_exact_match' and field_value:
                # Check for exact match in DB (all fields)
                # PATCH: Only use valid columns
                valid_columns = set(self._get_table_columns(rule['value']))
                filtered_record = {k: v for k, v in record.items() if k in valid_columns}
                sql_values = []
                for v in filtered_record.values():
                    if isinstance(v, (dict, list)):
                        sql_values.append(json.dumps(v, sort_keys=True))
                    else:
                        sql_values.append(v)
                placeholders = ' AND '.join([f"{k} = %s" for k in filtered_record.keys()])
                if not placeholders:
                    continue
                sql = f"SELECT COUNT(*) FROM {rule['value']} WHERE {placeholders}"
                self.db.cursor.execute(sql, tuple(sql_values))
                count = list(self.db.cursor.fetchone().values())[0]
                if count > 0:
                    return 'filtered', "Exact duplicate record", rule_id
            # Add more rule types as needed
            # If action is 'allow', skip to next rule if not matched
        return 'allowed', '', None

    def _evaluate_condition(self, condition: str, record: Dict[str, Any]) -> bool:
        """
        Evaluate a simple condition string like 'field=version AND field=description'.
        Supports AND/OR logic for now. Extend as needed.
        """
        # Split by AND/OR
        if ' AND ' in condition:
            parts = condition.split(' AND ')
            return all(self._eval_single_condition(p, record) for p in parts)
        elif ' OR ' in condition:
            parts = condition.split(' OR ')
            return any(self._eval_single_condition(p, record) for p in parts)
        else:
            return self._eval_single_condition(condition, record)

    def _eval_single_condition(self, cond: str, record: Dict[str, Any]) -> bool:
        # Example: 'field=version' means version must be present and non-empty
        if cond.startswith('field='):
            field = cond.split('=')[1].strip()
            return bool(record.get(field))
        # Extend for more complex conditions as needed
        return False

    def _deduplication(self, record: Dict[str, Any]) -> str:
        """
        Check for exact duplicates in the target table based on unique fields and full-record match.
        Returns 'duplicate' if found, otherwise 'unique'.
        Only uses columns that exist in the tools table.
        """
        import json
        # Get only valid columns for the tools table
        valid_columns = set(self._get_table_columns('tools'))
        # Only use keys that are valid columns
        filtered_record = {k: v for k, v in record.items() if k in valid_columns}
        # Check for unique fields (medusa_id, tool_name)
        unique_fields = ['medusa_id', 'tool_name']
        for field in unique_fields:
            value = record.get(field)
            if value:
                try:
                    self.db.cursor.execute(
                        f"SELECT COUNT(*) FROM tools WHERE {field} = %s", (value,)
                    )
                    count = list(self.db.cursor.fetchone().values())[0]
                    if count > 0:
                        return 'duplicate'
                except Exception as e:
                    self.logger.error(f"[AntiGumf] Deduplication error for field {field}: {e}")
        # Check for full-record duplicate (all fields)
        try:
            # PATCH: Serialize dict/list values to JSON for SQL
            sql_values = []
            for v in filtered_record.values():
                if isinstance(v, (dict, list)):
                    sql_values.append(json.dumps(v, sort_keys=True))
                else:
                    sql_values.append(v)
            placeholders = ' AND '.join([f"{k} = %s" for k in filtered_record.keys()])
            if not placeholders:
                return 'unique'
            sql = f"SELECT COUNT(*) FROM tools WHERE {placeholders}"
            self.db.cursor.execute(sql, tuple(sql_values))
            count = list(self.db.cursor.fetchone().values())[0]
            if count > 0:
                return 'duplicate'
        except Exception as e:
            self.logger.error(f"[AntiGumf] Full-record deduplication error: {e}")
        return 'unique'

    def _fuzzy_deduplication(self, record: Dict[str, Any]) -> str:
        """
        Fuzzy deduplication using SimHash for tool descriptions.
        Stores and compares SimHash values in antigumf_similarity_index.
        Returns 'near-duplicate' if a similar record is found, otherwise 'not-near-duplicate'.
        """
        try:
            description = record.get('description', '')
            medusa_id = record.get('medusa_id')
            if not description or not medusa_id:
                return 'not-near-duplicate'
            simhash = self._simhash(description)
            # Check for near-duplicates in antigumf_similarity_index
            self.db.cursor.execute(
                "SELECT entity_id, simhash FROM antigumf_similarity_index WHERE entity_type = %s",
                ('tool',)
            )
            for row in self.db.cursor.fetchall():
                other_id = row['entity_id']
                other_simhash = int(row['simhash'])
                similarity = self._simhash_similarity(simhash, other_simhash)
                if similarity >= 0.90 and other_id != medusa_id:
                    # Log similarity in quarantine/audit if needed
                    record['near_duplicate_of'] = other_id
                    record['similarity_score'] = similarity
                    return 'near-duplicate'
            # Store/update simhash for this record
            self.db.cursor.execute(
                "INSERT INTO antigumf_similarity_index (entity_type, entity_id, simhash, last_updated) "
                "VALUES (%s, %s, %s, NOW()) "
                "ON CONFLICT (entity_type, entity_id) DO UPDATE SET simhash = EXCLUDED.simhash, last_updated = NOW()",
                ('tool', medusa_id, str(simhash))
            )
            self.db.conn.commit()
            return 'not-near-duplicate'
        except Exception as e:
            self.logger.error(f"[AntiGumf] Fuzzy deduplication error: {e}")
            return 'not-near-duplicate'

    def _simhash(self, text: str) -> int:
        """
        Simple SimHash implementation for demonstration. For production, use a library.
        """
        from hashlib import md5
        # Tokenize and hash
        tokens = text.lower().split()
        v = [0] * 64
        for token in tokens:
            h = int(md5(token.encode('utf-8')).hexdigest(), 16)
            for i in range(64):
                bitmask = 1 << i
                v[i] += 1 if h & bitmask else -1
        fingerprint = 0
        for i in range(64):
            if v[i] >= 0:
                fingerprint |= 1 << i
        return fingerprint

    def _simhash_similarity(self, hash1: int, hash2: int) -> float:
        """
        Returns similarity as a float between 0 and 1 (1 = identical).
        """
        x = hash1 ^ hash2
        dist = bin(x).count('1')
        return 1 - dist / 64.0

    def _relevance_score(self, record: Dict[str, Any], context: Optional[Dict[str, Any]]) -> str:
        """
        Heuristic-based relevance scoring. Returns 'high' or 'low'.
        Stores the score in the record for audit/quarantine.
        Prepares for future AI model integration.
        """
        try:
            description = record.get('description', '')
            keywords = context.get('keywords', []) if context else []
            min_length = 30
            min_keyword_matches = 1 if keywords else 0
            # Heuristic: score based on length and keyword presence
            score = 0
            if len(description) >= min_length:
                score += 0.5
            if keywords:
                matches = sum(1 for kw in keywords if kw.lower() in description.lower())
                if matches >= min_keyword_matches:
                    score += 0.5
            # Store the score for audit/quarantine
            record['relevance_score'] = score
            if score < 0.5:
                return 'low'
            return 'high'
        except Exception as e:
            self.logger.error(f"[AntiGumf] Relevance scoring error: {e}")
            record['relevance_score'] = 0
            return 'low'

    def _log_audit_event(self, record, result, reason, rule_id, dedup_result, fuzzy_result, relevance):
        try:
            self._insert_audit_log(result, rule_id, record.get('medusa_id'), record.get('tool_name'), reason)
        except Exception as e:
            self.logger.error(f"[AntiGumf] Audit log error: {e}")

    def _insert_audit_log(self, event_type, rule_id, medusa_id, tool_name, reason):
        self.db.cursor.execute(
            """
            INSERT INTO antigumf_audit_log (event_type, rule_id, medusa_id, tool_name, field, value, reason, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (event_type, rule_id, medusa_id, tool_name, None, None, reason, 'antigumf')
        )
        self.db.conn.commit()

    def _quarantine_record(self, record, reason):
        try:
            self._insert_quarantine(record, reason)
        except Exception as e:
            self.logger.error(f"[AntiGumf] Quarantine error: {e}")

    def _insert_quarantine(self, record, reason):
        self.db.cursor.execute(
            """
            INSERT INTO antigumf_quarantine (raw_data, reason, source, timestamp, status)
            VALUES (%s, %s, %s, NOW(), %s)
            """,
            (str(record), reason, 'antigumf', 'pending')
        )
        self.db.conn.commit()

    def _get_table_columns(self, table_name):
        try:
            self.db.cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position
            """, (table_name,))
            rows = self.db.cursor.fetchall()
            if not rows or not isinstance(rows, list):
                self.logger.error(f"[AntiGumf] No columns found for table {table_name}. Got: {rows}")
                raise Exception(f"No columns found for table {table_name}")
            columns = [row['column_name'] for row in rows]
            self.logger.info(f"[AntiGumf] Columns for {table_name}: {columns}")
            return columns
        except Exception as e:
            self.logger.error(f"[AntiGumf] Failed to get columns for {table_name}: {e}\n{traceback.format_exc()}")
            raise

    def _sanitize_import_dict(self, data, table_name):
        columns = self._get_table_columns(table_name)
        return {k: v for k, v in data.items() if k in columns}

    def import_rules(self, rules_json: Any) -> Dict[str, Any]:
        results = {'success': [], 'failed': []}
        rules = rules_json if isinstance(rules_json, list) else [rules_json]
        try:
            columns = self._get_table_columns('antigumf_rules')
            self.logger.info(f"[AntiGumf] Importing rules with columns: {columns}")
        except Exception as e:
            results['failed'].append({'error': str(e)})
            return results
        for rule in rules:
            try:
                self.logger.debug(f"[AntiGumf] Importing rule: {rule}")
                db_rule = {k: rule.get(k) for k in columns if k in rule and k != 'id'}
                if 'rule_book_id' in columns:
                    db_rule['rule_book_id'] = rule.get('id')
                if 'description' in columns and not db_rule.get('description'):
                    db_rule['description'] = rule.get('description', rule.get('name', ''))
                if 'enabled' in columns:
                    db_rule['enabled'] = rule.get('enabled', True)
                if 'priority' in columns:
                    db_rule['priority'] = rule.get('priority', 1)
                if 'value' in columns and isinstance(db_rule.get('value'), (dict, list)):
                    db_rule['value'] = json.dumps(db_rule['value'])
                db_rule = {k: v for k, v in db_rule.items() if v is not None}
                fields = ', '.join(db_rule.keys())
                placeholders = ', '.join(['%s'] * len(db_rule))
                updates = ', '.join([f"{k} = EXCLUDED.{k}" for k in db_rule.keys() if k != 'rule_book_id'])
                if 'updated_at' in columns:
                    updates += ', updated_at=NOW()'
                sql = f"INSERT INTO antigumf_rules ({fields}) VALUES ({placeholders}) ON CONFLICT (rule_book_id) DO UPDATE SET {updates} RETURNING rule_book_id"
                self.db.cursor.execute(sql, tuple(db_rule.values()))
                rule_id = self.db.cursor.fetchone()['rule_book_id']
                results['success'].append(rule_id)
            except Exception as e:
                self.logger.error(f"EXCEPTION: {e}\n{traceback.format_exc()}")
                self.db.conn.rollback()
                self.logger.error(f"[AntiGumf] Failed to import rule: {rule} | Error: {e}\n{traceback.format_exc()}")
                results['failed'].append({'rule': rule, 'error': str(e), 'trace': traceback.format_exc()})
        self.db.conn.commit()
        return results

    def import_filters(self, filters_json: Any) -> Dict[str, Any]:
        results = {'success': [], 'failed': []}
        filters = filters_json if isinstance(filters_json, list) else [filters_json]
        try:
            columns = self._get_table_columns('antigumf_filters')
            self.logger.info(f"[AntiGumf] Importing filters with columns: {columns}")
        except Exception as e:
            results['failed'].append({'error': str(e)})
            return results
        for filt in filters:
            try:
                self.logger.debug(f"[AntiGumf] Importing filter: {filt}")
                db_filter = {k: filt.get(k) for k in columns if k in filt}
                if 'enabled' in columns:
                    db_filter['enabled'] = filt.get('enabled', True)
                if 'priority' in columns:
                    db_filter['priority'] = filt.get('priority', 1)
                if 'value' in columns and isinstance(db_filter.get('value'), (dict, list)):
                    db_filter['value'] = json.dumps(db_filter['value'])
                fields = ', '.join(db_filter.keys())
                placeholders = ', '.join(['%s'] * len(db_filter))
                updates = ', '.join([f"{k} = EXCLUDED.{k}" for k in db_filter.keys() if k != 'id'])
                if 'updated_at' in columns:
                    updates += ', updated_at=NOW()'
                sql = f"INSERT INTO antigumf_filters ({fields}) VALUES ({placeholders}) ON CONFLICT (id) DO UPDATE SET {updates} RETURNING id"
                self.db.cursor.execute(sql, tuple(db_filter.values()))
                filter_id = self.db.cursor.fetchone()['id']
                results['success'].append(filter_id)
            except Exception as e:
                self.logger.error(f"EXCEPTION: {e}\n{traceback.format_exc()}")
                self.db.conn.rollback()
                self.logger.error(f"[AntiGumf] Failed to import filter: {filt} | Error: {e}\n{traceback.format_exc()}")
                results['failed'].append({'filter': filt, 'error': str(e), 'trace': traceback.format_exc()})
        self.db.conn.commit()
        return results

    def import_tags(self, tags_json: Any) -> Dict[str, Any]:
        results = {'success': [], 'failed': []}
        tags = tags_json if isinstance(tags_json, list) else [tags_json]
        try:
            columns = self._get_table_columns('antigumf_tags')
            self.logger.info(f"[AntiGumf] Importing tags with columns: {columns}")
        except Exception as e:
            results['failed'].append({'error': str(e)})
            return results
        for tag in tags:
            try:
                self.logger.debug(f"[AntiGumf] Importing tag: {tag}")
                db_tag = {k: tag.get(k) for k in columns if k in tag}
                if 'tag' in columns and not db_tag.get('tag'):
                    db_tag['tag'] = tag.get('name')
                if 'enabled' in columns:
                    db_tag['enabled'] = tag.get('enabled', True)
                fields = ', '.join(db_tag.keys())
                placeholders = ', '.join(['%s'] * len(db_tag))
                updates = ', '.join([f"{k} = EXCLUDED.{k}" for k in db_tag.keys() if k != 'tag'])
                if 'updated_at' in columns:
                    updates += ', updated_at=NOW()'
                sql = f"INSERT INTO antigumf_tags ({fields}) VALUES ({placeholders}) ON CONFLICT (tag) DO UPDATE SET {updates} RETURNING tag"
                self.db.cursor.execute(sql, tuple(db_tag.values()))
                tag_name = self.db.cursor.fetchone()['tag']
                results['success'].append(tag_name)
            except Exception as e:
                self.logger.error(f"EXCEPTION: {e}\n{traceback.format_exc()}")
                self.db.conn.rollback()
                self.logger.error(f"[AntiGumf] Failed to import tag: {tag} | Error: {e}\n{traceback.format_exc()}")
                results['failed'].append({'tag': tag, 'error': str(e), 'trace': traceback.format_exc()})
        self.db.conn.commit()
        return results

    def import_categories(self, categories_json: Any) -> Dict[str, Any]:
        results = {'success': [], 'failed': []}
        cats = categories_json if isinstance(categories_json, list) else [categories_json]
        try:
            columns = self._get_table_columns('antigumf_categories')
            self.logger.info(f"[AntiGumf] Importing categories with columns: {columns}")
        except Exception as e:
            results['failed'].append({'error': str(e)})
            return results
        for cat in cats:
            try:
                self.logger.debug(f"[AntiGumf] Importing category: {cat}")
                db_cat = {k: cat.get(k) for k in columns if k in cat}
                if 'category' in columns and not db_cat.get('category'):
                    db_cat['category'] = cat.get('name')
                if 'enabled' in columns:
                    db_cat['enabled'] = cat.get('enabled', True)
                fields = ', '.join(db_cat.keys())
                placeholders = ', '.join(['%s'] * len(db_cat))
                updates = ', '.join([f"{k} = EXCLUDED.{k}" for k in db_cat.keys() if k != 'category'])
                if 'updated_at' in columns:
                    updates += ', updated_at=NOW()'
                sql = f"INSERT INTO antigumf_categories ({fields}) VALUES ({placeholders}) ON CONFLICT (category) DO UPDATE SET {updates} RETURNING category"
                self.db.cursor.execute(sql, tuple(db_cat.values()))
                cat_name = self.db.cursor.fetchone()['category']
                results['success'].append(cat_name)
            except Exception as e:
                self.logger.error(f"EXCEPTION: {e}\n{traceback.format_exc()}")
                self.db.conn.rollback()
                self.logger.error(f"[AntiGumf] Failed to import category: {cat} | Error: {e}\n{traceback.format_exc()}")
                results['failed'].append({'category': cat, 'error': str(e), 'trace': traceback.format_exc()})
        self.db.conn.commit()
        return results

    def import_config(self, config_json: dict) -> dict:
        summary = {}
        try:
            if 'rules' in config_json:
                summary['rules'] = self.import_rules(config_json['rules'])
            if 'filters' in config_json:
                summary['filters'] = self.import_filters(config_json['filters'])
            if 'tags' in config_json:
                summary['tags'] = self.import_tags(config_json['tags'])
            if 'categories' in config_json:
                summary['categories'] = self.import_categories(config_json['categories'])
            if 'thresholds' in config_json:
                summary['thresholds'] = {}
                for k, v in config_json['thresholds'].items():
                    self.set_threshold(k, v)
                    summary['thresholds'][k] = 'set'
            self.load_all()
            self.logger.info(f"[AntiGumf] Bulk config import complete: {summary}")
        except Exception as e:
            self.logger.error(f"[AntiGumf] Bulk config import failed: {e}")
            summary['error'] = str(e)
        return summary

    def _cross_source_consistency(self, record: Dict[str, Any]) -> None:
        """
        Cross-source consistency flagging for tools (AGE4).
        Compares key fields for the same medusa_id from different sources.
        If contradictions are found, creates an entry in antigumf_consistency_review.
        """
        try:
            medusa_id = record.get('medusa_id')
            if not medusa_id:
                return
            key_fields = ['website', 'version', 'description']
            # Fetch all records for this medusa_id from antigumf_quarantine and tools
            self.db.cursor.execute(
                "SELECT source, raw_data->>'website' AS website, raw_data->>'version' AS version, raw_data->>'description' AS description "
                "FROM antigumf_quarantine WHERE raw_data->>'medusa_id' = %s UNION ALL "
                "SELECT 'tools' as source, website, version, description FROM tools WHERE medusa_id = %s",
                (medusa_id, medusa_id)
            )
            rows = self.db.cursor.fetchall()
            if len(rows) < 2:
                return  # No cross-source data to compare
            contradictions = {}
            sources = {}
            for field in key_fields:
                values = set()
                field_sources = {}
                for row in rows:
                    val = row[field]
                    src = row['source']
                    if val:
                        values.add(val)
                        field_sources.setdefault(val, []).append(src)
                if len(values) > 1:
                    contradictions[field] = list(values)
                    sources[field] = field_sources
            if contradictions:
                self.db.cursor.execute(
                    "INSERT INTO antigumf_consistency_review (entity_type, entity_id, field, conflicting_values, sources, status, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())",
                    ('tool', medusa_id, ','.join(contradictions.keys()),
                     str(contradictions), str(sources), 'pending')
                )
                self.db.conn.commit()
                self.logger.info(f"[AntiGumf] Consistency review created for {medusa_id}: {contradictions}")
        except Exception as e:
            self.logger.error(f"[AntiGumf] Consistency flagging error: {e}")

    # --- API CONTROL METHODS ---
    def get_status(self):
        return {
            'enabled': self.enabled,
            'paused': getattr(self, 'paused', {}),
            'thresholds': getattr(self, 'thresholds', {}),
            'rules_loaded': len(self.rules),
            'filters_loaded': len(self.filters),
            'tags_loaded': len(self.tags),
            'categories_loaded': len(self.categories),
        }

    def set_enabled(self, stage=None, enabled=True):
        if stage is None:
            self.enabled = enabled
        else:
            if not hasattr(self, 'stage_enabled'):
                self.stage_enabled = {}
            self.stage_enabled[stage] = enabled

    def set_paused(self, stage=None, paused=True):
        if not hasattr(self, 'paused'):
            self.paused = {}
        if stage is None:
            for s in ['deduplication', 'fuzzy', 'relevance', 'consistency']:
                self.paused[s] = paused
        else:
            self.paused[stage] = paused

    def set_threshold(self, stage, threshold):
        if not hasattr(self, 'thresholds'):
            self.thresholds = {}
        self.thresholds[stage] = threshold

    def reprocess_item(self, item_id):
        # Stub: reprocess a quarantined/filtered item by ID
        # You would fetch the item from antigumf_quarantine and re-run filter()
        try:
            with self.db.get_cursor() as cur:
                cur.execute("SELECT * FROM antigumf_quarantine WHERE id = %s", (item_id,))
                item = cur.fetchone()
                if not item:
                    return {'error': 'Item not found'}
                # Re-run filter logic (simplified)
                result = self.filter(item)
                return {'item_id': item_id, 'result': result}
        except Exception as e:
            return {'error': str(e)}

    def get_audit_log(self, limit=100):
        # Stub: fetch recent audit log entries
        try:
            with self.db.get_cursor() as cur:
                cur.execute("SELECT * FROM antigumf_audit_log ORDER BY timestamp DESC LIMIT %s", (limit,))
                return cur.fetchall()
        except Exception as e:
            return [{'error': str(e)}] 