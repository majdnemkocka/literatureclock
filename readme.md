# Magyar Irodalmi Óra & Naptár (Literature Clock & Calendar)

A **Literature Clock** egy magyar irodalmi idézeteket gyűjtő és megjelenítő nyílt forráskódú rendszer, amely a nap minden percéhez (1440 perc), napszakához és az év minden napjához (366 naptári nap, évszakok, hét napjai) releváns, kontextusban gazdag könyvidézeteket társít.

A projekt a [`notAnElephant/literatureclock`](https://github.com/notAnElephant/literatureclock) tárolón alapul, jelentősen továbbfejlesztve közvetlen HTTP MEK scraperrel, intervallum-alapú és napszakos/napos idézetválasztással, AI minőségellenőrzéssel, terminálos TUI Dashboarddal és SvelteKit webes felülettel.

---

## 🌟 Főbb Képességek

### 1. Irodalmi Óra (Literature Clock)
- **1440 perc lefedettség:** Konkrét időpontok (`13:45`, `fél kettő`) kinyerése.
- **Napszakok és Intervallumok:** 12 magyar napszak kategória (`hajnal`, `reggel`, `délelőtt`, `dél`, `kora délután`, `délután`, `alkonyat`, `este`, `éjfél körül`, `éjjel`) `time_min_str` – `time_max_str` intervallumokkal.
- **Éjfél átfordulás (24+ órás jelölés):** `24:00` feletti percek támogatása az éjfélt átlépő időszakokhoz (pl. `23:00` – `25:30` -> 1380..1530 perc), megőrizve a `min <= max` invariánst.
- **Súlyozott Idézetválasztó (`quote_selector.py`):** Pontossági és távolsági súlyozás: $\frac{1}{(1 + \text{precision}) \times (1 + \text{dist})}$, szigorúan nem nulla súllyal.

### 2. Irodalmi Naptár (Literature Calendar)
- **366 naptári nap (`MM-DD`):** Évfüggetlen öröknaptár leképezés (`01-01` .. `12-31`).
- **Hozzávetőleges időszakok & Hónaprészek:** `"március elején"` (`03-01`..`03-10`), `"április közepén"`, `"december végén"`.
- **Évszakok & Ünnepek:** Tavasz, Nyár, Ősz, Tél (365+ kiterjesztett téli évet átívelő napokkal: `12-01` .. `02-28` -> napok 335..425), Karácsony, Újév, Húsvét, Halottak napja, stb.
- **Hét Napjai:** Hétfő .. Vasárnap, Hétvége.
- **2D Naptári Idézetválasztó (`calendar_quote_selector.py`):** Dátumintervallum és nap egyezés, $4\times$ hibrid bónusszal ha mindkettő illeszkedik.

### 3. MEK Keresőmotor (Wildcard `*` & Pipe `|` Optimalizáció)
- **Közvetlen HTTP POST (`elfulltext`):** 10–20x gyorsabb a böngészős scrapelésnél.
- **Szóvégi csonkolás (`*`):** A toldalékos alakok egybevonására (`"március*"`, `"hétfő*"`, `"tavasz*"`).
- **VAGY operátor (`|`):** Pipe operátoros lekérdezés-tömörítés determinisztikus találatszám-olvasással és lapozással.

### 4. Gemini AI Minőségellenőrzés (`ai_grader.py` & `calendar_ai_grader.py`)
- Automatikus kontextus-, tartalom- és intervallum-ellenőrzés Google Gemini Flash modellel.
- Pontszám (0–5), indoklás és validált `time_min`/`time_max` vagy `date_min`/`date_max` mentése.

### 5. Interaktív TUI Dashboard (`dashboard_app.py`)
- Textual alapú terminálos vezérlőközpont pipeline-okkal, script taskokkal, környezeti változó szerkesztővel és élő konzollal.

### 6. Webes Értékelő Felület (`grading-app/`)
- SvelteKit + Tailwind CSS alapú mobilbarát felület emberi ellenőrzésre, szavazásra és Book Review funkcióra.

---

## 🚀 Gyors Indítás (Quick Start)

### 1. Előfeltételek és Környezet
```bash
# Függőségek telepítése
pip install -r requirements.txt

# .env fájl beállítása
DATABASE_URL=postgres://user:password@ep-host.neon.tech/neondb
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. TUI Dashboard Indítása
```bash
python dashboard_app.py
```

### 3. CLI Parancsok és Folyamatok

#### Irodalmi Óra folyamat:
```bash
# 1. Keresés a MEK-en (1440 perc és napszakok)
python scrapers/mek_search/mek_time_search.py --include-dayparts --limit 100

# 2. Adatbázis migráció és feltöltés
python migrate_add_time_interval_cols.py
python seed_db.py

# 3. AI Minőségellenőrzés
python ai_grader.py
```

#### Irodalmi Naptár folyamat:
```bash
# 1. Keresés a MEK-en (366 nap, évszakok, napok, hónaprészek)
python scrapers/mek_search/mek_calendar_search.py --include-all --limit 100

# 2. Naptár adatbázis migráció és feltöltés
python migrate_add_calendar_interval_cols.py
python seed_calendar_db.py

# 3. Naptár AI Minőségellenőrzés
python calendar_ai_grader.py
```

#### Webes felület indítása:
```bash
cd grading-app
npm install
npm run dev
```

---

## 🧪 Tesztelés

A teljes egység- és integrációs tesztcsomag futtatása:
```bash
pytest tests/ -v
```
*(118 egység- és integrációs teszt az időpontok, naptár, napszakok, selectorok és dashboard modulok lefedésére).*

---

## 📄 Licenc
MIT Licenc.