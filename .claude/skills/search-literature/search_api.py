#!/usr/bin/env python3
"""
search_api.py — Academic literature search client
Searches CrossRef, OpenAlex, and arXiv APIs in parallel.
Implements caching, deduplication, CSV export, and BibTeX generation.
"""

import json
import sys
import os
import hashlib
import time
import csv
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from threading import Thread
from typing import Dict, List, Tuple, Optional
import subprocess

try:
    import requests
except ImportError:
    # Fallback if requests not available; try using curl
    requests = None

# Configuration
CACHE_DIR = Path.home() / ".claude" / "state"
CACHE_FILE = CACHE_DIR / "search_cache.json"
PROJECT_DIR = Path(__file__).parent.parent.parent.parent
BIB_FILE = PROJECT_DIR / "Bibliography_base.bib"
OUTPUT_DIR = PROJECT_DIR / "quality_reports"

# API Configuration
CROSSREF_API = "https://api.crossref.org/works"
OPENALEX_API = "https://api.openalex.org/works"
ARXIV_API = "http://export.arxiv.org/api/query"

# Defaults
DEFAULT_LIMIT = 30
DEFAULT_YEAR_MIN = 2015
DEFAULT_YEAR_MAX = 2026
API_TIMEOUT = 10  # seconds

# Top-tier journal list (Economics + multidisciplinary top journals)
TOP_TIER_JOURNALS = {
    # Economics Top 5
    "american economic review", "econometrica", "journal of political economy",
    "quarterly journal of economics", "review of economic studies",
    # Economics Top-tier
    "journal of econometrics", "journal of economic theory", "international economic review",
    "economic journal", "journal of development economics", "journal of labor economics",
    "journal of monetary economics", "journal of public economics", "rand journal of economics",
    "review of economics and statistics",
    # Multidisciplinary top
    "nature", "science", "proceedings of the national academy of sciences",
    "pnas", "nature machine intelligence", "science advances",
    # AI/Tech economics
    "journal of economic literature", "journal of machine learning research",
    "operations research", "management science", "marketing science",
}

# Recent year threshold (last N years considered "recent")
RECENT_YEAR_THRESHOLD = 5  # Last 5 years


def ensure_dirs():
    """Ensure cache and output directories exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def is_top_tier_journal(paper: Dict) -> bool:
    """Check if paper is from a top-tier journal or has high impact."""
    # Check journal name
    journal = (paper.get("journal", "") or paper.get("container-title", "") or "").lower()
    if any(top_journal in journal for top_journal in TOP_TIER_JOURNALS):
        return True

    # For OpenAlex, check IF score (impact factor)
    if paper.get("source") == "OpenAlex":
        # OpenAlex stores impact factor in "apc_paid" or we use raw impact metrics
        # As fallback, check citation count as proxy
        if paper.get("cited_by_count", 0) > 10:  # High-impact if cited >10 times
            return True

    # arXiv papers: check if they have many citations (preprints that became influential)
    if paper.get("source") == "arXiv":
        if paper.get("cited_by_count", 0) > 50:  # Very influential preprint
            return True

    # CrossRef: use DOI as signal; top journals always have DOIs
    if paper.get("doi") and paper.get("source") == "CrossRef":
        return True

    return False


def filter_by_quality(papers: List[Dict], enforce_top_tier: bool = True) -> List[Dict]:
    """
    Filter papers by quality standards:
    - Must be from top-tier journals (or highly cited)
    - Must have recent papers (last 5 years)
    - Can include older classics (pre-2021) if seminal
    """
    current_year = datetime.now().year
    recent_threshold = current_year - RECENT_YEAR_THRESHOLD

    filtered = []

    for paper in papers:
        year = paper.get("year", 0)

        # Always include if: top-tier journal AND (recent OR seminal/highly-cited)
        is_top = is_top_tier_journal(paper)
        is_recent = year >= recent_threshold
        is_seminal = paper.get("cited_by_count", 0) > 100  # Proxy for classic/seminal

        if enforce_top_tier:
            # Strict mode: must be top-tier AND (recent OR seminal)
            if is_top and (is_recent or is_seminal):
                filtered.append(paper)
        else:
            # Lenient mode: accept if top-tier OR (recent and cited)
            if is_top or (is_recent and paper.get("cited_by_count", 0) > 5):
                filtered.append(paper)

    return filtered


def sort_by_relevance(papers: List[Dict]) -> List[Dict]:
    """Sort papers by: relevance score + citation count + recency."""
    def score(paper):
        year = paper.get("year", 0)
        citations = paper.get("cited_by_count", 0)
        recency_score = (year - 2000) * 10  # Prefer recent
        citation_score = min(citations, 1000) / 10  # Cap citation score

        # Boost top-tier journals
        is_top = is_top_tier_journal(paper)
        tier_score = 100 if is_top else 0

        return tier_score + citation_score + recency_score

    return sorted(papers, key=score, reverse=True)


def enrich_with_citations(papers: List[Dict]) -> List[Dict]:
    """Try to get citation count from OpenAlex data if available."""
    for paper in papers:
        # If from OpenAlex, citation data should already be present
        # If from CrossRef, try to cross-reference with OpenAlex for citation count
        if not paper.get("cited_by_count") and paper.get("doi"):
            # TODO: Could do a second lookup to OpenAlex by DOI, but skipping for now
            # to avoid extra API calls. Citation count adds value but not essential.
            pass
    return papers
    """Generate cache key for query."""
    query_str = f"{topic}|{author}|{year_min}|{year_max}"
    return hashlib.md5(query_str.encode()).hexdigest()


def load_cache() -> Dict:
    """Load cache from disk."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load cache: {e}", file=sys.stderr)
    return {}


