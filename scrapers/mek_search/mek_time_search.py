import argparse
import json
import logging
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

# Add repo root and scrapers directory to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / 'scrapers') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'scrapers'))

from mek_metadata import MekMetadataFetcher
from extractor import extract_from_html

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    webdriver = None

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

class MekSourceFetcher:
    """
    Downloads and caches source document pages (HTML/TXT) using transparent relative paths.
    """
    def __init__(self, cache_dir: Optional[Path] = None, request_delay_sec: float = 0.5):
        self.cache_dir = Path(cache_dir) if cache_dir else Path(__file__).resolve().parent / "cache" / "pages"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.request_delay_sec = request_delay_sec
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "LiteratureClockHU/1.0 (+https://github.com/notAnElephant/literatureclock) SourceFetcher"
        })

    def get_cache_path(self, source_url: str) -> Optional[Path]:
        parsed = urlparse(source_url)
        rel_path = parsed.path.lstrip("/")
        if not rel_path:
            return None
        return self.cache_dir / rel_path

    def fetch_page(self, source_url: str, force_refresh: bool = False) -> Optional[str]:
        if not source_url:
            return None
        cache_path = self.get_cache_path(source_url)
        if cache_path and not force_refresh and cache_path.exists():
            try:
                raw_bytes = cache_path.read_bytes()
                from bs4.dammit import UnicodeDammit
                dammit = UnicodeDammit(raw_bytes, is_html=True)
                return dammit.unicode_markup or raw_bytes.decode("latin-2", "ignore")
            except Exception as e:
                logging.warning(f"Failed to read cached page at {cache_path}: {e}")

        try:
            time.sleep(self.request_delay_sec)
            resp = self.session.get(source_url, timeout=(10, 60))
            if 200 <= resp.status_code < 400 and resp.content:
                if cache_path:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_bytes(resp.content)
                from bs4.dammit import UnicodeDammit
                dammit = UnicodeDammit(resp.content, is_html=True)
                return dammit.unicode_markup or resp.content.decode("latin-2", "ignore")
        except Exception as e:
            logging.warning(f"Failed to fetch page from {source_url}: {e}")

        return None

