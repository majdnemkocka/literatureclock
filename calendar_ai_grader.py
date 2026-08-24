import json
import os
import re
import time

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from openai import OpenAI, APITimeoutError, APIConnectionError

from date_utils import validated_mmdd, parse_day_of_week

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
You are a strict data cleaner and date evaluator for a Hungarian "Literature Calendar" project.
Your goal is to evaluate Hungarian literary snippets for concrete calendar date and/or day-of-week references.

The snippet may contain `<span class="marked">...</span>` around matched date/time tokens.

For each entry, determine:
- "status": "KEEP" (valid literary date/weekday mention) or "DENY" (OCR garbage, bibliography, table of contents, pure chapter number, no calendar meaning).
- "rate": integer 0 to 5 (quality rating).
- "reason": short string in Hungarian or English explaining the decision.
- "date_min_str": "MM-DD" or null (e.g. "03-15" for March 15; "03-01" for March start; "12-01" for winter).
- "date_max_str": "MM-DD" or null (e.g. "03-15" for exact; "03-10" for March start; "02-28" for winter).
- "date_focus_str": "MM-DD" or null (most probable focus point within interval, e.g. "03-05").
- "day_of_week": "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY", "WEEKEND", or null if not weekday-specific.

Guidelines for Hungarian Dates & Intervals:
1. Exact dates: "március 15." -> date_min_str="03-15", date_max_str="03-15", date_focus_str="03-15", day_of_week=null.
2. Month parts: "március elején" -> "03-01" to "03-10", focus="03-05".
   "március derekán" / "közepén" -> "03-10" to "03-20", focus="03-15".
   "március végén" -> "03-20" to "03-31", focus="03-28".
3. Seasons: "tavasszal" -> "03-01" to "05-31", focus="04-15".
   "nyáron" -> "06-01" to "08-31", focus="07-15".
   "ősszel" -> "09-01" to "11-30", focus="10-15".
   "télen" -> "12-01" to "02-28", focus="01-15".
4. Weekdays: "hétfőn" -> day_of_week="MONDAY".
5. Hybrid: "egy forró augusztusi hétfőn" -> date_min="08-01", date_max="08-31", date_focus="08-15", day_of_week="MONDAY".

Input Data (JSON):
{data}

Output Format (JSON list):
Respond ONLY with a JSON array of objects containing the fields: id, status, rate, reason, date_min_str, date_max_str, date_focus_str, day_of_week.
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
            SELECT e.id, e.title, e.snippet, e.date_min_str, e.date_max_str, e.day_of_week
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
            SELECT id, title, snippet, date_min_str, date_max_str, day_of_week
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
        d_min_raw = row.get("date_min_str")
        d_max_raw = row.get("date_max_str") or d_min_raw
        d_foc_raw = row.get("date_focus_str") or d_min_raw
        dow_raw = row.get("day_of_week")

        d_min_str, d_min_d = validated_mmdd(d_min_raw)
        d_max_str, d_max_d = validated_mmdd(d_max_raw)
        d_foc_str, d_foc_d = validated_mmdd(d_foc_raw)

        # Handle year crossing (e.g. 12-01=335 to 02-28=59 -> 59 + 366 = 425)
        if d_min_d is not None and d_max_d is not None:
            if d_min_d > d_max_d:
                d_max_d += 366
            if d_foc_d is not None and d_foc_d < d_min_d and d_min_d > 300:
                d_foc_d += 366

            # Validate bounds
            if d_min_d > d_max_d:
                d_min_str, d_min_d = None, None
                d_max_str, d_max_d = None, None
                d_foc_str, d_foc_d = None, None
            elif d_foc_d is not None and not (d_min_d <= d_foc_d <= d_max_d):
                d_foc_str, d_foc_d = None, None

        dow_str, dow_num = parse_day_of_week(dow_raw)

        cur.execute("""
            UPDATE calendar_entries
            SET ai_checked = TRUE,
                ai_rating = %s,
                ai_reason = %s,
                date_min_str = %s,
                date_max_str = %s,
                date_focus_str = %s,
                date_min_d = %s,
                date_max_d = %s,
                date_focus_d = %s,
                day_of_week = %s,
                day_of_week_num = %s
            WHERE id = %s
        """, (
            row.get('rate'),
            row.get('reason'),
            d_min_str,
            d_max_str,
            d_foc_str,
            d_min_d,
            d_max_d,
            d_foc_d,
            dow_str,
            dow_num,
            row['id']
        ))


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
