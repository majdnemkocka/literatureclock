#!/usr/bin/env python3
from __future__ import annotations

import json, json5, re, sys, unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Any

from bs4 import BeautifulSoup
from bs4.dammit import UnicodeDammit

RULES_PATH = Path(__file__).with_name("rules.json5")

# ---------- utils ----------
def norm(s: str) -> str:
    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))

def load_rules() -> dict:
    rules = json5.loads(RULES_PATH.read_text(encoding="utf-8"))
    for r in rules["rules"]:
        r["_re"] = re.compile(r["pattern"], re.IGNORECASE | re.UNICODE)
    return rules

def raw_html_to_text(raw: bytes | str) -> str:
    if isinstance(raw, bytes):
        dammit = UnicodeDammit(raw, is_html=True)
        html = dammit.unicode_markup or raw.decode("latin-2", "ignore")
    else:
        html = raw
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    text = soup.get_text(separator=" ", strip=False)
    return re.sub(r"\s+", " ", text)

def html_to_text(path: Path) -> str:
    return raw_html_to_text(path.read_bytes())

def extract_from_html(html_content: str | bytes, rules: Optional[dict] = None) -> List[dict]:
    """
    Extracts time records directly from an in-memory HTML string or bytes.
    """
    if rules is None:
        rules = load_rules()
    elif not rules.get("rules", []) or "_re" not in rules["rules"][0]:
        # Compile regexes if not already compiled
        for r in rules.get("rules", []):
            if "_re" not in r:
                r["_re"] = re.compile(r["pattern"], re.IGNORECASE | re.UNICODE)
    text = raw_html_to_text(html_content)
    return list(extract(text, rules))

def hhmm_to_minute(h: int, m: int) -> int:
    return (h % 24) * 60 + (m % 60)

# number-word parsing for minutes (0..59)
ONES = {
    "nulla":0,"zero":0,"zéro":0,
    "egy":1,"kettő":2,"ketto":2,"két":2,"ket":2,"három":3,"harom":3,"négy":4,"negy":4,
    "öt":5,"ot":5,"hat":6,"hét":7,"het":7,"nyolc":8,"kilenc":9,"tíz":10,"tiz":10,
    "tizenegy":11,"tizenkettő":12,"tizenketto":12,"tizenhárom":13,"tizenharom":13,
    "tizennégy":14,"tizennegy":14,"tizenöt":15,"tizenot":15,"tizenhat":16,
    "tizenhét":17,"tizenhet":17,"tizennyolc":18,"tizenkilenc":19
}
TENS_BASE = {
    "húsz":20,"husz":20,"húszon":20,"huszon":20,
    "harminc":30,"negyven":40,"ötven":50,"otven":50
}
def parse_hu_number_word(token: str) -> Optional[int]:
    t = norm(token)
    if t in ONES: return ONES[t]
    for pref in ("huszon","húszon"):
        if t.startswith(pref):
            rest = t[len(pref):]
            return 20 + ONES.get(rest, -1) if rest in ONES else (20 if rest=="" else None)
    for base, val in TENS_BASE.items():
        if t == base: return val
        if t.startswith(base):
            rest = t[len(base):]
            return val + ONES.get(rest, -1) if rest in ONES else None
    return None

def find_dayparts(text: str, rules: dict) -> List[Tuple[int,int,str]]:
    dp_rule = next(x for x in rules["rules"] if x["semantics"] == "daypart_for_bias")
    rx = dp_rule["_re"]
    return [(m.start(), m.end(), m.group(0)) for m in rx.finditer(text)]

def nearby(tokens: List[Tuple[int,int,str]], i0: int, i1: int, radius: int = 40) -> List[str]:
    out = []
    for a,b,t in tokens:
        if not (i1 + radius < a or b < i0 - radius):
            out.append(t)
    return out

def disambiguate_hour_candidates(h: int, ctx_tokens: List[str]) -> List[int]:
    """
    Return candidate hours in 24h.
    - If context has AM/PM cue → single candidate.
    - Else if 1..12 → return [h, h+12 (mod 24)].
    - Else (already 24h digit) → [h].
    """
    if not (0 <= h <= 23):
        h = h % 24
    if not (1 <= h <= 12):
        return [h]

    ctx = {norm(t) for t in ctx_tokens}
    if any(t in ctx for t in ("de.", "reggel", "délelőtt", "delelott", "hajnal", "dél", "del")):
        return [0 if h==12 else h]
    if any(t in ctx for t in ("du.", "délután", "delutan", "este", "éjjel", "ejjel")):
        return [12 if h==12 else (h+12)]
    # ambiguous on purpose: both candidates
    return [0 if h==12 else h, 12 if h==12 else (h+12)]

def emit_record(rule_id: str, match_txt: str, s: int, e: int, text: str,
                hour_candidates: List[int], minute_value: int) -> dict:
    if len(hour_candidates) == 1:
        minute = hhmm_to_minute(hour_candidates[0], minute_value)
        return {
            "rule_id": rule_id,
            "match": match_txt,
            "norm_time": f"{minute//60:02d}:{minute%60:02d}",
            "minute": minute,
            "context": text[max(0,s-60):min(len(text),e+60)].strip()
        }
    else:
        mins = [hhmm_to_minute(h, minute_value) for h in hour_candidates]
        return {
            "rule_id": rule_id,
            "match": match_txt,
            "minute": None,
            "minute_candidates": sorted(mins),
            "ambiguous_12h": True,
            "context": text[max(0,s-60):min(len(text),e+60)].strip()
        }

