# Search Literature Skill

**Version:** 1.0
**Status:** Ready for testing
**Date Created:** 2026-03-23

---

## Overview

`/search-literature` is a Python-based skill that searches academic databases (CrossRef, OpenAlex, arXiv) in parallel, with local caching, automatic BibTeX export, and CSV table generation.

### What It Does

- **Searches:** Three major academic databases simultaneously
- **Caches:** Results locally to avoid redundant API calls
- **Deduplicates:** Merges results from multiple sources by DOI/arXiv ID
- **Exports:** Generates Markdown report, CSV spreadsheet, and auto-appends BibTeX entries
- **Handles failures:** Graceful degradation if one API fails

### What You Get

1. **Markdown report** — All papers with metadata, authors, abstracts, links
2. **CSV table** — Sortable in Excel/Google Sheets for filtering and ranking
3. **Updated Bibliography** — New BibTeX entries automatically added to `Bibliography_base.bib`
4. **Local cache** — Same query again costs 0 API calls

---

## Quality Standards

All search results are **automatically filtered for academic rigor**. You only get top-tier papers that meet specific criteria.

### What Gets Included

✅ **Top-Tier Economics Journals:**
- Big 5: AER, Econometrica, JPolE, QJE, RES
- Other top-tier: JEconometrics, JE Theory, IER, EconJ, JDE, JLE, JME, JPE, RAND JE, RES
- Applied: Management Science, Marketing Science, Operations Research

✅ **Multidisciplinary Leaders:**
- Nature, Science, PNAS, Nature Machine Intelligence, Science Advances

✅ **Recent Papers (2021–2026):**
- Ensures your bibliography is current

✅ **Classic/Seminal Works:**
- Papers with >100 citations included even if older
- Provides foundational grounding

### What Gets Filtered Out

❌ **Low-rank journals** — Local, regional, or specialized outlets
❌ **Outdated papers** — Pre-2021 with <100 citations
❌ **Uncited preprints** — arXiv papers with few citations

### Ranking Strategy

Papers appear in order of:
1. **Journal Quality** — Top 5 > other top-tier > multidisciplinary
2. **Citation Impact** — Higher cited papers first
3. **Recency** — Newer published papers first

### Example Output

**Before filtering:** 127 results from CrossRef, OpenAlex, arXiv
**After quality filter:** 18 papers from top journals (2021–2026 + classics)
**Your bibliography:** Ready to use, peer-reviewed by journal ranking

### Requirements

- Python 3.7+
- `requests` library (optional; will fall back to `curl`)
- Internet connection (first search only; cached results work offline)

### Install Python Requests (Optional)

If `requests` not available, the script falls back to `curl` (pre-installed on macOS/Linux).

```bash
pip install requests  # Optional; not required
```

### Directories

The skill automatically creates:
- `~/.claude/state/search_cache.json` — Local search cache
- `quality_reports/search_literature_*.md` — Reports
- `quality_reports/search_literature_*.csv` — Spreadsheets

---

## Usage

### Basic Syntax

```bash
/search-literature "[topic]" [optional: author:Name year:YYYY-YYYY limit:N]
```

### Examples

**Simple search:**
```bash
/search-literature "AI and productivity"
```

**With author filter:**
```bash
/search-literature "AI investment" author:Chen
```

**Specific year range and higher result limit:**
```bash
/search-literature "home bias" year:2015-2026 limit:50
```

**Multiple filters:**
```bash
/search-literature "machine learning economics" author:Agrawal year:2018-2026 limit:100
```

### Parse Rules

- **Required:** Topic (first argument, can be multiple words)
- **Optional filters (any order):**
  - `author:LastName` — Filter by author surname (exact match)
  - `year:YYYY-YYYY` — Date range (inclusive)
  - `limit:N` — Max results per API (default: 30, max: 100)

---

## API Sources

### CrossRef
- **Coverage:** 140M+ journal articles, conference papers
- **Strengths:** Most comprehensive, excellent metadata
- **Rate limit:** ~100k requests/day (no registration needed)

### OpenAlex
- **Coverage:** 200M+ papers (journals + preprints)
- **Strengths:** Modern, includes open access status, citation counts
- **Rate limit:** Unlimited with backoff

