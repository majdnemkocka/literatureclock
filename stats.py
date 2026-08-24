import argparse
import json
from pathlib import Path
from typing import Any, Dict


def get_hits_stats(jsonl_path='hits.jsonl') -> Dict[str, Any]:
    """
    Reads a JSONL results file (hits.jsonl or mek_search_results.jsonl),
    collects stats including ordered norm times, rule distribution, source types,
    and fallback counts.
    """
    path = Path(jsonl_path)
    if not path.exists():
        return {
            'total_hits': 0,
            'ordered_norm_times': [],
            'rule_id_distribution': {},
            'source_type_distribution': {},
            'literature_count': 0,
            'fallback_count': 0
        }

    norm_times = set()
    total_hits = 0
    rule_id_counts = {}
    source_type_counts = {}
    literature_count = 0
    fallback_count = 0

    with path.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue

            total_hits += 1

            # Extract normalized times from time_min_str or norm_time
            if data.get('time_min_str'):
                norm_times.add(data['time_min_str'])
            elif data.get('norm_time'):
                norm_times.add(data['norm_time'])

            if data.get('rule_id'):
                rule_id = data['rule_id']
                rule_id_counts[rule_id] = rule_id_counts.get(rule_id, 0) + 1

            source_type = data.get('source_type', 'snippet_fallback' if data.get('is_fallback') else 'legacy')
            source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1

            if data.get('is_literature', False):
                literature_count += 1

            if data.get('is_fallback', False):
                fallback_count += 1

    ordered_norm_times = sorted(norm_times)
    rule_id_distribution = dict(sorted(rule_id_counts.items()))
    return {
        'total_hits': total_hits,
        'unique_times_count': len(ordered_norm_times),
        'ordered_norm_times': ordered_norm_times,
        'rule_id_distribution': rule_id_distribution,
        'source_type_distribution': source_type_counts,
        'literature_count': literature_count,
        'fallback_count': fallback_count
    }


def load_stats(summary_path: str = "mek_downloads/_summary.json") -> dict:
    """Load and return the stats from _summary.json."""
    path = Path(summary_path)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def print_summary(summary_path: str = 'mek_downloads/_summary.json') -> None:
    """Load and display summary in table form."""
    data = load_stats(summary_path)
    summary = data.get('summary', {})
    exts = summary.get('all_available_exts', [])
    counts = summary.get('all_available_exts_count', {})

    total = sum(counts.values()) or 1

    print('Download Summary:')
    print('-' * 50)
    print(f"{'Extension':<10} | {'Count':>6}")
    print('-' * 50)
    for ext in sorted(exts, key=lambda e: counts.get(e, 0), reverse=True):
        count = counts.get(ext, 0)
        print(f"{ext:<10} | {count:>6}")
    print('-' * 50)
    print(f"Total extensions: {len(exts)}   Total files: {total}\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Analyze hits and downloads statistics.")
    parser.add_argument('--file', default='scrapers/mek_search/mek_search_results.jsonl',
                        help="Path to JSONL hits file to analyze.")
    parser.add_argument('--summary', default='mek_downloads/_summary.json',
                        help="Path to download _summary.json file.")
    args = parser.parse_args()

    if Path(args.summary).exists():
        print_summary(args.summary)

    hits_file = args.file if Path(args.file).exists() else 'hits.jsonl'
    if Path(hits_file).exists():
        print(f"Analyzing hits in {hits_file}:")
        print('=' * 50)
        stats = get_hits_stats(hits_file)
        for stat, val in stats.items():
            if stat == 'ordered_norm_times':
                print(f"  {stat}: {len(val)} unique minutes covered")
            else:
                print(f"  {stat}: {val}")
    else:
        print(f"No hits file found at {args.file} or hits.jsonl")
