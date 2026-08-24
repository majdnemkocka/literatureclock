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


