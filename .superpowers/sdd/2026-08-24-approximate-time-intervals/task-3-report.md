# Task 3 Report: AI Grader — Prompt and Output Handling

**Status:** DONE

## Commit

`1b86b0f` feat: extend AI grader to emit time_min/max/focus interval fields

## Changes Made

### `ai_grader.py`

1. **Added import** (line 23):
   ```python
   from time_utils import validated_extended_hhmm
   ```

2. **Replaced `PROMPT_TEMPLATE`**: The output spec now instructs the AI to return:
   - `"corrected_time": null` (deprecated, kept for backward JSON compat)
   - `"time_min_str"`: start of interval in HH:MM (extended notation allowed)
   - `"time_max_str"`: end of interval in HH:MM (extended notation allowed)
   - `"time_focus_str"`: single most probable moment within interval
   - Interval width guidelines for AI reasoning
   - The old `corrected_time` parsing branch is REMOVED.

3. **Replaced `mark_as_checked()`**: New implementation:
   - Calls `validated_extended_hhmm()` on all three interval fields.
   - Enforces `time_min_m <= time_max_m`: if violated, nulls all three field pairs.
   - Enforces `time_focus_m in [time_min_m, time_max_m]`: if violated, nulls focus fields only (keeps min/max).
   - Single `UPDATE entries SET ... time_min_str, time_min_m, time_max_str, time_max_m, time_focus_str, time_focus_m`.
   - Old branches (valid_times ARRAY update, corrected_time parsing) are fully removed.

### `tests/test_ai_grader_interval.py` (new file)

4 integration tests, all using real DB via `DATABASE_URL`:
- `test_exact_time_written` — exact 17:30 → all three `_m = 1050`
- `test_fuzzy_midnight_written` — 23:45/24:15/24:00 → 1425/1455/1440
- `test_invalid_min_gt_max_nulled` — 17:30>16:00 → all three NULL
- `test_focus_out_of_range_nulled` — focus 16:00 outside [13:00, 15:00] → min/max written, focus NULL

## Test Results

### Task-specific tests
```
tests/test_ai_grader_interval.py — 4 passed in 5.23s
```

### Full suite
```
50 collected | 49 passed | 1 failed (21.44s)
```

The 1 failure (`test_default_models_fallback_when_no_key`) is **pre-existing and unrelated to Task 3**:
it asserts `gemini-2.0-flash` is in the live Gemini model list, but the API no longer serves that model
(only newer versions like `gemini-2.5-flash` etc. are available). This failure existed before Task 3.

## Constraints Verified

- UTF-8: all files written with UTF-8 encoding.
- Extended HH:MM (h>=24): handled by `validated_extended_hhmm` from Task 1.
- `time_min_m <= time_max_m` enforced: violation → all three interval pairs set to NULL.
- `time_focus_m` within `[time_min_m, time_max_m]`: violation → focus fields only set to NULL.
- `corrected_time` in prompt: returns `null` (deprecated note included).
- Old `corrected_time` parsing branch: REMOVED from `mark_as_checked`.
- `votes.corrected_time` (human votes): untouched.
- Integration tests skip gracefully when `DATABASE_URL` not set.
