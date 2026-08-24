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
    from selenium.webdriver.support.ui import Select, WebDriverWait
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    webdriver = None

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
        self.special_terms = rules.get('special_terms', [])

    def generate_terms(self):
        term_to_dates = defaultdict(set)

        for month in self.months:
            month_num = month['num']
            month_forms = month.get('forms', [])

            for day in range(1, 32):
                date_mmdd = f"{month_num:02}-{day:02}"

                for month_form in month_forms:
                    for suffix in self.day_suffixes:
                        term_to_dates[f"{month_form} {day}{suffix}"].add(date_mmdd)
                        term_to_dates[f"{month_form} {day:02}{suffix}"].add(date_mmdd)

                # Numeric variants without year
                term_to_dates[f"{month_num}.{day}."].add(date_mmdd)
                term_to_dates[f"{month_num:02}.{day:02}."].add(date_mmdd)
                term_to_dates[f"{day}.{month_num}."].add(date_mmdd)
                term_to_dates[f"{day:02}.{month_num:02}."].add(date_mmdd)
                term_to_dates[f"{day:02}.{month_num:02}."].add(date_mmdd)
                term_to_dates[f"{day:02}. {month_num:02}."].add(date_mmdd)
                term_to_dates[f"{day:02}-{month_num:02}"].add(date_mmdd)
                term_to_dates[f"{day:02}/{month_num:02}"].add(date_mmdd)

                # Numeric variants with common placeholder year patterns
                term_to_dates[f"2015. {month_num:02}. {day:02}."].add(date_mmdd)
                term_to_dates[f"2011.{month_num:02}.{day:02}"].add(date_mmdd)
                term_to_dates[f"{day:02}.{month_num:02}.2015"].add(date_mmdd)

        for item in self.special_terms:
            term = item.get('term')
            mapped_dates = item.get('valid_dates', [])
            if not term:
                continue
            if mapped_dates:
                for mapped in mapped_dates:
                    term_to_dates[term].add(mapped)
            else:
                # Keep term searchable even if date is movable/unspecified.
                term_to_dates[term]

        return term_to_dates


class MekSearcher:
    def __init__(self, headless: bool = True, download_covers: bool = False, cache_dir: Optional[Path] = None):
        if not webdriver:
            raise ImportError("A MekSearcher futtatásához a 'selenium' csomag szükséges (pip install selenium webdriver-manager).")
        self.options = webdriver.ChromeOptions()
        if headless:
            self.options.add_argument("--headless")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.url = "https://mek.oszk.hu/hu/search/elfulltext/#sealist"
        self.download_covers = download_covers
        base_cache = Path(cache_dir) if cache_dir else Path(__file__).resolve().parent / "cache"
        self.metadata_fetcher = MekMetadataFetcher(cache_dir=base_cache / "metadata")
        self._init_driver()

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
        for attempt in range(2):
            try:
                return self._search_attempt(term)
            except WebDriverException as e:
                logging.error(f"WebDriver error during search for '{term}' (attempt {attempt + 1}/2): {e}")
                if attempt == 0:
                    self.restart_driver()
                else:
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

        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "hit"))
            )
        except TimeoutException:
            logging.info("  -> No hits found (timeout waiting for .hit).")
            return []

        hit_divs = self.driver.find_elements(By.CLASS_NAME, "hit")
        logging.info(f"Found {len(hit_divs)} hit blocks.")

        for i, div in enumerate(hit_divs):
            try:
                html = div.get_attribute('outerHTML')
                soup = BeautifulSoup(html, 'html.parser')
                link_elem = soup.find('a', class_='etitem')
                if not link_elem:
                    continue

                link = link_elem.get('href', '')
                author_elem = link_elem.find(class_='dcauthor')
                author = author_elem.get_text(strip=True) if author_elem else ""
                title_elem = link_elem.find(class_='dctitle')
                title = title_elem.get_text(strip=True) if title_elem else ""
                snippet_elem = link_elem.find(class_='foundtext')
                snippet = str(snippet_elem) if snippet_elem else ""

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
                    logging.warning(f"Hit {i}: skipped because title is empty")
            except Exception as e:
                logging.warning(f"Error parsing hit block {i}: {e}")

        if not raw_results:
            return []

        valid_results = []
        fallback_results = []
        for res in raw_results:
            meta = self.metadata_fetcher.fetch_metadata(res['link'])
            is_lit = meta.get("is_literature", False)
            topics = meta.get("topics", [])
            
            # If is_literature or topics not in meta, ensure it is populated
            if "is_literature" not in meta or "topics" not in meta:
                is_lit, topics = self.check_is_literature(res['link'])
                meta["is_literature"] = is_lit
                meta["topics"] = topics

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
            logging.info(f"  -> {len(valid_results)} literature hits kept.")
            return valid_results
        if fallback_results:
            logging.info(f"  -> 0 literature hits. Returning {len(fallback_results)} non-literature hits as fallback.")
            return fallback_results
        return []

    def check_is_literature(self, link: str) -> Tuple[bool, List[str]]:
        if not link:
            return False, []
        try:
            meta = self.metadata_fetcher.fetch_metadata(link)
            return meta.get("is_literature", False), meta.get("topics", [])
        except Exception as e:
            logging.warning(f"Failed to check literature status for {link}: {e}")
            return False, []

    def close(self):
        self.driver.quit()


