import os
import json
import time
import re
import psycopg2
from psycopg2.extras import execute_values
from openai import OpenAI, APITimeoutError, APIConnectionError
from typing import List, Dict
from dotenv import load_dotenv

# Add repo root to sys.path
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / 'scrapers') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'scrapers'))
if str(REPO_ROOT / 'scrapers' / 'mek_search') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'scrapers' / 'mek_search'))

from extractor import raw_html_to_text
from time_utils import validated_extended_hhmm
try:
    from mek_time_search import MekSourceFetcher
    source_fetcher = MekSourceFetcher()
except Exception:
    source_fetcher = None

# Load environment variables from .env file
load_dotenv()

# Configuration
BATCH_SIZE = 8
DATABASE_URL = os.environ.get('DATABASE_URL')
MAX_RETRIES = 3
TIMEOUT_SECONDS = BATCH_SIZE * 30
BUDGET_USD = float(os.environ.get('BUDGET_USD', '2.0'))
RE_GRADE_AI_ONLY = os.environ.get('RE_GRADE_AI_ONLY', 'true').strip().lower() in ('1', 'true', 'yes')
RESET_AI_CHECKED_FOR_REGRADE = os.environ.get('RESET_AI_CHECKED_FOR_REGRADE', 'true').strip().lower() in ('1', 'true', 'yes')

# AI Provider Configuration
AI_PROVIDER = os.environ.get('AI_PROVIDER', "gemini").strip().lower()
LM_STUDIO_BASE_URL = os.environ.get('LM_STUDIO_BASE_URL', "http://localhost:1234/v1")
DEFAULT_LMSTUDIO_MODEL_NAME = os.environ.get('MODEL_NAME', "local-model")
GEMINI_BASE_URL = os.environ.get('GEMINI_BASE_URL', "https://generativelanguage.googleapis.com/v1beta/openai/")
GEMINI_MODEL_NAME = os.environ.get('GEMINI_MODEL') or os.environ.get('MODEL_NAME') or "gemini-2.0-flash"
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GEMINI_FLASH_INPUT_USD_PER_M = float(os.environ.get('GEMINI_FLASH_INPUT_USD_PER_M', '0.30'))
GEMINI_FLASH_OUTPUT_USD_PER_M = float(os.environ.get('GEMINI_FLASH_OUTPUT_USD_PER_M', '2.50'))

# Global Counters
total_input_tokens = 0
total_output_tokens = 0
total_cost_usd = 0.0

if not DATABASE_URL:
    print("Error: DATABASE_URL is not set.")
    exit(1)

def init_client_and_model():
    if AI_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            print("Error: GEMINI_API_KEY is not set while AI_PROVIDER=gemini.")
            exit(1)
        print(f"Connecting to Gemini API at {GEMINI_BASE_URL}...")
        client = OpenAI(base_url=GEMINI_BASE_URL, api_key=GEMINI_API_KEY)
        model_name = GEMINI_MODEL_NAME
        print(f"Using model: {model_name}\n")
        return client, model_name

    # Default: LM Studio
    print(f"Connecting to LM Studio at {LM_STUDIO_BASE_URL}...")
    client = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key="lm-studio")
    model_name = DEFAULT_LMSTUDIO_MODEL_NAME
    try:
        models = client.models.list()
        if models.data:
            available_ids = [m.id for m in models.data]
            print(f"Available local models: {', '.join(available_ids)}")
            if DEFAULT_LMSTUDIO_MODEL_NAME not in available_ids:
                model_name = available_ids[0]
    except Exception as e:
        print(f"Warning: Could not list models: {e}")
    print(f"Using model: {model_name}\n")
    return client, model_name

client, MODEL_NAME = init_client_and_model()

