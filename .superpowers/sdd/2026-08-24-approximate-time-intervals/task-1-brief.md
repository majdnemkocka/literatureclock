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