def main():
    parser = argparse.ArgumentParser(description="Search MEK for calendar/date patterns with LOD metadata.")
    parser.add_argument("--limit", type=int, default=200, help="Max number of terms to search. Use <=0 for all.")
    parser.add_argument("--output", default="mek_calendar_search_results.jsonl", help="Output file path.")
    parser.add_argument("--visible", action="store_true", help="Run browser in visible mode.")
    parser.add_argument("--term", help="Search for a specific term (ignores generator).")
    parser.add_argument("--download-covers", action="store_true", default=False,
                        help="Download cover images when available into covers/ directory.")
    args = parser.parse_args()

    rules_path = Path(__file__).parent.parent.parent / 'rules_calendar.json5'
    rules = load_rules(rules_path)
    if not rules:
        logging.error("Could not load calendar rules. Exiting.")
        return

    processed_terms = set()
    output_path = Path(args.output)
    if output_path.exists():
        with open(output_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if "search_term" in record:
                        processed_terms.add(record["search_term"])
                except json.JSONDecodeError:
                    pass
        logging.info(f"Found {len(processed_terms)} already processed terms.")

    searcher = MekSearcher(
        headless=not args.visible,
        download_covers=args.download_covers
    )

    try:
        if args.term:
            term_to_dates = {args.term: set()}
            search_queue = [args.term]
        else:
            generator = DateTermGenerator(rules)
            term_to_dates = generator.generate_terms()
            all_terms = sorted(term_to_dates.keys())
            remaining_terms = [t for t in all_terms if t not in processed_terms]
            if args.limit > 0:
                search_queue = random.sample(remaining_terms, min(args.limit, len(remaining_terms)))
            else:
                search_queue = remaining_terms

        logging.info(f"Starting search for {len(search_queue)} date terms...")
        start_time = time.time()

        with open(args.output, 'a', encoding='utf-8') as f:
            for i, term in enumerate(search_queue):
                logging.info(f"[{i + 1}/{len(search_queue)}] Searching: {term}")
                results = searcher.search(term)
                valid_dates = sorted(list(term_to_dates.get(term, [])))

                if results:
                    for res in results:
                        res["valid_dates"] = valid_dates
                        f.write(json.dumps(res, ensure_ascii=False) + "\n")
                else:
                    no_match_record = {
                        "search_term": term,
                        "valid_dates": valid_dates,
                        "count": 0
                    }
                    f.write(json.dumps(no_match_record, ensure_ascii=False) + "\n")
                f.flush()

                done = i + 1
                total = len(search_queue)
                percent = (done / total) * 100 if total else 100.0
                elapsed = time.time() - start_time
                speed = done / elapsed if elapsed > 0 else 0.0
                remaining = total - done
                eta_seconds = int(remaining / speed) if speed > 0 else 0
                eta_h, rem = divmod(eta_seconds, 3600)
                eta_m, eta_s = divmod(rem, 60)
                logging.info(
                    f"Progress: {done}/{total} ({percent:.2f}%) | "
                    f"Speed: {speed:.2f} terms/s | ETA: {eta_h:02d}:{eta_m:02d}:{eta_s:02d}"
                )
    finally:
        searcher.close()


if __name__ == "__main__":
    main()
