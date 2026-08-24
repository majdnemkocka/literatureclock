#!/usr/bin/env python3
"""
One-shot migration: add time interval columns to entries.
Safe to re-run (idempotent).
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("Error: DATABASE_URL not set.", file=sys.stderr)
    sys.exit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
    ALTER TABLE entries ADD COLUMN IF NOT EXISTS time_min_str   VARCHAR(7);
    ALTER TABLE entries ADD COLUMN IF NOT EXISTS time_max_str   VARCHAR(7);
    ALTER TABLE entries ADD COLUMN IF NOT EXISTS time_focus_str VARCHAR(7);
    ALTER TABLE entries ADD COLUMN IF NOT EXISTS time_min_m     SMALLINT;
    ALTER TABLE entries ADD COLUMN IF NOT EXISTS time_max_m     SMALLINT;
    ALTER TABLE entries ADD COLUMN IF NOT EXISTS time_focus_m   SMALLINT;
""")

cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_entries_time_min_m ON entries(time_min_m);
    CREATE INDEX IF NOT EXISTS idx_entries_time_max_m ON entries(time_max_m);
""")

conn.commit()
cur.close()
conn.close()
print("Migration complete.")
