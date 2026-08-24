# Literature Clock & Literature Calendar (Magyar Irodalmi Óra és Naptár)

A projekt célja, hogy magyar irodalmi művekből gyűjtsön időpont- és dátumhivatkozásokat, feldolgozza és pontozza azokat, majd egy modern webes felületen ("Irodalmi Óra" és "Irodalmi Naptár") megjelenítse a nap minden percéhez és napjához illeszkedő idézeteket.

Alapul szolgáló upstream projekt: [`notAnElephant/literatureclock`](https://github.com/notAnElephant/literatureclock)

---

## 🚀 Gyorsindítási Útmutató (Hol kezdjem?)

Ha most találkozol először a projekttel, az alábbi lépésekben tudod a legegyszerűbben elindítani a folyamatot a nyers kereséstől a kész webes felületig.

---

### ⚡ 1. Ajánlott gyors folyamat (Hibrid Keresés ➔ Adatbázis ➔ AI Értékelés ➔ Web UI)

Ez a leggyorsabb módja annak, hogy valós, kerek bekezdésekkel rendelkező idézeteket szerezz és azonnal lásd a webes felületen.

#### 1. lépés: Függőségek telepítése
```bash
pip install -r requirements.txt
cd grading-app && npm install && cd ..
```
- ⏱️ **Időigény:** ~1–2 perc

#### 2. lépés: Hibrid mélykeresés a MEK-en (Teljes bekezdések + LOD metaadatok)
```bash
python scrapers/mek_search/mek_time_search.py --limit 500 --output scrapers/mek_search/mek_search_results.jsonl
```
- 🔍 **Mit csinál?** A `rules.json5` kifejezéseit beküldi a MEK keresőjébe, automatikusan letölti és gyorsítótárazza a *"Találat helye"* fejezeteket, és az `extractor.py` segítségével kerek bekezdéseket és többes találatokat (multi-hit) nyer ki, csatolva a szabványos MEK Linked Open Data (LOD) metaadatokat (URN, szerző, cím, műfaj).
- ⏱️ **Időigény:** ~5–15 perc (a limit méretétől függően).
- 📄 **Várható kimenet:** `scrapers/mek_search/mek_search_results.jsonl` (több ezer gazdag metaadatú idézet).

#### 3. lépés: Adatbázis inicializálása és feltöltése (Seeding)
```bash
DATABASE_URL="postgresql://user:pass@host/db" python seed_db.py
```
- 🗄️ **Mit csinál?** Létrehozza az `entries` és `votes` táblákat a PostgreSQL (pl. ingyenes [Neon.tech](https://neon.tech)) adatbázisban, és betölti a kinyert snippeteket.
- ⏱️ **Időigény:** ~10–30 másodperc.
- 📄 **Várható kimenet:** Feltöltött adatbázis rekordok.

#### 4. lépés: AI Minőségellenőrzés és Szűrés (Opcionális, de erősen ajánlott)
```bash
GEMINI_API_KEY="your-api-key" BUDGET_USD=2 python ai_grader.py
```
*(Helyi modell esetén [LM Studio]: `AI_PROVIDER=lmstudio python ai_grader.py`)*
- 🤖 **Mit csinál?** Egy LLM ellenőrzi az idézetek irodalmi értékét, a pontosságot és kontextust, valamint kiszűri a nem-irodalmi találatokat.
- ⏱️ **Időigény:** ~2–5 perc.
- 📄 **Várható kimenet:** `grader.log`, valamint az adatbázisban az `is_literature` és pontszám mezők automatikus frissítése.

#### 5. lépés: Webes felület indítása (Grading App)
```bash
cd grading-app
DATABASE_URL="postgresql://user:pass@host/db" npm run dev
```
- 🌐 **Mit csinál?** Elindítja a SvelteKit webalkalmazást a `http://localhost:5173` címen.
- ⏱️ **Időigény:** ~5 másodperc.
- 📄 **Várható kimenet:** Böngészőben megnyitható és használható felület az idézetek böngészésére, szűrésére és manuális ellenőrzésére.

---

### 📚 2. Teljes könyvek letöltése és offline feldolgozása

Ha teljes könyveket (több száz kötet) szeretnél offline letölteni és lokálisan elemezni:

1. **Könyvek letöltése:** `python scrapers/mek_scraper.py`  
   - ⏱️ *Időigény:* ~30–60 perc (több száz mű HTML/EPUB/TXT letöltése a `mek_downloads/` könyvtárba).
2. **Időpontok kinyerése a könyvekből:** `python extractor.py mek_downloads/ > hits.jsonl`  
   - ⏱️ *Időigény:* ~1–3 perc.  
   - 📄 *Kimenet:* `hits.jsonl` fájl az összes talált időponttal és szövegkörnyezettel.
3. **Statisztikák és lefedettség megtekintése:** `python stats.py` vagy `python db_stats_viz.py`  
   - ⏱️ *Időigény:* ~5 másodperc.  
   - 📊 *Kimenet:* Percalapú lefedettségi összesítő és interaktív diagram (`db_stats_chart.html`).

---

### 📅 3. Naptár mód (Literature Calendar)

Ha a nap percei helyett az év naptári napjaihoz (hónap + nap) szeretnél idézeteket gyűjteni:
1. **Keresés:** `python scrapers/mek_search/mek_calendar_search.py --limit 500 --output scrapers/mek_search/mek_calendar_search_results.jsonl` (~5–15 perc)
2. **Migráció & Seed:** `npm --prefix grading-app run migrate:calendar` majd `DATABASE_URL=... python seed_calendar_db.py` (~30 mp)
3. **AI Értékelés:** `GEMINI_API_KEY=... python calendar_ai_grader.py` (~2–5 perc)
4. **Megjelenítés:** A Grading App felületén a fejlécben átváltható `Date Mode`-ra.

---

## 🌟 Kiemelt Funkciók

### 🎯 Hibrid Mélykeresés (Targeted Deep Extraction)
A kereső nem csupán a találati oldal 100-200 karakteres, sokszor csonka snippetjét menti le:
1. **Pontos fejezetletöltés:** A találati blokkban lévő *"Találat helye"* linkről letölti a konkrét HTML fejezetet/dokumentumot.
2. **Szerverkímélő gyorsítótárazás:** A letöltött oldalakat és metaadatokat a MEK relatív útvonala szerint lementi (`scrapers/mek_search/cache/`), így minden fejezetet és metaadatot **kizárólag egyszer tölt le**.
3. **Multi-hit extrakció:** Az `extractor.py` a teljes letöltött fejezetet átfésüli, így egyetlen letöltött fejezetből **az összes benne szereplő időpont kinyerhető** kerek, teljes bekezdésekkel és pontos 12h/24h napszak-feloldással (pl. József Attila: *Curriculum Vitae* szövegéből egyszerre születik meg a `07:30` és a `21:00` bejegyzés).
4. **Biztonsági Fallback:** Ha a forrásfejezet nem érhető el vagy nem parse-olható, a rendszer automatikusan megőrzi az eredeti keresési snippetet `is_fallback: true` jelöléssel.

### 🏛️ MEK LOD (Linked Open Data) & Metaadat-integráció
A `scrapers/mek_metadata.py` modul szabványos RDF/XML és Dublin Core feldolgozással az alábbi mezőket nyeri ki és csatolja minden bejegyzéshez:
- `urn`: Szabványos nemzeti könyvtári azonosító (pl. `urn:nbn:hu-2707`)
- `title` & `author`: Egységesített cím és szerző (magyar és nemzetközi név, VIAF link)
- `genre`: Pontos műfaj (pl. `poems`, `novel`, `plays`, `short stories`)
- `source_url`: A fejezet közvetlen forráslinkje
- `cover_url`: Borítókép közvetlen elérhetősége (`borito.jpg`)
- `raw_metadata`: A teljes nyers könyvészeti szótár (ISBN, fájlok, gyűjtemények)

### ⚙️ Kereső CLI Kapcsolók (`mek_time_search.py`)
- `--limit N`: Maximálisan keresendő kifejezések száma (alapértelmezett: 5, teljes futtatáshoz: `<=0`).
- `--term "kifejezés"`: Egyetlen kifejezés célzott keresése és azonnali tesztelése.
- `--deep-extract` / `--no-deep-extract`: Fejezetszintű mélykeresés be/kikapcsolása (alapértelmezetten bekapcsolva).
- `--download-covers`: Borítóképek letöltése a `covers/` mappába.
- `--output file.jsonl`: Kimeneti fájl megadása.
- `--visible`: Böngészőablak megjelenítése (nem headless mód).

---

## 📂 Fájlstruktúra és Részletes Leírások

### ⚙️ 1. Szabályok és Konfigurációk
- **`rules.json5`**: A magyar időpont-kifejezések regex és szemantikai szabályrendszere (pl. `14:30`, `fél három`, `negyed 8-kor`, `10 perccel öt után`), valamint a szám-szöveg szótárak (ones, tens, word2hour).
- **`rules_calendar.json5`**: A magyar naptári dátumok szabályrendszere (hónapnevek, ragozott alakok, numerikus formák, ünnepek/speciális napok).
- **`requirements.txt`**: A Python környezet függőségei (BeautifulSoup4, Selenium, json5, psycopg2, openai, dotenv stb.).

---

### 🕷️ 2. Scraperek és Szövegkeresők (`scrapers/`)
- **`scrapers/mek_metadata.py`**: A MEK Linked Open Data (LOD) / `metadata.rdf` és Dublin Core metaadat-kinyerő és gyorsítótárazó modulja (URN, pontos cím, szerző, VIAF, műfaj, nyelv, ISBN és opcionális borítókép-letöltő).
- **`scrapers/mek_search/mek_time_search.py`**: A MEK teljes szöveges keresőjét (`elfulltext`) automatizáló hibrid eszköz. A `rules.json5` alapján keres, automatikusan letölti és gyorsítótárazza a *"Találat helye"* fejezeteket, és az `extractor.py`-on keresztül teljes bekezdéseket és többes találatokat (multi-hit) nyer ki LOD metaadatokkal gazdagítva.
- **`scrapers/mek_search/mek_calendar_search.py`**: A MEK teljes szöveges keresőjét naptári dátumkifejezésekkel pásztázó keresőmotor LOD metaadat-támogatással.
- **`scrapers/mek_scraper.py`**: A Magyar Elektronikus Könyvtár (MEK) könyvletöltője. Előre definiált magyar szerzők műveit tölti le több formátumban (HTML, EPUB, PDF, TXT), sebességkorlátozással és udvarias lekérésekkel.
- **`scrapers/dia_scraper.py`**: A Digitális Irodalmi Akadémia (DIA) Selenium alapú crawlerezője, amely szerzők és művek katalógusát fésüli át online olvasó linkekért.
- **`scrapers/downloadNovelByDiaUrl.py`**: DIA webes olvasójából fejezetenként kinyeri a regények szövegét és összefűzött HTML formátumba menti.
- **`deduplicate_mek.py`**: A MEK keresési és letöltési találatok közötti duplikációkat szűrő segédprogram.

---

### 🔍 3. Időpont- és Szövegkinyerés
- **`extractor.py`**: A letöltött HTML/TXT szövegekből kinyeri a tiszta szöveget, normalizálja az ékezeteket és karakterkódolást, majd a `rules.json5` szabályait illesztve JSONL formátumban kimenti a talált időpontokat és a környező szövegkörnyezetet (context snippet). Támogatja a közvetlen memóriabeli HTML extrakciót (`extract_from_html`) és 12/24 órás napszak-feloldást végez ("reggel", "este" stb. alapján).

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
- **`tests/`**: Egységtesztek (`test_rules_and_terms.py`), amelyek ellenőrzik a relatív időszabályokat (fél/negyed), a LOD metaadat-kinyerést, a lemezes gyorsítótárazást, a teljes 24 órás lefedettséget és a hibakezelést.

---

## 📌 Ismert Fejlesztési Irányok és Feladatok
1. **Fejezetekre bontott MEK HTML-ek összefűzése:** Néhány MEK regény csak tartalomjegyzékes HTML formátumban érhető el, ahol az egyes fejezetek külön linkeken vannak (pl. `17462`). Ezeket egy összefűző modullal érdemes letölteni.
2. **DIA összetett megjelenítési struktúrák:** A DIA több kiadású/megjelenésű rekordjainál az alternatív verziók automatikus felderítésének továbbfejlesztése.