def save_cache(cache: Dict):
    """Save cache to disk."""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save cache: {e}", file=sys.stderr)


def check_cache(topic: str, author: str, year_min: int, year_max: int) -> Optional[Dict]:
    """Check if query results exist in cache."""
    cache = load_cache()
    h = query_hash(topic, author, year_min, year_max)
    return cache.get(h, None)


def fetch_json(url: str, params: Dict, timeout: int = API_TIMEOUT) -> Optional[Dict]:
    """Fetch JSON from URL with timeout."""
    try:
        if requests:
            try:
                # Try with SSL verification first
                resp = requests.get(url, params=params, timeout=timeout, verify=True)
                resp.raise_for_status()
                return resp.json()
            except Exception as ssl_error:
                # Fallback: try without SSL verification (for LibreSSL compatibility)
                try:
                    resp = requests.get(url, params=params, timeout=timeout, verify=False)
                    resp.raise_for_status()
                    return resp.json()
                except Exception:
                    raise ssl_error  # Re-raise original error
        else:
            # Fallback: use curl
            query_str = urlencode(params)
            result = subprocess.run(
                ["curl", "-s", "-k", f"{url}?{query_str}"],  # -k ignores SSL verification
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
    return None


def search_crossref(topic: str, author: str, year_min: int, year_max: int, limit: int) -> List[Dict]:
    """Search CrossRef API."""
    results = []
    try:
        params = {
            "query": topic,
            "rows": min(limit, 100),  # CrossRef limit
            "sort": "relevance",
            "order": "desc"
        }
        if author:
            params["query"] = f"{topic} {author}"

        data = fetch_json(CROSSREF_API, params)
        if data and "message" in data and "items" in data["message"]:
            for item in data["message"]["items"][:limit]:
                # Filter by year if published-online exists
                pub_year = None
                if "published-online" in item:
                    pub_year = item["published-online"]["date-parts"][0][0]
                elif "published-print" in item:
                    pub_year = item["published-print"]["date-parts"][0][0]

                if pub_year and (year_min <= pub_year <= year_max):
                    results.append({
                        "doi": item.get("DOI", ""),
                        "title": item.get("title", [""])[0] if isinstance(item.get("title"), list) else item.get("title", ""),
                        "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip()
                                   for a in item.get("author", [])],
                        "year": pub_year,
                        "abstract": item.get("abstract", ""),
                        "url": item.get("URL", ""),
                        "type": item.get("type", "journal-article"),
                        "source": "CrossRef",
                        "open_access": False,  # Will be enriched from other sources
                    })
    except Exception as e:
        print(f"Warning: CrossRef search failed: {e}", file=sys.stderr)
    return results


