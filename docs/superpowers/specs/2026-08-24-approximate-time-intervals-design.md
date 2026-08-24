# Közelítő Időintervallumok Kezelése — Design Spec

**Dátum:** 2026-08-24  
**Státusz:** Jóváhagyva, implementációra vár  
**Érintett komponensek:** DB séma, `ai_grader.py`, megjelenítési logika (`grading-app`, `literature-calendar`)

---

## Összefoglalás

A scraper jelenleg pontos perceket keres (regex alapon), de a megtalált idézetek egy része közelítő időkifejezést tartalmaz (`"éjfél körül"`, `"nem sokkal fél hat előtt"`, `"az éjféli harangszót követően rögvest"`). Ezeket az idézeteket jelenleg az egyetlen illesztett percre (`valid_times`) cimkézi a rendszer — ez szemantikailag hibás.

Ez a spec bevezeti az **intervallum-alapú időreprezentációt**: minden idézethez `[time_min, time_max]` intervallum és egy `time_focus` fókuszpont tartozik. Az AI grader már amúgy is feldolgoz minden megtartott idézetet, így az intervallum-meghatározást ide delegáljuk külön feldolgozási lépés nélkül.

---

## Alapelvek

1. **Minden belekerül az adatbázisba** — a túl tág időkifejezések (pl. `"este"`) sem kizártak; a megjelenítési logika súlyozza őket.
2. **Minél pontosabb, annál nagyobb esély** — a véletlenszerű kiválasztás súlyozott; a nulla esély nem megengedett.
3. **Az AI rendel intervallumot** — a regex réteg változatlan marad; az intervallum-határokat az AI grader határozza meg a szövegkörnyezet alapján. Ez azért jobb, mint regex-szabályok, mert az AI olyan fuzzy kifejezéseket is értelmez, amelyeket a regex nem jelölne meg (pl. `"az éjféli harangszót követően rögvest"`).
4. **Éjféli wrap-around: 24+ notáció** — az éjfelet átlépő intervallumokban `time_max` értéke `>= 24:00` lehet (pl. `"23:45–24:15"`), így mindig fennáll `time_min <= time_max`, és nincs szükség körös aritmetikára.
5. **Kettős tárolás a kényelemért** — az emberi olvashatóság érdekében a string alak (`"24:15"`) és a percalapú integer egyaránt tárolva van.

---

## Adatmodell változások

### Új oszlopok az `entries` táblában

```sql
-- Emberi olvashatóság (autoritatív forrás, AI adja)
ALTER TABLE entries ADD COLUMN time_min_str    VARCHAR(7);   -- pl. "23:45", "24:15"
ALTER TABLE entries ADD COLUMN time_max_str    VARCHAR(7);   -- pl. "24:15", "26:00"
ALTER TABLE entries ADD COLUMN time_focus_str  VARCHAR(7);   -- pl. "24:00", "17:30"

-- Számítási kényelem (mindig time_*_str-ből derivált, soha nem kézzel írva)
ALTER TABLE entries ADD COLUMN time_min_m      SMALLINT;     -- percek 00:00 óta, 0–1439
ALTER TABLE entries ADD COLUMN time_max_m      SMALLINT;     -- 0–2879 (max ~48:00, reálisan max ~27:00)
ALTER TABLE entries ADD COLUMN time_focus_m    SMALLINT;     -- 0–2879
```

A `valid_times TEXT[]` mező **deprecated** — új rekordoknál nem töltjük, meglévő adat visszafelé-kompatibilitás céljából marad, de a megjelenítési logika az új mezőket használja.

A `corrected_time` az AI grader outputjában **deprecated** — szerepét a `time_focus_str` veszi át (pontos időknél `time_min == time_max == time_focus`).

### Indexek

```sql
CREATE INDEX IF NOT EXISTS idx_entries_time_min_m  ON entries(time_min_m);
CREATE INDEX IF NOT EXISTS idx_entries_time_max_m  ON entries(time_max_m);
```

### Konverziós segédfüggvény

```python
def parse_extended_hhmm(s: str) -> int:
    """
    Pl. "17:30" -> 1050, "24:15" -> 1455, "26:00" -> 1560.
    Elfogad HH:MM alakot, ahol HH >= 24 az éjfélen átnyúló intervallumokat jelzi.
    """
    h, m = map(int, s.split(":"))
    return h * 60 + m
```

---

## Példák — várható értékek

