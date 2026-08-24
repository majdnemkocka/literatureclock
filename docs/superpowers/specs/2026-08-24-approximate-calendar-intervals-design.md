# Approximate Calendar Intervals & Day-of-Week Design Spec

**Date:** 2026-08-24  
**Status:** Approved  
**Author:** Antigravity / Gemini  

---

## 1. Overview

The **Literature Calendar** (Irodalmi Naptár) extracts literary quotes that reference specific calendar dates (e.g. `"március 15."`), fuzzy/approximate date intervals (e.g. `"március elején"`, `"karácsony előtt pár nappal"`, `"tavasszal"`), or specific days of the week (e.g. `"hétfőn"`, `"egy péntek délután"`, `"vasárnap délelőtt"`).

This spec defines the data model, query generation with MEK wildcard optimization (`*`), extraction rules, AI grader schema, and weighted selection logic for the Literature Calendar.

---

## 2. Core Decisions & Principles

1. **Perpetual Calendar (`MM-DD`):** The primary focus is day-of-year matching without pinning to specific historical years. Dates are formatted as `"MM-DD"` (e.g. `"03-15"`).
2. **Interval Representation:**
   - Dual representation: String (`"MM-DD"`) for human readability and integer day-of-year (`1..366`, up to `425` for year-crossing intervals like winter) for high-performance database filtering and distance computation.
   - Separate `date_focus` field: The most probable date within the interval (e.g. `"március elején"` -> `date_min="03-01"`, `date_max="03-10"`, `date_focus="03-05"`).
3. **Year-Crossing (Winter / Year-End):**
   - 365+ extended notation for winter intervals that cross December 31 to January (e.g. `"télen"`: December 1 to February 28 -> days `335` to `424` where Jan 1 = 366, Feb 28 = 424).
   - Invariant: `date_min_d <= date_max_d` always holds.
4. **Days of the Week (`DOW`):**
   - `day_of_week` (`"MONDAY"`, `"TUESDAY"`, `"WEDNESDAY"`, `"THURSDAY"`, `"FRIDAY"`, `"SATURDAY"`, `"SUNDAY"`, `"WEEKEND"` or `null`).
   - `day_of_week_num` (`1..7`, where 1 = Monday, 7 = Sunday; `null` if generic).
5. **MEK Fulltext Search Optimization:**
   - Pipe `|` operator for OR clauses.
   - Suffix truncation `*` for inflected forms (e.g. `"hétfő*"`, `"kedd*"`, `"tavasz*"`, `"március elej*"`).
6. **Selection Weighting:**
   - Precision penalty: narrower intervals are preferred over wide season-long intervals.
   - Distance penalty: quotes closer to `date_focus` receive higher weight.
   - Day of week bonus: quotes matching the current day of the week receive weight; hybrid quotes matching both the calendar date and weekday receive top priority.
   - Non-zero weight: every eligible candidate maintains a strictly positive probability ($> 0$).

---

## 3. Database Schema

```sql
-- Migration on calendar_entries:
ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_min_str    VARCHAR(5);   -- "03-01", "12-24"
ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_max_str    VARCHAR(5);   -- "03-10", "12-26"
ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_focus_str  VARCHAR(5);   -- "03-05", "12-25"
ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_min_d      SMALLINT;     -- 1..366 (or >365 for year-crossing)
ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_max_d      SMALLINT;
ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_focus_d    SMALLINT;
ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS day_of_week     VARCHAR(15);  -- "MONDAY", "FRIDAY", "WEEKEND", NULL
ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS day_of_week_num SMALLINT;     -- 1..7, NULL

CREATE INDEX IF NOT EXISTS idx_cal_date_min_d ON calendar_entries(date_min_d);
CREATE INDEX IF NOT EXISTS idx_cal_date_max_d ON calendar_entries(date_max_d);
CREATE INDEX IF NOT EXISTS idx_cal_dow ON calendar_entries(day_of_week_num);

-- Drop legacy valid_dates
ALTER TABLE calendar_entries DROP COLUMN IF EXISTS valid_dates;
```

---

## 4. Extended Date Utility (`date_utils.py`)

- `mmdd_to_day_of_year(mmdd: str) -> int`: Standard leap-year calendar mapping (Jan 1 = 1, Dec 31 = 366).
- `day_of_year_to_mmdd(day: int) -> str`: Inverse mapping (e.g. `1 -> "01-01"`, `366 -> "12-31"`, `380 -> "01-14"`).
- `circular_day_dist(d1: int, d2: int) -> int`: Shortest distance on a 366-day circular calendar ($[0, 183]$).
- `parse_day_of_week(s: str) -> tuple[str | None, int | None]`: Maps Hungarian weekday terms (`"hétfő"`, `"kedd"`, etc.) to `("MONDAY", 1)`, etc.

---

## 5. Calendar Quote Selector (`calendar_quote_selector.py`)

Eligibility check:
```python
def is_calendar_eligible(entry, current_day: int, current_dow: int) -> bool:
    # 1. Date interval match
    date_match = False
    if entry.date_min_d is not None and entry.date_max_d is not None:
        date_match = (entry.date_min_d <= current_day <= entry.date_max_d or
                      entry.date_min_d <= current_day + 366 <= entry.date_max_d)
    
    # 2. Weekday match
    dow_match = False
    if entry.day_of_week_num is not None:
        dow_match = (entry.day_of_week_num == current_dow)
    elif entry.day_of_week == "WEEKEND" and current_dow in (6, 7):
        dow_match = True

    # Eligible if either date matches or weekday matches
    return date_match or dow_match
```

Selection weighting:
```python
def calendar_quote_weight(entry, current_day: int, current_dow: int) -> float:
    base_weight = 1.0
    
    # Date precision and distance weighting
    if entry.date_min_d is not None and entry.date_max_d is not None:
        precision = max(0, entry.date_max_d - entry.date_min_d)
        focus = entry.date_focus_d if entry.date_focus_d is not None else entry.date_min_d
        dist = circular_day_dist(current_day, focus % 366)
        date_factor = 1.0 / ((1 + precision) * (1 + dist))
    else:
        date_factor = 0.2  # Weekday-only quote has lower base weight than exact date

    # Weekday alignment bonus
    dow_bonus = 1.0
    if entry.day_of_week_num == current_dow or (entry.day_of_week == "WEEKEND" and current_dow in (6, 7)):
        dow_bonus = 2.0  # 2x multiplier for weekday match

    # Hybrid bonus (both date and weekday match)
    if (entry.date_min_d is not None and is_calendar_eligible(entry, current_day, current_dow) 
        and entry.day_of_week_num == current_dow):
        dow_bonus = 4.0

    return max(0.001, date_factor * dow_bonus)
```

---

## 6. AI Grader Prompt Updates (`calendar_ai_grader.py`)

The Gemini AI Grader prompt is updated to output:
- `status`: `"KEEP"` or `"DENY"`
- `rate`: 0–5
- `reason`: Explanation
- `date_min_str`: `"MM-DD"` or `null`
- `date_max_str`: `"MM-DD"` or `null`
- `date_focus_str`: `"MM-DD"` or `null`
- `day_of_week`: `"MONDAY"`, `"TUESDAY"`, `"WEDNESDAY"`, `"THURSDAY"`, `"FRIDAY"`, `"SATURDAY"`, `"SUNDAY"`, `"WEEKEND"`, or `null`
