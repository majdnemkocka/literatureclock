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
