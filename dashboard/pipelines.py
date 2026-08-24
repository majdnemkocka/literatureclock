import sys
from pathlib import Path
from typing import List
from .models import Pipeline, PipelineStep, ScriptTask, StepParameter

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_command_for_step(step: PipelineStep) -> List[str]:
    cmd = list(step.command)
    for param in step.parameters:
        cmd.extend(param.to_cli_args())
    return cmd


def get_all_pipelines() -> List[Pipeline]:
    py = sys.executable

    # 1. Literature Clock Pipeline (Időpont folyamat)
    clock_steps = [
        PipelineStep(
            id="search",
            title="1. Hibrid MEK Időpont Keresés",
            description="Kifejezések keresése a MEK-en, fejezetek letöltése, kerek bekezdések és LOD metaadatok kinyerése.",
            command=[py, "scrapers/mek_search/mek_time_search.py"],
            parameters=[
                StepParameter("limit", "Keresési limit (0 = mind)", "int", 50, 50, flag_name="--limit", description="Maximálisan keresendő kifejezések"),
                StepParameter("deep_extract", "Mélykeresés (fejezet letöltés)", "bool", True, True, flag_name="--deep-extract", description="Teljes fejezetek letöltése kerek bekezdésekért"),
                StepParameter("include_dayparts", "Napszakok keresése is", "bool", False, False, flag_name="--include-dayparts", description="Napszavak (reggel, este, délután) keresése is"),
                StepParameter("download_covers", "Borítóképek letöltése", "bool", False, False, flag_name="--download-covers", description="Könyvborítók mentése covers/ mappába"),
            ],
            output_files=["scrapers/mek_search/mek_time_search_results.jsonl"],
        ),
        PipelineStep(
            id="seed",
            title="2. Adatbázis Inicializálás & Feltöltés",
            description="PostgreSQL 'entries' és 'votes' táblák létrehozása és a talált idézetek betöltése.",
            command=[py, "seed_db.py"],
            required_files=["scrapers/mek_search/mek_time_search_results.jsonl"],
            required_env=["DATABASE_URL"],
        ),
        PipelineStep(
            id="ai_grade",
            title="3. AI Minőségellenőrzés & Szűrés",
            description="LLM (Gemini / OpenAI / LM Studio) segítségével ellenőrzi az irodalmi minőséget és kontextust.",
            command=[py, "ai_grader.py"],
            required_env=["DATABASE_URL"],
            parameters=[
                StepParameter("budget", "Költségkeret (USD)", "str", "2.0", "2.0", description="Maximális költési keret USD-ben"),
                StepParameter("provider", "AI Szolgáltató", "choice", "gemini", "gemini", choices=["gemini", "openai", "lmstudio"], description="AI API szolgáltató"),
            ],
        ),
        PipelineStep(
            id="viz",
            title="4. Statisztikák és Diagramok Frissítése",
            description="Lefedettségi és minőségi diagramok generálása HTML formátumban.",
            command=[py, "db_stats_viz.py"],
            required_env=["DATABASE_URL"],
            output_files=["db_stats_chart.html"],
        ),
        PipelineStep(
            id="web_app",
            title="5. Grading App Webes Felület Indítása",
            description="SvelteKit webalkalmazás elindítása az idézetek böngészéséhez (http://localhost:5173).",
            command=["npm", "run", "dev"],
            cwd="grading-app",
            required_env=["DATABASE_URL"],
        ),
    ]

    # 2. Literature Calendar Pipeline (Naptári folyamat)
    calendar_steps = [
        PipelineStep(
            id="cal_search",
            title="1. MEK Naptári Dátum Keresés",
            description="Naptári kifejezések (hónap, nap, évszakok, hét napjai) keresése a MEK-en.",
            command=[py, "scrapers/mek_search/mek_calendar_search.py"],
            parameters=[
                StepParameter("limit", "Keresési limit (0 = mind)", "int", 50, 50, flag_name="--limit"),
                StepParameter("include_all", "Minden keresési típus bevonása", "bool", False, False, flag_name="--include-all", description="Dátumok, hónaprészek, évszakok, napok keresése"),
            ],
            output_files=["scrapers/mek_search/mek_calendar_search_results.jsonl"],
        ),
        PipelineStep(
            id="cal_migrate",
            title="2. Naptár DB Migráció",
            description="Naptári táblák létrehozása és intervallum-oszlopok biztosítása az adatbázisban.",
            command=[py, "migrate_add_calendar_interval_cols.py"],
            required_env=["DATABASE_URL"],
        ),
        PipelineStep(
            id="cal_seed",
            title="3. Naptár Adatbázis Feltöltés",
            description="Naptári találatok betöltése a táblákba.",
            command=[py, "seed_calendar_db.py"],
            required_files=["scrapers/mek_search/mek_calendar_search_results.jsonl"],
            required_env=["DATABASE_URL"],
        ),
        PipelineStep(
            id="cal_ai",
            title="4. Naptári AI Értékelés",
            description="Naptári idézetek automatikus AI osztályozása és pontozása.",
            command=[py, "calendar_ai_grader.py"],
            required_env=["DATABASE_URL"],
        ),
    ]

    # 3. Offline Books Pipeline (Könyvtár letöltés & feldolgozás)
    offline_steps = [
        PipelineStep(
            id="scrape_mek",
            title="1. MEK Könyvek Letöltése",
            description="Magyar szerzők műveinek tömeges letöltése HTML/TXT formátumban a mek_downloads/ mappába.",
            command=[py, "scrapers/mek_scraper.py"],
        ),
        PipelineStep(
            id="extract_hits",
            title="2. Időpontok Kinyerése Kötetekből",
            description="Szövegfeldolgozás és időpont-szabályok illesztése a letöltött kötetekre.",
            command=[py, "extractor.py", "mek_downloads/"],
            output_files=["hits.jsonl"],
        ),
        PipelineStep(
            id="stats_summary",
            title="3. Statisztikai Összesítés",
            description="Időbeli lefedettség és szabály-gyakoriság kimutatása.",
            command=[py, "stats.py"],
            required_files=["hits.jsonl"],
        ),
    ]

    # 4. Diagnostics & Tests (Tesztelés & Rendszer-ellenőrzés)
    diag_steps = [
        PipelineStep(
            id="run_tests",
            title="1. Teljes Tesztcsomag Futtatása",
            description="Minden egységteszt (időpontok, naptár, napszakok, AI grader, selectorok) ellenőrzése pytesttel.",
            command=[py, "-m", "pytest", "tests/", "-v"],
        ),
        PipelineStep(
            id="dedup_check",
            title="2. MEK Duplikációk Szűrése",
            description="Keresési találatok és letöltések közötti átfedések elemzése.",
            command=[py, "deduplicate_mek.py"],
        ),
    ]

    return [
        Pipeline("clock", "Irodalmi Óra Folyamat (Literature Clock)", "Hibrid keresés, betöltés, AI pontozás és webes megjelenítés.", "🕒", clock_steps),
        Pipeline("calendar", "Irodalmi Naptár Folyamat (Literature Calendar)", "Éves naptári napok, évszakok és napok idézeteinek gyűjtése.", "📅", calendar_steps),
        Pipeline("offline", "Offline Könyvtár & Batch Feldolgozás", "Teljes kötetek letöltése és offline időpont-kinyerés.", "📚", offline_steps),
        Pipeline("diagnostics", "Diagnosztika & Tesztek", "Rendszer-ellenőrzés, duplikáció-szűrés és egységtesztek.", "🧪", diag_steps),
    ]


