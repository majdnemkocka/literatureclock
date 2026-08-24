# Literature Calendar (Irodalmi Naptár)

A **Literature Calendar** a magyar nyelvű Irodalmi Óra naptári testvérprojektje: a MEK (Magyar Elektronikus Könyvtár) teljes szövegű adatbázisából gyűjt pontos naptári napokra (`03-15`), hozzávetőleges dátumintervallumokra (`március elején`, `tavasszal`, `karácsonykor`) és a hét napjaira (`hétfőn`, `szombaton`, `hétvégén`) vonatkozó irodalmi idézeteket.

---

## 📂 Kulcsfájlok és Modulok

- **Szabályok és Kifejezések:** `rules_calendar.json5` (hónapok, hónaprészek, évszakok, hét napjai, ünnepnapok)
- **Dátum Utility:** `date_utils.py` (366 napos öröknaptár leképezés, téli 365+ kiterjesztés, távolság, napnevek)
- **Keresőmotor:** `scrapers/mek_search/mek_calendar_search.py` (közvetlen HTTP kereső wildcard `*` és pipe `|` optimalizációval)
- **Adatbázis Migráció:** `migrate_add_calendar_interval_cols.py` (idempotens PostgreSQL migráció)
- **Adatbázis Feltöltő:** `seed_calendar_db.py` (találatok betöltése a `calendar_entries` táblába)
- **AI Minőségellenőrző:** `calendar_ai_grader.py` (Gemini Flash alapú kontextus-, intervallum- és napelemzés)
- **2D Idézetválasztó:** `calendar_quote_selector.py` (pontosság, fókusz-távolság és napi illeszkedés súlyozás)

---

## 🛠️ Futtatási Sorrend és Használat

### 1. Keresés futtatása a MEK-en
```bash
# Mind a 366 naptári nap keresése
python scrapers/mek_search/mek_calendar_search.py --dates-only

# Csak az évszakok keresése (tavasz, nyár, ősz, tél)
python scrapers/mek_search/mek_calendar_search.py --seasons-only

# Csak a hét napjainak keresése (hétfő .. vasárnap, hétvége)
python scrapers/mek_search/mek_calendar_search.py --weekdays-only

# Csak hónaprészek keresése (elején, közepén, végén)
python scrapers/mek_search/mek_calendar_search.py --month-parts-only

# Teljes körű keresés (dátumok + hónaprészek + évszakok + napok + ünnepek)
python scrapers/mek_search/mek_calendar_search.py --include-all --output scrapers/mek_search/mek_calendar_search_results.jsonl
```

### 2. Adatbázis migráció és feltöltés
```bash
# Táblák és intervallum-oszlopok biztosítása
python migrate_add_calendar_interval_cols.py

# Keresési találatok betöltése
python seed_calendar_db.py
```

### 3. AI Értékelés (Gemini Flash)
```bash
python calendar_ai_grader.py
```

### 4. Idézetek böngészése és emberi értékelése
Indítsd el a webalkalmazást:
```bash
cd grading-app
npm run dev
```
Nyisd meg a böngészőben a `http://localhost:5173` címet, és válts **Date Mode**-ra.
