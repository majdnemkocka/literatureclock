import json
import os
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

INPUT_FILE = os.environ.get('INPUT_FILE', 'scrapers/mek_search/mek_search_results.jsonl')
DATABASE_URL = os.environ.get('DATABASE_URL')

def seed():
    if not DATABASE_URL:
        print("Error: DATABASE_URL environment variable is not set.")
        print("Please set DATABASE_URL (e.g. in a .env file or environment variable).")
        return

    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    print(f"Connecting to database using {INPUT_FILE}...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("Creating tables...")
    cur.execute("""
        DROP TABLE IF EXISTS votes;
        DROP TABLE IF EXISTS entries;

        CREATE TABLE entries (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            link TEXT,
            snippet TEXT,
            is_literature BOOLEAN,
            valid_times TEXT[],
            categories TEXT[],
            urn TEXT,
            author TEXT,
            genre TEXT,
            source_url TEXT,
            source_type TEXT,
            is_fallback BOOLEAN DEFAULT FALSE,
            ai_checked BOOLEAN DEFAULT FALSE
        );

        CREATE TABLE votes (
            id SERIAL PRIMARY KEY,
            entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE,
            rating INTEGER CHECK (rating >= 0 AND rating <= 5),
            am_pm VARCHAR(20),
            corrected_time VARCHAR(10),
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_entries_ai_checked ON entries(ai_checked);
        CREATE INDEX IF NOT EXISTS idx_entries_is_lit ON entries(is_literature);
    """)

    print("Reading entries and batch inserting...")
    batch_size = 1000
    batch = []
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                batch.append((
                    data.get('title', ''),
                    data.get('link', ''),
                    data.get('snippet', ''),
                    data.get('is_literature', False),
                    data.get('valid_times', []),
                    data.get('topics', []),
                    data.get('urn', ''),
                    data.get('author', ''),
                    data.get('genre', ''),
                    data.get('source_url', ''),
                    data.get('source_type', 'snippet_fallback'),
                    data.get('is_fallback', False)
                ))

                if len(batch) >= batch_size:
                    insert_batch(cur, batch)
                    batch = []
                    print(f"Inserted {batch_size} entries...")
            except Exception as e:
                print(f"Skip error: {e}")

        if batch:
            insert_batch(cur, batch)
            print(f"Inserted final {len(batch)} entries.")

    conn.commit()
    cur.close()
    conn.close()
    print("\nSeeding completed successfully!")

def insert_batch(cur, batch):
    query = """
        INSERT INTO entries (
            title, link, snippet, is_literature, valid_times, categories,
            urn, author, genre, source_url, source_type, is_fallback
        ) VALUES %s
    """
    execute_values(cur, query, batch)

if __name__ == '__main__':
    seed()
