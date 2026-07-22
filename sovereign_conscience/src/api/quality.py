from flask import Blueprint, jsonify
from medusa.src.database import get_db

bp = Blueprint('quality', __name__)

S_RANK_FIELDS = {
    'tools': ['website', 'version', 'license', 'categories', 'tags', 'supported_os', 'usage_summary', 'installation_instructions'],
    'vulnerabilities': ['cve_id', 'description', 'cvss_v3_base_score', 'references', 'affected_products', 'state', 'date_published', 'date_updated']
}

@bp.route('/api/quality/missing_fields/<table>/<int:record_id>')
def missing_fields(table, record_id):
    db = get_db()
    cur = db.cursor()
    if table not in S_RANK_FIELDS:
        return jsonify({'error': 'Invalid table'}), 400
    cur.execute(f'SELECT * FROM {table} WHERE id = %s', (record_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({'error': 'Record not found'}), 404
    fields = S_RANK_FIELDS[table]
    missing = []
    for f in fields:
        v = row[f] if f in row else None
        if isinstance(v, list):
            if not v or not any(v):
                missing.append(f)
        elif v is None or v == '' or v == '{}':
            missing.append(f)
    score = round(100 * (len(fields) - len(missing)) / len(fields), 1)
    if score >= 95:
        rank = 'S'
    elif score >= 90:
        rank = 'A'
    elif score >= 80:
        rank = 'B'
    elif score >= 70:
        rank = 'C'
    elif score >= 60:
        rank = 'D'
    else:
        rank = 'F'
    return jsonify({'missing': missing, 'rank': rank, 'score': score}) 