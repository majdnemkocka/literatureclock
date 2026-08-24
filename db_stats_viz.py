import os
import json
import collections
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')
OUTPUT_HTML = 'db_stats_chart.html'

def main():
    if not DATABASE_URL:
        print("Error: DATABASE_URL is not set.")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 1. Get counts for Cleaned Literature (Not DENYed, includes unchecked)
    print("Fetching cleaned literature counts...")
    cur.execute("""
        SELECT t, count(*) 
        FROM (
            SELECT time_min_str as t
            FROM entries e
            WHERE is_literature = TRUE
            AND time_min_str IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM votes v WHERE v.entry_id = e.id AND v.corrected_time = 'AI_DENY'
            )
        ) sub
        WHERE t ~ '^[0-9]{2}:[0-9]{2}$'
        GROUP BY t
    """)
    rows_cleaned = cur.fetchall()
    minute_counts_cleaned = {r[0]: r[1] for r in rows_cleaned}

    # 2. Get counts for Explicitly KEEPed Literature (ai_checked = TRUE and NOT DENYed)
    print("Fetching explicitly KEEPed literature counts...")
    cur.execute("""
        SELECT t, count(*) 
        FROM (
            SELECT time_min_str as t
            FROM entries e
            WHERE is_literature = TRUE
            AND time_min_str IS NOT NULL
            AND ai_checked = TRUE
            AND NOT EXISTS (
                SELECT 1 FROM votes v WHERE v.entry_id = e.id AND v.corrected_time = 'AI_DENY'
            )
        ) sub
        WHERE t ~ '^[0-9]{2}:[0-9]{2}$'
        GROUP BY t
    """)
    rows_kept = cur.fetchall()
    minute_counts_kept = {r[0]: r[1] for r in rows_kept}

    # 3. Get counts for All Literature
    print("Fetching all literature counts...")
    cur.execute("""
        SELECT t, count(*) 
        FROM (
            SELECT time_min_str as t
            FROM entries e
            WHERE is_literature = TRUE
            AND time_min_str IS NOT NULL
        ) sub
        WHERE t ~ '^[0-9]{2}:[0-9]{2}$'
        GROUP BY t
    """)
    rows_all = cur.fetchall()
    minute_counts_all_lit = {r[0]: r[1] for r in rows_all}

    # 4. Get overall stats
    cur.execute("SELECT COUNT(*) FROM entries WHERE is_literature = TRUE")
    total_lit = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*) FROM entries e
        WHERE is_literature = TRUE 
        AND NOT EXISTS (
            SELECT 1 FROM votes v WHERE v.entry_id = e.id AND v.corrected_time = 'AI_DENY'
        )
    """)
    total_cleaned = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM entries e
        WHERE is_literature = TRUE 
        AND ai_checked = TRUE
        AND NOT EXISTS (
            SELECT 1 FROM votes v WHERE v.entry_id = e.id AND v.corrected_time = 'AI_DENY'
        )
    """)
    total_kept = cur.fetchone()[0]

    cur.close()
    conn.close()

    # Analyze coverage (Kept)
    minutes_in_day = 24 * 60
    all_minutes = [f"{h:02d}:{m:02d}" for h in range(24) for m in range(60)]
    
    covered_minutes_kept = len(minute_counts_kept)
    missing_minutes_kept = minutes_in_day - covered_minutes_kept
    missing_percent_kept = (missing_minutes_kept / minutes_in_day) * 100

    print(f"\nTotal Explicitly Kept: {total_kept}")
    print(f"Coverage (Kept): {covered_minutes_kept}/{minutes_in_day} minutes")
    print(f"Missing (Kept): {missing_minutes_kept} ({missing_percent_kept:.2f}%)")

    # Generate HTML
    generate_html_chart(all_minutes, minute_counts_all_lit, minute_counts_cleaned, minute_counts_kept, total_kept, missing_minutes_kept, missing_percent_kept)
    print(f"\nDetailed HTML chart generated: {OUTPUT_HTML}")

def generate_html_chart(all_minutes, counts_all, counts_cleaned, counts_kept, total_val, missing_val, missing_pct):
    labels_json = json.dumps(all_minutes)
    
    data_all = [counts_all.get(m, 0) for m in all_minutes]
    data_cleaned = [counts_cleaned.get(m, 0) for m in all_minutes]
    data_kept = [counts_kept.get(m, 0) for m in all_minutes]
    
    data_all_json = json.dumps(data_all)
    data_cleaned_json = json.dumps(data_cleaned)
    data_kept_json = json.dumps(data_kept)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Literature Clock Stats (Cleaned)</title>
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
        <h1>Literature Clock - Cleaned Stats</h1>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-val">{total_val}</div>
                <div class="stat-label">Explicitly Kept</div>
            </div>
            <div class="stat-box">
                <div class="stat-val">{missing_val}</div>
                <div class="stat-label">Missing Minutes</div>
            </div>
            <div class="stat-box">
                <div class="stat-val">{missing_pct:.2f}%</div>
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
                        label: 'Explicitly Kept (AI Verified)',
                        data: {data_kept_json},
                        backgroundColor: 'rgba(54, 162, 235, 0.7)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1,
                        order: 1
                    }},
                    {{
                        label: 'Cleaned (Not Denied)',
                        data: {data_cleaned_json},
                        backgroundColor: 'rgba(75, 192, 192, 0.4)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 1,
                        hidden: false,
                        order: 2
                    }},
                    {{
                        label: 'All Literature (Raw)',
                        data: {data_all_json},
                        backgroundColor: 'rgba(200, 200, 200, 0.2)',
                        borderColor: 'rgba(200, 200, 200, 0.5)',
                        borderWidth: 1,
                        hidden: true,
                        order: 3
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
