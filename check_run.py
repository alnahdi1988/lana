import sqlite3
import json
conn = sqlite3.connect('.doctrine/operations.db')
cursor = conn.cursor()

# Get the latest run
cursor.execute("SELECT run_id, run_status, total_symbols, succeeded_symbols, skipped_symbols, failed_symbols, generated_signals, generated_trade_plans, sendable_alerts, telegram_sent, telegram_failed, started_at, finished_at FROM runs WHERE started_at >= '2026-03-16' ORDER BY started_at DESC LIMIT 1")
run = cursor.fetchone()
if run:
    print(f"Run ID: {run[0]}")
    print(f"Status: {run[1]}")
    print(f"Total symbols: {run[2]}")
    print(f"Succeeded: {run[3]}, Skipped: {run[4]}, Failed: {run[5]}")
    print(f"Generated signals: {run[6]}")
    print(f"Generated trade plans: {run[7]}")
    print(f"Sendable alerts: {run[8]}")
    print(f"Telegram sent: {run[9]}, failed: {run[10]}")
    print(f"Started: {run[11]}")
    print(f"Finished: {run[12]}")
    
    # Get symbol summaries for this run
    print("\n--- Symbol Summaries ---")
    cursor.execute("SELECT ticker, status, stage_reached, signal, error_message FROM symbol_runs WHERE run_id = ? ORDER BY ticker", (run[0],))
    for row in cursor.fetchall():
        print(f"{row[0]}: {row[1]} at {row[2]} | signal={row[3]} | error={row[4][:50] if row[4] else 'None'}")
else:
    print("No runs found for 2026-03-16")

conn.close()
