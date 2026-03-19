import sqlite3
import json
conn = sqlite3.connect('.doctrine/operations.db')
cursor = conn.cursor()
cursor.execute("SELECT event_type, status, detail, metadata_json, created_at FROM operator_events WHERE created_at >= '2026-03-16' ORDER BY created_at DESC LIMIT 20")
for row in cursor.fetchall():
    print(f"{row[4]} | {row[0]} | {row[1]}")
    if row[2]:
        print(f"  Detail: {row[2][:100]}")
    if row[3]:
        try:
            meta = json.loads(row[3])
            print(f"  Meta: {json.dumps(meta, indent=2)[:200]}")
        except:
            print(f"  Meta: {row[3][:100]}")
conn.close()
