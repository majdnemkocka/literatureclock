# Approximate Time Intervals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce interval-based time representation (`time_min_str`, `time_max_str`, `time_focus_str` + integer counterparts) so that approximate time expressions (e.g. `"éjfél körül"`, `"este"`) are stored with realistic uncertainty rather than pinned to a single minute.

**Architecture:** The DB schema gains six new columns on `entries`; `valid_times` is dropped. The AI grader prompt is extended to emit three new JSON fields per KEEP entry; `corrected_time` is deprecated. Display/query logic uses the new `time_min_m`/`time_max_m` integer columns for fast range checks and `time_focus_m` for proximity weighting.

**Tech Stack:** Python 3.11+, PostgreSQL (psycopg2), pytest, existing `ai_grader.py` / `seed_db.py` / `extractor.py` stack.

**Spec:** [`docs/superpowers/specs/2026-08-24-approximate-time-intervals-design.md`](../specs/2026-08-24-approximate-time-intervals-design.md)

## Global Constraints

- UTF-8 everywhere: all `open()` calls use `encoding="utf-8"`.
- Subprocess env: `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1` when spawning subprocesses.
- Extended HH:MM notation: hours ≥ 24 are legal for midnight-crossing intervals (e.g. `"24:15"`).
- Integer minute values: `time_min_m` is always `H*60+M` (0–2879); never stored independently from its `_str` counterpart.
- `time_min_m <= time_max_m` is a hard invariant; records violating it are silently nulled at write time.
- `time_focus_m` must lie within `[time_min_m, time_max_m]`; if the AI returns an out-of-range value, set focus fields to NULL (do not reject the whole record).
- No hard limit on interval width — store whatever the AI returns; a heatmap analysis will decide policy later.
- `valid_times` column is **dropped** from the schema (no production data to preserve).

---

### Task 1: Utility — `parse_extended_hhmm` and `validated_extended_hhmm`

**Files:**
- Create: `time_utils.py` (repo root, next to `ai_grader.py`)
- Create: `tests/test_time_utils.py`

**Interfaces:**
- Produces:
  - `parse_extended_hhmm(s: str) -> int` — converts `"HH:MM"` (HH may be ≥ 24) to integer minutes; raises `ValueError` on malformed input.
  - `validated_extended_hhmm(s) -> tuple[str, int] | tuple[None, None]` — wraps `parse_extended_hhmm`, returns `(None, None)` instead of raising; also rejects `m > 59` or `h > 48`.
  - `minutes_to_hhmm(m: int) -> str` — inverse: `1455 -> "24:15"`, `1050 -> "17:30"`.
  - `circular_dist(a_m: int, b_m: int) -> int` — shortest circular distance between two 0–1439 minute values (both are taken mod 1440 first); result in [0, 720].

**Consumes:** nothing (standalone utility).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_time_utils.py
import pytest
from time_utils import parse_extended_hhmm, validated_extended_hhmm, minutes_to_hhmm, circular_dist

class TestParseExtendedHHMM:
    def test_normal(self):
        assert parse_extended_hhmm("17:30") == 1050
    def test_midnight_exact(self):
        assert parse_extended_hhmm("00:00") == 0
    def test_extended_24(self):
        assert parse_extended_hhmm("24:15") == 1455
    def test_extended_26(self):
        assert parse_extended_hhmm("26:00") == 1560
    def test_bad_format_raises(self):
        with pytest.raises(ValueError):
            parse_extended_hhmm("badvalue")
    def test_bad_minutes_raises(self):
        with pytest.raises(ValueError):
            parse_extended_hhmm("10:60")

class TestValidatedExtendedHHMM:
    def test_valid_normal(self):
        assert validated_extended_hhmm("13:45") == ("13:45", 825)
    def test_valid_extended(self):
        assert validated_extended_hhmm("24:15") == ("24:15", 1455)
    def test_none_input(self):
        assert validated_extended_hhmm(None) == (None, None)
    def test_bad_minutes(self):
        assert validated_extended_hhmm("10:60") == (None, None)
    def test_h_too_large(self):
        assert validated_extended_hhmm("49:00") == (None, None)
    def test_non_string(self):
        assert validated_extended_hhmm(1730) == (None, None)

