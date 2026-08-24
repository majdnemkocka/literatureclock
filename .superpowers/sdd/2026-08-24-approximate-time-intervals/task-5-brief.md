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


