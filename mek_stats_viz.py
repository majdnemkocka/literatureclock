import json
import collections
import os
import sys

INPUT_FILE = 'scrapers/mek_search/mek_search_results.jsonl'
OUTPUT_HTML = 'mek_stats_chart.html'

def get_entries_for_time(target_time, only_literature=False):
    """Finds the first 5 entries for a specific HH:MM time slot."""
    entries = []
    if not os.path.exists(INPUT_FILE):
        return entries

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if only_literature and not data.get('is_literature', False):
                    continue
                    
                matched_time = data.get('time_min_str') or data.get('norm_time')
                if target_time == matched_time:
                    entries.append(data)
                    if len(entries) >= 5:
                        break
            except json.JSONDecodeError:
                continue
    return entries

def show_entries(query_time):
    print(f"\n--- First 5 entries for {query_time} (Literature favored) ---")
    # We'll fetch all matches then sort/filter for display if we wanted complexity, 
    # but here let's just show what we find, maybe marking them.
    # Actually, let's fetch entries and display a tag if it is literature.
    
    entries = get_entries_for_time(query_time)
    if not entries:
        print("No entries found for this time.")
    for i, entry in enumerate(entries, 1):
        is_lit = entry.get('is_literature', False)
        lit_tag = "[LIT]" if is_lit else "[---]"
        
        print(f"\n{i}. {lit_tag} {entry.get('title')}")
        print(f"   Link: {entry.get('link')}")
        snippet = entry.get('snippet', '')
        snippet = snippet.replace('<div class="foundtext">', '').replace('</div>', '').replace('<span class="marked">', '').replace('</span>', '')
        snippet = snippet.replace('\n', ' ').strip()
        print(f"   Snippet: {snippet[:300]}...")

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    # If an argument is passed, treat it as a search query
    if len(sys.argv) > 1:
        query_time = sys.argv[1]
        show_entries(query_time)
        return

    # Initialize counters
    minute_counts_all = collections.defaultdict(int)
    minute_counts_lit = collections.defaultdict(int)
    total_all = 0
    total_lit = 0
    
    print(f"Reading {INPUT_FILE}...")
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    is_lit = data.get('is_literature', False)
                    matched_time = data.get('time_min_str') or data.get('norm_time')
                    if matched_time and len(matched_time) == 5 and matched_time[2] == ':':
                        minute_counts_all[matched_time] += 1
                        total_all += 1
                        if is_lit:
                            minute_counts_lit[matched_time] += 1
                            total_lit += 1
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Analyze coverage
    minutes_in_day = 24 * 60
    
    # Stats for Literature
    covered_minutes_lit = len(minute_counts_lit)
    missing_minutes_lit = minutes_in_day - covered_minutes_lit
    missing_percent_lit = (missing_minutes_lit / minutes_in_day) * 100
    
    # Stats for All
    covered_minutes_all = len(minute_counts_all)
    missing_minutes_all = minutes_in_day - covered_minutes_all
    
    # 1. Stats Output
    print("\n" + "="*40)
    print("STATISTICS (LITERATURE ONLY)")
    print("="*40)
    print(f"Total entries: {total_lit}")
    print(f"Coverage: {covered_minutes_lit}/{minutes_in_day} minutes")
    print(f"Missing: {missing_minutes_lit} ({missing_percent_lit:.2f}%)")
    
    print("\n" + "-"*40)
    print("STATISTICS (ALL)")
    print("-" * 40)
    print(f"Total entries: {total_all}")
    print(f"Coverage: {covered_minutes_all}/{minutes_in_day} minutes")


    # 2. ASCII Chart (Hourly aggregation - Literature)
    print("\n" + "="*40)
    print("HOURLY DISTRIBUTION (LITERATURE)")
    print("="*40)
    
    hourly_counts = [0] * 24
    for t, count in minute_counts_lit.items():
        h = int(t.split(':')[0])
        hourly_counts[h] += count
    
    max_hourly = max(hourly_counts) if hourly_counts else 1
    scale = 50.0 / max_hourly if max_hourly > 0 else 1

    for h in range(24):
        count = hourly_counts[h]
        bar_len = int(count * scale)
        bar = '#' * bar_len
        print(f"{h:02d}:00 - {h:02d}:59 | {count:5d} | {bar}")

    # 3. HTML Chart Generation
    all_minutes = [f"{h:02d}:{m:02d}" for h in range(24) for m in range(60)]
    generate_html_chart(all_minutes, minute_counts_all, minute_counts_lit, total_lit, missing_minutes_lit, missing_percent_lit)
    print(f"\nDetailed HTML chart generated: {OUTPUT_HTML}")

    # 4. Interactive Lookup
    print("\n" + "="*40)
    print("QUICK LOOKUP")
    print("="*40)
    print("Enter a time (HH:MM) to see entries, or 'q' to quit.")
    
    while True:
        try:
            val = input("\nTime > ").strip()
            if not val:
                continue
            if val.lower() == 'q':
                break
            if len(val) == 5 and val[2] == ':' and val[:2].isdigit() and val[3:].isdigit():
                show_entries(val)
            else:
                print("Invalid format. Please use HH:MM (e.g., 21:44).")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

