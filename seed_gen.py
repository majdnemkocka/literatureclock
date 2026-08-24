import json
import os

INPUT_FILE = os.environ.get('INPUT_FILE', 'scrapers/mek_search/mek_search_results.jsonl')
OUTPUT_SQL = os.environ.get('OUTPUT_SQL', 'seed.sql')

def escape_sql(text):
    if text is None:
        return "NULL"
    return "'" + str(text).replace("'", "''") + "'"

def to_m(s):
    if not s or ':' not in s:
        return None
    try:
        parts = s.split(':')
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return None

def escape_sql_array(items):
    if not items:
        return "'{}'"
    escaped_items = []
    for item in items:
        clean = str(item).replace('\\', '\\\\').replace('"', '\\"').replace("'", "''")
        escaped_items.append(f'"{clean}"')
    return "'{" + ",".join(escaped_items) + "}'"

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    print(f"Generating {OUTPUT_SQL} from {INPUT_FILE}...")
    
    with open(OUTPUT_SQL, 'w', encoding='utf-8') as sql_file:
        # Create Tables
        sql_file.write("""
DROP TABLE IF EXISTS votes;
DROP TABLE IF EXISTS entries;

CREATE TABLE entries (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    link TEXT,
    snippet TEXT,
    is_literature BOOLEAN,
    time_min_str VARCHAR(7),
    time_max_str VARCHAR(7),
    time_focus_str VARCHAR(7),
    time_min_m SMALLINT,
    time_max_m SMALLINT,
    time_focus_m SMALLINT,
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
CREATE INDEX IF NOT EXISTS idx_entries_time_min_m ON entries(time_min_m);
CREATE INDEX IF NOT EXISTS idx_entries_time_max_m ON entries(time_max_m);

-- Insert Data
""")
        
        count = 0
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    
                    title = data.get('title', '')
                    link = data.get('link', '')
                    snippet = data.get('snippet', '')
                    is_lit = 'true' if str(data.get('is_literature', False)).strip().lower() in ('1', 'true', 'yes') else 'false'
                    
                    time_min_str = data.get('time_min_str') or data.get('norm_time')
                    time_max_str = data.get('time_max_str') or time_min_str
                    time_focus_str = data.get('time_focus_str') or time_min_str

                    time_min_m = data.get('time_min_m') if data.get('time_min_m') is not None else to_m(time_min_str)
                    time_max_m = data.get('time_max_m') if data.get('time_max_m') is not None else to_m(time_max_str)
                    time_focus_m = data.get('time_focus_m') if data.get('time_focus_m') is not None else to_m(time_focus_str)

                    min_m_val = str(time_min_m) if time_min_m is not None else "NULL"
                    max_m_val = str(time_max_m) if time_max_m is not None else "NULL"
                    foc_m_val = str(time_focus_m) if time_focus_m is not None else "NULL"

                    categories_str = escape_sql_array(data.get('topics', []))

                    urn = data.get('urn', '')
                    author = data.get('author', '')
                    genre = data.get('genre', '')
                    source_url = data.get('source_url', '')
                    source_type = data.get('source_type', 'snippet_fallback')
                    is_fallback = 'true' if str(data.get('is_fallback', False)).strip().lower() in ('1', 'true', 'yes') else 'false'

                    sql = (
                        f"INSERT INTO entries (title, link, snippet, is_literature, time_min_str, time_max_str, time_focus_str, time_min_m, time_max_m, time_focus_m, categories, urn, author, genre, source_url, source_type, is_fallback) "
                        f"VALUES ({escape_sql(title)}, {escape_sql(link)}, {escape_sql(snippet)}, {is_lit}, {escape_sql(time_min_str)}, {escape_sql(time_max_str)}, {escape_sql(time_focus_str)}, {min_m_val}, {max_m_val}, {foc_m_val}, {categories_str}, "
                        f"{escape_sql(urn)}, {escape_sql(author)}, {escape_sql(genre)}, {escape_sql(source_url)}, {escape_sql(source_type)}, {is_fallback});\n"
                    )
                    sql_file.write(sql)
                    count += 1
                except json.JSONDecodeError:
                    continue
        
        print(f"Finished. Generated SQL for {count} entries into {OUTPUT_SQL}.")

if __name__ == '__main__':
    main()