PROMPT_TEMPLATE = """
You are a strict data cleaner for a "Literature Clock" project.
Your goal is to filter out invalid entries found by a scraper.

The scraper looked for time patterns (e.g. "12:30", "negyed három"), but it found many false positives.
The text is in Hungarian.
Important: The snippet may contain `<span class="marked">...</span>` around tokens matched by the scraper.
These exact tags indicate the anchor of the candidate time expression.

Criteria for DENYING an entry (marking it as bad):
1. **Not a Time**: The matching text refers to a date (e.g., "11/12" meaning Nov 12th), a quantity, a price, or a chapter number, NOT a time of day.
2. **Meta-text**: The snippet is a Table of Contents, a header, a footnote, or a bibliography, not a narrative sentence.
3. **Comment**: The data is not of the highest quality, it may include comments made on the book, not just the book's core text.
4. **Gibberish**: The snippet is broken, unreadable, or just a list of numbers.
5. **File/OCR metadata**: Filename/index artifacts like `.indd`, `.jpg`, page/index dumps, or dense timestamp logs.

Criteria for KEEPING:
1. It is a valid sentence from a book, or it is a diary's timestamp
2. It refers to a specific time of day, especially around `<span class="marked">...</span>`.

Prioritization rules:
- Judge primarily by the local context around `<span class="marked">...</span>`.
- If marker context is clearly metadata/listing noise, DENY.
- If marker context is natural narrative time-of-day usage, KEEP.

Input Data (JSON):
{data}

Output Format (JSON):
Return a list of objects. Each object must have:
- "id": (integer) The entry ID from the input.
- "reason": (string) Short explanation (e.g., "Valid quote", "Date format").
- "rate": (integer) 0-5 rating of quality (0 for DENY, 5 for perfect KEEP)
- "status": "DENY" or "KEEP"
- "am_pm": "AM", "PM", or "AMBIGUOUS"
  * Check the local snippet and the 'wider_context' for narrative cues about the time of day:
    - "AM": morning / daytime events (e.g. "reggel", "délelőtt", "hajnal", "reggeli", "ébredés").
    - "PM": afternoon / evening / night events (e.g. "este", "éjjel", "délután", "vacsora").
    - "AMBIGUOUS": only if the wider scene still gives no clue.
- "corrected_time": null  (deprecated — superseded by time_focus_str below)
- "time_min_str": (string or null)
  * If status=DENY, return null.
  * The start of the time interval in "HH:MM" format (24h).
  * For midnight-crossing intervals use extended notation so time_min_str <= time_max_str always holds.
    Example: "éjfél körül" -> time_min_str="23:45", time_max_str="24:15".
  * For exact times: time_min_str == time_max_str == time_focus_str.
- "time_max_str": (string or null)
  * If status=DENY, return null.
  * The end of the interval in "HH:MM" (extended notation allowed, e.g. "24:15", "26:00").
- "time_focus_str": (string or null)
  * If status=DENY, return null.
  * The single most probable moment within the interval. NOT necessarily the midpoint.
  * "nem sokkal fél hat előtt" -> focus is 17:29 (near the end), not 17:23.
  * "éjféli harangszót követően rögvest" -> focus is 24:01, not 24:05.
  * For exact times: equal to time_min_str and time_max_str.

Interval width guidelines:
  * Exact minute ("13:45", "fél hat", "negyed három"): interval width = 0 (all three fields equal).
  * Fuzzy symmetric ("körül", "tájban", "nagyjából X"): +-10-20 min, focus = centre.
  * Asymmetric ("rögvest", "nem sokkal X előtt/után"): focus near one end of interval.
  * Daytime sub-part ("kora délután", "késő este"): +-45-90 min.
  * Full daypart ("este", "reggel", "éjjel"): 3-5 hour wide interval.
"""

def get_unchecked_entries(cur, limit):
    if RE_GRADE_AI_ONLY:
        cur.execute("""
            SELECT e.id, e.title, e.snippet, e.time_min_str, e.source_url
            FROM entries e
            WHERE e.ai_checked IS FALSE
              AND e.is_literature IS TRUE
              AND NOT EXISTS (
                  SELECT 1
                  FROM votes v
                  WHERE v.entry_id = e.id
                    AND (v.corrected_time IS NULL OR v.corrected_time <> 'AI_DENY')
              )
            ORDER BY e.id
            LIMIT %s
        """, (limit,))
    else:
        cur.execute("""
            SELECT id, title, snippet, time_min_str, source_url
            FROM entries
            WHERE ai_checked IS FALSE
              AND is_literature IS TRUE
            ORDER BY id
            LIMIT %s
        """, (limit,))
    return cur.fetchall()

