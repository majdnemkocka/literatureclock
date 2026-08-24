import argparse
import os
import json
import collections
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')


def main():
    parser = argparse.ArgumentParser(description="Generate database coverage chart for Clock (time) or Calendar (date).")
    parser.add_argument("--dataset", choices=["time", "date"], default="time", help="Dataset to visualize (time or date).")
    parser.add_argument("--output", default=None, help="Output HTML file path.")
    args = parser.parse_args()

    if not DATABASE_URL:
        print("Error: DATABASE_URL is not set.")
        return

    output_html = args.output or ("db_calendar_stats_chart.html" if args.dataset == "date" else "db_stats_chart.html")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    if args.dataset == "date":
        # Calendar stats (366 days)
        print("Fetching cleaned calendar counts...")
        cur.execute("""
            SELECT t, count(*) 
            FROM (
                SELECT date_min_str as t
                FROM calendar_entries e
                WHERE is_literature = TRUE
                AND date_min_str IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM calendar_votes v WHERE v.entry_id = e.id AND v.corrected_date = 'AI_DENY'
                )
            ) sub
            WHERE t ~ '^[0-9]{2}-[0-9]{2}$'
            GROUP BY t
        """)
        rows_cleaned = cur.fetchall()
        counts_cleaned = {r[0]: r[1] for r in rows_cleaned}

        cur.execute("""
            SELECT t, count(*) 
            FROM (
                SELECT date_min_str as t
                FROM calendar_entries e
                WHERE is_literature = TRUE
                AND date_min_str IS NOT NULL
                AND ai_checked = TRUE
                AND NOT EXISTS (
                    SELECT 1 FROM calendar_votes v WHERE v.entry_id = e.id AND v.corrected_date = 'AI_DENY'
                )
            ) sub
            WHERE t ~ '^[0-9]{2}-[0-9]{2}$'
            GROUP BY t
        """)
        rows_kept = cur.fetchall()
        counts_kept = {r[0]: r[1] for r in rows_kept}

        cur.execute("""
            SELECT t, count(*) 
            FROM (
                SELECT date_min_str as t
                FROM calendar_entries e
                WHERE is_literature = TRUE
                AND date_min_str IS NOT NULL
            ) sub
            WHERE t ~ '^[0-9]{2}-[0-9]{2}$'
            GROUP BY t
        """)
        rows_all = cur.fetchall()
        counts_all = {r[0]: r[1] for r in rows_all}

        cur.execute("SELECT COUNT(*) FROM calendar_entries WHERE is_literature = TRUE")
        total_lit = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*) FROM calendar_entries e
            WHERE is_literature = TRUE 
            AND NOT EXISTS (
                SELECT 1 FROM calendar_votes v WHERE v.entry_id = e.id AND v.corrected_date = 'AI_DENY'
            )
        """)
        total_cleaned = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM calendar_entries e
            WHERE is_literature = TRUE 
            AND ai_checked = TRUE
            AND NOT EXISTS (
                SELECT 1 FROM calendar_votes v WHERE v.entry_id = e.id AND v.corrected_date = 'AI_DENY'
            )
        """)
        total_kept = cur.fetchone()[0]

        cur.close()
        conn.close()

        # 366 days in leap year base
        from date_utils import day_of_year_to_mmdd
        all_slots = [day_of_year_to_mmdd(d) for d in range(1, 367)]
        total_slots = 366
        slot_unit = "days"
        title_text = "Literature Calendar - Database Coverage"
    else:
        # Time stats (1440 minutes)
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
            WHERE t ~ '^[0-9]{1,2}:[0-9]{2}$'
            GROUP BY t
        """)
        rows_cleaned = cur.fetchall()
        counts_cleaned = {r[0]: r[1] for r in rows_cleaned}

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
            WHERE t ~ '^[0-9]{1,2}:[0-9]{2}$'
            GROUP BY t
        """)
        rows_kept = cur.fetchall()
        counts_kept = {r[0]: r[1] for r in rows_kept}

        cur.execute("""
            SELECT t, count(*) 
            FROM (
                SELECT time_min_str as t
                FROM entries e
                WHERE is_literature = TRUE
                AND time_min_str IS NOT NULL
            ) sub
            WHERE t ~ '^[0-9]{1,2}:[0-9]{2}$'
            GROUP BY t
        """)
        rows_all = cur.fetchall()
        counts_all = {r[0]: r[1] for r in rows_all}

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

        all_slots = [f"{h:02d}:{m:02d}" for h in range(24) for m in range(60)]
        total_slots = 1440
        slot_unit = "minutes"
        title_text = "Literature Clock - Database Coverage"

    covered_slots_kept = len(counts_kept)
    missing_slots_kept = total_slots - covered_slots_kept
    missing_percent_kept = (missing_slots_kept / total_slots) * 100 if total_slots else 0

    print(f"\nTotal Explicitly Kept: {total_kept}")
    print(f"Coverage (Kept): {covered_slots_kept}/{total_slots} {slot_unit}")
    print(f"Missing (Kept): {missing_slots_kept} ({missing_percent_kept:.2f}%)")

    # Generate HTML
    generate_html_chart(output_html, title_text, all_slots, counts_all, counts_cleaned, counts_kept, total_kept, missing_slots_kept, missing_percent_kept, slot_unit)
    print(f"\nDetailed HTML chart generated: {output_html}")


def generate_html_chart(output_html, title_text, all_slots, counts_all, counts_cleaned, counts_kept, total_val, missing_val, missing_pct, slot_unit):
    labels_json = json.dumps(all_slots)
    
    data_all = [counts_all.get(m, 0) for m in all_slots]
    data_cleaned = [counts_cleaned.get(m, 0) for m in all_slots]
    data_kept = [counts_kept.get(m, 0) for m in all_slots]
    
    data_all_json = json.dumps(data_all)
    data_cleaned_json = json.dumps(data_cleaned)
    data_kept_json = json.dumps(data_kept)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title_text}</title>
    <style>
        body {{ font-family: sans-serif; padding: 20px; background: #f4f4f4; }}
        .container {{ max_width: 1100px; margin: 0 auto; background: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
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
        <h1>{title_text}</h1>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-val">{total_val}</div>
                <div class="stat-label">Explicitly Kept</div>
            </div>
            <div class="stat-box">
                <div class="stat-val">{missing_val}</div>
                <div class="stat-label">Missing {slot_unit.capitalize()}</div>
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
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Number of Quotes'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: '{slot_unit.capitalize()}'
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html_content)


if __name__ == "__main__":
    main()
