from flask import Blueprint, jsonify
from medusa.src.database import get_db

bp = Blueprint('visualization', __name__)

@bp.route('/api/visualization/quality_stats')
def quality_stats():
    db = get_db()
    cur = db.cursor()
    # Tools breakdown
    cur.execute('SELECT COUNT(*), quality_rank FROM tools GROUP BY quality_rank')
    tool_ranks = {row[1]: row[0] for row in cur.fetchall()}
    cur.execute('SELECT COUNT(*) FROM tools')
    total_tools = cur.fetchone()[0]
    # Per-field completeness
    gold_fields = ['website', 'version', 'license', 'categories', 'tags', 'supported_os', 'usage_summary', 'installation_instructions']
    field_completeness = {}
    for f in gold_fields:
        cur.execute(f"SELECT COUNT(*) FROM tools WHERE {f} IS NOT NULL AND {f} <> ''")
        field_completeness[f] = round(100 * cur.fetchone()[0] / total_tools, 1) if total_tools else 0
    # Vulnerabilities breakdown
    cur.execute('SELECT COUNT(*), quality_rank FROM vulnerabilities GROUP BY quality_rank')
    vuln_ranks = {row[1]: row[0] for row in cur.fetchall()}
    cur.execute('SELECT COUNT(*) FROM vulnerabilities')
    total_vulns = cur.fetchone()[0]
    vuln_fields = ['cve_id', 'description', 'cvss_v3_base_score', 'references', 'affected_products', 'state', 'date_published', 'date_updated']
    vuln_field_completeness = {}
    for f in vuln_fields:
        cur.execute(f"SELECT COUNT(*) FROM vulnerabilities WHERE {f} IS NOT NULL AND {f} <> ''")
        vuln_field_completeness[f] = round(100 * cur.fetchone()[0] / total_vulns, 1) if total_vulns else 0
    return jsonify({
        'tool_ranks': tool_ranks,
        'total_tools': total_tools,
        'tool_field_completeness': field_completeness,
        'vuln_ranks': vuln_ranks,
        'total_vulns': total_vulns,
        'vuln_field_completeness': vuln_field_completeness
    }) 