### arXiv
- **Coverage:** 2.5M+ preprints (physics, CS, econ, math, statistic, etc.)
- **Strengths:** Preprints, working papers, discipline-specific
- **Rate limit:** 3 requests/second (handled internally)

All APIs are **public and free**. No API keys required.

---

## Caching

### How Caching Works

- **First search:** API calls to all three databases (1-3 seconds)
- **Identical query:** Cache hit detected, returns results instantly (0 API calls)
- **Cache key:** Hash of `[topic|author|year_min|year_max]`
- **Cache location:** `~/.claude/state/search_cache.json` (local to your machine, gitignored)

### Clear Cache

To force a fresh search (ignore cache):

```bash
rm ~/.claude/state/search_cache.json
/search-literature "your query"  # Will fetch fresh results
```

### Cache Contents

```json
{
  "query_hash_abc123": {
    "results": [ /* Array of deduplicated papers */ ],
    "metadata": {
      "crossref_count": 25,
      "openalex_count": 18,
      "arxiv_count": 5,
      "duplicates_removed": 8
    },
    "timestamp": "2026-03-23T10:30:00Z"
  }
}
```

---

## Output Files

### 1. Markdown Report

**Location:** `quality_reports/search_literature_[hash].md`

Contains:
- Full list of papers with metadata
- Authors, year, DOI/arXiv links
- Abstract snippets
- Open access status
- BibTeX keys for citation
- Statistics (total hits, duplicates removed, OA count)

### 2. CSV Spreadsheet

**Location:** `quality_reports/search_literature_[hash].csv`

Columns:
| Column | Content | Use |
|--------|---------|-----|
| Title | Paper title | Scanning |
| Authors | All authors | Citation |
| Year | Publication year | Filtering |
| DOI | Digital Object Identifier | Citation |
| arXiv | arXiv preprint ID | Citation |
| Source | CrossRef / OpenAlex / arXiv | Origin tracking |
| Open Access | Yes / No | Filter for free PDFs |
| URL | Link to paper/preprint | Download |
| BibTeX Key | Generated citation key | LaTeX citation |
| Abstract | First 500 chars | Quick reading |

**How to use:**
1. Download CSV file
2. Open in Excel or Google Sheets
3. Sort/filter by Open Access, Year, Source
4. Copy URLs to download PDFs
5. Use BibTeX keys in your LaTeX/Quarto document

### 3. Bibliography Update

**Location:** `Bibliography_base.bib` (appended)

All new papers are automatically added as BibTeX entries:
```bibtex
@article{chen26ai,
  author = {Chen, Shaojian and ...},
  title = {AI and Investment Home Bias},
  year = {2026},
  doi = {10.1234/example.doi},
  url = {https://doi.org/10.1234/example.doi}
}
```

**Note:** Check for duplicate DOIs before committing. Manual review recommended if importing large batches.

---

## Duplicate Detection & Merging

The skill deduplicates by:

1. **DOI (primary)** — Most reliable; groups papers across databases
2. **arXiv ID (secondary)** — For preprints
3. **Title + first author (tertiary)** — As fallback

When duplicates found, the skill merges metadata:
- Keeps DOI from CrossRef
- Adds open access status from OpenAlex
- Combines author lists if different sources have different author counts

**Result:** One paper entry, enriched with best available metadata.

---

## BibTeX Auto-Export

### What Happens

1. After search completes, script checks `Bibliography_base.bib` for existing DOIs
2. Skips papers already in bibliography (duplicate detection)
3. Appends new papers in valid BibTeX format
4. Adds timestamp comment marking auto-generated section

### Example

```bibtex
% Auto-generated entries from /search-literature
% Generated: 2026-03-23T10:30:45.123456

@article{chen26ai,
  author = {Chen, Shaojian},
  title = {Can Artificial Intelligence Mitigate Home Bias in Investment?},
  year = {2026},
  doi = {10.2139/ssrn.4567890},
  url = {https://ssrn.com/abstract=4567890}
}
```

### In Your Paper

```latex
\cite{chen26ai}  % Generates citation automatically
```

---

## Troubleshooting

### No Results Returned

**Causes:**
- Misspelled query term
- Extremely narrow date range
- Very specific author filter

**Solutions:**
- Broaden query (use simpler terms)
- Remove year filter: `/search-literature "home bias" author:Chen`
- Check author spelling: `author:Poterba` not `author:Pote`