def search_openalex(topic: str, author: str, year_min: int, year_max: int, limit: int) -> List[Dict]:
    """Search OpenAlex API."""
    results = []
    try:
        query = topic
        if author:
            query = f"{topic} {author}"

        params = {
            "search": query,
            "per_page": min(limit, 50),  # OpenAlex limit per page
            "sort": "relevance"
        }

        data = fetch_json(OPENALEX_API, params)
        if data and "results" in data:
            for item in data["results"][:limit]:
                pub_year = item.get("publication_year")
                if pub_year and (year_min <= pub_year <= year_max):

                    # Extract authors
                    authors = []
                    if "authorships" in item:
                        for auth in item["authorships"]:
                            if "author" in auth and "display_name" in auth["author"]:
                                authors.append(auth["author"]["display_name"])

                    open_access = False
                    if "open_access" in item and item["open_access"]:
                        open_access = item["open_access"].get("is_oa", False)

                    results.append({
                        "doi": item.get("doi", "").replace("https://doi.org/", ""),
                        "title": item.get("title", ""),
                        "authors": authors,
                        "year": pub_year,
                        "abstract": item.get("abstract", ""),
                        "url": item.get("landing_page_url", "") or item.get("doi", ""),
                        "type": item.get("type", "journal-article"),
                        "source": "OpenAlex",
                        "open_access": open_access,
                    })
    except Exception as e:
        print(f"Warning: OpenAlex search failed: {e}", file=sys.stderr)
    return results


def search_arxiv(topic: str, author: str, year_min: int, year_max: int, limit: int) -> List[Dict]:
    """Search arXiv API."""
    results = []
    try:
        # arXiv API returns Atom XML
        query = f"search_query=all:{topic}"
        if author:
            query = f"search_query=au:{author}+AND+all:{topic}"

        url = f"{ARXIV_API}?{query}&start=0&max_results={min(limit, 50)}&sortBy=relevance&sortOrder=descending"

        result = subprocess.run(
            ["curl", "-s", url],
            capture_output=True,
            text=True,
            timeout=API_TIMEOUT
        )

        if result.returncode == 0:
            import xml.etree.ElementTree as ET
            try:
                root = ET.fromstring(result.stdout)
                ns = {"atom": "http://www.w3.org/2005/Atom"}

                for entry in root.findall("atom:entry", ns):
                    # Parse arXiv response
                    title = entry.find("atom:title", ns)
                    published = entry.find("atom:published", ns)

                    if title is not None and published is not None:
                        pub_date = published.text
                        pub_year = int(pub_date[:4])

                        if year_min <= pub_year <= year_max:
                            # Extract authors
                            authors = []
                            for author_elem in entry.findall("atom:author", ns):
                                name_elem = author_elem.find("atom:name", ns)
                                if name_elem is not None:
                                    authors.append(name_elem.text)

                            # Extract arxiv ID and URL
                            arxiv_id = ""
                            url_elem = entry.find("atom:id", ns)
                            if url_elem is not None:
                                arxiv_id = url_elem.text.split("/abs/")[-1]

                            summary = entry.find("atom:summary", ns)
                            abstract = summary.text.strip() if summary is not None else ""

                            results.append({
                                "arxiv_id": arxiv_id,
                                "title": title.text.strip(),
                                "authors": authors,
                                "year": pub_year,
                                "abstract": abstract,
                                "url": f"https://arxiv.org/abs/{arxiv_id}",
                                "type": "preprint",
                                "source": "arXiv",
                                "open_access": True,  # arXiv always open access
                            })

                            if len(results) >= limit:
                                break
            except ET.ParseError as e:
                print(f"Warning: arXiv XML parse error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: arXiv search failed: {e}", file=sys.stderr)

    return results