def get_all_script_tasks() -> List[ScriptTask]:
    py = sys.executable
    return [
        ScriptTask(
            id="time_search",
            category="Keresés & Scraper",
            title="MEK Időpont Kereső (mek_time_search.py)",
            description="Időpont-kifejezések keresése a MEK-en mély fejezet-extrakcióval és napszakokkal.",
            command=[py, "scrapers/mek_search/mek_time_search.py"],
            parameters=[
                StepParameter("limit", "Limit", "int", 50, 50, flag_name="--limit"),
                StepParameter("term", "Egyedi kifejezés", "str", "", "", flag_name="--term"),
                StepParameter("deep_extract", "Mélykeresés", "bool", True, True, flag_name="--deep-extract"),
                StepParameter("dayparts_only", "Csak napszakok", "bool", False, False, flag_name="--dayparts-only"),
                StepParameter("include_dayparts", "Napszakok is", "bool", False, False, flag_name="--include-dayparts"),
                StepParameter("download_covers", "Borítók letöltése", "bool", False, False, flag_name="--download-covers"),
            ],
        ),
        ScriptTask(
            id="calendar_search",
            category="Keresés & Scraper",
            title="MEK Naptár Kereső (mek_calendar_search.py)",
            description="Naptári dátumok, évszakok és hét napjainak keresése a MEK-en wildcarddal.",
            command=[py, "scrapers/mek_search/mek_calendar_search.py"],
            parameters=[
                StepParameter("limit", "Limit", "int", 50, 50, flag_name="--limit"),
                StepParameter("term", "Egyedi kifejezés", "str", "", "", flag_name="--term"),
                StepParameter("dates_only", "Csak 366 dátum", "bool", False, False, flag_name="--dates-only"),
                StepParameter("seasons_only", "Csak 4 évszak", "bool", False, False, flag_name="--seasons-only"),
                StepParameter("weekdays_only", "Csak hét napjai", "bool", False, False, flag_name="--weekdays-only"),
                StepParameter("month_parts_only", "Csak hónap részei", "bool", False, False, flag_name="--month-parts-only"),
                StepParameter("include_all", "Minden naptári keresés", "bool", False, False, flag_name="--include-all"),
            ],
        ),
        ScriptTask(
            id="mek_scraper",
            category="Keresés & Scraper",
            title="MEK Könyv Letöltő (mek_scraper.py)",
            description="Szerzők műveinek letöltése a MEK-ről a mek_downloads/ mappába.",
            command=[py, "scrapers/mek_scraper.py"],
        ),
        ScriptTask(
            id="dia_scraper",
            category="Keresés & Scraper",
            title="DIA Katalógus Scraper (dia_scraper.py)",
            description="Digitális Irodalmi Akadémia online műveinek feltérképezése.",
            command=[py, "scrapers/dia_scraper.py"],
        ),
        ScriptTask(
            id="extractor",
            category="Kinyerés & Elemzés",
            title="Időpont Extractor (extractor.py)",
            description="Időpontok kinyerése helyi HTML/TXT állományokból a rules.json5 szabályai alapján.",
            command=[py, "extractor.py", "mek_downloads/"],
        ),
        ScriptTask(
            id="deduplicate",
            category="Kinyerés & Elemzés",
            title="Duplikáció Szűrő (deduplicate_mek.py)",
            description="Találatok egyediségének vizsgálata és duplikációk kiszűrése.",
            command=[py, "deduplicate_mek.py"],
        ),
        ScriptTask(
            id="seed_db",
            category="Adatbázis",
            title="Adatbázis Seeder (seed_db.py)",
            description="PostgreSQL táblák inicializálása és adatok betöltése.",
            command=[py, "seed_db.py"],
            required_env=["DATABASE_URL"],
        ),
        ScriptTask(
            id="migrate_time",
            category="Adatbázis",
            title="Óra Intervallum Migráció (migrate_add_time_interval_cols.py)",
            description="Időpont-intervallum (time_min/max/focus) oszlopok létrehozása az adatbázisban.",
            command=[py, "migrate_add_time_interval_cols.py"],
            required_env=["DATABASE_URL"],
        ),
        ScriptTask(
            id="seed_calendar_db",
            category="Adatbázis",
            title="Naptár Adatbázis Seeder (seed_calendar_db.py)",
            description="Naptári adatok betöltése az adatbázisba.",
            command=[py, "seed_calendar_db.py"],
            required_env=["DATABASE_URL"],
        ),
        ScriptTask(
            id="migrate_calendar",
            category="Adatbázis",
            title="Naptár Intervallum Migráció (migrate_add_calendar_interval_cols.py)",
            description="Naptári intervallum és nap (date_min/max/focus, day_of_week) oszlopok létrehozása az adatbázisban.",
            command=[py, "migrate_add_calendar_interval_cols.py"],
            required_env=["DATABASE_URL"],
        ),
        ScriptTask(
            id="ai_grader",
            category="AI Minőség",
            title="AI Időpont Értékelő (ai_grader.py)",
            description="LLM alapú minőségellenőrzés és pontozás.",
            command=[py, "ai_grader.py"],
            required_env=["DATABASE_URL"],
            parameters=[
                StepParameter("budget", "Költségkeret USD", "str", "2.0", "2.0"),
                StepParameter("provider", "AI Szolgáltató", "choice", "gemini", "gemini", choices=["gemini", "openai", "lmstudio"]),
            ],
        ),
        ScriptTask(
            id="calendar_ai_grader",
            category="AI Minőség",
            title="AI Naptár Értékelő (calendar_ai_grader.py)",
            description="LLM alapú naptári idézet ellenőrzés.",
            command=[py, "calendar_ai_grader.py"],
            required_env=["DATABASE_URL"],
        ),
        ScriptTask(
            id="stats",
            category="Statisztika & Vizualizáció",
            title="Lefedettség Statisztika (stats.py)",
            description="hits.jsonl fájl elemzése és lefedettségi mutatók kiírása.",
            command=[py, "stats.py"],
        ),
        ScriptTask(
            id="db_stats_viz",
            category="Statisztika & Vizualizáció",
            title="Adatbázis Diagram Készítő (db_stats_viz.py)",
            description="Interaktív db_stats_chart.html diagram generálása.",
            command=[py, "db_stats_viz.py"],
            required_env=["DATABASE_URL"],
        ),
        ScriptTask(
            id="ai_stats_viz",
            category="Statisztika & Vizualizáció",
            title="AI Statisztika Diagram (ai_stats_viz.py)",
            description="AI pontozási eloszlás vizualizáció készítése.",
            command=[py, "ai_stats_viz.py"],
            required_env=["DATABASE_URL"],
        ),
        ScriptTask(
            id="mek_stats_viz",
            category="Statisztika & Vizualizáció",
            title="MEK Scraper Diagram (mek_stats_viz.py)",
            description="MEK letöltési megoszlás diagram generálása.",
            command=[py, "mek_stats_viz.py"],
        ),
        ScriptTask(
            id="pytest_all",
            category="Tesztek & Karbantartás",
            title="Egységtesztek Futtatása (pytest)",
            description="Az összes egységteszt automatikus futtatása.",
            command=[py, "-m", "pytest", "tests/", "-v"],
        ),
    ]
