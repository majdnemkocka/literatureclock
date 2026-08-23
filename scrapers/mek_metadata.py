from __future__ import annotations

import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "cache" / "metadata"


class MekMetadataFetcher:
    """
    Fetches, parses, and caches bibliographic metadata and Linked Open Data (LOD)
    for MEK (Magyar Elektronikus Könyvtár) catalog items.
    """

    def __init__(self, cache_dir: Optional[Path] = None, request_delay_sec: float = 0.5):
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.request_delay_sec = request_delay_sec
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "LiteratureClockHU/1.0 (+https://github.com/notAnElephant/literatureclock) MetadataFetcher"
        })

    @staticmethod
    def extract_mek_id(url_or_id: str) -> Optional[Tuple[str, str]]:
        """
        Extracts (prefix, id) from URL or ID string.
        E.g. 'https://mek.oszk.hu/00700/00708/' -> ('00700', '00708')
             '/16000/16078/16078.htm' -> ('16000', '16078')
             'MEK-00708' -> ('00700', '00708')
             '00708' -> ('00700', '00708')
        """
        if not url_or_id:
            return None

        # Matches /00700/00708 or 00700/00708
        match = re.search(r'(?:^|[^\d])(\d{2,5})/(\d{2,5})(?:[^\d]|$)', url_or_id)
        if match:
            prefix, mek_id = match.group(1).zfill(5), match.group(2).zfill(5)
            return prefix, mek_id

        # Matches MEK-00708 or plain numeric ID
        id_match = re.search(r'(?:MEK-)?(\d+)', url_or_id, re.IGNORECASE)
        if id_match:
            raw_id = int(id_match.group(1))
            mek_id = f"{raw_id:05d}"
            prefix = f"{(raw_id // 100) * 100:05d}"
            return prefix, mek_id

        return None

    def get_cache_path(self, prefix: str, mek_id: str) -> Path:
        return self.cache_dir / prefix / mek_id / "metadata.json"

    def fetch_metadata(self, url_or_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetches metadata for a MEK item, checking local cache first.
        """
        extracted = self.extract_mek_id(url_or_id)
        if not extracted:
            return {
                "error": f"Invalid MEK ID or URL: {url_or_id}",
                "url": url_or_id
            }

        prefix, mek_id = extracted
        cache_path = self.get_cache_path(prefix, mek_id)

        if not force_refresh and cache_path.exists():
            try:
                with cache_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                return data
            except Exception as e:
                logger.warning(f"Failed to read cached metadata at {cache_path}: {e}")

        # Fetch from network (RDF first, then HTML fallback)
        data = self._fetch_from_rdf(prefix, mek_id)
        if not data or not data.get("title"):
            html_data = self._fetch_from_html(prefix, mek_id)
            if html_data:
                if data:
                    # Merge HTML data into RDF data
                    html_data.update(data)
                    data = html_data
                else:
                    data = html_data

        if not data:
            data = {
                "mek_id": mek_id,
                "prefix": prefix,
                "url": f"https://mek.oszk.hu/{prefix}/{mek_id}/",
                "title": "",
                "author": "",
                "urn": "",
                "is_literature": False
            }

        # Cache the result
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write metadata cache at {cache_path}: {e}")

        return data

    def _fetch_from_rdf(self, prefix: str, mek_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches and parses metadata.rdf for the item.
        """
        rdf_url = f"https://mek.oszk.hu/{prefix}/{mek_id}/metadata.rdf"
        try:
            time.sleep(self.request_delay_sec)
            resp = self.session.get(rdf_url, timeout=(10, 30))
            if resp.status_code != 200 or not resp.content:
                return None

            root = ET.fromstring(resp.content)
            
            # Namespaces used by MEK LOD RDF
            ns = {
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "dcterms": "http://purl.org/dc/terms/",
                "bibo": "http://purl.org/ontology/bibo/",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "ore": "http://www.openarchives.org/ore/terms/",
                "foaf": "http://xmlns.com/foaf/0.1/",
                "owl": "http://www.w3.org/2002/07/owl#"
            }

            title = ""
            title_elem = root.find(".//dcterms:title", ns)
            if title_elem is not None and title_elem.text:
                title = title_elem.text.strip()

            urn = ""
            urn_elem = root.find(".//dcterms:identifier", ns)
            if urn_elem is not None and urn_elem.text:
                urn = urn_elem.text.strip()

            genre = ""
            genre_elem = root.find(".//dcterms:type", ns)
            if genre_elem is not None and genre_elem.text:
                genre = genre_elem.text.strip()

            isbn = ""
            isbn_elem = root.find(".//bibo:isbn13", ns)
            if isbn_elem is not None and isbn_elem.text:
                isbn = isbn_elem.text.strip()

            author = ""
            viaf_url = ""
            creator_node = root.find(".//dcterms:creator", ns)
            if creator_node is not None:
                hu_name = creator_node.find(".//foaf:name[@xml:lang='hu']", {"foaf": ns["foaf"], "xml": "http://www.w3.org/XML/1998/namespace"})
                if hu_name is not None and hu_name.text:
                    author = hu_name.text.strip()
                elif creator_node.find(".//rdfs:label", ns) is not None:
                    author = creator_node.find(".//rdfs:label", ns).text.strip()

                owl_same = creator_node.find(".//owl:sameAs", ns)
                if owl_same is not None:
                    viaf_url = owl_same.get(f"{{{ns['rdf']}}}resource", "")

            # Aggregated files
            aggregates = []
            for agg in root.findall(".//ore:aggregates", ns):
                res = agg.get(f"{{{ns['rdf']}}}resource")
                if res:
                    aggregates.append(res)

            return {
                "mek_id": mek_id,
                "prefix": prefix,
                "url": f"https://mek.oszk.hu/{prefix}/{mek_id}/",
                "cover_url": f"https://mek.oszk.hu/{prefix}/{mek_id}/borito.jpg",
                "urn": urn,
                "title": title,
                "author": author,
                "genre": genre,
                "isbn": isbn,
                "viaf_url": viaf_url,
                "aggregates": aggregates,
                "source": "rdf",
                "raw_metadata": {
                    "title": title,
                    "author": author,
                    "urn": urn,
                    "genre": genre,
                    "isbn": isbn,
                    "viaf": viaf_url,
                    "files": aggregates
                }
            }
        except Exception as e:
            logger.debug(f"RDF fetch/parse failed for {prefix}/{mek_id}: {e}")
            return None

    def _fetch_from_html(self, prefix: str, mek_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches and parses Dublin Core / Open Graph meta tags from the MEK HTML catalog page.
        """
        item_url = f"https://mek.oszk.hu/{prefix}/{mek_id}/"
        try:
            time.sleep(self.request_delay_sec)
            resp = self.session.get(item_url, timeout=(10, 30))
            if resp.status_code != 200 or not resp.text:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            
            title = ""
            author = ""
            urn = ""
            cover_url = f"https://mek.oszk.hu/{prefix}/{mek_id}/borito.jpg"
            topics = []

            for m in soup.find_all("meta"):
                name = (m.get("name") or m.get("property") or "").lower()
                content = m.get("content", "").strip()
                if not content:
                    continue
                if name in ("dc.title", "og:title"):
                    if not title or name == "dc.title":
                        title = content
                elif name in ("dc.creator", "author"):
                    author = content
                elif name == "dc.identifier" and m.get("scheme", "").upper() == "URN":
                    urn = content
                elif name == "og:image":
                    cover_url = urljoin(item_url, content)
                elif name in ("dc.subject", "keywords"):
                    topics.append(content)

            tags = soup.select(".topic, .subtopic")
            for t in tags:
                txt = t.get_text(strip=True)
                if txt and txt not in topics:
                    topics.append(txt)

            is_lit = any(
                ("irodalom" in t.lower()) and ("irodalomtudomány" not in t.lower()) and ("irodalomtudomany" not in t.lower())
                for t in topics
            )

            return {
                "mek_id": mek_id,
                "prefix": prefix,
                "url": item_url,
                "cover_url": cover_url,
                "urn": urn,
                "title": title,
                "author": author,
                "topics": topics,
                "is_literature": is_lit,
                "source": "html",
                "raw_metadata": {
                    "title": title,
                    "author": author,
                    "urn": urn,
                    "topics": topics,
                    "cover_url": cover_url
                }
            }
        except Exception as e:
            logger.debug(f"HTML fetch/parse failed for {prefix}/{mek_id}: {e}")
            return None

    def fetch_cover_image(self, url_or_id: str, dest_dir: Path) -> Optional[Path]:
        """
        Optionally downloads the book cover image if available.
        """
        extracted = self.extract_mek_id(url_or_id)
        if not extracted:
            return None
        prefix, mek_id = extracted
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        cover_path = dest_dir / f"{prefix}_{mek_id}_borito.jpg"

        if cover_path.exists():
            return cover_path

        cover_url = f"https://mek.oszk.hu/{prefix}/{mek_id}/borito.jpg"
        try:
            time.sleep(self.request_delay_sec)
            resp = self.session.get(cover_url, timeout=(10, 30))
            if resp.status_code == 200 and resp.content and len(resp.content) > 500:
                cover_path.write_bytes(resp.content)
                return cover_path
        except Exception as e:
            logger.debug(f"Failed to fetch cover image from {cover_url}: {e}")

        return None