def mark_as_checked(cur, results):
    if not results:
        return

    for r in results:
        am_pm_val = r.get('am_pm', 'AMBIGUOUS')
        if am_pm_val not in ('AM', 'PM', 'AMBIGUOUS'):
            am_pm_val = 'AMBIGUOUS'

        min_str, min_m = validated_extended_hhmm(r.get('time_min_str'))
        max_str, max_m = validated_extended_hhmm(r.get('time_max_str'))
        foc_str, foc_m = validated_extended_hhmm(r.get('time_focus_str'))

        # Enforce time_min_m <= time_max_m
        if min_m is not None and max_m is not None and min_m > max_m:
            min_str = max_str = foc_str = None
            min_m = max_m = foc_m = None

        # Enforce time_focus_m within [time_min_m, time_max_m]
        if foc_m is not None and min_m is not None and max_m is not None:
            if not (min_m <= foc_m <= max_m):
                foc_str, foc_m = None, None

        cur.execute("""
            UPDATE entries
            SET ai_checked     = TRUE,
                ai_rating      = %s,
                ai_reason      = %s,
                ai_am_pm       = %s,
                time_min_str   = %s,
                time_min_m     = %s,
                time_max_str   = %s,
                time_max_m     = %s,
                time_focus_str = %s,
                time_focus_m   = %s
            WHERE id = %s
        """, (
            r.get('rate'), r.get('reason'), am_pm_val,
            min_str, min_m,
            max_str, max_m,
            foc_str, foc_m,
            r['id']
        ))

def insert_deny_votes(cur, denials):
    if not denials: return
    # (entry_id, rating, am_pm, corrected_time)
    values = [(d['id'], 0, 'ambiguous', 'AI_DENY') for d in denials]
    execute_values(cur, """
        INSERT INTO votes (entry_id, rating, am_pm, corrected_time)
        VALUES %s
    """, values)

def clear_ai_deny_votes(cur, entry_ids):
    if not entry_ids:
        return
    cur.execute("""
        DELETE FROM votes
        WHERE corrected_time = 'AI_DENY'
          AND entry_id = ANY(%s)
    """, (entry_ids,))

def strip_html(text):
    if not text: return ""
    # Preserve exact scraper markers (<span class="marked">...</span>) and strip every other tag.
    preserved_spans = []
    def keep_marked_span(match):
        preserved_spans.append(match.group(0))
        return f"__MARKED_SPAN_{len(preserved_spans)-1}__"

    with_placeholders = re.sub(
        r'<span\s+class="marked">.*?</span>',
        keep_marked_span,
        text,
        flags=re.DOTALL
    )

    clean = re.sub(r'<[^>]*>', '', with_placeholders)

    for i, original_span in enumerate(preserved_spans):
        clean = clean.replace(f"__MARKED_SPAN_{i}__", original_span)

    return clean

def estimate_call_cost_usd(input_tokens, output_tokens):
    if AI_PROVIDER != "gemini":
        return 0.0
    in_cost = (input_tokens / 1_000_000) * GEMINI_FLASH_INPUT_USD_PER_M
    out_cost = (output_tokens / 1_000_000) * GEMINI_FLASH_OUTPUT_USD_PER_M
    return in_cost + out_cost

