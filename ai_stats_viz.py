import argparse
import os
import json
import psycopg2
import statistics
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')


def normalize_reason(reason):
    if not reason:
        return "Unknown"
    
    r = reason.lower()
    
    if "table of contents" in r or "toc" in r:
        return "Meta-text (TOC)"
    if "bibliography" in r:
        return "Meta-text (Bibliography)"
    if "meta-text" in r or "metatext" in r:
        return "Meta-text (General)"
    if "date" in r:
        return "Date/Format"
    if "gibberish" in r:
        return "Gibberish"
    if "chapter" in r:
        return "Chapter Numbers"
    if "not a time" in r or "not a_time" in r:
        return "Not a Time"
    if "comment" in r:
        return "Comment"
    
    return "Other"


def main():
    parser = argparse.ArgumentParser(description="Generate AI grading statistics chart for Clock (time) or Calendar (date).")
    parser.add_argument("--dataset", choices=["time", "date"], default="time", help="Dataset to visualize (time or date).")
    parser.add_argument("--output", default=None, help="Output HTML file path.")
    args = parser.parse_args()

    if not DATABASE_URL:
        print("Error: DATABASE_URL is not set.")
        return

    table_name = "calendar_entries" if args.dataset == "date" else "entries"
    output_html = args.output or ("ai_calendar_stats_chart.html" if args.dataset == "date" else "ai_stats_chart.html")
    title_text = f"AI Grading Statistics ({'Calendar' if args.dataset == 'date' else 'Clock'})"

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 1. Get AI ratings and reasons
    print(f"Fetching AI ratings and reasons from {table_name}...")
    cur.execute(f"""
        SELECT ai_rating, ai_reason 
        FROM {table_name}
        WHERE ai_checked = TRUE
    """)
    rows = cur.fetchall()
    
    ratings = [r[0] for r in rows if r[0] is not None]
    denied_reasons = [r[1] for r in rows if r[0] == 0 and r[1] is not None]

    # 2. Calculate Stats
    total_checked = len(ratings)
    if total_checked == 0:
        print("No AI checked entries found.")
        return

    mean_rating = statistics.mean(ratings)
    median_rating = statistics.median(ratings)
    rating_counts = {i: ratings.count(i) for i in range(6)}

    # 3. Categorize Denied Reasons
    denied_stats = {}
    for reason in denied_reasons:
        norm = normalize_reason(reason)
        denied_stats[norm] = denied_stats.get(norm, 0) + 1
    
    # Sort denied stats by count
    denied_stats = dict(sorted(denied_stats.items(), key=lambda item: item[1], reverse=True))

    cur.close()
    conn.close()

    # Generate HTML
    generate_html(output_html, title_text, total_checked, rating_counts, mean_rating, median_rating, denied_stats)
    print(f"\nAI Stats HTML generated: {output_html}")


def generate_html(output_html, title_text, total, counts, mean, median, denied_reasons):
    rating_labels = [str(i) for i in range(6)]
    rating_data = [counts[i] for i in range(6)]
    
    denied_labels = list(denied_reasons.keys())
    denied_data = list(denied_reasons.values())

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title_text}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; background: #f0f2f5; color: #333; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
        h1, h2 {{ text-align: center; color: #1a73e8; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .stat-box {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; border: 1px solid #e0e0e0; }}
        .stat-val {{ font-size: 2em; font-weight: bold; color: #1a73e8; margin-bottom: 5px; }}
        .stat-label {{ font-size: 0.9em; color: #5f6368; text-transform: uppercase; letter-spacing: 1px; }}
        .charts-container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }}
        @media (max-width: 768px) {{ .charts-container {{ grid-template-columns: 1fr; }} }}
        .chart-box {{ background: white; padding: 15px; border: 1px solid #eee; border-radius: 8px; }}
        canvas {{ width: 100% !important; height: auto !important; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <h1>AI Grading Statistics</h1>
        
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-val">{total}</div>
                <div class="stat-label">Total AI Checked</div>
            </div>
            <div class="stat-box">
                <div class="stat-val">{mean:.2f}</div>
                <div class="stat-label">Mean Rating</div>
            </div>
            <div class="stat-box">
                <div class="stat-val">{median}</div>
                <div class="stat-label">Median Rating</div>
            </div>
            <div class="stat-box">
                <div class="stat-val">{counts[0]}</div>
                <div class="stat-label">Denied (0 stars)</div>
            </div>
        </div>

        <div class="charts-container">
            <div class="chart-box">
                <h2>Rating Distribution</h2>
                <canvas id="ratingChart"></canvas>
            </div>
            <div class="chart-box">
                <h2>Denied Reasons (Categorized)</h2>
                <canvas id="deniedChart"></canvas>
            </div>
        </div>
    </div>

    <script>
        // Rating Distribution Chart
        const ctxRating = document.getElementById('ratingChart').getContext('2d');
        new Chart(ctxRating, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(rating_labels)},
                datasets: [{{
                    label: 'Number of Entries',
                    data: {json.dumps(rating_data)},
                    backgroundColor: [
                        'rgba(234, 67, 53, 0.7)',  // 0
                        'rgba(251, 188, 5, 0.7)',   // 1
                        'rgba(251, 188, 5, 0.7)',   // 2
                        'rgba(66, 133, 244, 0.7)',  // 3
                        'rgba(66, 133, 244, 0.7)',  // 4
                        'rgba(52, 168, 83, 0.7)'    // 5
                    ],
                    borderColor: 'rgba(255, 255, 255, 1)',
                    borderWidth: 1
                }}]
            }},
            options: {{
                scales: {{ y: {{ beginAtZero: true }} }},
                plugins: {{ legend: {{ display: false }} }}
            }}
        }});

        // Denied Reasons Chart
        const ctxDenied = document.getElementById('deniedChart').getContext('2d');
        new Chart(ctxDenied, {{
            type: 'pie',
            data: {{
                labels: {json.dumps(denied_labels)},
                datasets: [{{
                    data: {json.dumps(denied_data)},
                    backgroundColor: [
                        '#4285F4', '#EA4335', '#FBBC05', '#34A853',
                        '#FF6D01', '#46BDC6', '#7BAAF7', '#F07B72'
                    ]
                }}]
            }},
            options: {{
                plugins: {{
                    legend: {{ position: 'bottom', labels: {{ boxWidth: 12 }} }}
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