### "API Rate Limit Exceeded"

**Causes:**
- arXiv enforces 3 requests/second (rare, but can happen with many parallel searches)

**Solutions:**
- Results still returned from other databases; check CSV
- Retry in 30 seconds
- Use cache: `/search-literature "same query again"` returns instant cached results

### BibTeX Keys Conflict

**Causes:**
- Script auto-generates keys like `chen26ai` (first author + year + title words)
- Collisions possible if multiple papers by same author, same year

**Solutions:**
- Check `Bibliography_base.bib` for conflicts
- Manually rename duplicate keys to make them unique
- Use DOI as backup: `@article{doi:10.1234/example,}`

### CSV Won't Open in Excel

**Causes:**
- Encoding issue (UTF-8 vs ANSI)

**Solutions:**
- Re-run skill: `/search-literature "your query"` (generates fresh CSV)
- Try opening in Google Sheets (better Unicode support)
- Check that file isn't corrupted: open in text editor first

### Slow Performance (First Run Takes 10+ Seconds)

**Causes:**
- API timeouts (API servers are slow that day)
- Network latency

**Solutions:**
- Retry: `/search-literature "same query"` (cached, instant)
- Check internet connection
- Try simpler query (fewer parameters reduce time)

### Offline (No Internet)

**Causes:**
- Network disconnected

**Solutions:**
- Offline searches still work: uses local cache + Grep search in Bibliography_base.bib
- Returns data from previous searches
- Graceful degradation: "No internet detected; using cached results"

---

## Advanced Usage

### Batch Searching

Run multiple searches in sequence:

```bash
/search-literature "AI productivity" author:Agrawal year:2018-2026
/search-literature "machine learning labor" author:Acemoglu year:2015-2026
/search-literature "automation economic impact" year:2010-2026 limit:100
```

Each search caches independently; no duplicate APIs calls.

### Exporting for Reading

1. Run search: `/search-literature "your topic"`
2. Open CSV: `open quality_reports/search_literature_*.csv`
3. Filter for open access: `Open Access` column = "Yes"
4. Copy URLs, download PDFs
5. View Markdown report for summaries

### Integrating with LaTeX

After BibTeX auto-export:

```latex
\documentclass{article}
\usepackage{natbib}

\begin{document}

\cite{chen26ai, acemoglu20auto}  % Uses auto-exported keys

\bibliography{Bibliography_base}  % Loads updated file

\end{document}
```

Run `bibtex` as usual; new citations appear automatically.

---

## Implementation Details

### Dependencies

- **Required:** Python 3.7+, curl (for arXiv API)
- **Optional:** `requests` library (falls back to curl if not available)
- **Built-ins:** json, csv, threading, urllib, pathlib, re, subprocess

### Python Script Location

`.claude/skills/search-literature/search_api.py`

Invoked automatically by SKILL.md workflow; not meant for direct command-line use.

### Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| First search | 1-3 sec | All three APIs queried in parallel |
| Cache hit | <100 ms | Instant retrieval from disk |
| BibTeX export | <1 sec | Deduplication + formatting |
| CSV generation | <1 sec | Per-paper row creation |

### Testing

Manual testing completed on:
- CrossRef API: ✓ Direct call, bulk results
- OpenAlex API: ✓ Direct call, OA metadata
- arXiv API: ✓ XML parsing, preprint extraction
- Caching: ✓ Hit/miss detection
- Deduplication: ✓ DOI, arXiv ID merging
- BibTeX export: ✓ Append, duplicate detection
- CSV export: ✓ UTF-8 encoding, Excel compatibility

---

## Future Enhancements

Potential improvements:
- [ ] Add Semantic Scholar API (AI-powered recommendations)
- [ ] Add SSRN API (working papers)
- [ ] Add full-text search (where available)
- [ ] Filter by open access on input
- [ ] Batch export from Markdown to PDF
- [ ] Automatic PDF download
- [ ] Tag/annotation system
- [ ] Search history + favorites

---

## Support

For issues or questions:
1. Check **Troubleshooting** section above
2. Review `SKILL.md` for workflow details
3. Check cache file: `~/.claude/state/search_cache.json`
4. Run manual API test: `python3 .claude/skills/search-literature/search_api.py --help`

---

## License

Part of the Claude Code academic workflow. Free to use, modify, and distribute.
