import psycopg
conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/doctrine")
cur = conn.cursor()
for tbl in ["signals", "trade_plans"]:
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position", (tbl,))
    rows = cur.fetchall()
    print(f"=== {tbl.upper()} ===")
    for row in rows:
        print(row)
conn.close()
