---
name: search-literature
description: Search academic databases with parallel queries, local caching, BibTeX auto-export, and CSV table generation
argument-hint: "[topic] [optional: author:LastName year:YYYY-YYYY limit:N]"
allowed-tools: ["Read", "Bash", "Write", "Glob"]
---

# Search Literature

Search academic databases (CrossRef, OpenAlex, arXiv) for papers matching your query.

**Input:** `$ARGUMENTS`

Required:
- **topic** — keyword(s) to search (required)

Optional:
- **author:LastName** — filter by author surname
- **year:YYYY-YYYY** — date range (default: 2015-2026)
- **limit:N** — results per database (default: 30, max: 100)

**Example:** `/search-literature "AI and productivity" author:Agrawal year:2018-2026 limit:50`

---

## How It Works

```
Parse arguments
     ↓
Check cache for exact query match
     ├→ Cache hit? Return cached results (no API calls)
     └→ Cache miss? Proceed to API searches
     ↓
Parallel API calls (simultaneous):
  • CrossRef API (largest scholarly index)
  • OpenAlex API (modern, with OA metadata)
  • arXiv API (preprints + working papers)
     ↓
Aggregate results from all sources
     ↓
Deduplicate by: DOI → arXiv ID → title+authors
     ↓
Generate outputs:
  • Markdown report (quality_reports/)
  • CSV table (quality_reports/)
  • BibTeX auto-append (Bibliography_base.bib)
     ↓
Update cache (for future queries)
     ↓
Return summary + file paths to user
```

---

## Steps (Detailed Workflow)

### 1. Parse Arguments
Extract from `$ARGUMENTS`:
- `TOPIC` (required, e.g., "AI and productivity")
- `AUTHOR` (optional, e.g., "Agrawal" → author filtering)
- `YEAR_MIN`, `YEAR_MAX` (optional, default: 2015–2026)
- `LIMIT` (optional, default: 30 results/database)

### 2. Check Cache
Call Python script: `python3 .claude/skills/search-literature/search_api.py --check-cache "$TOPIC" "$AUTHOR" "$YEAR_MIN" "$YEAR_MAX"`

**If cache hit:**
- Return cached results immediately (0 API calls)
- Skip to Step 6 (Generate Outputs)
- Report: "Returning cached results from [date]"

**If cache miss:** Continue to Step 3

### 3. Execute Parallel API Searches
Call Python script: `python3 .claude/skills/search-literature/search_api.py --search "$TOPIC" "$AUTHOR" "$YEAR_MIN" "$YEAR_MAX" "$LIMIT" --output /tmp/search_results.json`

Three API calls happen in parallel (threaded):
1. **CrossRef API** — DOI registry, most comprehensive
2. **OpenAlex API** — Modern papers, open access metadata
3. **arXiv API** — Preprints, working papers

### 4. Deduplicate Results
The Python script automatically:
- Groups papers by: DOI (primary) → arXiv ID (secondary) → title+authors (tertiary)
- Removes duplicates, keeps richest metadata
- Merges metadata from multiple sources (e.g., DOI from CrossRef + OA status from OpenAlex)

### 5. Format & Export Outputs
Generate three output files:

**A. Markdown Report**
- File: `quality_reports/search_literature_[query_hash].md`
- Contains: 20-50 papers with metadata, BibTeX keys, open access status
- Sortable metadata for manual curation

**B. CSV Table**
- File: `quality_reports/search_literature_[query_hash].csv`
- Columns: Title | Authors | Year | DOI | Source | OpenAccess | URL | BibTeXKey | Abstract
- Importable to Excel/Google Sheets for filtering, sorting, ranking

**C. BibTeX Auto-Append**
- Target: `Bibliography_base.bib`
- Action: Automatically append new BibTeX entries (checks for duplicates by DOI)
- User can merge/resolve manually if needed

### 6. Update Cache
Store search results locally:
- File: `~/.claude/state/search_cache.json`
- Include: query parameters, results, timestamp, API hit counts
- Purpose: Avoid redundant API calls for identical future queries

### 7. Return Summary to User
Print:
- Number of results from each API
- Duplicates removed
- Cache hit/miss status
- File paths to report, CSV, cached results
- Suggested next actions (open CSV, review abstracts, filter for open access)

---

## Output Locations