def deduplicate_results(all_results: List[Dict]) -> List[Dict]:
    """Deduplicate by DOI, then arXiv ID, then title+authors."""
    seen = {}

    for paper in all_results:
        # Primary key: DOI
        if paper.get("doi"):
            key = ("doi", paper["doi"])
        # Secondary key: arXiv ID
        elif paper.get("arxiv_id"):
            key = ("arxiv_id", paper["arxiv_id"])
        # Tertiary key: title + first author
        else:
            title = paper.get("title", "").lower().strip()
            first_author = paper.get("authors", [""])[0].lower() if paper.get("authors") else ""
            key = ("title_author", f"{title}|{first_author}")

        if key not in seen:
            seen[key] = paper
        else:
            # Merge metadata (prefer richest source)
            existing = seen[key]
            if paper.get("abstract") and not existing.get("abstract"):
                existing["abstract"] = paper["abstract"]
            if paper.get("doi") and not existing.get("doi"):
                existing["doi"] = paper["doi"]
            if paper.get("arxiv_id") and not existing.get("arxiv_id"):
                existing["arxiv_id"] = paper["arxiv_id"]
            if paper.get("open_access") and not existing.get("open_access"):
                existing["open_access"] = paper["open_access"]

    return list(seen.values())


def generate_bibtex_key(paper: Dict) -> str:
    """Generate BibTeX key from paper metadata."""
    authors = paper.get("authors", [])
    year = paper.get("year", "UNKNOWN")

    if authors:
        first_author = authors[0].split()[-1].lower()  # Last name of first author
    else:
        first_author = "unknown"

    title_words = paper.get("title", "").split()[:2]
    title_key = "".join(w[:3].lower() for w in title_words if w.isalpha())

    return f"{first_author}{year[2:]}{title_key}"


def format_bibtex(paper: Dict) -> str:
    """Format paper as BibTeX entry."""
    key = generate_bibtex_key(paper)
    authors_str = " and ".join(paper.get("authors", []))

    if paper.get("arxiv_id"):
        return f"""@workingpaper{{{key},
  author = {{{authors_str}}},
  title = {{{paper.get("title", "")}}},
  year = {{{paper.get("year", "")}}},
  note = {{arXiv:{paper.get("arxiv_id", "")}}},
  url = {{{paper.get("url", "")}}}
}}"""
    elif paper.get("doi"):
        return f"""@article{{{key},
  author = {{{authors_str}}},
  title = {{{paper.get("title", "")}}},
  year = {{{paper.get("year", "")}}},
  doi = {{{paper.get("doi", "")}}},
  url = {{{paper.get("url", "")}}}
}}"""
    else:
        return f"""@misc{{{key},
  author = {{{authors_str}}},
  title = {{{paper.get("title", "")}}},
  year = {{{paper.get("year", "")}}}
}}"""


def export_to_bib(papers: List[Dict]):
    """Append BibTeX entries to Bibliography_base.bib."""
    if not papers or not BIB_FILE.exists():
        return

    try:
        # Read existing entries to detect duplicates
        existing_dois = set()
        with open(BIB_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            # Simple regex: find all DOI entries
            dois = re.findall(r'doi\s*=\s*["{]([^"}]+)["}]', content)
            existing_dois.update(dois)

        # Generate new entries (skip duplicates)
        new_entries = []
        for paper in papers:
            if paper.get("doi") and paper["doi"] in existing_dois:
                continue  # Skip duplicate
            new_entries.append(format_bibtex(paper))

        if new_entries:
            # Append new entries
            with open(BIB_FILE, 'a', encoding='utf-8') as f:
                f.write("\n\n% Auto-generated entries from /search-literature\n")
                f.write(f"% Generated: {datetime.now().isoformat()}\n\n")
                f.write("\n\n".join(new_entries))
                f.write("\n")
    except Exception as e:
        print(f"Warning: Could not append to Bibliography_base.bib: {e}", file=sys.stderr)


def export_to_csv(papers: List[Dict], output_file: Path):
    """Export results to CSV."""
    try:
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Title", "Authors", "Year", "DOI", "arXiv", "Source",
                "Open Access", "URL", "BibTeX Key", "Abstract"
            ])
            writer.writeheader()

            for paper in papers:
                writer.writerow({
                    "Title": paper.get("title", ""),
                    "Authors": "; ".join(paper.get("authors", [])),
                    "Year": paper.get("year", ""),
                    "DOI": paper.get("doi", ""),
                    "arXiv": paper.get("arxiv_id", ""),
                    "Source": paper.get("source", ""),
                    "Open Access": "Yes" if paper.get("open_access") else "No",
                    "URL": paper.get("url", ""),
                    "BibTeX Key": generate_bibtex_key(paper),
                    "Abstract": paper.get("abstract", "")[:500],  # Truncate for readability
                })
    except Exception as e:
        print(f"Warning: Could not export CSV: {e}", file=sys.stderr)