def process_batch(cur, entries):
    global total_input_tokens, total_output_tokens, total_cost_usd
    # Prepare data
    input_data = []
    longest_entry = None
    max_length = -1

    for e in entries:
        # e = (id, title, snippet, time_min_str, source_url)
        
        # Preprocess snippet: strip HTML and truncate
        raw_snippet = e[2] or ""
        clean_snippet = strip_html(raw_snippet)
        
        current_length = len(clean_snippet)
        if current_length > max_length:
            max_length = current_length
            longest_entry = {"id": e[0], "title": e[1], "length": current_length}

        if len(clean_snippet) > 780:
            clean_snippet = clean_snippet[:780] + "..."

        wider_context = None
        source_url = e[4] if len(e) > 4 else None
        if source_url and source_fetcher:
            try:
                page_html = source_fetcher.fetch_page(source_url)
                if page_html:
                    doc_text = raw_html_to_text(page_html)
                    raw_quote = re.sub(r'<[^>]+>', '', raw_snippet).strip()
                    sample_words = " ".join(raw_quote.split()[:6])
                    if sample_words:
                        pos = doc_text.find(sample_words)
                        if pos != -1:
                            w_start = max(0, pos - 500)
                            w_end = min(len(doc_text), pos + len(raw_quote) + 500)
                            candidate_ctx = doc_text[w_start:w_end].strip()
                            if len(candidate_ctx) > len(clean_snippet) + 40:
                                wider_context = candidate_ctx
            except Exception:
                pass

        item_data = {
            "id": e[0],
            "title": e[1],
            "snippet": clean_snippet,
            "matched_time": e[3]
        }
        if wider_context:
            item_data["wider_context"] = wider_context

        input_data.append(item_data)

    if longest_entry:
        print(f"  -> Longest in batch: ID {longest_entry['id']}, Length: {longest_entry['length']}, Title: {longest_entry['title']}")

    prompt = PROMPT_TEMPLATE.format(data=json.dumps(input_data, ensure_ascii=False))

    results = []
    input_token_count = 0
    output_token_count = 0
    
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a strict data cleaner. Respond only with JSON. The snippet provided has been pre-cleaned of HTML tags."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                timeout=TIMEOUT_SECONDS
            )
            
            # Get usage metadata
            if response.usage:
                input_token_count = response.usage.prompt_tokens or 0
                output_token_count = response.usage.completion_tokens or 0
            total_input_tokens += input_token_count
            total_output_tokens += output_token_count

            content = response.choices[0].message.content
            print(f"  -> AI Raw Response:\n{content}\n")
            # Local models sometimes wrap JSON in code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            results_data = json.loads(content)
            # Handle both list and object with list formats
            if isinstance(results_data, dict):
                # Try to find a list within the dict if it's not a list itself
                for key in results_data:
                    if isinstance(results_data[key], list):
                        results = results_data[key]
                        break
                else:
                    results = [] # Fallback
            else:
                results = results_data
            
            # If we reached here, success!
            break

        except (APITimeoutError, APIConnectionError) as e:
            wait_time = (attempt + 1) * 5
            print(f"  -> LM Studio Timeout/Connection Error (Attempt {attempt+1}/{MAX_RETRIES}): {e}")
            print(f"     Problematic Input Data Summary:")
            for item in input_data:
                print(f"       - ID {item['id']}: {item['title']} ({len(item['snippet'])} chars)")
            
            if attempt < MAX_RETRIES - 1:
                print(f"     Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                with open("grader_errors.log", "a", encoding="utf-8") as f:
                    f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | CRITICAL: All {MAX_RETRIES} retries failed for batch starting with ID {entries[0][0]}\n")
                    f.write(f"     Input IDs: {[item['id'] for item in input_data]}\n")
                return False
        except Exception as e:
            print(f"  -> Unexpected Error: {e}")
            with open("grader_errors.log", "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | Error: {str(e)} for batch starting with ID {entries[0][0]}\n")
            return False

    denials = [r for r in results if r.get('status') == 'DENY']
    keeps = [r for r in results if r.get('status') == 'KEEP']

    # Debug: always print last item input/output in each batch
    if input_data:
        last_input = input_data[-1]
        last_output = next((r for r in results if r.get('id') == last_input.get('id')), None)
        print(f"  -> Last Item Input: {json.dumps(last_input, ensure_ascii=False)}")
        print(f"  -> Last Item Output: {json.dumps(last_output, ensure_ascii=False) if last_output else 'NO_OUTPUT_MATCH'}")
    
    print(f"  -> AI Decision: {len(denials)} DENY, {len(keeps)} KEEP")
    print(f"  -> Tokens: Input +{input_token_count}, Output +{output_token_count}")
    print(f"  -> Total Tokens: {total_input_tokens + total_output_tokens}")
    batch_cost = estimate_call_cost_usd(input_token_count, output_token_count)
    total_cost_usd += batch_cost
    if AI_PROVIDER == "gemini":
        print(f"  -> Cost: Batch ${batch_cost:.6f} | Total ${total_cost_usd:.6f} / ${BUDGET_USD:.2f}")

    # DB Updates
    clear_ai_deny_votes(cur, [r['id'] for r in results if 'id' in r])
    insert_deny_votes(cur, denials)
    mark_as_checked(cur, results)

    # Log to file
    with open("grader.log", "a", encoding="utf-8") as f:
        f.write(f"Batch: {len(entries)} entries | Input: {input_token_count} | Output: {output_token_count} | Total: {input_token_count + output_token_count}\n")
        if AI_PROVIDER == "gemini":
            f.write(f"  Cost: Batch ${batch_cost:.6f} | Total ${total_cost_usd:.6f}\n")
        if longest_entry:
            f.write(f"  Longest: ID {longest_entry['id']}, {longest_entry['length']} chars\n")

    return True # Signal success

def main():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False # We'll commit after each batch
    cur = conn.cursor()

    cur.execute("""
        ALTER TABLE entries ADD COLUMN IF NOT EXISTS ai_checked BOOLEAN DEFAULT FALSE;
        ALTER TABLE entries ADD COLUMN IF NOT EXISTS ai_rating INTEGER;
        ALTER TABLE entries ADD COLUMN IF NOT EXISTS ai_reason TEXT;
    """)
    conn.commit()

    if RE_GRADE_AI_ONLY and RESET_AI_CHECKED_FOR_REGRADE:
        cur.execute("""
            UPDATE entries e
            SET ai_checked = FALSE
            WHERE e.is_literature IS TRUE
              AND NOT EXISTS (
                  SELECT 1
                  FROM votes v
                  WHERE v.entry_id = e.id
                    AND (v.corrected_time IS NULL OR v.corrected_time <> 'AI_DENY')
              )
        """)
        conn.commit()
        print("Reset ai_checked=FALSE for literature entries without human (non-AI) ratings.")
    elif RE_GRADE_AI_ONLY:
        print("Keeping existing ai_checked flags (resume mode for prior re-grade run).")

    # Get total count for progress tracking
    if RE_GRADE_AI_ONLY:
        cur.execute("""
            SELECT count(*)
            FROM entries e
            WHERE e.ai_checked IS FALSE
              AND e.is_literature IS TRUE
              AND NOT EXISTS (
                  SELECT 1
                  FROM votes v
                  WHERE v.entry_id = e.id
                    AND (v.corrected_time IS NULL OR v.corrected_time <> 'AI_DENY')
              )
        """)
    else:
        cur.execute("SELECT count(*) FROM entries WHERE ai_checked IS FALSE AND is_literature IS TRUE")
    total_to_process = cur.fetchone()[0]
    
    if total_to_process == 0:
        print("No unchecked entries found. Everything is already processed.")
        cur.close()
        conn.close()
        return

    print(f"Starting processing of {total_to_process} entries...")
    total_processed = 0
    start_time = time.time()

    try:
        while True:
            entries = get_unchecked_entries(cur, BATCH_SIZE)
            if not entries:
                print("\nNo more unchecked entries found.")
                break

            print(f"\nProcessing batch of {len(entries)} entries...")
            success = process_batch(cur, entries)
            
            if success == "RETRY":
                continue # Try the same batch again
                
            if not success:
                print("Batch processing failed. Stopping script.")
                break
            
            conn.commit()
            
            total_processed += len(entries)
            elapsed_time = time.time() - start_time
            
            # Progress calculations
            progress_pct = (total_processed / total_to_process) * 100
            avg_time_per_entry = elapsed_time / total_processed
            remaining_entries = total_to_process - total_processed
            etc_seconds = remaining_entries * avg_time_per_entry
            
            # Format ETC
            etc_mins, etc_secs = divmod(int(etc_seconds), 60)
            etc_hours, etc_mins = divmod(etc_mins, 60)
            etc_str = f"{etc_hours:02d}:{etc_mins:02d}:{etc_secs:02d}"

            print(f"Progress: {total_processed}/{total_to_process} ({progress_pct:.2f}%)")
            print(f"Avg Speed: {1/avg_time_per_entry:.2f} entries/sec | ETC: {etc_str}")
            if AI_PROVIDER == "gemini":
                print(f"Cost So Far: ${total_cost_usd:.6f} / ${BUDGET_USD:.2f}")
                if total_cost_usd >= BUDGET_USD:
                    print("Budget limit reached. Stopping after committed batch.")
                    break
            
            # Small delay to keep the local machine responsive
            time.sleep(1.0) 

    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"\nCritical Error: {e}")
        conn.rollback()
    finally:
        # Final Summary
        duration = time.time() - start_time
        print("\n" + "="*30)
        print("FINAL SESSION SUMMARY")
        print("="*30)
        print(f"Entries Processed: {total_processed}")
        print(f"Total Time:        {duration:.2f}s")
        print(f"Total Input Tokens:  {total_input_tokens}")
        print(f"Total Output Tokens: {total_output_tokens}")
        print(f"Total Tokens Used:   {total_input_tokens + total_output_tokens}")
        if AI_PROVIDER == "gemini":
            print(f"Estimated Cost:      ${total_cost_usd:.6f}")
            print(f"Budget Limit:        ${BUDGET_USD:.2f}")
        print("="*30)
        
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