class MekSearcher:
    def __init__(self, headless: bool = True, rules: Optional[dict] = None,
                 deep_extract: bool = True, download_covers: bool = False,
                 cache_dir: Optional[Path] = None):
        if not webdriver:
            raise ImportError("A MekSearcher futtatásához a 'selenium' csomag szükséges (pip install selenium webdriver-manager).")
        self.headless = headless
        self.rules = rules
        self.deep_extract = deep_extract
        self.download_covers = download_covers
        
        base_cache = Path(cache_dir) if cache_dir else Path(__file__).resolve().parent / "cache"
        self.metadata_fetcher = MekMetadataFetcher(cache_dir=base_cache / "metadata")
        self.source_fetcher = MekSourceFetcher(cache_dir=base_cache / "pages")

        self.options = webdriver.ChromeOptions()
        if headless:
            self.options.add_argument("--headless")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self._init_driver()
        self.url = "https://mek.oszk.hu/hu/search/elfulltext/#sealist"

    def _init_driver(self):
        logging.info("Initializing Chrome Driver...")
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=self.options)

    def restart_driver(self):
        logging.warning("Restarting Chrome Driver due to error...")
        try:
            self.driver.quit()
        except Exception:
            pass
        self._init_driver()
        
    def search(self, term: str) -> List[Dict[str, Any]]:
        # Retry loop for driver stability
        for attempt in range(2):
            try:
                return self._search_attempt(term)
            except WebDriverException as e:
                logging.error(f"WebDriver error during search for '{term}' (attempt {attempt+1}/2): {e}")
                if attempt == 0:
                    self.restart_driver()
                else:
                    logging.error("Failed to search even after restart.")
                    return []
            except Exception as e:
                logging.error(f"Unexpected error during search for '{term}': {e}")
                return []
        return []

    def _search_attempt(self, term: str) -> List[Dict[str, Any]]:
        raw_results = []
        logging.info(f"Navigating to {self.url}...")
        self.driver.get(self.url)
        search_input = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.NAME, "body"))
        )
        
        # Set results per page to 100
        try:
            size_select = Select(self.driver.find_element(By.NAME, "size"))
            size_select.select_by_value("100")
        except Exception as e:
            logging.warning(f"Could not set result size to 100: {e}")

        quoted_term = f'"{term}"'
        logging.info(f"Searching for: {quoted_term}")
        search_input.clear()
        search_input.send_keys(quoted_term)
        submit_btn = self.driver.find_element(By.XPATH, "//input[@type='submit']")
        submit_btn.click()
        
        # Wait for results
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "hit"))
            )
        except TimeoutException:
            logging.info("  -> No hits found (timeout waiting for .hit).")
            return []
        
        # Grab all HTML immediately
        hit_divs = self.driver.find_elements(By.CLASS_NAME, "hit")
        logging.info(f"Found {len(hit_divs)} hit blocks.")
        
        hits_html = []
        for div in hit_divs:
            try:
                hits_html.append(div.get_attribute('outerHTML'))
            except Exception as e:
                logging.warning(f"Error grabbing HTML for a hit: {e}")

        # Parse with BeautifulSoup
        for i, html in enumerate(hits_html):
            try:
                soup = BeautifulSoup(html, 'html.parser')
                
                link_elem = soup.find('a', class_='etitem')
                if not link_elem:
                    logging.warning(f"Hit {i}: Could not find .etitem inside .hit")
                    continue

                link = link_elem.get('href', '')
                
                author_elem = link_elem.find(class_='dcauthor')
                author = author_elem.get_text(strip=True) if author_elem else ""
                    
                title_elem = link_elem.find(class_='dctitle')
                title = title_elem.get_text(strip=True) if title_elem else ""
                    
                snippet_elem = link_elem.find(class_='foundtext')
                snippet = str(snippet_elem) if snippet_elem else ""
                
                # Extract "Találat helye" link (.mekfound)
                found_elem = soup.find('a', class_='mekfound')
                found_href = found_elem.get('href', '').strip() if found_elem else ''
                source_url = urljoin('https://mek.oszk.hu', found_href) if found_href else ''

                full_title = f"{author}: {title}" if author else title

                if full_title:
                    raw_results.append({
                        "search_term": term,
                        "title": full_title,
                        "author": author,
                        "link": link,
                        "source_url": source_url,
                        "snippet": snippet
                    })
                else:
                        logging.warning(f"Hit {i}: Skipped because title is empty.")

            except Exception as e:
                logging.warning(f"Error parsing hit block {i}: {e}")
        
        # Enrich with metadata, deep extraction and literature checks
        if raw_results:
            logging.info(f"Processing {len(raw_results)} hits (deep_extract={self.deep_extract})...")
            valid_results = []
            fallback_results = []
            
            for res in raw_results:
                meta = self.metadata_fetcher.fetch_metadata(res['link'])
                is_lit = meta.get("is_literature", False)
                topics = meta.get("topics", [])
                
                if not is_lit and not topics:
                    is_lit, topics = self.check_is_literature(res['link'])
                    meta["is_literature"] = is_lit
                    meta["topics"] = topics

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
                                    valid_time_list = [norm_t] if norm_t else []
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
                                        "minute": rec.get("minute"),
                                        "minute_candidates": rec.get("minute_candidates"),
                                        "rule_id": rec.get("rule_id"),
                                        "valid_times": valid_time_list,
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
                logging.info(f"  -> {len(valid_results)} literature hits kept.")
                return valid_results
            elif fallback_results:
                logging.info(f"  -> 0 literature hits. Returning {len(fallback_results)} non-literature hits as fallback.")
                return fallback_results
        
        return []

    def check_is_literature(self, link: str) -> Tuple[bool, List[str]]:
        if not link:
            return False, []
        try:
            self.driver.get(link)
            tags = self.driver.find_elements(By.CSS_SELECTOR, ".topic, .subtopic")
            topics = [t.text for t in tags]
            lowered_topics = [t.lower() for t in topics]
            is_lit = any(
                ("irodalom" in t) and ("irodalomtudomány" not in t) and ("irodalomtudomany" not in t)
                for t in lowered_topics
            )
            return is_lit, topics
        except WebDriverException:
            # Re-raise WebDriverException to trigger driver restart in search()
            raise
        except Exception as e:
            logging.warning(f"Failed to check link {link}: {e}")
            return False, []

    def close(self):
        self.driver.quit()

