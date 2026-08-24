import argparse
import json
import logging
import math
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse

import json5
import requests
from bs4 import BeautifulSoup

# Add repo root and scrapers directory to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / 'scrapers') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'scrapers'))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def load_rules(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json5.load(f)
    except Exception as e:
        logging.error(f"Failed to load rules from {path}: {e}")
        return None


class DateTermGenerator:
    def __init__(self, rules):
        self.rules = rules
        self.months = rules.get('months', [])
        self.day_suffixes = rules.get('day_suffixes', ['.'])
        self.month_parts = rules.get('month_parts', [])
        self.seasons = rules.get('seasons', [])
        self.weekdays = rules.get('weekdays', [])
        self.special_terms = rules.get('special_terms', [])

    def generate_terms_for_date(self, month_num: int, day: int) -> List[str]:
        terms = set()
        
        # Find matching month config
        month_cfg = next((m for m in self.months if m.get("num") == month_num), None)
        month_forms = month_cfg.get("forms", []) if month_cfg else []

        for month_form in month_forms:
            for suffix in self.day_suffixes:
                terms.add(f"{month_form} {day}{suffix}")
                terms.add(f"{month_form} {day:02}{suffix}")

        # Numeric variants
        terms.add(f"{month_num}.{day}.")
        terms.add(f"{month_num:02}.{day:02}.")
        terms.add(f"{day}.{month_num}.")
        terms.add(f"{day:02}.{month_num:02}.")
        terms.add(f"{day:02}. {month_num:02}.")
        terms.add(f"{day:02}-{month_num:02}")
        terms.add(f"{day:02}/{month_num:02}")

        return list(terms)

    def generate_month_part_queries(self) -> List[Tuple[str, List[str], str, Dict[str, Any]]]:
        """
        Generates month-part queries (e.g. "március elején", "április közepén").
        Returns list of (query_id, terms, query_str, meta_dict).
        """
        results = []
        for month_cfg in self.months:
            m_num = month_cfg.get("num")
            m_name = month_cfg.get("name", "")
            max_days = month_cfg.get("max_days", 31)
            month_forms = month_cfg.get("forms", [m_name])

            for part_cfg in self.month_parts:
                part_name = part_cfg.get("part")
                suffix_forms = part_cfg.get("suffix_forms", [])
                off_min = part_cfg.get("offset_min", 1)
                off_max = max_days if part_cfg.get("offset_max") == "max" else part_cfg.get("offset_max", 10)
                off_foc = part_cfg.get("offset_focus", 5)

                d_min_str = f"{m_num:02d}-{off_min:02d}"
                d_max_str = f"{m_num:02d}-{off_max:02d}"
                d_foc_str = f"{m_num:02d}-{off_foc:02d}"

                terms = set()
                for mf in month_forms:
                    for sf in suffix_forms:
                        terms.add(f"{mf} {sf}")

                query_id = f"month_part_{m_num:02d}_{part_name}"
                query_str = MekQueryBuilder.build_query(list(terms))
                meta = {
                    "date_min_str": d_min_str,
                    "date_max_str": d_max_str,
                    "date_focus_str": d_foc_str,
                    "day_of_week": None
                }
                results.append((query_id, list(terms), query_str, meta))
        return results

    def generate_season_queries(self) -> List[Tuple[str, List[str], str, Dict[str, Any]]]:
        """
        Generates season queries (tavasz, nyár, ősz, tél).
        """
        results = []
        for s in self.seasons:
            query_id = f"season_{s['id']}"
            terms = s.get("terms", [])
            query_str = MekQueryBuilder.build_query(terms)
            meta = {
                "date_min_str": s.get("date_min"),
                "date_max_str": s.get("date_max"),
                "date_focus_str": s.get("date_focus"),
                "day_of_week": None
            }
            results.append((query_id, terms, query_str, meta))
        return results

    def generate_weekday_queries(self) -> List[Tuple[str, List[str], str, Dict[str, Any]]]:
        """
        Generates day-of-week queries (hétfő, kedd, ..., vasárnap, hétvége).
        """
        results = []
        for w in self.weekdays:
            query_id = f"dow_{w['id']}"
            terms = w.get("terms", [])
            query_str = MekQueryBuilder.build_query(terms)
            meta = {
                "date_min_str": None,
                "date_max_str": None,
                "date_focus_str": None,
                "day_of_week": w.get("dow")
            }
            results.append((query_id, terms, query_str, meta))
        return results

    def generate_special_queries(self) -> List[Tuple[str, List[str], str, Dict[str, Any]]]:
        """
        Generates special holiday / festival queries.
        """
        results = []
        for item in self.special_terms:
            term = item.get("term")
            if not term:
                continue
            query_id = f"special_{re.sub(r'[^a-zA-Z0-9_]', '_', term)}"
            query_str = MekQueryBuilder.build_query([term])
            meta = {
                "date_min_str": item.get("date_min"),
                "date_max_str": item.get("date_max"),
                "date_focus_str": item.get("date_focus"),
                "day_of_week": item.get("dow")
            }
            results.append((query_id, [term], query_str, meta))
        return results


