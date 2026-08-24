import json
import os
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

from date_utils import validated_mmdd, parse_day_of_week

load_dotenv()

INPUT_FILE = os.environ.get('CALENDAR_INPUT_FILE', 'scrapers/mek_search/mek_calendar_search_results.jsonl')
DATABASE_URL = os.environ.get('DATABASE_URL')


def create_calendar_tables(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS calendar_entries (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            link TEXT,
            snippet TEXT,
            is_literature BOOLEAN,
            categories TEXT[],
            urn TEXT,
            author TEXT,
            genre TEXT,
            source_url TEXT,
            source_type TEXT,
            is_fallback BOOLEAN DEFAULT FALSE,
            ai_rating INTEGER,
            ai_reason TEXT,
            ai_checked BOOLEAN DEFAULT FALSE,
            date_min_str    VARCHAR(5),
            date_max_str    VARCHAR(5),
            date_focus_str  VARCHAR(5),
            date_min_d      SMALLINT,
            date_max_d      SMALLINT,
            date_focus_d    SMALLINT,
            day_of_week     VARCHAR(15),
            day_of_week_num SMALLINT
        );

        CREATE TABLE IF NOT EXISTS calendar_votes (
            id SERIAL PRIMARY KEY,
            entry_id INTEGER REFERENCES calendar_entries(id) ON DELETE CASCADE,
            rating INTEGER CHECK (rating >= 0 AND rating <= 5),
            date_class VARCHAR(20),
            corrected_date TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_calendar_entries_ai_checked ON calendar_entries(ai_checked);
        CREATE INDEX IF NOT EXISTS idx_calendar_entries_is_lit ON calendar_entries(is_literature);
        CREATE INDEX IF NOT EXISTS idx_cal_date_min_d ON calendar_entries(date_min_d);
        CREATE INDEX IF NOT EXISTS idx_cal_date_max_d ON calendar_entries(date_max_d);
        CREATE INDEX IF NOT EXISTS idx_cal_dow ON calendar_entries(day_of_week_num);
    """)


def insert_batch(cur, batch):
    query = """
        INSERT INTO calendar_entries (
            title, link, snippet, is_literature, categories,
            urn, author, genre, source_url, source_type, is_fallback,
            date_min_str, date_max_str, date_focus_str, date_min_d, date_max_d, date_focus_d,
            day_of_week, day_of_week_num
        )
        VALUES %s
    """
    execute_values(cur, query, batch)


def seed():
    if not DATABASE_URL:
        print("Error: DATABASE_URL environment variable not set.")
        return

    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    print(f"Connecting to database using {INPUT_FILE}...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    create_calendar_tables(cur)

    print("Reading calendar entries and batch inserting...")
    batch_size = 1000
    batch = []
    inserted = 0

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if data.get('count') == 0:
                    continue
                title = data.get('title', '')
                snippet = data.get('snippet', '')
                if not title or not snippet:
                    continue

                is_lit = str(data.get('is_literature', False)).strip().lower() in ('1', 'true', 'yes')
                categories = data.get('topics', [])
                urn = data.get('urn', '')
                author = data.get('author', '')
                genre = data.get('genre', '')
                source_url = data.get('source_url', '')
                source_type = data.get('source_type', 'snippet_fallback')
                is_fallback = str(data.get('is_fallback', False)).strip().lower() in ('1', 'true', 'yes')

                # Date intervals & weekdays
                d_min_str, d_min_d = validated_mmdd(data.get('date_min_str') or (data.get('valid_dates', [None])[0] if data.get('valid_dates') else None))
                d_max_str, d_max_d = validated_mmdd(data.get('date_max_str') or d_min_str)
                d_foc_str, d_foc_d = validated_mmdd(data.get('date_focus_str') or d_min_str)

                dow_str, dow_num = parse_day_of_week(data.get('day_of_week'))

                batch.append((
                    title,
                    data.get('link', ''),
                    snippet,
                    is_lit,
                    categories,
                    urn,
                    author,
                    genre,
                    source_url,
                    source_type,
                    is_fallback,
                    d_min_str,
                    d_max_str,
                    d_foc_str,
                    d_min_d,
                    d_max_d,
                    d_foc_d,
                    dow_str,
                    dow_num
                ))

                if len(batch) >= batch_size:
                    insert_batch(cur, batch)
                    inserted += len(batch)
                    print(f"Inserted {inserted} calendar entries...")
                    batch = []
            except Exception as e:
                print(f"Skip error: {e}")

    if batch:
        insert_batch(cur, batch)
        inserted += len(batch)
        print(f"Inserted final {len(batch)} calendar entries.")

    conn.commit()
    cur.close()
    conn.close()
    print(f"Calendar seeding completed successfully! Total inserted: {inserted}")


if __name__ == '__main__':
    seed()