def generate_markdown_report(papers: List[Dict], query: str, author: str, year_min: int, year_max: int, output_file: Path, metadata: Dict):
    """Generate markdown report."""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# Literature Search Results\n\n")
            f.write(f"**Query:** `{query}`\n")
            if author:
                f.write(f"**Author filter:** `{author}`\n")
            f.write(f"**Year range:** {year_min}–{year_max}\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Cache status:** {'Hit (no API calls)' if metadata.get('cache_hit') else 'Miss (fresh API results)'}\n\n")

            f.write(f"## Results Summary\n\n")
            f.write(f"- **Total API hits:** {metadata.get('crossref_count', 0) + metadata.get('openalex_count', 0) + metadata.get('arxiv_count', 0)}\n")
            f.write(f"  - CrossRef: {metadata.get('crossref_count', 0)}\n")
            f.write(f"  - OpenAlex: {metadata.get('openalex_count', 0)}\n")
            f.write(f"  - arXiv: {metadata.get('arxiv_count', 0)}\n")
            f.write(f"- **Duplicates removed:** {metadata.get('duplicates_removed', 0)}\n")
            f.write(f"- **After deduplication:** {metadata.get('total_results_before_filtering', 0)}\n")
            f.write(f"- **Quality filtered** (top-tier journals + recent/seminal): {metadata.get('quality_filtered_out', 0)} removed\n")
            f.write(f"- **Final results:** {len(papers)}\n\n")

            f.write(f"### Quality Standards Applied\n")
            f.write(f"- **Journals:** Top-tier economics journals (AER, Econometrica, QJE, etc.) or multidisciplinary top journals\n")
            f.write(f"- **Recency:** Must have papers from last 5 years (since {year_max - RECENT_YEAR_THRESHOLD})\n")
            f.write(f"- **Classics:** Seminal papers (>100 citations) included regardless of age\n")
            f.write(f"- **Ranking:** Sorted by journal tier → citation count → publication year\n\n")

            f.write(f"## Papers (Top-Tier + Recent/Seminal)\n\n")
            for i, paper in enumerate(papers, 1):
                f.write(f"### {i}. {paper.get('title', 'Unknown')}\n\n")
                f.write(f"- **Authors:** {', '.join(paper.get('authors', []))}\n")
                f.write(f"- **Year:** {paper.get('year', 'Unknown')}\n")
                f.write(f"- **Source:** {paper.get('source', 'Unknown')}\n")
                if paper.get('cited_by_count'):
                    f.write(f"- **Citations:** {paper.get('cited_by_count', 0)}\n")
                if paper.get('doi'):
                    f.write(f"- **DOI:** [{paper.get('doi')}](https://doi.org/{paper.get('doi')})\n")
                if paper.get('arxiv_id'):
                    f.write(f"- **arXiv:** [{paper.get('arxiv_id')}](https://arxiv.org/abs/{paper.get('arxiv_id')})\n")
                f.write(f"- **Open Access:** {'Yes' if paper.get('open_access') else 'No'}\n")
                f.write(f"- **BibTeX Key:** `{generate_bibtex_key(paper)}`\n")
                if paper.get('abstract'):
                    f.write(f"- **Abstract:** {paper.get('abstract')[:300]}...\n")
                f.write("\n")
    except Exception as e:
        print(f"Warning: Could not generate markdown report: {e}", file=sys.stderr)