class MekQueryBuilder:
    """
    Constructs optimized boolean search queries for MEK fulltext search.
    """
    @staticmethod
    def build_query(terms: List[str]) -> str:
        formatted = []
        for t in sorted(set(terms)):
            t_clean = t.strip()
            if not t_clean:
                continue
            if " " in t_clean or ":" in t_clean or "-" in t_clean or "/" in t_clean or "." in t_clean:
                formatted.append(f'"{t_clean}"')
            else:
                formatted.append(t_clean)
        return " | ".join(formatted)


class MekSearcher:
    """
    Fast, direct HTTP-based searcher for MEK calendar fulltext search.
    """
    def __init__(
        self,
        download_covers: bool = False,
        max_pages: int = 5,
        request_delay_sec: float = 0.4,
        cache_dir: Optional[Path] = None,
        headless: bool = True  # Backward compatibility
    ):
        self.url = "https://mek.oszk.hu/hu/search/elfulltext/"
        self.download_covers = download_covers
        self.max_pages = max_pages
        self.request_delay_sec = request_delay_sec
        base_cache = Path(cache_dir) if cache_dir else Path(__file__).resolve().parent / "cache"
        self.metadata_fetcher = MekMetadataFetcher(cache_dir=base_cache / "metadata")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "hu-HU,hu;q=0.9,en;q=0.8",
        })

    def search(self, term_or_query: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
        effective_max_pages = max_pages if max_pages is not None else self.max_pages
        raw_results = []

        try:
            time.sleep(self.request_delay_sec)
            resp = self.session.post(self.url, data={"body": term_or_query, "size": "100", "from": "1"}, timeout=(10, 30))
            if resp.status_code != 200 or not resp.text:
                logging.warning(f"Search request failed for '{term_or_query}', status: {resp.status_code}")
                return []

            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            num_elem = soup.find(class_="numberofhits") or soup.select_one("div.elful.results h4") or soup.find("h4")
            total_hits = 0
            if num_elem:
                match = re.search(r"(\d+)", num_elem.get_text(strip=True))
                if match:
                    total_hits = int(match.group(1))

            page_1_hits = self._parse_hit_elements(soup, term_or_query)
            raw_results.extend(page_1_hits)

            if total_hits == 0 and not raw_results:
                return []

            expected_pages = math.ceil(total_hits / 100) if total_hits > 0 else (1 if len(page_1_hits) < 100 else effective_max_pages)
            pages_to_fetch = min(effective_max_pages, max(1, expected_pages))

            logging.info(f"Query [{term_or_query[:60]}...] -> {total_hits} total hits ({pages_to_fetch}/{expected_pages} pages)")

            for page in range(2, pages_to_fetch + 1):
                offset = (page - 1) * 100 + 1
                time.sleep(self.request_delay_sec)
                p_resp = self.session.post(self.url, data={"body": term_or_query, "size": "100", "from": str(offset)}, timeout=(10, 30))
                if p_resp.status_code == 200 and p_resp.text:
                    p_resp.encoding = "utf-8"
                    p_soup = BeautifulSoup(p_resp.text, "html.parser")
                    p_hits = self._parse_hit_elements(p_soup, term_or_query)
                    if not p_hits:
                        break
                    raw_results.extend(p_hits)
                else:
                    break

        except Exception as e:
            logging.error(f"Error during HTTP search for '{term_or_query}': {e}")
            return []

        return self._process_and_enrich_hits(raw_results, term_or_query)

    def _parse_hit_elements(self, soup: BeautifulSoup, term: str) -> List[Dict[str, Any]]:
        results = []
        hit_blocks = soup.find_all("div", class_="hit")
        for hit in hit_blocks:
            try:
                author_elem = hit.find(class_="dcauthor")
                title_elem = hit.find(class_="dctitle")
                author = author_elem.get_text(strip=True) if author_elem else ""
                title = title_elem.get_text(strip=True) if title_elem else ""

                link = ""
                source_url = ""
                for a in hit.find_all("a"):
                    href = a.get("href", "")
                    text = a.get_text(strip=True)
                    if not link and ("mek.oszk.hu" in href or re.match(r"^/\d{5}/", href)):
                        link = urljoin("https://mek.oszk.hu", href)
                    if "Találat helye" in text or "talalat" in href.lower():
                        source_url = urljoin("https://mek.oszk.hu", href)

                foundtext = hit.find(class_="foundtext")
                snippet = foundtext.get_text(separator=" ", strip=True) if foundtext else ""

                if link and (title or author):
                    results.append({
                        "search_term": term,
                        "title": title,
                        "author": author,
                        "link": link,
                        "source_url": source_url,
                        "snippet": snippet
                    })
            except Exception as e:
                logging.debug(f"Failed to parse hit element: {e}")
        return results

    def _process_and_enrich_hits(self, raw_results: List[Dict[str, Any]], term: str) -> List[Dict[str, Any]]:
        if not raw_results:
            return []

        valid_results = []
        fallback_results = []
        for res in raw_results:
            meta = self.metadata_fetcher.fetch_metadata(res["link"])
            is_lit = meta.get("is_literature", False)
            topics = meta.get("topics", [])

            res["source_type"] = "snippet_fallback"
            res["is_fallback"] = True
            res["is_literature"] = is_lit
            res["topics"] = topics
            res["urn"] = meta.get("urn", "")
            res["genre"] = meta.get("genre", "")
            res["cover_url"] = meta.get("cover_url", "")
            res["raw_metadata"] = meta.get("raw_metadata", {})

            if self.download_covers and meta.get("mek_id"):
                self.metadata_fetcher.fetch_cover_image(meta["mek_id"], Path("covers"))

            if is_lit:
                valid_results.append(res)
            else:
                fallback_results.append(res)

        if valid_results:
            return valid_results
        if fallback_results:
            return fallback_results
        return []

    def close(self):
        self.session.close()


def main():
    parser = argparse.ArgumentParser(description="Search MEK for calendar/date patterns with optimized HTTP query compression.")
    parser.add_argument("--rules", default=str(REPO_ROOT / "rules_calendar.json5"), help="Path to rules_calendar.json5")
    parser.add_argument("--limit", type=int, default=0, help="Max items to search (0 = all).")
    parser.add_argument("--max-pages", type=int, default=5, help="Max pagination pages per exact date query (default: 5).")
    parser.add_argument("--fuzzy-max-pages", type=int, default=3, help="Max pagination pages per fuzzy/season/weekday query (default: 3).")
    parser.add_argument("--output", default="mek_calendar_search_results.jsonl", help="Output file path.")
    parser.add_argument("--term", help="Search for a specific term directly.")
    parser.add_argument("--dates-only", action="store_true", default=False, help="Search only 366 exact calendar dates.")
    parser.add_argument("--seasons-only", action="store_true", default=False, help="Search only 4 seasons (tavasz, nyár, ősz, tél).")
    parser.add_argument("--weekdays-only", action="store_true", default=False, help="Search only 7 weekdays and weekend.")
    parser.add_argument("--month-parts-only", action="store_true", default=False, help="Search only month parts (elején/közepén/végén).")
    parser.add_argument("--include-all", action="store_true", default=False, help="Search dates, month parts, seasons, weekdays, and special holidays.")
    parser.add_argument("--download-covers", action="store_true", default=False, help="Download cover images.")
    parser.add_argument("--visible", action="store_true", help="Kept for backward compatibility.")
    args = parser.parse_args()

    rules_path = Path(args.rules)
    rules = load_rules(rules_path)
    if not rules:
        logging.error("Could not load rules. Exiting.")
        return

    processed_ids = set()
    output_path = Path(args.output)
    if output_path.exists():
        logging.info(f"Reading existing results from {output_path}...")
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        if "query_id" in record:
                            processed_ids.add(record["query_id"])
                        elif "date_min_str" in record and record["date_min_str"]:
                            processed_ids.add(record["date_min_str"])
                        elif "search_term" in record:
                            processed_ids.add(record["search_term"])
                    except json.JSONDecodeError:
                        pass
            logging.info(f"Found {len(processed_ids)} already processed items.")
        except Exception as e:
            logging.warning(f"Error reading existing file: {e}")

    searcher = MekSearcher(
        download_covers=args.download_covers,
        max_pages=args.max_pages
    )

    try:
        generator = DateTermGenerator(rules)
        search_queue = []

        if args.term:
            meta = {"date_min_str": None, "date_max_str": None, "date_focus_str": None, "day_of_week": None}
            search_queue.append((args.term, [args.term], args.term, args.max_pages, meta))
        elif args.seasons_only:
            logging.info("Generating season queries...")
            for q_id, terms, q_str, meta in generator.generate_season_queries():
                search_queue.append((q_id, terms, q_str, args.fuzzy_max_pages, meta))
        elif args.weekdays_only:
            logging.info("Generating weekday queries...")
            for q_id, terms, q_str, meta in generator.generate_weekday_queries():
                search_queue.append((q_id, terms, q_str, args.fuzzy_max_pages, meta))
        elif args.month_parts_only:
            logging.info("Generating month-part queries...")
            for q_id, terms, q_str, meta in generator.generate_month_part_queries():
                search_queue.append((q_id, terms, q_str, args.fuzzy_max_pages, meta))
        else:
            # Default or include_all: 366 dates
            logging.info("Generating date terms and compressed queries for all 366 days...")
            for month_cfg in rules.get("months", []):
                m_num = month_cfg.get("num")
                for day in range(1, 32):
                    date_str = f"{m_num:02}-{day:02}"
                    terms = generator.generate_terms_for_date(m_num, day)
                    query = MekQueryBuilder.build_query(terms)
                    meta = {
                        "date_min_str": date_str,
                        "date_max_str": date_str,
                        "date_focus_str": date_str,
                        "day_of_week": None
                    }
                    search_queue.append((date_str, terms, query, args.max_pages, meta))

            if args.include_all:
                logging.info("Appending month parts, seasons, weekdays, and special terms to queue...")
                for q_id, terms, q_str, meta in generator.generate_month_part_queries():
                    search_queue.append((q_id, terms, q_str, args.fuzzy_max_pages, meta))
                for q_id, terms, q_str, meta in generator.generate_season_queries():
                    search_queue.append((q_id, terms, q_str, args.fuzzy_max_pages, meta))
                for q_id, terms, q_str, meta in generator.generate_weekday_queries():
                    search_queue.append((q_id, terms, q_str, args.fuzzy_max_pages, meta))
                for q_id, terms, q_str, meta in generator.generate_special_queries():
                    search_queue.append((q_id, terms, q_str, args.fuzzy_max_pages, meta))

        # Filter already processed
        remaining = [item for item in search_queue if item[0] not in processed_ids]
        if len(remaining) < len(search_queue):
            logging.info(f"Skipping {len(search_queue) - len(remaining)} items already processed. {len(remaining)} remaining.")

        if args.limit > 0:
            logging.info(f"Test mode: selecting {args.limit} items.")
            search_queue = remaining[:args.limit]
        else:
            search_queue = remaining

        logging.info(f"Starting optimized MEK calendar search for {len(search_queue)} queries...")
        start_time = time.time()

        with open(args.output, "a", encoding="utf-8") as f:
            for i, (q_id, terms, query, q_max_pages, meta) in enumerate(search_queue):
                logging.info(f"[{i + 1}/{len(search_queue)}] Searching {q_id} ({len(terms)} terms compressed, max {q_max_pages} pages)...")
                orig_max_pages = searcher.max_pages
                searcher.max_pages = q_max_pages
                results = searcher.search(query)
                searcher.max_pages = orig_max_pages

                if results:
                    logging.info(f"  -> Found {len(results)} valid matches for {q_id}.")
                    for res in results:
                        res["query_id"] = q_id
                        res["date_min_str"] = meta.get("date_min_str")
                        res["date_max_str"] = meta.get("date_max_str")
                        res["date_focus_str"] = meta.get("date_focus_str")
                        res["day_of_week"] = meta.get("day_of_week")
                        f.write(json.dumps(res, ensure_ascii=False) + "\n")
                else:
                    logging.info(f"  -> No matches for {q_id}.")
                    no_match_record = {
                        "query_id": q_id,
                        "search_term": query,
                        "date_min_str": meta.get("date_min_str"),
                        "date_max_str": meta.get("date_max_str"),
                        "date_focus_str": meta.get("date_focus_str"),
                        "day_of_week": meta.get("day_of_week"),
                        "count": 0
                    }
                    f.write(json.dumps(no_match_record, ensure_ascii=False) + "\n")
                f.flush()

                done = i + 1
                total = len(search_queue)
                percent = (done / total) * 100 if total else 100.0
                elapsed = time.time() - start_time
                speed = done / elapsed if elapsed > 0 else 0.0
                remaining_count = total - done
                eta_s = int(remaining_count / speed) if speed > 0 else 0
                eta_m, eta_sec = divmod(eta_s, 60)
                logging.info(f"Progress: {done}/{total} ({percent:.1f}%) | Speed: {speed:.2f} items/s | ETA: {eta_m}m {eta_sec}s")

    finally:
        searcher.close()


if __name__ == "__main__":
    main()
