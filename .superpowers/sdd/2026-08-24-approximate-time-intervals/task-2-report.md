# Task 2 Report: DB Schema Migration

**Status:** DONE  
**Date:** 2026-08-24  
**Commit:** `36184b8` (`feat: add time interval columns to entries, drop valid_times`)

---

## 1. Overview of Changes

1. **`seed_db.py`**:
   - Updated `CREATE TABLE entries` DDL: dropped `valid_times TEXT[]` column and added 6 new interval columns:
     - `time_min_str VARCHAR(7)`
     - `time_max_str VARCHAR(7)`
     - `time_focus_str VARCHAR(7)`
     - `time_min_m SMALLINT`
     - `time_max_m SMALLINT`
     - `time_focus_m SMALLINT`
   - Added indexes:
     - `idx_entries_time_min_m ON entries(time_min_m)`
     - `idx_entries_time_max_m ON entries(time_max_m)`
   - Updated `insert_batch()` and `seed()` batch tuple construction to omit `valid_times`.

2. **`migrate_add_time_interval_cols.py`**:
   - Created idempotent migration script that:
     - Executes `ALTER TABLE entries ADD COLUMN IF NOT EXISTS ...` for the 6 new columns.
     - Creates indexes `idx_entries_time_min_m` and `idx_entries_time_max_m` `IF NOT EXISTS`.
     - Drops legacy column `ALTER TABLE entries DROP COLUMN IF EXISTS valid_times;`.

---

## 2. Verification & Test Results

1. **Migration Execution**:
   - Ran `python migrate_add_time_interval_cols.py` against dev database.
   - Result: `Migration complete.` (Exit code 0).
   - Tested re-running migration to confirm idempotency: succeeded without error.

2. **Schema Verification**:
   - Verified columns via `information_schema.columns`:
     - Present: `time_min_str`, `time_max_str`, `time_focus_str`, `time_min_m`, `time_max_m`, `time_focus_m`.
     - Absent: `valid_times`.
   - Verified indexes via `pg_indexes`:
     - `idx_entries_time_min_m` (btree on `time_min_m`)
     - `idx_entries_time_max_m` (btree on `time_max_m`)

3. **Regression Tests**:
   - Ran full test suite (`pytest`): 46 passed in 16.71s.

---

## 3. Concerns / Notes

- None. All schema changes and migration requirements satisfied.
