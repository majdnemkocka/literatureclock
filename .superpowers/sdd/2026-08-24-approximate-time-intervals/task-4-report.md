# Task 4 Report: Display / Eligibility Logic

## Summary
Implemented the quote eligibility evaluation and weighted random selection module `quote_selector.py` along with unit tests `tests/test_quote_selector.py`.

## Implementation Details
1. **`quote_selector.py`**:
   - `_get(entry, attr)`: Helper to extract fields from either object attributes or dictionary keys.
   - `is_eligible(entry, current_m: int) -> bool`: Checks whether the entry's interval `[time_min_m, time_max_m]` covers `current_m`. Correctly handles midnight-crossing intervals (`time_max_m >= 1440`) by testing both `current_m` and `current_m + 1440`. Returns `False` when fields are `None`.
   - `quote_weight(entry, current_m: int) -> float`: Calculates selection weight `1.0 / ((1 + precision) * (1 + dist_to_focus))` where `dist_to_focus` is calculated using `circular_dist(current_m, focus_m % 1440)`. Ensures weights are always strictly positive (`> 0`).
   - `pick_quote(candidates: list, current_m: int) -> Any | None`: Filters candidates for eligibility at `current_m` and picks one quote using `random.choices` weighted by `quote_weight`. Returns `None` if candidates list is empty or no candidates are eligible.

2. **`tests/test_quote_selector.py`**:
   - 19 test cases covering exact time matches, fuzzy interval bounds, midnight-crossing intervals, null/missing fields, weighting comparisons (wider intervals vs exact, focus proximity, non-zero guarantee), dict and object representation support, and weighted candidate picking.

## Test Results
- Ran `python -m pytest tests/test_quote_selector.py -v`: 19 passed in 0.11s.
- Ran combined interval test suite (`tests/test_time_utils.py`, `tests/test_ai_grader_interval.py`, `tests/test_quote_selector.py`): 42 passed in 4.85s.

## Commit
- `4970030`: `feat: add quote_selector with interval eligibility and weighted pick`
