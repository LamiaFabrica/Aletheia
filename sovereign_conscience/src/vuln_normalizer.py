import re
from typing import Dict, Any

def normalize_vulnerability(raw_vuln_data: Dict[str, Any]) -> Dict[str, Any]:
    # Gold standard fields for vulnerabilities
    gold_fields = [
        'cve_id', 'description', 'cvss_v3_base_score', 'references', 'affected_products', 'state', 'date_published', 'date_updated'
    ]
    vuln = dict(raw_vuln_data)
    present = 0
    for f in gold_fields:
        v = vuln.get(f)
        if isinstance(v, list):
            if v and any(v):
                present += 1
        elif v:
            present += 1
    vuln['data_quality_score'] = round(100 * present / len(gold_fields), 1)
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
    vuln['quality_rank'] = get_quality_rank(vuln['data_quality_score'])
    return vuln 