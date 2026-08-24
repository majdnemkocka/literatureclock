### Task 2: DB Schema Migration

**Files:**
- Modify: `seed_db.py` — replace `CREATE TABLE` DDL; remove `valid_times`, add six new time columns.
- Create: `migrate_add_time_interval_cols.py` — one-shot migration for any existing DB (runs ALTER TABLE, safe to re-run).

**Interfaces:**
- Consumes: nothing.
- Produces: DB `entries` table with columns:
  - `time_min_str VARCHAR(7)`, `time_max_str VARCHAR(7)`, `time_focus_str VARCHAR(7)`
  - `time_min_m SMALLINT`, `time_max_m SMALLINT`, `time_focus_m SMALLINT`
  - `valid_times` **absent** from new installs.

- [ ] **Step 1: Update `seed_db.py` CREATE TABLE**

In `seed_db.py`, replace the `CREATE TABLE entries` block:

```python
    cur.execute("""
        DROP TABLE IF EXISTS votes;
        DROP TABLE IF EXISTS entries;

        CREATE TABLE entries (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            link TEXT,
            snippet TEXT,
            is_literature BOOLEAN,
            categories TEXT[],
            urn TEXT,
            author TEXT,
            genre TEXT,
            source_url TEXT,
            source_type TEXT,
            is_fallback BOOLEAN DEFAULT FALSE,
            ai_rating INTEGER,
            ai_reason TEXT,
            ai_am_pm TEXT,
            ai_checked BOOLEAN DEFAULT FALSE,
            time_min_str    VARCHAR(7),
            time_max_str    VARCHAR(7),
            time_focus_str  VARCHAR(7),
            time_min_m      SMALLINT,
            time_max_m      SMALLINT,
            time_focus_m    SMALLINT
        );

        CREATE TABLE votes (
            id SERIAL PRIMARY KEY,
            entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE,
            rating INTEGER CHECK (rating >= 0 AND rating <= 5),
            am_pm VARCHAR(20),
            corrected_time VARCHAR(10),
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_entries_ai_checked ON entries(ai_checked);
        CREATE INDEX IF NOT EXISTS idx_entries_is_lit ON entries(is_literature);
        CREATE INDEX IF NOT EXISTS idx_entries_time_min_m ON entries(time_min_m);
        CREATE INDEX IF NOT EXISTS idx_entries_time_max_m ON entries(time_max_m);
    """)
```

Also remove `valid_times` from the `insert_batch` INSERT statement and the batch tuple in `seed()`:

```python
# In insert_batch():
    query = """
        INSERT INTO entries (
            title, link, snippet, is_literature, categories,
            urn, author, genre, source_url, source_type, is_fallback
        ) VALUES %s
    """

# In seed() batch.append():
                batch.append((
                    data.get('title', ''),
                    data.get('link', ''),
                    data.get('snippet', ''),
                    str(data.get('is_literature', False)).strip().lower() in ('1', 'true', 'yes'),
                    data.get('topics', []),
                    data.get('urn', ''),
                    data.get('author', ''),
                    data.get('genre', ''),
                    data.get('source_url', ''),
                    data.get('source_type', 'snippet_fallback'),
                    str(data.get('is_fallback', False)).strip().lower() in ('1', 'true', 'yes'),
                ))
```

- [ ] **Step 2: Create `migrate_add_time_interval_cols.py`**

This script is safe to re-run (uses `ADD COLUMN IF NOT EXISTS` and `DROP COLUMN IF EXISTS`):

```python
#!/usr/bin/env python3
"""
One-shot migration: add time interval columns to entries, drop valid_times.
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

cur.execute("ALTER TABLE entries DROP COLUMN IF EXISTS valid_times;")

conn.commit()
cur.close()
conn.close()
print("Migration complete.")
```

- [ ] **Step 3: Run migration on existing dev DB (if any)**

```bash
python migrate_add_time_interval_cols.py
```

Expected output: `Migration complete.`

- [ ] **Step 4: Verify schema**

```bash
python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='entries' ORDER BY ordinal_position\")
print([r[0] for r in cur.fetchall()])
conn.close()
"
```

Expected: list includes `time_min_str`, `time_max_str`, `time_focus_str`, `time_min_m`, `time_max_m`, `time_focus_m`; does NOT include `valid_times`.

- [ ] **Step 5: Commit**

```bash
git add seed_db.py migrate_add_time_interval_cols.py
git commit -m "feat: add time interval columns to entries, drop valid_times"
```

---