| Output | Path | Format | Notes |
|--------|------|--------|-------|
| Main report | `quality_reports/search_literature_[query_hash].md` | Markdown | Filtered results, quality stats |
| Spreadsheet | `quality_reports/search_literature_[query_hash].csv` | CSV (UTF-8) | Sortable, quality-ranked |
| Bibliography | `Bibliography_base.bib` | BibTeX | Auto-appended, top-tier only |
| Cache | `~/.claude/state/search_cache.json` | JSON | Local, gitignored, auto-created |

## Quality Standards

All results are automatically filtered for academic rigor:

### Journal Tier Requirements
✅ **Economics Top 5:** American Economic Review, Econometrica, Journal of Political Economy, Quarterly Journal of Economics, Review of Economic Studies

✅ **Economics Top-tier:** Journal of Econometrics, International Economic Review, Journal of Development Economics, Journal of Labor Economics, Quarterly Journal of Economics, Management Science, etc.

✅ **Multidisciplinary Top:** Nature, Science, PNAS, Nature Machine Intelligence, Science Advances

✅ **Other criteria:** High citation count (>50 for arXiv preprints) accepted as proxy for quality

### Publication Year Strategy
- **Recent threshold:** Last 5 years (2021–2026)
- **Must-have:** At least papers from recent period
- **Classics:** Seminal works (>100 citations) included regardless of age
- **Balance:** Mix of cutting-edge and foundational references

### Sorting & Ranking
Papers are automatically ranked by:
1. Journal tier (top-tier first)
2. Citation count (most cited first)
3. Publication year (recent first)

---

## Features & Advantages

| Feature | Benefit |
|---------|---------|
| **Parallel API calls** | Fast (typically 1-3 seconds for 90 papers) |
| **Local caching** | Repeated searches cost 0 API calls |
| **Deduplication** | One paper = one entry (from best source) |
| **Auto-export BibTeX** | New entries go directly to project bibliography |
| **CSV output** | Filter, sort, rank in spreadsheet before importing |
| **Metadata enrichment** | Combines DOI, arXiv, abstract, OA status from multiple APIs |
| **Graceful degradation** | If one API fails, others succeed; return partial results |
| **Offline fallback** | No internet? Use cached results + local Grep search |

---

## Important Notes

- **API Keys:** None required. All APIs are free public endpoints.
- **Rate Limits:** Implemented backoff; user is informed if rate limit hit.
- **Citation Accuracy:** BibTeX checked for valid formatting before append.
- **Duplicate Detection:** Only by DOI (most reliable). Manual review recommended.
- **Cache Expiry:** No automatic expiry; user can rm ~/.claude/state/search_cache.json to force refresh.
- **Large Results:** If >100 papers, only first 100 returned; increase `limit:N` to fetch more.
- **Author Filtering:** Exact match on surname (e.g., `author:Chen` finds Chen et al.).
- **Year Range:** Inclusive (e.g., `year:2020-2023` includes 2020 and 2023).

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No results returned | Broaden query (remove author/year filters), check spelling |
| "API rate limit exceeded" | Retry in 30 seconds, or use cached results |
| BibTeX keys conflict | Check Bibliography_base.bib for duplicates, edit manually if needed |
| CSV won't open in Excel | Delete cache and re-run; check UTF-8 encoding |
| Slow performance | First run takes 1-3 sec (API calls); subsequent identical queries instant (cache) |
| "No internet connection" | Returns cached results if available; offline Grep search on local files |

---

## Example Usage

```bash
# Search for papers on AI and investment, authored by Chen, 2020-2026
/search-literature "AI investment home bias" author:Chen year:2020-2026

# Search for productivity economics, get up to 50 results per API
/search-literature "productivity economics" limit:50 year:2015-2026

# Quick search, use defaults (30 results, 2015-2026)
/search-literature "home bias"

# Search for arXiv preprints only (implicit, but arXiv will have many)
/search-literature "distributed systems" year:2023-2026 limit:100
```

---

## Next Steps (After Skill Invocation)

1. **Review CSV:** Open `search_literature_*.csv` in Excel/Google Sheets
2. **Filter by relevance:** Mark/rank papers for your needs
3. **Check Open Access:** Use "OpenAccess" column to find free PDFs
4. **Verify BibTeX:** Check that Bibliography_base.bib was updated
5. **Resolve conflicts:** If duplicate keys detected, edit .bib manually
6. **Download PDFs:** Use URLs in CSV to access preprints/journals
7. **Update citations in paper:** Use BibTeX keys to cite in LaTeX/Quarto