class TestMinutesToHHMM:
    def test_normal(self):
        assert minutes_to_hhmm(1050) == "17:30"
    def test_midnight(self):
        assert minutes_to_hhmm(1440) == "24:00"
    def test_extended(self):
        assert minutes_to_hhmm(1455) == "24:15"

class TestCircularDist:
    def test_same(self):
        assert circular_dist(600, 600) == 0
    def test_simple(self):
        assert circular_dist(600, 620) == 20
    def test_wrap_midnight(self):
        # 23:50 (1430) to 00:10 (10): dist = 20, not 1420
        assert circular_dist(1430, 10) == 20
    def test_max_dist(self):
        assert circular_dist(0, 720) == 720
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_time_utils.py -v
```

Expected: `ModuleNotFoundError: No module named 'time_utils'`

- [ ] **Step 3: Implement `time_utils.py`**

```python
# time_utils.py
"""Utility functions for extended HH:MM time notation used by the literature clock."""

from __future__ import annotations
import re


def parse_extended_hhmm(s: str) -> int:
    """
    Parse "HH:MM" to integer minutes since 00:00.
    HH may be >= 24 for midnight-crossing intervals (e.g. "24:15" -> 1455).
    Raises ValueError on malformed input or invalid minutes.
    """
    if not isinstance(s, str):
        raise ValueError(f"Expected str, got {type(s)}")
    s = s.strip()
    if not re.match(r'^\d{1,2}:\d{2}$', s):
        raise ValueError(f"Invalid HH:MM format: {s!r}")
    h, m = map(int, s.split(':'))
    if m > 59:
        raise ValueError(f"Minutes out of range: {m}")
    return h * 60 + m


def validated_extended_hhmm(s) -> tuple[str, int] | tuple[None, None]:
    """
    Like parse_extended_hhmm but returns (None, None) instead of raising.
    Also rejects h > 48 (practical upper bound ~27:00 for 'éjjel' intervals).
    """
    if not isinstance(s, str):
        return None, None
    try:
        minutes = parse_extended_hhmm(s)
    except ValueError:
        return None, None
    h = minutes // 60
    if h > 48:
        return None, None
    return s.strip(), minutes


def minutes_to_hhmm(m: int) -> str:
    """Convert integer minutes to "HH:MM" (HH may be >= 24)."""
    return f"{m // 60:02d}:{m % 60:02d}"


