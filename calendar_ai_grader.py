import json
import os
import re
import time

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from openai import OpenAI, APITimeoutError, APIConnectionError

load_dotenv()

BATCH_SIZE = int(os.environ.get('CALENDAR_BATCH_SIZE', '8'))
MAX_RETRIES = 3
TIMEOUT_SECONDS = BATCH_SIZE * 30
DATABASE_URL = os.environ.get('DATABASE_URL')

GEMINI_BASE_URL = os.environ.get('GEMINI_BASE_URL', "https://generativelanguage.googleapis.com/v1beta/openai/")
GEMINI_MODEL_NAME = os.environ.get('GEMINI_MODEL') or os.environ.get('MODEL_NAME') or "gemini-2.5-flash"
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

BUDGET_USD = float(os.environ.get('BUDGET_USD', '2.0'))
GEMINI_FLASH_INPUT_USD_PER_M = float(os.environ.get('GEMINI_FLASH_INPUT_USD_PER_M', '0.30'))
GEMINI_FLASH_OUTPUT_USD_PER_M = float(os.environ.get('GEMINI_FLASH_OUTPUT_USD_PER_M', '2.50'))
RE_GRADE_AI_ONLY = os.environ.get('RE_GRADE_AI_ONLY', 'true').strip().lower() in ('1', 'true', 'yes')
RESET_AI_CHECKED_FOR_REGRADE = os.environ.get('RESET_AI_CHECKED_FOR_REGRADE', 'true').strip().lower() in ('1', 'true', 'yes')

if not DATABASE_URL:
    print("Error: DATABASE_URL is not set.")
    raise SystemExit(1)
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY is not set.")
    raise SystemExit(1)

client = OpenAI(base_url=GEMINI_BASE_URL, api_key=GEMINI_API_KEY)

total_input_tokens = 0
total_output_tokens = 0
total_cost_usd = 0.0

PROMPT_TEMPLATE = """
You are a strict data cleaner for a "Literature Calendar" project.
Your goal is to filter out invalid date entries found by a scraper.

The snippet is Hungarian and may contain `<span class="marked">...</span>` around matched date tokens.

DENY criteria:
1. Not a date reference (just numbers, IDs, pagination, filenames, or clocks without calendar-date meaning).
2. Meta-text only (TOC, bibliography, index, OCR file headers, dumps of timestamps).
3. Broken/gibberish snippet where date meaning is unreliable.

KEEP criteria:
1. Literary sentence/diary/event context with a concrete calendar date reference.
2. Marker context clearly supports a date mention.

Input Data (JSON):
{data}

Output Format (JSON list):
- "id": integer
- "reason": short string
- "rate": integer 0-5
- "status": "DENY" or "KEEP"
"""


def estimate_cost(input_tokens, output_tokens):
    return ((input_tokens / 1_000_000) * GEMINI_FLASH_INPUT_USD_PER_M) + (
        (output_tokens / 1_000_000) * GEMINI_FLASH_OUTPUT_USD_PER_M
    )


def strip_html_keep_marked(text):
    if not text:
        return ""

    marked_spans = []

    def keep_span(match):
        marked_spans.append(match.group(0))
        return f"__MARKED_SPAN_{len(marked_spans)-1}__"

    with_placeholders = re.sub(
        r'<span\s+class="marked">.*?</span>',
        keep_span,
        text,
        flags=re.DOTALL
    )
    clean = re.sub(r'<[^>]*>', '', with_placeholders)
    for i, original in enumerate(marked_spans):
        clean = clean.replace(f"__MARKED_SPAN_{i}__", original)
    return clean


def reset_regrade_scope(cur):
    if not (RE_GRADE_AI_ONLY and RESET_AI_CHECKED_FOR_REGRADE):
        return
    cur.execute("""
        UPDATE calendar_entries e
        SET ai_checked = FALSE
        WHERE e.is_literature IS TRUE
          AND NOT EXISTS (
              SELECT 1
              FROM calendar_votes v
              WHERE v.entry_id = e.id
                AND (v.corrected_date IS NULL OR v.corrected_date <> 'AI_DENY')
          )
    """)


def fetch_unchecked(cur, limit):
    if RE_GRADE_AI_ONLY:
        cur.execute("""
            SELECT e.id, e.title, e.snippet, e.valid_dates
            FROM calendar_entries e
            WHERE e.ai_checked IS FALSE
              AND e.is_literature IS TRUE
              AND NOT EXISTS (
                  SELECT 1
                  FROM calendar_votes v
                  WHERE v.entry_id = e.id
                    AND (v.corrected_date IS NULL OR v.corrected_date <> 'AI_DENY')
              )
            ORDER BY e.id
            LIMIT %s
        """, (limit,))
    else:
        cur.execute("""
            SELECT id, title, snippet, valid_dates
            FROM calendar_entries
            WHERE ai_checked IS FALSE
              AND is_literature IS TRUE
            ORDER BY id
            LIMIT %s
        """, (limit,))
    return cur.fetchall()