def generate_html_chart(all_minutes, counts_all, counts_lit, total_lit, missing_lit, missing_pct_lit):
    labels_json = json.dumps(all_minutes)
    
    data_all = [counts_all.get(m, 0) for m in all_minutes]
    data_lit = [counts_lit.get(m, 0) for m in all_minutes]
    
    data_all_json = json.dumps(data_all)
    data_lit_json = json.dumps(data_lit)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MEK Search Stats (Literature)</title>
    <style>
        body {{ font-family: sans-serif; padding: 20px; background: #f4f4f4; }}
        .container {{ max_width: 1000px; margin: 0 auto; background: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        h1 {{ text-align: center; }}
        .stats {{ display: flex; justify-content: space-around; margin-bottom: 20px; padding: 10px; background: #eee; border-radius: 5px; }}
        .stat-box {{ text-align: center; }}
        .stat-val {{ font-size: 1.5em; font-weight: bold; color: #333; }}
        .stat-label {{ font-size: 0.9em; color: #666; }}
        #chart-container {{ position: relative; height: 60vh; width: 100%; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <h1>Literature Clock - Search Stats</h1>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-val">{total_lit}</div>
                <div class="stat-label">Lit Entries Found</div>
            </div>
            <div class="stat-box">
                <div class="stat-val">{missing_lit}</div>
                <div class="stat-label">Missing Minutes (Lit)</div>
            </div>
            <div class="stat-box">
                <div class="stat-val">{missing_pct_lit:.2f}%</div>
                <div class="stat-label">Missing %</div>
            </div>
        </div>

        <div id="chart-container">
            <canvas id="myChart"></canvas>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('myChart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: {labels_json},
                datasets: [
                    {{
                        label: 'Literature Entries',
                        data: {data_lit_json},
                        backgroundColor: 'rgba(75, 192, 192, 0.7)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 1,
                        order: 1
                    }},
                    {{
                        label: 'All Entries',
                        data: {data_all_json},
                        backgroundColor: 'rgba(200, 200, 200, 0.3)',
                        borderColor: 'rgba(200, 200, 200, 0.5)',
                        borderWidth: 1,
                        hidden: true, // Default to hidden to focus on Literature
                        order: 2
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{
                    mode: 'index',
                    intersect: false,
                }},
                scales: {{
                    x: {{
                        ticks: {{
                            maxTicksLimit: 24,
                            callback: function(val, index) {{
                                return this.getLabelForValue(val).endsWith(':00') ? this.getLabelForValue(val) : '';
                            }}
                        }},
                        grid: {{ display: false }}
                    }},
                    y: {{
                        beginAtZero: true,
                        title: {{ display: true, text: 'Count' }}
                    }}
                }},
                plugins: {{
                    tooltip: {{
                        callbacks: {{
                            title: function(context) {{
                                return 'Time: ' + context[0].label;
                            }}
                        }}
                    }},
                    legend: {{ display: true }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html_content)

if __name__ == '__main__':
    main()
