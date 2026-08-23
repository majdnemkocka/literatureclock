# Literature Clock & Literature Calendar (Magyar Irodalmi Óra és Naptár)

A projekt célja, hogy magyar irodalmi művekből gyűjtsön időpont- és dátumhivatkozásokat, feldolgozza és pontozza azokat, majd egy modern webes felületen ("Irodalmi Óra" és "Irodalmi Naptár") megjelenítse a nap minden percéhez és napjához illeszkedő idézeteket.

Alapul szolgáló upstream projekt: [`notAnElephant/literatureclock`](https://github.com/notAnElephant/literatureclock)

---

## 📂 Fájlstruktúra és Fájlleírások

### ⚙️ 1. Szabályok és Konfigurációk
- **`rules.json5`**: A magyar időpont-kifejezések regex és szemantikai szabályrendszere (pl. `14:30`, `fél három`, `negyed 8-kor`, `10 perccel öt után`), valamint a szám-szöveg szótárak (ones, tens, word2hour).
- **`rules_calendar.json5`**: A magyar naptári dátumok szabályrendszere (hónapnevek, ragozott alakok, numerikus formák, ünnepek/speciális napok).
- **`requirements.txt`**: A Python környezet függőségei (BeautifulSoup4, Selenium, json5, psycopg2, openai, dotenv stb.).

---

### 🕷️ 2. Scraperek és Szövegkeresők (`scrapers/`)
- **`scrapers/mek_scraper.py`**: A Magyar Elektronikus Könyvtár (MEK) könyvletöltője. Előre definiált magyar szerzők műveit tölti le több formátumban (HTML, EPUB, PDF, TXT), sebességkorlátozással és udvarias lekérésekkel.
- **`scrapers/dia_scraper.py`**: A Digitális Irodalmi Akadémia (DIA) Selenium alapú crawlerezője, amely szerzők és művek katalógusát fésüli át online olvasó linkekért.
- **`scrapers/downloadNovelByDiaUrl.py`**: DIA webes olvasójából fejezetenként kinyeri a regények szövegét és összefűzött HTML formátumba menti.
- **`scrapers/mek_search/mek_time_search.py`**: A MEK teljes szöveges keresőjét (`elfulltext`) automatizáló eszköz. A `rules.json5` alapján generál időpont-keresőkifejezéseket, és kimenti a releváns találati snippeteket (`hits.jsonl`).
- **`scrapers/mek_search/mek_calendar_search.py`**: A MEK teljes szöveges keresőjét naptári dátumkifejezésekkel pásztázó keresőmotor.
- **`deduplicate_mek.py`**: A MEK keresési és letöltési találatok közötti duplikációkat szűrő segédprogram.

---

### 🔍 3. Időpont- és Szövegkinyerés
- **`extractor.py`**: A letöltött HTML/TXT szövegekből kinyeri a tiszta szöveget, normalizálja az ékezeteket és karakterkódolást, majd a `rules.json5` szabályait illesztve JSONL formátumban kimenti a talált időpontokat és a környező szövegkörnyezetet (context snippet). 12/24 órás egyértelműsítést is végez ("reggel", "este" stb. alapján).

---

### 🤖 4. AI Értékelés és Pontozás
- **`ai_grader.py`**: LLM alapú (OpenAI / Gemini API vagy helyi LM Studio) minőségellenőrző pipeline. A kinyert időpont-idézeteket értékeli: ellenőrzi, hogy valódi szépirodalmi műből származik-e, pontos-e az időpont, és elég szép/érthető-e a szövegrészlet.
- **`calendar_ai_grader.py`**: Naptári dátumtalálatok automatizált LLM-es osztályozója és értékelője.

---

### 🗄️ 5. Adatbázis és Seeding
- **`seed_db.py`**: PostgreSQL (pl. Neon) adatbázis sémájának létrehozása és az irodalmi óra találatok betöltése (`entries` és `votes` táblák).
- **`seed_calendar_db.py`**: A naptár találatok betöltése a naptár-specifikus adatbázistáblákba.
- **`seed_gen.py`**: SQL seed fájlokat generáló szkript.
- **`seed.sql`**: Előre generált SQL dump az adatbázis kezdeti feltöltéséhez.

---

### 📊 6. Statisztikák és Vizualizáció
- **`stats.py`**: Statisztikai összesítést készít a kinyert találatokról (`hits.jsonl`) és a letöltött fájlokról (`_summary.json`). Megmutatja az időbeli lefedettséget és a szabályok gyakoriságát.
- **`db_stats_viz.py` & `db_stats_chart.html`**: Az adatbázisban tárolt időpontok lefedettségét és pontszámait vizualizáló interaktív diagram.
- **`ai_stats_viz.py` & `ai_stats_chart.html`**: Az AI által pontozott idézetek minőségi eloszlását bemutató diagram.
- **`mek_stats_viz.py` & `mek_stats_chart.html`**: A MEK scraper működésének, formátum-megoszlásának és letöltési eredményeinek diagramja.
- **`debug_first_hit.html`**: Teszt/debug felület egy kiválasztott találat vizuális megjelenítésére.

---

### 🌐 7. Alkalmazások és Almodulok
- **`grading-app/`**: SvelteKit + Tailwind CSS webalkalmazás. Lehetővé teszi az idézetek kézi átnézését, pontozását, könyvenkénti kezelését, valamint a Naptár / Óra módok közötti váltást.
- **`literature-calendar/`**: A "Literature Calendar" alprojekt dokumentációja és futtatási útmutatója.
- **`tests/`**: Egységtesztek (`test_rules_and_terms.py`), amelyek ellenőrzik a relatív időszabályokat (fél/negyed), a teljes 24 órás lefedettséget és a hibakezelést.

---

## 📌 Ismert Fejlesztési Irányok és Feladatok
1. **Fejezetekre bontott MEK HTML-ek összefűzése:** Néhány MEK regény csak tartalomjegyzékes HTML formátumban érhető el, ahol az egyes fejezetek külön linkeken vannak (pl. `17462`). Ezeket egy összefűző modullal érdemes letölteni.
2. **DIA összetett megjelenítési struktúrák:** A DIA több kiadású/megjelenésű rekordjainál az alternatív verziók automatikus felderítésének továbbfejlesztése.