def circular_dist(a_m: int, b_m: int) -> int:
    """
    Shortest circular distance between two minute values on a 1440-minute clock.
    Both inputs are taken mod 1440 first.
    Result is in [0, 720].
    """
    a = a_m % 1440
    b = b_m % 1440
    diff = abs(a - b)
    return min(diff, 1440 - diff)
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_time_utils.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add time_utils.py tests/test_time_utils.py
git commit -m "feat: add time_utils with extended HH:MM parsing and circular distance"
```

---

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

### Task 3: AI Grader — Prompt and Output Handling

**Files:**
- Modify: `ai_grader.py` — update `PROMPT_TEMPLATE`, update `mark_as_checked()`.

**Interfaces:**
- Consumes: `validated_extended_hhmm` from `time_utils.py` (Task 1).
- Produces: `entries.time_min_str`, `entries.time_max_str`, `entries.time_focus_str` (and `_m` variants) populated for every KEEP result.

- [ ] **Step 1: Add import at top of `ai_grader.py`**

```python
from time_utils import validated_extended_hhmm
```

- [ ] **Step 2: Replace `PROMPT_TEMPLATE` output format section**

Find the section starting with `- "corrected_time": (string or null)` and replace the entire output spec block at the end of `PROMPT_TEMPLATE`:

```python
PROMPT_TEMPLATE = """
You are a strict data cleaner for a "Literature Clock" project.
Your goal is to filter out invalid entries found by a scraper.

The scraper looked for time patterns (e.g. "12:30", "negyed három"), but it found many false positives.
The text is in Hungarian.
Important: The snippet may contain `<span class="marked">...</span>` around tokens matched by the scraper.
These exact tags indicate the anchor of the candidate time expression.

Criteria for DENYING an entry (marking it as bad):
1. **Not a Time**: The matching text refers to a date (e.g., "11/12" meaning Nov 12th), a quantity, a price, or a chapter number, NOT a time of day.
2. **Meta-text**: The snippet is a Table of Contents, a header, a footnote, or a bibliography, not a narrative sentence.
3. **Comment**: The data is not of the highest quality, it may include comments made on the book, not just the book's core text.
4. **Gibberish**: The snippet is broken, unreadable, or just a list of numbers.
5. **File/OCR metadata**: Filename/index artifacts like `.indd`, `.jpg`, page/index dumps, or dense timestamp logs.

Criteria for KEEPING:
1. It is a valid sentence from a book, or it is a diary's timestamp
2. It refers to a specific time of day, especially around `<span class="marked">...</span>`.

Prioritization rules:
- Judge primarily by the local context around `<span class="marked">...</span>`.
- If marker context is clearly metadata/listing noise, DENY.
- If marker context is natural narrative time-of-day usage, KEEP.

Input Data (JSON):
{data}

Output Format (JSON):
Return a list of objects. Each object must have:
- "id": (integer) The entry ID from the input.
- "reason": (string) Short explanation (e.g., "Valid quote", "Date format").
- "rate": (integer) 0-5 rating of quality (0 for DENY, 5 for perfect KEEP).
- "status": "DENY" or "KEEP"
- "am_pm": "AM", "PM", or "AMBIGUOUS"
  * Check the local snippet and the 'wider_context' for narrative cues about the time of day:
    - "AM": morning / daytime events (e.g. "reggel", "délelőtt", "hajnal", "reggeli", "ébredés").
    - "PM": afternoon / evening / night events (e.g. "este", "éjjel", "délután", "vacsora").
    - "AMBIGUOUS": only if the wider scene still gives no clue.
- "corrected_time": null  (deprecated — superseded by time_focus_str below)
- "time_min_str": (string or null)
  * If status=DENY, return null.
  * The start of the time interval in "HH:MM" format (24h).
  * For midnight-crossing intervals use extended notation so time_min_str <= time_max_str always holds.
    Example: "éjfél körül" -> time_min_str="23:45", time_max_str="24:15".
  * For exact times: time_min_str == time_max_str == time_focus_str.
- "time_max_str": (string or null)
  * If status=DENY, return null.
  * The end of the interval in "HH:MM" (extended notation allowed, e.g. "24:15", "26:00").
- "time_focus_str": (string or null)
  * If status=DENY, return null.
  * The single most probable moment within the interval. NOT necessarily the midpoint.
  * "nem sokkal fél hat előtt" -> focus is 17:29 (near the end), not 17:23.
  * "éjféli harangszót követően rögvest" -> focus is 24:01, not 24:05.
  * For exact times: equal to time_min_str and time_max_str.

Interval width guidelines:
  * Exact minute ("13:45", "fél hat", "negyed három"): interval width = 0 (all three fields equal).
  * Fuzzy symmetric ("körül", "tájban", "nagyjából X"): +-10-20 min, focus = centre.
  * Asymmetric ("rögvest", "nem sokkal X előtt/után"): focus near one end of interval.
  * Daytime sub-part ("kora délután", "késő este"): +-45-90 min.
  * Full daypart ("este", "reggel", "éjjel"): 3-5 hour wide interval.
"""
```

- [ ] **Step 3: Update `mark_as_checked()` to write interval columns**

Replace the entire `mark_as_checked` function:

```python
def mark_as_checked(cur, results):
    if not results:
        return

    for r in results:
        am_pm_val = r.get('am_pm', 'AMBIGUOUS')
        if am_pm_val not in ('AM', 'PM', 'AMBIGUOUS'):
            am_pm_val = 'AMBIGUOUS'

        min_str, min_m = validated_extended_hhmm(r.get('time_min_str'))
        max_str, max_m = validated_extended_hhmm(r.get('time_max_str'))
        foc_str, foc_m = validated_extended_hhmm(r.get('time_focus_str'))

        # Enforce time_min_m <= time_max_m
        if min_m is not None and max_m is not None and min_m > max_m:
            min_str = max_str = foc_str = None
            min_m = max_m = foc_m = None

        # Enforce time_focus_m within [time_min_m, time_max_m]
        if foc_m is not None and min_m is not None and max_m is not None:
            if not (min_m <= foc_m <= max_m):
                foc_str, foc_m = None, None

        cur.execute("""
            UPDATE entries
            SET ai_checked     = TRUE,
                ai_rating      = %s,
                ai_reason      = %s,
                ai_am_pm       = %s,
                time_min_str   = %s,
                time_min_m     = %s,
                time_max_str   = %s,
                time_max_m     = %s,
                time_focus_str = %s,
                time_focus_m   = %s
            WHERE id = %s
        """, (
            r.get('rate'), r.get('reason'), am_pm_val,
            min_str, min_m,
            max_str, max_m,
            foc_str, foc_m,
            r['id']
        ))
