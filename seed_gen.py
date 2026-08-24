import json
import os

INPUT_FILE = os.environ.get('INPUT_FILE', 'scrapers/mek_search/mek_search_results.jsonl')
OUTPUT_SQL = os.environ.get('OUTPUT_SQL', 'seed.sql')

def escape_sql(text):
    if text is None:
        return "NULL"
    return "'" + str(text).replace("'", "''") + "'"

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
                    is_lit = str(str(data.get('is_literature', False)).strip().lower() in ('1', 'true', 'yes')).lower()
                    
                    valid_times_str = escape_sql_array(data.get('valid_times', []))
                    categories_str = escape_sql_array(data.get('topics', []))

                    urn = data.get('urn', '')
                    author = data.get('author', '')
                    genre = data.get('genre', '')
                    source_url = data.get('source_url', '')
                    source_type = data.get('source_type', 'snippet_fallback')
                    is_fallback = str(str(data.get('is_fallback', False)).strip().lower() in ('1', 'true', 'yes')).lower()

                    sql = (
                        f"INSERT INTO entries (title, link, snippet, is_literature, valid_times, categories, urn, author, genre, source_url, source_type, is_fallback) "
                        f"VALUES ({escape_sql(title)}, {escape_sql(link)}, {escape_sql(snippet)}, {is_lit}, {valid_times_str}, {categories_str}, "
                        f"{escape_sql(urn)}, {escape_sql(author)}, {escape_sql(genre)}, {escape_sql(source_url)}, {escape_sql(source_type)}, {is_fallback});\n"
                    )
                    sql_file.write(sql)
                    count += 1
                except json.JSONDecodeError:
                    continue
        
        print(f"Finished. Generated SQL for {count} entries into {OUTPUT_SQL}.")

if __name__ == '__main__':
    main()
