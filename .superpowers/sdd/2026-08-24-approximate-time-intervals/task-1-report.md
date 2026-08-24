# Task 1 Report: Utility — `parse_extended_hhmm` and `validated_extended_hhmm`

## Summary
Implemented the standalone `time_utils.py` module and unit tests in `tests/test_time_utils.py`.

## Interfaces Provided
- `parse_extended_hhmm(s: str) -> int`: Parses `"HH:MM"` (where HH can be >= 24) to minutes from midnight. Raises `ValueError` on malformed input or invalid minutes.
- `validated_extended_hhmm(s) -> tuple[str, int] | tuple[None, None]`: Safe wrapper around `parse_extended_hhmm`, returning `(None, None)` for invalid inputs or hours > 48.
- `minutes_to_hhmm(m: int) -> str`: Converts integer minutes into formatted extended `"HH:MM"`.
- `circular_dist(a_m: int, b_m: int) -> int`: Calculates the shortest circular distance between two minute timestamps on a 1440-minute circular clock.

## Test Results
- TDD Red Phase: Ran `pytest tests/test_time_utils.py` and confirmed failure with `ModuleNotFoundError: No module named 'time_utils'`.
- TDD Green Phase: After implementation, all 19 tests in `tests/test_time_utils.py` passed.
- Full Suite: All 46 tests across the test suite passed.

## Commit
- `17a939d feat: add time_utils with extended HH:MM parsing and circular distance`

## Concerns / Notes
- None. Module is self-contained with no external dependencies and ready for consumption by downstream tasks.