```

- [ ] **Step 4: Write a focused integration test**

```python
# tests/test_ai_grader_interval.py
"""
Tests for the mark_as_checked interval-writing logic.
Uses a real psycopg2 connection via DATABASE_URL (integration test).
Skip gracefully if DATABASE_URL is not set.
"""
import os
import re
import pytest
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.environ.get('DATABASE_URL')
pytestmark = pytest.mark.skipif(not DB_URL, reason="DATABASE_URL not set")

@pytest.fixture
def db_entry():
    """Insert a throwaway entry, yield its id, clean up after."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO entries (title, is_literature, ai_checked)
        VALUES ('Test Entry', TRUE, FALSE)
        RETURNING id
    """)
    eid = cur.fetchone()[0]
    conn.commit()
    yield eid, cur, conn
    cur.execute("DELETE FROM entries WHERE id = %s", (eid,))
    conn.commit()
    cur.close()
    conn.close()

def test_exact_time_written(db_entry):
    from ai_grader import mark_as_checked
    eid, cur, conn = db_entry
    mark_as_checked(cur, [{
        'id': eid, 'rate': 5, 'reason': 'test', 'am_pm': 'PM',
        'time_min_str': '17:30', 'time_max_str': '17:30', 'time_focus_str': '17:30',
        'corrected_time': None
    }])
    conn.commit()
    cur.execute("SELECT time_min_m, time_max_m, time_focus_m FROM entries WHERE id=%s", (eid,))
    row = cur.fetchone()
    assert row == (1050, 1050, 1050)

def test_fuzzy_midnight_written(db_entry):
    from ai_grader import mark_as_checked
    eid, cur, conn = db_entry
    mark_as_checked(cur, [{
        'id': eid, 'rate': 4, 'reason': 'test', 'am_pm': 'AMBIGUOUS',
        'time_min_str': '23:45', 'time_max_str': '24:15', 'time_focus_str': '24:00',
        'corrected_time': None
    }])
    conn.commit()
    cur.execute("SELECT time_min_m, time_max_m, time_focus_m FROM entries WHERE id=%s", (eid,))
    row = cur.fetchone()
    assert row == (1425, 1455, 1440)

def test_invalid_min_gt_max_nulled(db_entry):
    from ai_grader import mark_as_checked
    eid, cur, conn = db_entry
    # time_min > time_max without 24+ notation -> should null all three
    mark_as_checked(cur, [{
        'id': eid, 'rate': 3, 'reason': 'test', 'am_pm': 'AM',
        'time_min_str': '17:30', 'time_max_str': '16:00', 'time_focus_str': '17:00',
        'corrected_time': None
    }])
    conn.commit()
    cur.execute("SELECT time_min_m, time_max_m, time_focus_m FROM entries WHERE id=%s", (eid,))
    row = cur.fetchone()
    assert row == (None, None, None)

def test_focus_out_of_range_nulled(db_entry):
    from ai_grader import mark_as_checked
    eid, cur, conn = db_entry
    mark_as_checked(cur, [{
        'id': eid, 'rate': 3, 'reason': 'test', 'am_pm': 'AM',
        'time_min_str': '13:00', 'time_max_str': '15:00', 'time_focus_str': '16:00',
        'corrected_time': None
    }])
    conn.commit()
    cur.execute("SELECT time_min_m, time_max_m, time_focus_m FROM entries WHERE id=%s", (eid,))
    row = cur.fetchone()
    assert row[0] == 780 and row[1] == 900 and row[2] is None
