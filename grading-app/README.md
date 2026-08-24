# Literature Clock & Calendar Grading App

Mobilbarát, modern SvelteKit webalkalmazás a magyar irodalmi óra (Literature Clock) és naptár (Literature Calendar) találatainak emberi áttekintésére, osztályozására és pontozására.

---

## 🌟 Funkciók

- **Kettős üzemmód:**
  - **Time Mode (Óra):** 1440 perc és napszakok (`time_min_str` – `time_max_str`) megjelenítése, szavazás, AM/PM és időpont javítás.
  - **Date Mode (Naptár):** 366 naptári nap, évszakok, hónaprészek és hét napjai szerinti idézetek áttekintése.
- **Könyv-szintű minőségellenőrzés:** Book Review nézet az egyes kötetek találatainak aggregált pontozásához és törléséhez.
- **Statisztika és szűrés:** AI minősítés (0–5 pont), jóváhagyott/elutasított szűrések, hiányzó percek/napok hőtérképe.

---

## 🛠️ Telepítés és Futtatás

### 1. Környezeti változók
Másold át a `.env.example` fájlt vagy állítsd be a `DATABASE_URL` változót:
```bash
DATABASE_URL=postgres://user:password@ep-host.neon.tech/neondb
```

### 2. Adatbázis migráció
Futtasd le az adatbázis sémát inicializáló scripteket a gyökérkönyvtárból:
```bash
python migrate_add_time_interval_cols.py
python migrate_add_calendar_interval_cols.py
```

### 3. Fejlesztői szerver indítása
```bash
npm install
npm run dev
```
Nyisd meg a böngészőben: `http://localhost:5173`.

---

## 🚀 Technológiai Verem

* **Frontend & Backend:** SvelteKit 2
* **Stílus:** Tailwind CSS
* **Adatbázis:** Neon PostgreSQL (`@neondatabase/serverless` & `psycopg2`)
* **Telepítés:** Vercel kompatibilis (`@sveltejs/adapter-auto`)