# Approximate Calendar Intervals & Day-of-Week Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce date interval representation (`date_min_str`, `date_max_str`, `date_focus_str` + integer day-of-year counterparts) and day-of-week handling (`day_of_week`, `day_of_week_num`) to the Literature Calendar, with MEK wildcard query optimization (`*`).

**Architecture:** Database schema on `calendar_entries` adds 8 new columns; legacy `valid_dates` is dropped. `date_utils.py` handles day-of-year conversion and circular distance. `rules_calendar.json5` and `mek_calendar_search.py` add fuzzy seasons, month parts, holidays, and weekdays with wildcard-compressed queries. `calendar_quote_selector.py` provides 2D date/weekday weighted selection. `calendar_ai_grader.py` updates prompt and DB writes.

**Tech Stack:** Python 3.11+, PostgreSQL (psycopg2), pytest, json5, BeautifulSoup4.

**Spec:** [`docs/superpowers/specs/2026-08-24-approximate-calendar-intervals-design.md`](../specs/2026-08-24-approximate-calendar-intervals-design.md)

---

### Task 1: Date Utilities — `date_utils.py`

**Files:**
- Create: `date_utils.py` (repo root)
- Create: `tests/test_date_utils.py`

**Interfaces:**
- `mmdd_to_day_of_year(s: str) -> int` — converts `"MM-DD"` (leap year 366-day base) to `1..366`.
- `day_of_year_to_mmdd(day: int) -> str` — converts integer day `1..366` (or `>366` for year-crossing) to `"MM-DD"`.
- `validated_mmdd(s: str) -> tuple[str, int] | tuple[None, None]` — safe validator.
- `circular_day_dist(d1: int, d2: int) -> int` — circular distance on 366-day calendar ($[0, 183]$).
- `parse_day_of_week(s: str) -> tuple[str | None, int | None]` — maps Hungarian weekday name to `(UPPER_NAME, 1..7)` or `("WEEKEND", None)`.

- [ ] **Step 1: Write failing tests in `tests/test_date_utils.py`**
- [ ] **Step 2: Run tests to confirm failure**
- [ ] **Step 3: Implement `date_utils.py`**
- [ ] **Step 4: Run tests to confirm pass**
- [ ] **Step 5: Commit**

---

### Task 2: Calendar DB Schema Migration

**Files:**
- Modify: `seed_calendar_db.py` — update table DDL, drop `valid_dates`, add 8 new columns + indexes.
- Create: `migrate_add_calendar_interval_cols.py` — idempotent migration script.

- [ ] **Step 1: Update `seed_calendar_db.py` DDL and insert logic**
- [ ] **Step 2: Create `migrate_add_calendar_interval_cols.py`**
- [ ] **Step 3: Run migration on dev DB**
- [ ] **Step 4: Verify schema**
- [ ] **Step 5: Commit**

---

### Task 3: Rules & Wildcard Query Searcher (`rules_calendar.json5` & `mek_calendar_search.py`)

**Files:**
- Modify: `rules_calendar.json5` — add month parts, seasons, holidays, and weekdays with wildcard patterns.
- Modify: `scrapers/mek_search/mek_calendar_search.py` — expand `DateTermGenerator` to generate fuzzy terms, seasons, and weekdays with suffix truncation `*`; add CLI modes (`--dates-only`, `--seasons-only`, `--weekdays-only`, `--include-all`).
- Create: `tests/test_calendar_search.py` — unit tests for query generation and wildcard patterns.

- [ ] **Step 1: Write failing tests for term generator and query formatting**
- [ ] **Step 2: Update `rules_calendar.json5`**
- [ ] **Step 3: Update `scrapers/mek_search/mek_calendar_search.py`**
- [ ] **Step 4: Run tests to verify pass**
- [ ] **Step 5: Commit**

---

### Task 4: Calendar Quote Selector (`calendar_quote_selector.py`)

**Files:**
- Create: `calendar_quote_selector.py` (repo root)
- Create: `tests/test_calendar_quote_selector.py`

**Interfaces:**
- `is_calendar_eligible(entry, current_day: int, current_dow: int) -> bool`
- `calendar_quote_weight(entry, current_day: int, current_dow: int) -> float`
- `pick_calendar_quote(candidates: list, current_day: int, current_dow: int) -> Any | None`

- [ ] **Step 1: Write failing tests for eligibility, weighting, and random selection**
- [ ] **Step 2: Implement `calendar_quote_selector.py`**
- [ ] **Step 3: Run tests to verify pass**
- [ ] **Step 4: Commit**

---

### Task 5: Calendar AI Grader Update (`calendar_ai_grader.py`)

**Files:**
- Modify: `calendar_ai_grader.py` — update `PROMPT_TEMPLATE` to output `date_min_str`, `date_max_str`, `date_focus_str`, `day_of_week`; update `mark_checked()` to write all new columns and enforce invariants.
- Create: `tests/test_calendar_ai_grader.py` — integration tests for grader interval and weekday handling.

- [ ] **Step 1: Update `calendar_ai_grader.py` prompt and `mark_checked`**
- [ ] **Step 2: Write tests in `tests/test_calendar_ai_grader.py`**
- [ ] **Step 3: Run tests to verify pass**
- [ ] **Step 4: Commit**

---

### Task 6: Cleanup & Full Suite Verification

**Files:**
- Modify: `grading-app/migrate_calendar.js` (if exists) or any remaining references.
- Run full pytest suite across clock and calendar modules.

- [ ] **Step 1: Search and replace remaining `valid_dates` references**
- [ ] **Step 2: Run full test suite (`pytest tests/ -v`)**
- [ ] **Step 3: Commit**
