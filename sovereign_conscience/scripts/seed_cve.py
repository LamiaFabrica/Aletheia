from src.database import Database
import zipfile
import json
import os
import random
import string

def generate_mde_id(existing_ids):
    while True:
        mde_id = 'MDE_' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
        if mde_id not in existing_ids:
            return mde_id

def ensure_mde_id_column(db):
    db.cursor.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='vulnerabilities' AND column_name='mde_id'
            ) THEN
                ALTER TABLE vulnerabilities ADD COLUMN mde_id TEXT UNIQUE;
            END IF;
        END
        $$;
    """)
    db.conn.commit()

def main():
    db = Database(
        db_name="ai-test",
        db_user="medusa",
        db_password="EN5FrsEFhm!*",
        db_host="localhost",
        db_port="5432"
    )
    ensure_mde_id_column(db)
    existing_mde_ids = set()
    db.cursor.execute("SELECT mde_id FROM vulnerabilities WHERE mde_id IS NOT NULL")
    for row in db.cursor.fetchall():
        existing_mde_ids.add(row['mde_id'])

    zip_path = os.path.join(os.path.dirname(__file__), '../../cvelistV5-main.zip')
    if not os.path.exists(zip_path):
        print(f"CVE zip file not found: {zip_path}")
        return
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for filename in zip_ref.namelist():
            if filename.endswith('.json'):
                with zip_ref.open(filename) as file:
                    cve_data = json.load(file)
                    for cve_entry in cve_data:
                        cve_id = cve_entry.get('cve_id')
                        description = cve_entry.get('description', '')
                        severity = cve_entry.get('severity', 'Unknown')
                        affected_os = cve_entry.get('affected_os', 'Unknown')
                        exploit_tool_id = cve_entry.get('exploit_tool_id')
                        mde_id = generate_mde_id(existing_mde_ids)
                        existing_mde_ids.add(mde_id)
                        db.cursor.execute(
                            """
                            INSERT INTO vulnerabilities (cve_id, description, severity, affected_os, exploit_tool_id, mde_id)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (cve_id) DO NOTHING
                            """,
                            (cve_id, description, severity, affected_os, exploit_tool_id, mde_id)
                        )
    db.conn.commit()
    print("CVE data loaded and MDE IDs assigned successfully.")

if __name__ == "__main__":
    main() 