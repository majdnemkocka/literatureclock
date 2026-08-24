# tests/test_calendar_ai_grader.py
import os
import sys
from pathlib import Path
import pytest
import psycopg2
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL")


@pytest.fixture
def db_conn():
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not set")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        # Create a test entry
        cur.execute("""
            INSERT INTO calendar_entries (title, snippet, is_literature)
            VALUES ('Test Book', 'Március 15-én gyűltünk össze.', TRUE)
            RETURNING id;
        """)
        entry_id = cur.fetchone()[0]
        conn.commit()
        yield conn, entry_id
        # Cleanup
        cur.execute("DELETE FROM calendar_entries WHERE id = %s", (entry_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        pytest.skip(f"Database connection error: {e}")


def test_mark_checked_exact_date(db_conn):
    conn, entry_id = db_conn
    from calendar_ai_grader import mark_checked

    row = {
        "id": entry_id,
        "rate": 5,
        "reason": "Clear exact date",
        "date_min_str": "03-15",
        "date_max_str": "03-15",
        "date_focus_str": "03-15",
        "day_of_week": None,
    }
    cur = conn.cursor()
    mark_checked(cur, [row])
    conn.commit()

    cur.execute("""
        SELECT ai_checked, ai_rating, date_min_str, date_max_str, date_focus_str, date_min_d, date_max_d, date_focus_d, day_of_week, day_of_week_num
        FROM calendar_entries WHERE id = %s
    """, (entry_id,))
    res = cur.fetchone()
    cur.close()

    assert res[0] is True
    assert res[1] == 5
    assert res[2] == "03-15"
    assert res[3] == "03-15"
    assert res[4] == "03-15"
    assert res[5] == 75
    assert res[6] == 75
    assert res[7] == 75
    assert res[8] is None
    assert res[9] is None


def test_mark_checked_winter_year_crossing(db_conn):
    conn, entry_id = db_conn
    from calendar_ai_grader import mark_checked

    row = {
        "id": entry_id,
        "rate": 4,
        "reason": "Winter season",
        "date_min_str": "12-01",
        "date_max_str": "02-28",
        "date_focus_str": "01-15",
        "day_of_week": None,
    }
    cur = conn.cursor()
    mark_checked(cur, [row])
    conn.commit()

    cur.execute("""
        SELECT date_min_str, date_max_str, date_focus_str, date_min_d, date_max_d, date_focus_d
        FROM calendar_entries WHERE id = %s
    """, (entry_id,))
    res = cur.fetchone()
    cur.close()

    assert res[0] == "12-01"
    assert res[1] == "02-28"
    assert res[2] == "01-15"
    assert res[3] == 336  # Dec 1 in leap year base
    assert res[4] == 425  # 59 + 366
    assert res[3] <= res[4]


def test_mark_checked_weekday_and_hybrid(db_conn):
    conn, entry_id = db_conn
    from calendar_ai_grader import mark_checked

    row = {
        "id": entry_id,
        "rate": 5,
        "reason": "Summer Monday",
        "date_min_str": "08-01",
        "date_max_str": "08-31",
        "date_focus_str": "08-15",
        "day_of_week": "hétfő",
    }
    cur = conn.cursor()
    mark_checked(cur, [row])
    conn.commit()

    cur.execute("""
        SELECT date_min_str, day_of_week, day_of_week_num
        FROM calendar_entries WHERE id = %s
    """, (entry_id,))
    res = cur.fetchone()
    cur.close()

    assert res[0] == "08-01"
    assert res[1] == "MONDAY"
    assert res[2] == 1