| Kifejezés | time_min_str | time_max_str | time_focus_str | time_min_m | time_max_m | time_focus_m |
|---|---|---|---|---|---|---|
| `"fél hat"` | 17:30 | 17:30 | 17:30 | 1050 | 1050 | 1050 |
| `"13:45"` | 13:45 | 13:45 | 13:45 | 825 | 825 | 825 |
| `"éjfél körül"` | 23:45 | 24:15 | 24:00 | 1425 | 1455 | 1440 |
| `"éjféli harangszót követően rögvest"` | 24:00 | 24:10 | 24:01 | 1440 | 1450 | 1441 |
| `"nem sokkal fél hat előtt"` | 17:18 | 17:29 | 17:29 | 1038 | 1049 | 1049 |
| `"pár perccel délután négy után"` | 16:02 | 16:10 | 16:04 | 962 | 970 | 964 |
| `"kora délután"` | 13:00 | 15:00 | 14:00 | 780 | 900 | 840 |
| `"este"` | 19:00 | 23:00 | 21:00 | 1140 | 1380 | 1260 |
| `"éjjel"` | 22:00 | 26:00 | 24:00 | 1320 | 1560 | 1440 |

> **Megjegyzés a fókuszpontról:** `time_focus` **nem** szükségszerűen a midpoint — az AI a szöveg alapján határozza meg a legtipikusabb időpontot. Pl. `"éjféli harangszót követően rögvest"` fókusza `24:01`, nem `24:05`.

---

## AI Grader változások (`ai_grader.py`)

### Prompt kiegészítés

A `PROMPT_TEMPLATE`-be kerül a következő blokk (a jelenlegi `corrected_time` leírása mellé/helyett):

```
- "time_min_str": (string) Az intervallum kezdete "HH:MM" formátumban.
  * Ha az intervallum átlépi az éjfelet, a time_max_str-ben "24:xx" (vagy "25:xx" stb.)
    jelölést használj, hogy time_min_str <= time_max_str mindig teljesüljön.
  * Pontos időnél time_min_str == time_max_str == time_focus_str.
  * Ha status = DENY, értéke null.

- "time_max_str": (string) Az intervallum vége "HH:MM" formátumban (24+ jelölés megengedett).
  * Ha status = DENY, értéke null.

- "time_focus_str": (string) A legvalószínűbb időpont az intervallumon belül.
  * Ez NEM szükségszerűen a midpoint: "nem sokkal fél hat előtt" esetén
    a fókusz 17:29 (a végpont közelében van), nem 17:23.
  * "éjféli harangszót követően rögvest" esetén 24:01, nem 24:05.
  * Ha status = DENY, értéke null.

- "corrected_time": null  <- deprecated, ne töltsd, a time_focus_str váltja ki.

Irányelvek az intervallum meghatározásához:
  * Pontos perc ("13:45", "fél hat", "negyed három"): intervallum = 0 perc.
  * Fuzzy módosítóval ("körül", "tájban", "nagyjából"): +-10-20 perc, szimmetrikus.
  * Aszimmetrikus kifejezések ("rögvest", "nem sokkal X előtt/után"):
    a fókusz az intervallum egyik végéhez közel van.
  * Napszakrész ("kora délután", "késő este"): +-45-90 perc.
  * Napszak ("este", "reggel", "éjjel"): 3-5 óra széles intervallum.
```

### Output séma változás

```json
{
  "id": 42,
  "status": "KEEP",
  "rate": 4,
  "reason": "Fuzzy midnight reference",
  "am_pm": "AMBIGUOUS",
  "corrected_time": null,
  "time_min_str": "23:45",
  "time_max_str": "24:15",
  "time_focus_str": "24:00"
}
```

### `mark_as_checked()` változás

A meglévő `corrected_time` feldolgozó ág mellé kerül az intervallum-feldolgozás:

```python
def validated_extended_hhmm(s):
    """Visszaad (str, int) párt, vagy (None, None) ha érvénytelen."""
    if not s or not isinstance(s, str):
        return None, None
    s = s.strip()
    if not re.match(r'^\d{1,2}:\d{2}$', s):
        return None, None
    h, m = map(int, s.split(':'))
    if m > 59 or h > 48:   # Reális felső korlát
        return None, None
    return s, h * 60 + m

min_str, min_m = validated_extended_hhmm(r.get('time_min_str'))
max_str, max_m = validated_extended_hhmm(r.get('time_max_str'))
foc_str, foc_m = validated_extended_hhmm(r.get('time_focus_str'))

# Konzisztencia-ellenőrzés: time_min <= time_max, fókusz belül van
if min_m is not None and max_m is not None:
    if min_m > max_m:
        min_str = max_str = foc_str = None
        min_m = max_m = foc_m = None
    elif foc_m is not None and not (min_m <= foc_m <= max_m):
        foc_str, foc_m = None, None  # Fókusz kiesett az intervallumon kívül

cur.execute("""
    UPDATE entries
    SET ai_checked = TRUE,
        ai_rating = %s,
        ai_reason = %s,
        ai_am_pm = %s,
        time_min_str   = %s, time_min_m   = %s,
        time_max_str   = %s, time_max_m   = %s,
        time_focus_str = %s, time_focus_m = %s
    WHERE id = %s
""", (
    r.get('rate'), r.get('reason'), am_pm_val,
    min_str, min_m,
    max_str, max_m,
    foc_str, foc_m,
    r['id']
))
```