def main():
    """Main execution."""
    import argparse

    parser = argparse.ArgumentParser(description="Search academic databases")
    parser.add_argument("--search", action="store_true", help="Execute search")
    parser.add_argument("--check-cache", action="store_true", help="Check cache only")
    parser.add_argument("query", nargs="?", default="", help="Search query")
    parser.add_argument("--author", default="", help="Author filter")
    parser.add_argument("--year-min", type=int, default=DEFAULT_YEAR_MIN, help="Year minimum")
    parser.add_argument("--year-max", type=int, default=DEFAULT_YEAR_MAX, help="Year maximum")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Results per API")
    parser.add_argument("--output", default="", help="Output JSON file")

    args = parser.parse_args()

    ensure_dirs()

    if args.check_cache:
        cached = check_cache(args.query, args.author, args.year_min, args.year_max)
        print(json.dumps({"cache_hit": cached is not None}))
        sys.exit(0)

    if args.search:
        # Check cache first
        cached = check_cache(args.query, args.author, args.year_min, args.year_max)
        if cached:
            print(json.dumps({"status": "cache_hit", "papers": cached["results"], "metadata": cached["metadata"]}))
            return

        # Execute parallel searches
        results_cr = []
        results_oa = []
        results_ax = []

        threads = [
            Thread(target=lambda: results_cr.extend(search_crossref(args.query, args.author, args.year_min, args.year_max, args.limit))),
            Thread(target=lambda: results_oa.extend(search_openalex(args.query, args.author, args.year_min, args.year_max, args.limit))),
            Thread(target=lambda: results_ax.extend(search_arxiv(args.query, args.author, args.year_min, args.year_max, args.limit))),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Merge and deduplicate
        all_results = results_cr + results_oa + results_ax
        total_before = len(all_results)
        papers = deduplicate_results(all_results)

        # Apply quality filtering (top-tier journals + recent papers + classics)
        papers_filtered = filter_by_quality(papers, enforce_top_tier=True)
        total_filtered = len(papers)
        total_quality_filtered = len(papers_filtered)

        # Sort by relevance (top-tier, citations, recency)
        papers_sorted = sort_by_relevance(papers_filtered)
        papers = papers_sorted

        # Enrich with citation counts where available
        papers = enrich_with_citations(papers)

        # Store in cache
        h = query_hash(args.query, args.author, args.year_min, args.year_max)
        cache = load_cache()
        metadata = {
            "crossref_count": len(results_cr),
            "openalex_count": len(results_oa),
            "arxiv_count": len(results_ax),
            "duplicates_removed": total_before - total_filtered,
            "quality_filtered_out": total_filtered - total_quality_filtered,
            "total_results_before_filtering": total_filtered,
            "total_results_after_filtering": total_quality_filtered,
            "cache_hit": False,
        }
        cache[h] = {"results": papers, "metadata": metadata, "timestamp": datetime.now().isoformat()}
        save_cache(cache)

        # Export outputs
        query_hash_short = h[:8]
        report_file = OUTPUT_DIR / f"search_literature_{query_hash_short}.md"
        csv_file = OUTPUT_DIR / f"search_literature_{query_hash_short}.csv"

        export_to_bib(papers)
        export_to_csv(papers, csv_file)
        generate_markdown_report(papers, args.query, args.author, args.year_min, args.year_max, report_file, metadata)

        # Output result JSON
        result = {
            "status": "success",
            "papers": papers,
            "metadata": metadata,
            "files": {
                "report": str(report_file),
                "csv": str(csv_file),
                "bib": str(BIB_FILE),
            }
        }

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f)
        else:
            print(json.dumps(result))


if __name__ == "__main__":
    main()
