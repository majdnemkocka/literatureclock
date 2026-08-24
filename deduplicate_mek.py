import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Optional


def normalize_snippet_for_hash(snippet: str) -> str:
    """Strip tags and extra whitespace to accurately detect duplicate quotes."""
    text = re.sub(r'<[^>]+>', ' ', snippet or '')
    return ' '.join(text.split())


def deduplicate(input_file: str = 'scrapers/mek_search/mek_search_results.jsonl',
                output_file: Optional[str] = None):
    in_path = Path(input_file)
    if not in_path.exists():
        print(f"Error: {in_path} not found.")
        return

    out_path = Path(output_file) if output_file else in_path.with_suffix('.tmp.jsonl')

    seen_semantic_keys = set()
    removed_count = 0
    total_count = 0
    
    print(f"Deduplicating {in_path}...")
    
    with in_path.open('r', encoding='utf-8') as infile, \
         out_path.open('w', encoding='utf-8') as outfile:
        
        for line in infile:
            stripped = line.strip()
            if not stripped:
                continue
            
            total_count += 1
            try:
                data = json.loads(stripped)
                # Deduplicate by (identifier/title, norm_time/time_min_str, cleaned snippet)
                key_id = data.get('urn') or data.get('link') or data.get('title', '')
                time_range = f"{data.get('time_min_str', '')}-{data.get('time_max_str', '')}" if data.get('time_min_str') else None
                valid_d = tuple(sorted(str(d) for d in data.get('valid_dates', [])))
                key_time = data.get('norm_time') or time_range or (valid_d if valid_d else None) or ''
                key_snip = normalize_snippet_for_hash(data.get('snippet', ''))
                semantic_hash = hashlib.md5(f"{key_id}|{key_time}|{key_snip}".encode('utf-8')).hexdigest()
            except Exception:
                semantic_hash = hashlib.md5(stripped.encode('utf-8')).hexdigest()
            
            if semantic_hash not in seen_semantic_keys:
                seen_semantic_keys.add(semantic_hash)
                outfile.write(stripped + '\n')
            else:
                removed_count += 1

    print(f"\nProcessing complete:")
    print(f"  Total lines processed: {total_count}")
    print(f"  Duplicates removed:     {removed_count}")
    print(f"  Unique lines remaining: {total_count - removed_count}")
    
    if not output_file:
        out_path.replace(in_path)
        print(f"\nSuccessfully replaced {in_path}")
    else:
        print(f"\nSuccessfully created {out_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Deduplicate JSONL results semantically.")
    parser.add_argument('--input', default='scrapers/mek_search/mek_search_results.jsonl',
                        help="Input JSONL file.")
    parser.add_argument('--output', default=None,
                        help="Output JSONL file (defaults to updating in-place).")
    args = parser.parse_args()
    deduplicate(args.input, args.output)