```

- [ ] **Step 5: Run tests**

```
pytest tests/test_ai_grader_interval.py -v
```

Expected: all pass (or skip if no DATABASE_URL).

- [ ] **Step 6: Commit**

```bash
git add ai_grader.py tests/test_ai_grader_interval.py
git commit -m "feat: extend AI grader to emit time_min/max/focus interval fields"
```

---

### Task 4: Display / Eligibility Logic

**Files:**
- Create: `quote_selector.py` (repo root)
- Create: `tests/test_quote_selector.py`

**Interfaces:**
- Consumes: `circular_dist` from `time_utils` (Task 1).
- Produces:
  - `is_eligible(entry, current_m: int) -> bool`
  - `quote_weight(entry, current_m: int) -> float`
  - `pick_quote(candidates: list, current_m: int) -> object | None`
  - `entry` is any object/dict with `.time_min_m`, `.time_max_m`, `.time_focus_m` (or dict keys).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_quote_selector.py
import pytest
from types import SimpleNamespace
from quote_selector import is_eligible, quote_weight, pick_quote

def make_entry(min_m, max_m, focus_m):
    return SimpleNamespace(time_min_m=min_m, time_max_m=max_m, time_focus_m=focus_m)

class TestIsEligible:
    def test_exact_match(self):
        e = make_entry(1050, 1050, 1050)
        assert is_eligible(e, 1050) is True

    def test_exact_no_match(self):
        e = make_entry(1050, 1050, 1050)
        assert is_eligible(e, 1051) is False

    def test_fuzzy_inside(self):
        e = make_entry(1040, 1060, 1050)
        assert is_eligible(e, 1045) is True

    def test_fuzzy_outside(self):
        e = make_entry(1040, 1060, 1050)
        assert is_eligible(e, 1039) is False

    def test_midnight_crossing_before(self):
        # "éjfél körül": 23:45(1425) - 24:15(1455)
        e = make_entry(1425, 1455, 1440)
        assert is_eligible(e, 1430) is True  # 23:50, normal range

    def test_midnight_crossing_after(self):
        # current=0:05=5, check via +1440=1445 which is in [1425,1455]
        e = make_entry(1425, 1455, 1440)
        assert is_eligible(e, 5) is True   # 00:05

    def test_midnight_crossing_outside(self):
        e = make_entry(1425, 1455, 1440)
        assert is_eligible(e, 30) is False  # 00:30, too late

    def test_none_fields_not_eligible(self):
        e = SimpleNamespace(time_min_m=None, time_max_m=None, time_focus_m=None)
        assert is_eligible(e, 600) is False

class TestQuoteWeight:
    def test_exact_at_focus_max_weight(self):
        e = make_entry(1050, 1050, 1050)
        w = quote_weight(e, 1050)
        assert w == pytest.approx(1.0)

    def test_wider_interval_lower_weight(self):
        exact = make_entry(1050, 1050, 1050)
        fuzzy = make_entry(1040, 1060, 1050)
        assert quote_weight(exact, 1050) > quote_weight(fuzzy, 1050)

    def test_farther_from_focus_lower_weight(self):
        e = make_entry(1000, 1100, 1050)
        w_close = quote_weight(e, 1050)   # at focus
        w_far   = quote_weight(e, 1010)   # near edge
        assert w_close > w_far

    def test_never_zero(self):
        e = make_entry(1140, 1380, 1260)  # "este"
        assert quote_weight(e, 1140) > 0

class TestPickQuote:
    def test_returns_none_for_empty(self):
        assert pick_quote([], 600) is None

    def test_returns_eligible(self):
        e = make_entry(600, 600, 600)
        result = pick_quote([e], 600)
        assert result is e

    def test_filters_ineligible(self):
        e_ok  = make_entry(600, 600, 600)
        e_bad = make_entry(700, 700, 700)
        result = pick_quote([e_ok, e_bad], 600)
        assert result is e_ok

    def test_none_eligible_returns_none(self):
        e = make_entry(700, 700, 700)
        assert pick_quote([e], 600) is None
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_quote_selector.py -v
```

Expected: `ModuleNotFoundError: No module named 'quote_selector'`

- [ ] **Step 3: Implement `quote_selector.py`**