def count_remaining(cur):
    if RE_GRADE_AI_ONLY:
        cur.execute("""
            SELECT count(*)
            FROM calendar_entries e
            WHERE e.ai_checked IS FALSE
              AND e.is_literature IS TRUE
              AND NOT EXISTS (
                  SELECT 1
                  FROM calendar_votes v
                  WHERE v.entry_id = e.id
                    AND (v.corrected_date IS NULL OR v.corrected_date <> 'AI_DENY')
              )
        """)
    else:
        cur.execute("SELECT count(*) FROM calendar_entries WHERE ai_checked IS FALSE AND is_literature IS TRUE")
    return cur.fetchone()[0]


def clear_ai_deny_votes(cur, entry_ids):
    if not entry_ids:
        return
    cur.execute("""
        DELETE FROM calendar_votes
        WHERE corrected_date = 'AI_DENY'
          AND entry_id = ANY(%s)
    """, (entry_ids,))


def insert_denies(cur, deny_rows):
    if not deny_rows:
        return
    values = [(r['id'], 0, 'ambiguous', 'AI_DENY') for r in deny_rows]
    execute_values(cur, """
        INSERT INTO calendar_votes (entry_id, rating, date_class, corrected_date)
        VALUES %s
    """, values)


def mark_checked(cur, rows):
    for row in rows:
        cur.execute("""
            UPDATE calendar_entries
            SET ai_checked = TRUE,
                ai_rating = %s,
                ai_reason = %s
            WHERE id = %s
        """, (row.get('rate'), row.get('reason'), row['id']))


def call_model(batch_entries):
    global total_input_tokens, total_output_tokens, total_cost_usd

    input_rows = []
    for e in batch_entries:
        snippet = strip_html_keep_marked(e[2] or "")
        if len(snippet) > 780:
            snippet = snippet[:780] + "..."
        input_rows.append({
            "id": e[0],
            "title": e[1],
            "snippet": snippet,
            "matched_dates": e[3]
        })

    prompt = PROMPT_TEMPLATE.format(data=json.dumps(input_rows, ensure_ascii=False))
    parsed = []
    input_tokens = 0
    output_tokens = 0

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=GEMINI_MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a strict data cleaner. Respond only with JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                timeout=TIMEOUT_SECONDS
            )

            if response.usage:
                input_tokens = response.usage.prompt_tokens or 0
                output_tokens = response.usage.completion_tokens or 0
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            total_cost_usd += estimate_cost(input_tokens, output_tokens)

            content = response.choices[0].message.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result_data = json.loads(content)
            if isinstance(result_data, list):
                parsed = result_data
            elif isinstance(result_data, dict):
                parsed = next((v for v in result_data.values() if isinstance(v, list)), [])
            break

        except (APITimeoutError, APIConnectionError) as e:
            wait_time = (attempt + 1) * 5
            print(f"Timeout/connection error ({attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait_time)
            else:
                return None
        except Exception as e:
            print(f"Unexpected model error: {e}")
            return None

    if input_rows:
        last_input = input_rows[-1]
        last_output = next((r for r in parsed if r.get('id') == last_input['id']), None)
        print(f"  -> Last Item Input: {json.dumps(last_input, ensure_ascii=False)}")
        print(f"  -> Last Item Output: {json.dumps(last_output, ensure_ascii=False) if last_output else 'NO_OUTPUT_MATCH'}")

    print(f"  -> Tokens: +{input_tokens} in / +{output_tokens} out")
    print(f"  -> Cost so far: ${total_cost_usd:.6f} / ${BUDGET_USD:.2f}")
    return parsed


def main():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        reset_regrade_scope(cur)
        conn.commit()

        total_to_process = count_remaining(cur)
        if total_to_process == 0:
            print("No unchecked calendar entries found.")
            return

        print(f"Starting calendar AI grading for {total_to_process} entries...")
        processed = 0
        start = time.time()

        while True:
            entries = fetch_unchecked(cur, BATCH_SIZE)
            if not entries:
                print("No more unchecked calendar entries.")
                break

            print(f"\nProcessing calendar batch of {len(entries)} entries...")
            result_rows = call_model(entries)
            if result_rows is None:
                print("Batch failed; stopping.")
                break

            clear_ai_deny_votes(cur, [r['id'] for r in result_rows if 'id' in r])
            deny_rows = [r for r in result_rows if r.get('status') == 'DENY']
            insert_denies(cur, deny_rows)
            mark_checked(cur, result_rows)
            conn.commit()

            processed += len(entries)
            elapsed = time.time() - start
            speed = processed / elapsed if elapsed > 0 else 0
            print(f"Progress: {processed}/{total_to_process} | Speed: {speed:.2f} entries/sec")

            if total_cost_usd >= BUDGET_USD:
                print("Budget limit reached. Stopping after committed batch.")
                break

            time.sleep(0.5)

    finally:
        print("\n==============================")
        print("FINAL CALENDAR SESSION SUMMARY")
        print("==============================")
        print(f"Total Input Tokens:  {total_input_tokens}")
        print(f"Total Output Tokens: {total_output_tokens}")
        print(f"Total Tokens Used:   {total_input_tokens + total_output_tokens}")
        print(f"Estimated Cost:      ${total_cost_usd:.6f}")
        print(f"Budget Limit:        ${BUDGET_USD:.2f}")
        print("==============================")
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
