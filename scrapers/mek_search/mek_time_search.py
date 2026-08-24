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

from mek_metadata import MekMetadataFetcher
from extractor import extract_from_html, extract, raw_html_to_text, load_rules

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def load_rules(path):
    """Loads rules.json5 using json5 parser."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json5.load(f)
    except Exception as e:
        logging.error(f"Failed to load rules from {path}: {e}")
        return None


class TimeTermGenerator:
    def __init__(self, rules):
        self.rules = rules
        self.number_words = rules.get('number_words', {})
        
    def get_number_word(self, n):
        n_str = str(n)
        words = []
        if n_str in self.number_words:
            return self.number_words[n_str]
        if 13 <= n <= 19:
            prefix = self.number_words.get('13_19_prefix', ['tizen'])[0]
            digit = n % 10
            digit_words = self.get_number_word(digit)
            for dw in digit_words:
                words.append(prefix + dw)
        elif 21 <= n <= 29:
            prefix = self.number_words.get('20s_prefix', ['huszon'])[0]
            digit = n % 10
            digit_words = self.get_number_word(digit)
            for dw in digit_words:
                words.append(prefix + dw)
        elif n == 20:
             return self.number_words.get('20_exact', ['húsz'])
        elif n == 30:
             return self.number_words.get('30_exact', ['harminc'])
        elif 31 <= n <= 39:
            prefix = self.number_words.get('30s_prefix', ['harminc'])[0]
            digit = n % 10
            digit_words = self.get_number_word(digit)
            for dw in digit_words:
                words.append(prefix + dw)
        elif n == 40:
             return self.number_words.get('40_exact', ['negyven'])
        elif 41 <= n <= 49:
            prefix = self.number_words.get('40s_prefix', ['negyven'])[0]
            digit = n % 10
            digit_words = self.get_number_word(digit)
            for dw in digit_words:
                words.append(prefix + dw)
        elif n == 50:
             return self.number_words.get('50_exact', ['ötven'])
        elif 51 <= n <= 59:
            prefix = self.number_words.get('50s_prefix', ['ötven'])[0]
            digit = n % 10
            digit_words = self.get_number_word(digit)
            for dw in digit_words:
                words.append(prefix + dw)
        if not words and n_str in self.number_words:
             return self.number_words[n_str]
        return words if words else [str(n)]

    def generate_terms(self, h, m):
        terms = set()
        terms.add(f"{h}:{m:02}")
        terms.add(f"{h:02}:{m:02}")
        terms.add(f"{h} óra {m} perc")
        terms.add(f"{h:02} óra {m:02} perc")
        terms.add(f"{h} óra {m:02} perc")
        
        h_words = self.get_number_word(h)
        m_words = self.get_number_word(m)
        
        for hw in h_words:
            for mw in m_words:
                terms.add(f"{hw} óra {mw} perc")
                terms.add(f"{hw} óra {m} perc")
                terms.add(f"{h} óra {mw} perc")

        if m == 0:
            terms.add(f"{h} óra")
            terms.add(f"{h:02} óra")
            terms.add(f"{h} órakor")
            terms.add(f"{h:02} órakor")
            terms.add(f"{h}-kor")
            for hw in h_words:
                terms.add(f"{hw} óra")
                terms.add(f"{hw} órakor")
                terms.add(f"{hw}-kor") 

        # Hungarian relative quarter/half terms are strictly 1-12 based
        h_12 = 12 if h % 12 == 0 else h % 12
        next_h_12 = 1 if h_12 == 12 else h_12 + 1
        next_h_words = self.get_number_word(next_h_12)
        
        if m == 30:
            terms.add(f"fél {next_h_12}")
            for w in next_h_words:
                terms.add(f"fél {w}")
        
        if m == 15:
            terms.add(f"negyed {next_h_12}")
            for w in next_h_words:
                terms.add(f"negyed {w}")

        if m == 45:
            terms.add(f"háromnegyed {next_h_12}")
            for w in next_h_words:
                terms.add(f"háromnegyed {w}")

        if m > 0:
            terms.add(f"{m} perccel {h} óra után")
            if h != h_12:
                terms.add(f"{m} perccel {h_12} óra után")
            for mw in m_words:
                terms.add(f"{mw} perccel {h} óra után")
                if h != h_12:
                    terms.add(f"{mw} perccel {h_12} óra után")
                for hw in h_words:
                    terms.add(f"{mw} perccel {hw} óra után")
                if h != h_12:
                    for hw12 in self.get_number_word(h_12):
                        terms.add(f"{mw} perccel {hw12} óra után")
        
        y_before = 60 - m
        if 0 < y_before < 60:
            target_next_h = (h + 1) % 24
            target_next_h_12 = next_h_12
            terms.add(f"{y_before} perccel {target_next_h} óra előtt")
            if target_next_h != target_next_h_12:
                terms.add(f"{y_before} perccel {target_next_h_12} óra előtt")
            y_before_words = self.get_number_word(y_before)
            target_next_h_words = self.get_number_word(target_next_h)
            for ybw in y_before_words:
                terms.add(f"{ybw} perccel {target_next_h} óra előtt")
                if target_next_h != target_next_h_12:
                    terms.add(f"{ybw} perccel {target_next_h_12} óra előtt")
                for tnhw in target_next_h_words:
                    terms.add(f"{ybw} perccel {tnhw} óra előtt")
                if target_next_h != target_next_h_12:
                    for tnhw12 in self.get_number_word(target_next_h_12):
                        terms.add(f"{ybw} perccel {tnhw12} óra előtt")

        return list(terms)


class DaypartTermGenerator:
    """
    Generates canonical search terms and queries for broad and nuanced Hungarian dayparts.
    """
    DAYPART_CATEGORIES = [
        ("hajnal", ["hajnal*", "pirkadat*", "napkelte*", "pitymallat*"]),
        ("reggel", ["reggel*", "kora reggel*"]),
        ("delelott", ["délelőtt*"]),
        ("del", ["délben", "dél körül", "dél tájban", "déli harangszó*"]),
        ("kora_delutan", ["kora délután*"]),
        ("delutan", ["délután*"]),
        ("keso_delutan_alkonyat", ["késő délután*", "alkonyat*", "szürkület*", "napnyugta*", "naplemente*"]),
        ("kora_este", ["kora este*"]),
        ("este", ["este*", "esteled*"]),
        ("keso_este", ["késő este*"]),
        ("ejfel_korul", ["éjfél tájban*", "éjfél körül*", "éjfél után*", "éjfél előtt*"]),
        ("ejjel", ["éjjel*", "éjszaka*"]),
    ]

    @classmethod
    def generate_daypart_queries(cls) -> List[Tuple[str, List[str], str]]:
        """
        Returns a list of (category_id, terms_list, boolean_query).
        """
        queue = []
        for cat_id, terms in cls.DAYPART_CATEGORIES:
            query = MekQueryBuilder.build_query(terms)
            queue.append((cat_id, terms, query))
        return queue


class MekQueryBuilder:
    """
    Constructs optimized boolean search queries for MEK fulltext search.
    Wraps phrases in quotes and joins alternatives with pipe '|'.
    """
    @staticmethod
    def build_query(terms: List[str]) -> str:
        formatted = []
        for t in sorted(set(terms)):
            t_clean = t.strip()
            if not t_clean:
                continue
            if " " in t_clean or ":" in t_clean or "-" in t_clean:
                formatted.append(f'"{t_clean}"')
            else:
                formatted.append(t_clean)
        return " | ".join(formatted)


class MekSourceFetcher:
    """
    Fetches and caches MEK source pages (HTML/TXT) to local storage.
    """
    def __init__(self, cache_dir: Optional[Path] = None, request_delay_sec: float = 0.5):
        self.cache_dir = Path(cache_dir) if cache_dir else Path(__file__).resolve().parent / "cache" / "sources"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.request_delay_sec = request_delay_sec
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "LiteratureClockHU/1.0 (+https://github.com/notAnElephant/literatureclock) SourceFetcher"
        })

    def get_cache_path(self, url: str) -> Path:
        parsed = urlparse(url)
        path_str = parsed.path.lstrip("/")
        parts = path_str.split("/")
        if len(parts) >= 2:
            return self.cache_dir / Path(*parts)
        safe_name = re.sub(r'[^\w\-_\.]', '_', url)
        return self.cache_dir / f"{safe_name}.htm"

    def fetch_page(self, url: str) -> Optional[str]:
        if not url:
            return None
        cache_path = self.get_cache_path(url)
        is_pdf = url.lower().endswith(".pdf") or cache_path.suffix.lower() == ".pdf"
        txt_cache_path = cache_path.with_suffix(".extracted.txt") if is_pdf else None

        if is_pdf and txt_cache_path and txt_cache_path.exists():
            try:
                return txt_cache_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                logging.warning(f"Failed to read cached PDF text at {txt_cache_path}: {e}")
        elif not is_pdf and cache_path.exists():
            try:
                return cache_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                logging.warning(f"Failed to read cached source at {cache_path}: {e}")

        try:
            time.sleep(self.request_delay_sec)
            resp = self.session.get(url, timeout=(10, 45))
            if resp.status_code != 200 or not resp.content:
                logging.warning(f"Failed to fetch {url}, status: {resp.status_code}")
                return None

            if is_pdf:
                # Save raw PDF to cache
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_bytes(resp.content)
                except Exception as e:
                    logging.warning(f"Failed to write PDF cache at {cache_path}: {e}")

                # Extract text using pypdf
                try:
                    import io
                    import pypdf
                    reader = pypdf.PdfReader(io.BytesIO(resp.content))
                    pages_text = []
                    for page in reader.pages:
                        t = page.extract_text()
                        if t:
                            pages_text.append(t)
                    extracted = "\n\n".join(pages_text)
                    if txt_cache_path and extracted:
                        try:
                            txt_cache_path.write_text(extracted, encoding="utf-8", errors="replace")
                        except Exception:
                            pass
                    return extracted
                except Exception as e:
                    logging.warning(f"PDF text extraction failed for {url}: {e}")
                    return None
            else:
                resp.encoding = resp.apparent_encoding or "utf-8"
                content = resp.text
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(content, encoding="utf-8", errors="replace")
                except Exception as e:
                    logging.warning(f"Failed to write source cache at {cache_path}: {e}")
                return content
        except Exception as e:
            logging.warning(f"Network error fetching {url}: {e}")
            return None


class MekSearcher:
    """
    Fast, direct HTTP-based searcher for MEK fulltext search (https://mek.oszk.hu/hu/search/elfulltext/).
    Supports automatic hit count extraction and precise pagination.
    """
    def __init__(
        self,
        rules=None,
        deep_extract: bool = True,
        download_covers: bool = False,
        max_pages: int = 5,
        request_delay_sec: float = 0.4,
        cache_dir: Optional[Path] = None,
        headless: bool = True  # Backward compatibility parameter
    ):
        self.url = "https://mek.oszk.hu/hu/search/elfulltext/"
        self.rules = rules
        self.deep_extract = deep_extract
        self.download_covers = download_covers
        self.max_pages = max_pages
        self.request_delay_sec = request_delay_sec
        base_cache = Path(cache_dir) if cache_dir else Path(__file__).resolve().parent / "cache"
        self.metadata_fetcher = MekMetadataFetcher(cache_dir=base_cache / "metadata")
        self.source_fetcher = MekSourceFetcher(cache_dir=base_cache / "sources")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "hu-HU,hu;q=0.9,en;q=0.8",
        })

    def search(self, term_or_query: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Executes search via HTTP POST, parses exact hit count, paginates, and enriches hits.
        """
        effective_max_pages = max_pages if max_pages is not None else self.max_pages
        raw_results = []
        
        try:
            # 1. Fetch Page 1
            time.sleep(self.request_delay_sec)
            resp = self.session.post(self.url, data={"body": term_or_query, "size": "100", "from": "1"}, timeout=(10, 30))
            if resp.status_code != 200 or not resp.text:
                logging.warning(f"Search request failed for '{term_or_query}', status: {resp.status_code}")
                return []

            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Extract total hit count from HTML (.numberofhits or results h4)
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

            # Determine pagination
            expected_pages = math.ceil(total_hits / 100) if total_hits > 0 else (1 if len(page_1_hits) < 100 else effective_max_pages)
            pages_to_fetch = min(effective_max_pages, max(1, expected_pages))

            logging.info(f"Query [{term_or_query[:60]}...] -> {total_hits} total hits ({pages_to_fetch}/{expected_pages} pages)")

            # Fetch subsequent pages if any
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

        # Enrich with metadata, deep extraction, and literature checks
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

            # Deep extraction if source_url is present and enabled
            deep_success = False
            if self.deep_extract and res.get("source_url") and self.rules:
                html_page = self.source_fetcher.fetch_page(res["source_url"])
                if html_page:
                    try:
                        extracted_records = extract_from_html(html_page, self.rules)
                        if extracted_records:
                            deep_success = True
                            for rec in extracted_records:
                                norm_t = rec.get("norm_time")
                                deep_item = {
                                    "search_term": term,
                                    "title": meta.get("title") or res["title"],
                                    "author": meta.get("author") or res["author"],
                                    "link": res["link"],
                                    "source_url": res["source_url"],
                                    "source_type": "deep_extract",
                                    "is_fallback": False,
                                    "snippet": rec["context"],
                                    "matched_text": rec["match"],
                                    "norm_time": norm_t,
                                    "time_min_str": rec.get("time_min_str", norm_t),
                                    "time_max_str": rec.get("time_max_str", norm_t),
                                    "time_focus_str": rec.get("time_focus_str", norm_t),
                                    "time_min_m": rec.get("time_min_m", rec.get("minute")),
                                    "time_max_m": rec.get("time_max_m", rec.get("minute")),
                                    "time_focus_m": rec.get("time_focus_m", rec.get("minute")),
                                    "minute": rec.get("minute"),
                                    "minute_candidates": rec.get("minute_candidates"),
                                    "rule_id": rec.get("rule_id"),
                                    "is_literature": is_lit,
                                    "topics": topics,
                                    "urn": meta.get("urn", ""),
                                    "genre": meta.get("genre", ""),
                                    "cover_url": meta.get("cover_url", ""),
                                    "raw_metadata": meta.get("raw_metadata", {}),
                                    "fallback_snippet": res["snippet"]
                                }
                                if self.download_covers and meta.get("mek_id"):
                                    self.metadata_fetcher.fetch_cover_image(meta["mek_id"], Path("covers"))
                                if is_lit:
                                    valid_results.append(deep_item)
                                else:
                                    fallback_results.append(deep_item)
                    except Exception as e:
                        logging.warning(f"Deep extraction failed on {res['source_url']}: {e}")

            # Fallback to snippet if deep extract didn't yield records
            if not deep_success:
                fb_text = raw_html_to_text(res.get("snippet", ""))
                fb_records = list(extract(fb_text, self.rules)) if self.rules else []
                if fb_records:
                    res["norm_time"] = fb_records[0].get("norm_time")
                    res["time_min_str"] = fb_records[0].get("time_min_str", res["norm_time"])
                    res["time_max_str"] = fb_records[0].get("time_max_str", res["norm_time"])
                    res["time_focus_str"] = fb_records[0].get("time_focus_str", res["norm_time"])
                    res["matched_text"] = fb_records[0].get("match")
                else:
                    term_records = list(extract(term, self.rules)) if self.rules else []
                    if term_records:
                        res["norm_time"] = term_records[0].get("norm_time")
                        res["time_min_str"] = term_records[0].get("time_min_str", res["norm_time"])
                        res["time_max_str"] = term_records[0].get("time_max_str", res["norm_time"])
                        res["time_focus_str"] = term_records[0].get("time_focus_str", res["norm_time"])
                res["source_type"] = "snippet_fallback"
                res["is_fallback"] = True
                res["is_literature"] = is_lit
                res["topics"] = topics
                res["urn"] = meta.get("urn", "")
                res["genre"] = meta.get("genre", "")
                res["cover_url"] = meta.get("cover_url", "")
                res["raw_metadata"] = meta.get("raw_metadata", {})
                if is_lit:
                    valid_results.append(res)
                else:
                    fallback_results.append(res)

        if valid_results:
            return valid_results
        elif fallback_results:
            return fallback_results
        return []

    def close(self):
        self.session.close()


def main():
    parser = argparse.ArgumentParser(description="Search MEK for time patterns with optimized HTTP query compression.")
    parser.add_argument("--rules", default=str(REPO_ROOT / "rules.json5"), help="Path to rules.json5")
    parser.add_argument("--limit", type=int, default=0, help="Max minutes/terms to search (0 = all 1440 minutes).")
    parser.add_argument("--max-pages", type=int, default=5, help="Max pagination pages per minute query (default: 5).")
    parser.add_argument("--output", default="mek_time_search_results.jsonl", help="Output file path.")
    parser.add_argument("--deep-extract", action="store_true", default=True, help="Enable chapter deep extraction (default: enabled).")
    parser.add_argument("--no-deep-extract", action="store_false", dest="deep_extract", help="Disable chapter deep extraction.")
    parser.add_argument("--download-covers", action="store_true", default=False, help="Download cover images.")
    parser.add_argument("--term", help="Search for a specific term or query directly.")
    parser.add_argument("--dayparts-only", action="store_true", default=False, help="Search only Hungarian daypart categories.")
    parser.add_argument("--include-dayparts", action="store_true", default=False, help="Search standard 1440 minutes and dayparts.")
    parser.add_argument("--daypart-max-pages", type=int, default=3, help="Max pages per daypart query (default: 3).")
    parser.add_argument("--visible", action="store_true", help="Kept for backward compatibility (headless HTTP is standard).")
    args = parser.parse_args()

    rules_path = Path(args.rules)
    rules = load_rules(rules_path)
    if not rules:
        logging.error("Could not load rules. Exiting.")
        return

    # Load already processed minutes/terms to resume
    processed_minutes = set()
    output_path = Path(args.output)
    if output_path.exists():
        logging.info(f"Reading existing results from {output_path}...")
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        if "norm_time" in record and record["norm_time"]:
                            processed_minutes.add(record["norm_time"])
                        elif "search_term" in record:
                            processed_minutes.add(record["search_term"])
                    except json.JSONDecodeError:
                        pass
            logging.info(f"Found {len(processed_minutes)} already processed minutes/terms.")
        except Exception as e:
            logging.warning(f"Error reading existing file: {e}")

    searcher = MekSearcher(
        rules=rules,
        deep_extract=args.deep_extract,
        download_covers=args.download_covers,
        max_pages=args.max_pages
    )

    try:
        search_queue = []

        if args.term:
            search_queue.append((args.term, [args.term], args.term, args.max_pages))
        elif args.dayparts_only:
            logging.info("Generating daypart search queries...")
            for cat_id, terms, query in DaypartTermGenerator.generate_daypart_queries():
                search_queue.append((f"daypart_{cat_id}", terms, query, args.daypart_max_pages))
        else:
            generator = TimeTermGenerator(rules)
            logging.info("Generating canonical time terms and compressed queries for all 1440 minutes...")
            for h in range(24):
                for m in range(60):
                    time_str = f"{h:02}:{m:02}"
                    terms = generator.generate_terms(h, m)
                    query = MekQueryBuilder.build_query(terms)
                    search_queue.append((time_str, terms, query, args.max_pages))

            if args.include_dayparts:
                logging.info("Appending daypart search queries to queue...")
                for cat_id, terms, query in DaypartTermGenerator.generate_daypart_queries():
                    search_queue.append((f"daypart_{cat_id}", terms, query, args.daypart_max_pages))

        # Filter already processed
        remaining = [item for item in search_queue if item[0] not in processed_minutes]
        if len(remaining) < len(search_queue):
            logging.info(f"Skipping {len(search_queue) - len(remaining)} items already processed. {len(remaining)} remaining.")
        
        if args.limit > 0:
            logging.info(f"Test mode: selecting {args.limit} items.")
            search_queue = remaining[:args.limit]
        else:
            search_queue = remaining

        logging.info(f"Starting optimized MEK search for {len(search_queue)} queries...")
        start_time = time.time()

        with open(args.output, "a", encoding="utf-8") as f:
            for i, (item_id, terms, query, q_max_pages) in enumerate(search_queue):
                logging.info(f"[{i+1}/{len(search_queue)}] Searching {item_id} ({len(terms)} terms compressed, max {q_max_pages} pages)...")
                # Temporarily override max_pages if query specifies a custom limit
                orig_max_pages = searcher.max_pages
                searcher.max_pages = q_max_pages
                results = searcher.search(query)
                searcher.max_pages = orig_max_pages
                
                if results:
                    logging.info(f"  -> Found {len(results)} valid matches for {item_id}.")
                    for res in results:
                        if not res.get("time_min_str") and not res.get("norm_time"):
                            res["time_min_str"] = item_id if ":" in item_id else None
                        f.write(json.dumps(res, ensure_ascii=False) + "\n")
                else:
                    logging.info(f"  -> No matches for {item_id}.")
                    no_match_record = {
                        "search_term": query,
                        "time_min_str": item_id if ":" in item_id else None,
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