```python
# quote_selector.py
"""
Eligibility check and weighted random selection for Literature Clock quotes.
Supports interval-based times including midnight-crossing (time_max_m >= 1440).
"""
from __future__ import annotations
import random
from typing import Any

from time_utils import circular_dist


def _get(entry, attr: str):
    """Support both object attributes and dict keys."""
    if isinstance(entry, dict):
        return entry.get(attr)
    return getattr(entry, attr, None)


def is_eligible(entry, current_m: int) -> bool:
    """
    Return True if the entry's interval covers current_m.
    current_m: minutes since 00:00 (0..1439).
    Handles midnight-crossing intervals (time_max_m >= 1440) by also
    testing current_m + 1440.
    """
    min_m = _get(entry, 'time_min_m')
    max_m = _get(entry, 'time_max_m')
    if min_m is None or max_m is None:
        return False
    return (min_m <= current_m <= max_m or
            min_m <= current_m + 1440 <= max_m)


def quote_weight(entry, current_m: int) -> float:
    """
    Compute selection weight for an entry at current_m.
    Higher weight = more likely to be shown.
    Formula: 1 / ((1 + precision) * (1 + dist_to_focus))
    - precision = time_max_m - time_min_m  (0 for exact times)
    - dist_to_focus = circular distance (mod 1440) from current_m to time_focus_m
    Always > 0.
    """
    min_m   = _get(entry, 'time_min_m') or 0
    max_m   = _get(entry, 'time_max_m') or 0
    focus_m = _get(entry, 'time_focus_m') or min_m

    precision = max_m - min_m
    dist = circular_dist(current_m, focus_m % 1440)
    return 1.0 / ((1 + precision) * (1 + dist))


def pick_quote(candidates: list, current_m: int) -> Any | None:
    """
    Pick one quote using weighted random selection.
    Returns None if no candidate is eligible for current_m.
    """
    eligible = [e for e in candidates if is_eligible(e, current_m)]
    if not eligible:
        return None
    weights = [quote_weight(e, current_m) for e in eligible]
    return random.choices(eligible, weights=weights, k=1)[0]
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_quote_selector.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add quote_selector.py tests/test_quote_selector.py
git commit -m "feat: add quote_selector with interval eligibility and weighted pick"
```

---

### Task 5: Remove `valid_times` References from Remaining Files

**Files:**
- Modify: `seed_gen.py` — remove any `valid_times` field emission.
- Modify: `stats.py` — remove any `valid_times` queries/references.
- Modify: `grading-app/` — search and update any `valid_times` column reference.
- Modify: `dashboard/` — search and update any `valid_times` column reference.

**Interfaces:**
- Consumes: new schema from Task 2 (no `valid_times`).
- Produces: codebase with zero references to `valid_times`.

- [ ] **Step 1: Find all remaining references**

```bash
grep -rn "valid_times" D:\Dev\irodalom_ora\literatureclock --include="*.py" --include="*.js" --include="*.ts" --include="*.sql"
```

Note every file and line number found.

- [ ] **Step 2: Remove/replace each reference**

For each file found:
- If it *reads* `valid_times` to display a time: replace with `time_min_str || ' – ' || time_max_str` (SQL) or `f"{e.time_min_str}–{e.time_max_str}"` (Python).
- If it *writes* `valid_times` during ingestion: remove the field from the INSERT (already done in `seed_db.py`).
- If it *filters* by `valid_times IS NOT NULL`: replace with `time_min_m IS NOT NULL`.

- [ ] **Step 3: Verify no remaining references**

```bash
grep -rn "valid_times" D:\Dev\irodalom_ora\literatureclock --include="*.py" --include="*.js" --include="*.ts" --include="*.sql"
```

Expected: zero results.

- [ ] **Step 4: Run full test suite**

```
pytest D:\Dev\irodalom_ora\literatureclock\tests\ -v
```

Expected: all existing tests pass.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove all valid_times references, use time interval columns"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Six new columns (`time_min_str`, `time_max_str`, `time_focus_str` + `_m` variants) | Task 2 |
| `valid_times` dropped | Task 2 + Task 5 |
| `parse_extended_hhmm` / `validated_extended_hhmm` | Task 1 |
| `circular_dist` for display weighting | Task 1 |
| AI grader prompt updated with interval instructions | Task 3 |
| AI grader `mark_as_checked` writes interval columns | Task 3 |
| `time_min_m <= time_max_m` invariant enforced | Task 3 |
| `time_focus_m` in-range check | Task 3 |
| `is_eligible` with midnight-crossing support | Task 4 |
| Weighted `pick_quote` (never zero weight) | Task 4 |
| `corrected_time` deprecated (returns null) | Task 3 prompt |
| Integration test for grader DB writes | Task 3 |
| grading-app shows `time_min_str`–`time_max_str` strings | Task 5 (replace display refs) |
| No hard interval width limit | Task 3 (no cap in validator) |