# ---------- core extraction ----------
def extract(text: str, rules: dict) -> Iterable[dict]:
    dayparts = find_dayparts(text, rules)

    for r in rules["rules"]:
        kind = r["semantics"]; rx = r["_re"]
        if kind == "daypart_for_bias":
            continue  # never emit
        for m in rx.finditer(text):
            s,e = m.start(), m.end()
            # --- skip if 'múlva' is immediately after the match ---
            after = text[e:e+10]  # look ahead a bit
            if re.match(r"^[\s\.,;:!?-]*múlva\b", after, re.IGNORECASE):
                # print(f"Skipping match due to 'múlva': {m.group(0)}", file=sys.stderr)
                continue
            ctx = nearby(dayparts, s, e)
            match_txt = m.group(0)

            if kind == "clock_hh_mm":
                h, mm = int(m.group(1)), int(m.group(2))
                yield emit_record(r["id"], match_txt, s, e, text, [h], mm)

            elif kind == "clock_words_maybe_digits":
                hour_word = m.group(1)
                min_digits = m.group(2)
                min_word = m.group(3)
                h_raw = rules["word2hour"].get(norm(hour_word))
                if h_raw is None:
                    continue
                h_cands = disambiguate_hour_candidates(h_raw, ctx)
                if min_digits:
                    mm = int(min_digits)
                elif min_word:
                    mm = parse_hu_number_word(min_word)
                    if mm is None or mm > 59:
                        continue
                else:
                    continue
                yield emit_record(r["id"], match_txt, s, e, text, h_cands, mm)

            elif kind == "oclock_h":
                h = int(m.group(1))
                yield emit_record(r["id"], match_txt, s, e, text, [h], 0)

            elif kind in ("half_next_hour","quarter_next_hour","threequarter_next_hour"):
                target = m.group(1)
                # target can be digit or word
                if target.isdigit():
                    to_h = int(target)
                else:
                    to_h = rules["word2hour"].get(norm(target), None)
                    if to_h is None:
                        continue
                # candidates for the *incoming* hour
                to_cands = disambiguate_hour_candidates(to_h, ctx)
                # convert each candidate 'to' to (from, minute)
                mm = 30 if kind == "half_next_hour" else 15 if kind == "quarter_next_hour" else 45
                # from_h = (to_h - 1) % 24  → apply per candidate
                hours = [ (h-1) % 24 for h in to_cands ]
                yield emit_record(r["id"], match_txt, s, e, text, hours, mm)

            elif kind == "after_minutes":
                # groups: (Yd | Yw) ... Xh OR Xh ... (Yd | Yw)
                g = m.groups()
                # pick whichever is not None
                y_digits = next((int(v) for v in (g[0], g[4]) if v and v.isdigit()), None)
                y_word   = next((v for v in (g[1], g[5]) if v), None)
                x_hour   = next((int(v) for v in (g[2], g[3]) if v and v.isdigit()), None)
                if x_hour is None:
                    continue
                y = y_digits if y_digits is not None else (parse_hu_number_word(y_word) if y_word else None)
                if y is None or y > 59:
                    continue
                yield emit_record(r["id"], match_txt, s, e, text, [x_hour], y)

            elif kind == "before_minutes":
                g = m.groups()
                y_digits = next((int(v) for v in (g[0], g[4]) if v and v.isdigit()), None)
                y_word   = next((v for v in (g[1], g[5]) if v), None)
                x_hour   = next((int(v) for v in (g[2], g[3]) if v and v.isdigit()), None)
                if x_hour is None:
                    continue
                y = y_digits if y_digits is not None else (parse_hu_number_word(y_word) if y_word else None)
                if y is None or y > 59:
                    continue
                # (X-1):(60-Y)
                from_h = (x_hour - 1) % 24
                mm = (60 - y) % 60
                yield emit_record(r["id"], match_txt, s, e, text, [from_h], mm)

            elif kind == "oclock_word_needs_daypart":
                word = m.group(1)
                h_raw = rules["word2hour"].get(norm(word))
                if h_raw is None:
                    continue
                h_cands = disambiguate_hour_candidates(h_raw, ctx)
                yield emit_record(r["id"], match_txt, s, e, text, h_cands, 0)

def iter_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        if root.suffix.lower() in (".htm", ".html"):
            yield root
        return
    for p in root.rglob("*"):
        if p.suffix.lower() in (".htm", ".html"):
            yield p

def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("Usage: extractor.py <file-or-dir>", file=sys.stderr)
        return 2
    rules = load_rules()
    for path in iter_files(Path(argv[1])):
        try:
            text = html_to_text(path)
        except Exception as e:
            print(json.dumps({"file": str(path), "error": f"read_failed: {e}"}), flush=True)
            continue
        for hit in extract(text, rules):
            hit["file"] = str(path)
            print(json.dumps(hit, ensure_ascii=False), flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