def main():
    parser = argparse.ArgumentParser(description="Search MEK for time patterns with hybrid deep extraction.")
    parser.add_argument("--limit", type=int, default=5, help="Max number of terms to search.")
    parser.add_argument("--output", default="mek_search_results.jsonl", help="Output file path.")
    parser.add_argument("--visible", action="store_true", help="Run browser in visible mode.")
    parser.add_argument("--term", help="Search for a specific term (ignores generator).")
    parser.add_argument("--deep-extract", dest="deep_extract", action="store_true", default=True,
                        help="Perform deep extraction on 'Találat helye' chapter sources (default: True).")
    parser.add_argument("--no-deep-extract", dest="deep_extract", action="store_false",
                        help="Disable deep extraction and save only search snippets.")
    parser.add_argument("--download-covers", action="store_true", default=False,
                        help="Download cover images when available into covers/ directory.")
    args = parser.parse_args()

    rules_path = Path(__file__).parent.parent.parent / 'rules.json5'
    rules = load_rules(rules_path)
    if not rules:
        logging.error("Could not load rules. Exiting.")
        return

    # Load already processed terms to resume
    processed_terms = set()
    output_path = Path(args.output)
    if output_path.exists():
        logging.info(f"Reading existing results from {output_path}...")
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        if "search_term" in record:
                            processed_terms.add(record["search_term"])
                    except json.JSONDecodeError:
                        pass
            logging.info(f"Found {len(processed_terms)} already processed terms.")
        except Exception as e:
            logging.warning(f"Error reading existing file: {e}")

    searcher = MekSearcher(
        headless=not args.visible,
        rules=rules,
        deep_extract=args.deep_extract,
        download_covers=args.download_covers
    )

    try:
        term_to_times = defaultdict(set)
        
        if args.term:
            term = args.term
            logging.info(f"Single term mode: {term}")
            if term in processed_terms:
                logging.warning(f"Term '{term}' was already processed. Searching anyway (single term mode).")
            search_queue = [term]
        else:
            generator = TimeTermGenerator(rules)
            logging.info("Generating search terms...")
            for h in range(24):
                for m in range(60):
                    terms = generator.generate_terms(h, m)
                    time_str = f"{h:02}:{m:02}"
                    for t in terms:
                        term_to_times[t].add(time_str)
            
            sorted_terms = sorted(list(term_to_times.keys()))
            logging.info(f"Generated {len(sorted_terms)} unique search terms.")
            
            # Filter out processed terms
            remaining_terms = [t for t in sorted_terms if t not in processed_terms]
            if len(remaining_terms) < len(sorted_terms):
                logging.info(f"Skipping {len(sorted_terms) - len(remaining_terms)} terms already processed. {len(remaining_terms)} remaining.")
            
            if args.limit > 0:
                logging.info(f"Test mode: selecting {args.limit} random terms from remaining.")
                if not remaining_terms:
                    logging.info("No remaining terms to process.")
                    return
                search_queue = random.sample(remaining_terms, min(args.limit, len(remaining_terms)))
            else:
                search_queue = remaining_terms

        logging.info(f"Starting search for {len(search_queue)} terms...")
        
        # Open in APPEND mode
        with open(args.output, 'a', encoding='utf-8') as f:
            for i, term in enumerate(search_queue):
                logging.info(f"[{i+1}/{len(search_queue)}] Searching: {term}")
                results = searcher.search(term)
                
                valid_times = list(term_to_times.get(term, []))
                
                if results:
                    logging.info(f"  -> Found {len(results)} matches.")
                    for res in results:
                        if not res.get("valid_times"):
                            res["valid_times"] = valid_times
                        f.write(json.dumps(res, ensure_ascii=False) + "\n")
                else:
                    logging.info("  -> No matches.")
                    no_match_record = {
                        "search_term": term,
                        "valid_times": valid_times,
                        "count": 0
                    }
                    f.write(json.dumps(no_match_record, ensure_ascii=False) + "\n")
                f.flush()

    finally:
        searcher.close()

if __name__ == "__main__":
    main()
