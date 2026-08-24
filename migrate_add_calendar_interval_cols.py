#!/usr/bin/env python3
"""
One-shot migration: add calendar interval & day_of_week columns to calendar_entries, drop valid_dates.
Safe to re-run (idempotent).
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("Warning: DATABASE_URL not set. Skipping live DB migration.", file=sys.stderr)
    sys.exit(0)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
    ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_min_str    VARCHAR(5);
    ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_max_str    VARCHAR(5);
    ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_focus_str  VARCHAR(5);
    ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_min_d      SMALLINT;
    ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_max_d      SMALLINT;
    ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_focus_d    SMALLINT;
    ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS day_of_week     VARCHAR(15);
    ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS day_of_week_num SMALLINT;
""")

cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_cal_date_min_d ON calendar_entries(date_min_d);
    CREATE INDEX IF NOT EXISTS idx_cal_date_max_d ON calendar_entries(date_max_d);
    CREATE INDEX IF NOT EXISTS idx_cal_dow ON calendar_entries(day_of_week_num);
""")

cur.execute("ALTER TABLE calendar_entries DROP COLUMN IF EXISTS valid_dates;")

conn.commit()
cur.close()
conn.close()
print("Calendar schema migration complete.")