---

## Megjelenítési logika

### Jogosultság-ellenőrzés

```python
def is_eligible(entry, current_m: int) -> bool:
    """
    current_m: aktuális perc a nap elejétől (0..1439).
    Az éjfélen átnyúló intervallumokhoz (time_max_m >= 1440)
    current_m + 1440-nel is tesztelünk.
    """
    if entry.time_min_m is None or entry.time_max_m is None:
        return False
    return (entry.time_min_m <= current_m <= entry.time_max_m or
            entry.time_min_m <= current_m + 1440 <= entry.time_max_m)
```

### Súlyozás

```python
def weight(entry, current_m: int) -> float:
    """
    Minél szűkebb az intervallum és minél közelebb az aktuális perc a fókuszhoz,
    annál nagyobb a súly. Soha nem nulla.
    """
    precision = entry.time_max_m - entry.time_min_m  # 0 = pontos

    # Távolság a fókusztól (éjféli wrap-around kezeléssel)
    focus_mod = entry.time_focus_m % 1440
    raw_dist = abs(current_m - focus_mod)
    dist = min(raw_dist, 1440 - raw_dist)

    return 1.0 / ((1 + precision) * (1 + dist))


def pick_quote(candidates: list, current_m: int):
    import random
    eligible = [e for e in candidates if is_eligible(e, current_m)]
    if not eligible:
        return None
    weights = [weight(e, current_m) for e in eligible]
    return random.choices(eligible, weights=weights, k=1)[0]
```

---

## Migráció

### Meglévő bejegyzések újragradolása

A meglévő `ai_checked = TRUE` bejegyzésekre nincs `time_min_m` / `time_max_m` adat. Két lehetőség:

**1. Teljes újragradolás (ajánlott):** `RESET_AI_CHECKED_FOR_REGRADE=true` + az új AI grader futtatása. A meglévő humán szavazatok megmaradnak; csak az AI-mezők frissülnek.

**2. Fallback kitöltés (gyors, de pontatlan):** `valid_times[0]`-ból `time_min_m = time_max_m = time_focus_m`, azaz minden meglévő bejegyzést pontosnak jelöl. Gyorsan elvégezhető:

```sql
UPDATE entries
SET
    time_min_str   = valid_times[1],
    time_max_str   = valid_times[1],
    time_focus_str = valid_times[1],
    time_min_m     = (split_part(valid_times[1], ':', 1)::int * 60
                      + split_part(valid_times[1], ':', 2)::int),
    time_max_m     = (split_part(valid_times[1], ':', 1)::int * 60
                      + split_part(valid_times[1], ':', 2)::int),
    time_focus_m   = (split_part(valid_times[1], ':', 1)::int * 60
                      + split_part(valid_times[1], ':', 2)::int)
WHERE ai_checked = TRUE
  AND valid_times IS NOT NULL
  AND array_length(valid_times, 1) > 0
  AND time_min_m IS NULL;
```

A teljes újragradolás ajánlott, mert az összes fuzzy bejegyzés helyes intervallumot kap.

---

## Hatókör — ami NEM változik

- **Scraper regex**: változatlan. A fuzzy kifejezések nem igényelnek új keresési lekérdezést — a jelenlegi keresések (pl. `"éjfél"`) már most is megtalálják az `"éjfél körül"` típusú szövegeket.
- **Bejegyzések köre**: csak olyan szövegek kerülnek be, amelyekben a regex valamit talált. A teljesen generikus napszak-kifejezések (`"kora reggel sétált"`, semmilyen konkrét ankorral) továbbra sem kerülnek be — ez elfogadható korlát.
- **`is_fallback` logika**: változatlan.
- **Humán szavazatok (`votes` tábla)**: változatlan séma; a `corrected_time` a votes táblában marad a korábbi humán javításokhoz.

---

## Nyitott kérdések (implementáció előtt megválaszolandó)

- [ ] A `grading-app` melyik mezőt mutassa az UI-n debugoláshoz — `time_min_str`–`time_max_str` stringeket, vagy percértékeket?
- [ ] Legyen-e hard limit az AI által megadható intervallum szélességére (pl. max 6 óra = 360 perc), és mit tegyünk, ha az AI ennél szélesebbet ad?
- [ ] A `valid_times` mező mikor törölhető véglegesen (melyik milestone után)?
