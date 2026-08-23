from pathlib import Path
import json


def get_hits_stats(jsonl_path='hits.jsonl'):
    """
    Reads hits.jsonl, collects stats including the ordered set of norm times and rule_id distribution.
    Returns a dict with total hits, ordered norm times, and rule_id distribution.
    """
    path = Path(jsonl_path)
    if not path.exists():
        return {
            'total_hits': 0,
            'ordered_norm_times': [],
            'rule_id_distribution': {}
        }

    norm_times = set()
    total_hits = 0
    rule_id_counts = {}

    with path.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            if 'norm_time' in data:
                norm_times.add(data['norm_time'])
            if 'rule_id' in data:
                rule_id = data['rule_id']
                rule_id_counts[rule_id] = rule_id_counts.get(rule_id, 0) + 1
            total_hits += 1

    ordered_norm_times = sorted(norm_times)
    rule_id_distribution = dict(sorted(rule_id_counts.items()))
    return {
        'total_hits': total_hits,
        'ordered_norm_times': ordered_norm_times,
        'rule_id_distribution': rule_id_distribution
    }


def load_stats(summary_path: str = "mek_downloads/_summary.json") -> dict:
    """Load and return the stats from _summary.json."""
    path = Path(summary_path)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def print_summary(summary_path: str = 'mek_downloads/_summary.json') -> None:
    """Load and display summary (all_available_exts + counts + percentages) in table form."""
    data = load_stats(summary_path)
    summary = data.get('summary', {})
    exts = summary.get('all_available_exts', [])
    counts = summary.get('all_available_exts_count', {})

    total = sum(counts.values()) or 1  # avoid division by zero

    print('Summary:')
    print('-' * 50)
    print(f"{'Extension':<10} | {'Count':>6}")
    print('-' * 50)
    for ext in sorted(exts, key=lambda e: counts.get(e, 0), reverse=True):
        count = counts.get(ext, 0)
        print(f"{ext:<10} | {count:>6}")
    print('-' * 50)
    print(f"Total extensions: {len(exts)}   Total files: {total}")


if __name__ == '__main__':
    print_summary()

    stats = get_hits_stats()
    for stat in stats:
        print(stat, stats[stat])
