# Plan: Implement `/search-literature` Skill with API Integration

**Status:** DRAFT
**Date:** 2026-03-23
**Phase:** 1 (Exploration Complete) → Phase 2 (Design) → Phase 5 (Ready for Approval)

---

## Context

**Why this matters:**
- You need programmatic access to academic literature databases
- Current `/lit-review` skill synthesizes but doesn't systematically search
- Multiple free APIs exist: CrossRef, OpenAlex, Semantic Scholar, arXiv
- This enables rapid hypothesis validation and citation discovery

**Current state:**
- Project has 22 skills; only `/lit-review` uses external tools (WebSearch, WebFetch)
- Settings.json already permits: `Bash(python3 *)` — we can use Python for API calls
- No custom Python backend needed—just skill orchestration

**Goal:**
Create `/search-literature` skill that:
- Searches multiple academic databases in parallel
- Returns structured results (title, authors, year, abstract, DOI, URL)
- Generates BibTeX entries
- Saves report to `quality_reports/search_literature_[sanitized_query].md`
- Works offline gracefully (cached/local fallback)

---

## Proposed Implementation Strategy

### **High-Level Architecture**

```
User: `/search-literature "AI investment home bias" author:Chen year:2020-2026`
     ↓
Skill: Parse arguments (topic, author, year range, filters)
     ↓
Execute parallel searches:
  • CrossRef API (DOI registry, most comprehensive)
  • OpenAlex API (recent papers, open access links)
  • arXiv API (preprints, working papers)
     ↓
Deduplicate & merge results
     ↓
Generate structured report + BibTeX
     ↓
Save to quality_reports/search_literature_[query_hash].md
     ↓
Return summary + file path
```

### **Step 1: Create SKILL.md File**

**File:** `.claude/skills/search-literature/SKILL.md`

```yaml
---
name: search-literature
description: Search academic databases with structured query support (keywords, author, year)
argument-hint: "[topic] [optional: author:Name year:2020-2026 limit:50]"
allowed-tools: ["Read", "Bash", "Write", "Glob"]
---

# Search Literature

Search academic databases for papers matching query criteria.

**Input:** `$ARGUMENTS`
- **Required:** Search topic (e.g., "AI investment home bias")
- **Optional:** `author:LastName`, `year:YYYY-YYYY`, `limit:N` (default: 30)

---

## Steps

1. **Parse arguments** into:
   - `QUERY` (topic)
   - `AUTHOR` (filter by author, if provided)
   - `YEAR_MIN` / `YEAR_MAX` (date range, default: 2015-2026)
   - `LIMIT` (max results per database, default: 30)

2. **Execute parallel API searches** via Python script:
   - CrossRef: DOI registry (most comprehensive)
   - OpenAlex: Recent papers + open access metadata
   - arXiv: Preprints + working papers

3. **Deduplicate** by: DOI → arXiv ID → title+authors check

4. **Sort by relevance:** Relevance score + publication year (recency)

5. **Format output:**
   - Markdown report with structured results
   - BibTeX entries (properly formatted)
   - Metadata (search date, query, hit count)

6. **Save report** to `quality_reports/search_literature_[query_hash].md`

---

## Output Format

**Primary report:** `quality_reports/search_literature_[query_hash].md`
```markdown
# Literature Search Results

**Query:** "[topic]"
**Filters:** author=?, year=?, limit=?
**Date:** [YYYY-MM-DD]
**Cache hit:** Yes/No
**Total unique hits:** N

## Results (sorted by relevance + recency)

### 1. [Author et al. (Year)] — [Title]
- **DOI:** [url]
- **Authors:** Full list
- **Year:** YYYY
- **Abstract:** [First 200 chars]
- **Source:** CrossRef / OpenAlex / arXiv
- **OpenAccess:** Yes/No
- **URL:** [preprint/published]
- **BibTeX key:** [auto-generated key]

[Repeat for N results]

## BibTeX Entries (auto-exported to Bibliography_base.bib)

\`\`\`bibtex
@article{...}
@workingpaper{...}
\`\`\`

## CSV Table

File: `quality_reports/search_literature_[query_hash].csv`
Columns: Title, Authors, Year, DOI, Source, OpenAccess, URL, Abstract, BibTeXKey

## Statistics
- CrossRef hits: N
- OpenAlex hits: N (O/A: M)
- arXiv hits: N
- Duplicates removed: K
- Final unique papers: N
- Cache source: Fresh API / Cached (from YYYY-MM-DD)

## Automated Actions Completed
- ✓ BibTeX entries appended to Bibliography_base.bib
- ✓ CSV table exported for spreadsheet analysis
- ✓ Results cached for future queries

## Next Steps
1. Review CSV in spreadsheet: [path]
2. Filter by relevance and read abstracts
3. Download PDFs for selected papers
4. Update Bibliography_base.bib with custom keys if needed
```

**Secondary output files:**
- `quality_reports/search_literature_[query_hash].csv` — Spreadsheet-ready table
- `Bibliography_base.bib` — Updated with new BibTeX entries (appended)

---

## Step 2: Create Python API Client Script with Caching

**File:** `.claude/skills/search-literature/search_api.py`

**Responsibilities:**
- Call CrossRef API (free, no auth, ~100k papers/day)
- Call OpenAlex API (free, no auth, modern database)
- Call arXiv API (free, no auth, preprints)
- Handle rate limits & timeouts gracefully
- **Implement local caching** to avoid duplicate API queries
- Deduplicate results by DOI/arXiv ID
- Format BibTeX entries
- Export to Bibliography_base.bib (append mode)
- Generate CSV table for spreadsheet import
- Return JSON for skill to process

**Key functions:**
```python
# Caching layer
load_cache(cache_file)  # Load from ~/.claude/state/search_cache.json
save_cache(cache_dict)
check_cache_hit(query_hash)

# API searches
search_crossref(query, author, year_min, year_max, limit)
search_openalex(query, author, year_min, year_max, limit)
search_arxiv(query, author, year_min, year_max, limit)

# Post-processing
deduplicate_results(all_results)
format_bibtex(paper_dict)
export_to_bib(results, append_to_file)  # Append to Bibliography_base.bib
generate_csv(results, output_file)      # Create CSV table

# Main
main(args)  # CLI wrapper
```

**Cache structure:**
```json
{
  "query_hash_123abc": {
    "query": "AI investment home bias",
    "timestamp": "2026-03-23T10:30:00Z",
    "results": [
      // Array of deduplicated papers
    ],
    "metadata": {
      "crossref_count": 25,
      "openalex_count": 18,
      "arxiv_count": 5,
      "duplicates_removed": 8
    }
  }
}
```

**Exit gracefully if:**
- Cache hit: Use cached results (skip API calls)
- API timeout: Try other APIs, return partial results
- Rate limit: Inform user and suggest retry after N seconds
- No internet: Fall back to cache + Grep search in local files

---

## Step 3: Integration with Skill Workflow

**How the skill executes:**

1. **Parse `$ARGUMENTS`** using Bash parameter expansion
2. **Call Python script:**
   ```bash
   python3 .claude/skills/search-literature/search_api.py \
     --query "$QUERY" \
     --author "$AUTHOR" \
     --year "$YEAR_MIN-$YEAR_MAX" \
     --limit "$LIMIT" \
     --output search_api_output.json
   ```
3. **Process JSON output** (Read output_file with bash)
4. **Generate Markdown report** using Write tool
5. **Save to quality_reports/**
6. **Report back to user**

---

## Step 4: Add to settings.json (if needed)

**Current state:** `Bash(python3 *)` is already allowed ✓

**May need to add:**
```json
{
  "permissions": {
    "allow": [
      ...existing...
      "Bash(curl *)",        // For raw API calls if we use curl
      "Bash(wget *)",        // Alternative to curl
      "Bash(timeout *)"      // For API timeouts
    ]
  }
}
```

**Check:** Do these already exist? (They might—curl/wget are common)

---

## Step 5: Register Skill (Automatic)

Once files are created at:
- `.claude/skills/search-literature/SKILL.md`
- `.claude/skills/search-literature/search_api.py`

Claude Code automatically discovers it. User can invoke with:
```
/search-literature "AI and productivity" author:Agrawal year:2015-2026
```

---

## Files to Create

| File | Purpose | Size Estimate |
|------|---------|---------------|
| `.claude/skills/search-literature/SKILL.md` | Skill definition + workflow | 200-250 lines |
| `.claude/skills/search-literature/search_api.py` | API client (CrossRef, OpenAlex, arXiv) + caching + CSV export | 600-700 lines |
| `.claude/skills/search-literature/README.md` | Setup + API docs + cache management | 150 lines |
| `.claude/state/search_cache.json` | Local cache storage (gitignored) | Dynamic |

---

## Files to Modify

| File | Change | Reason |
|------|--------|--------|
| `.claude/settings.json` | Add curl/wget to allowed bash if missing | Enable fallback HTTP methods |
| (none required for core functionality) | | Python already allowed |

---

## API Integration Details

### CrossRef API
- **Endpoint:** `https://api.crossref.org/works`
- **Authentication:** None (public API)
- **Rate limit:** ~100k calls/day (no token required)
- **Response:** JSON with title, authors, DOI, URL, abstract
- **Query syntax:** `query.title=keyword` OR `query.author=name`
- **Reliability:** Excellent (95%+ uptime)

### OpenAlex API
- **Endpoint:** `https://api.openalex.org/works`
- **Authentication:** None
- **Rate limit:** Unlimited (but polite rate limiting recommended)
- **Response:** Very rich metadata (OA status, citations, topics, authors)
- **Query syntax:** `title.search=keyword` OR `author.search=name`
- **Reliability:** Excellent (maintained by NIH-funded project)

### arXiv API
- **Endpoint:** `http://export.arxiv.org/api/query`
- **Authentication:** None
- **Rate limit:** 3 requests/second (enforced with delays)
- **Response:** Atom XML (parse to structured data)
- **Query syntax:** `all:keyword` OR `au:author_name`
- **Reliability:** Excellent (decades old)

**Python libraries:**
- `requests` (HTTP calls) — may already installed in Claude Code env
- `xml.etree.ElementTree` (parse arXiv XML) — built-in
- `json` (parse API responses) — built-in
- `urllib.parse` (URL encoding) — built-in

---

## Verification Checklist

### Phase 1: API Testing
- [ ] Test CrossRef API call manually (curl/Python)
- [ ] Test OpenAlex API call manually
- [ ] Test arXiv API call manually
- [ ] Verify deduplication logic works
- [ ] Test BibTeX formatting for edge cases

### Phase 2: Caching & Export
- [ ] Cache file is created at `.claude/state/search_cache.json`
- [ ] Cache hit detection works (same query returns cached results)
- [ ] BibTeX appending to Bibliography_base.bib works correctly
- [ ] CSV export generates valid spreadsheet
- [ ] CSV columns are correct: Title, Authors, Year, DOI, Source, OpenAccess, URL, Abstract, BibTeXKey

### Phase 3: Skill Integration
- [ ] SKILL.md syntax is valid YAML frontmatter
- [ ] Skill is discoverable (appears in `/list-skills` conceptually)
- [ ] Python script runs without errors
- [ ] Output directory `quality_reports/` exists and is writable
- [ ] Cache directory `.claude/state/` exists and is writable

### Phase 4: End-to-End Test
- [ ] User invokes `/search-literature "test query"`
- [ ] Skill parses arguments correctly
- [ ] Python API client runs and fetches results
- [ ] Report is generated and saved to `quality_reports/`
- [ ] BibTeX entries are valid **and appended to Bibliography_base.bib**
- [ ] CSV file is created and contains all results
- [ ] User can open CSV in Excel/Google Sheets without errors

### Phase 5: Cache Testing
- [ ] Run same query again → cache hit detected → no API calls
- [ ] Run different query → cache miss, new API calls
- [ ] Cache metadata is updated correctly
- [ ] Timestamp and statistics are accurate

### Phase 6: Fallback Testing
- [ ] Timeout handling works (graceful degradation)
- [ ] Rate limiting doesn't break user experience
- [ ] Cache fallback works (if offline)
- [ ] Partial results returned if one API fails

---

## Success Criteria

✅ Skill is executable with `/search-literature` command
✅ Returns 20-50 unique results from multiple databases (deduped)
✅ Generates valid BibTeX entries and **auto-appends to Bibliography_base.bib**
✅ Report saved to `quality_reports/search_literature_*.md`
✅ **CSV table exported to `quality_reports/search_literature_*.csv`**
✅ **Local caching prevents duplicate API calls** (cache hit detected correctly)
✅ Handles API failures gracefully (timeout, rate limit, returns partial results)
✅ Offline fallback works (uses cache + searches Bibliography_base.bib)
✅ Output is formatted consistently for easy use
✅ **Auto-export to Bibliography_base.bib works without user intervention**
✅ Performance: <5 seconds for typical query (3 parallel API calls)
✅ Cache management: users can clear cache and refresh if needed

---

## Design Rationale

**Why this approach?**

1. **Minimal dependencies:** Python built-ins + requests (no exotic packages)
2. **Parallel execution:** 3 API calls happen simultaneously (speedup)
3. **Graceful degradation:** Works offline, falls back to local search
4. **No auth required:** All three APIs are free public endpoints
5. **Modular:** Easy to add more databases later (Semantic Scholar, SSRN, etc.)
6. **Skill pattern:** Fits existing `/lit-review` model but specialized for search
7. **User integration:** Natural command `/search-literature "query"`
8. **Output format:** Markdown + BibTeX matches project standards

---

## Known Limitations & Trade-Offs

| Limitation | Reason | Workaround |
|-----------|--------|-----------|
| No full-text search | APIs don't expose full text | Abstract search is sufficient |
| arXiv limited to preprints | By design (not peer-reviewed db) | CrossRef/OpenAlex cover journals |
| ~30 sec max timeout | API response time varies | User can retry; cached results help |
| No fuzzy author matching | Exact match needed | User specifies full lastname |
| Rate limit: 3 req/sec on arXiv | API policy | Parallelize across threads carefully |

---

## Timeline

- **Step 1 (SKILL.md design):** 30 minutes
- **Step 2 (Python API client + caching + CSV export):** 120 minutes
  - API integration: 40 min
  - Caching layer: 25 min
  - CSV export: 20 min
  - BibTeX auto-append: 25 min
  - Error handling: 10 min
- **Step 3 (Integration testing):** 90 minutes
- **Step 4 (Verification + fallback + cache testing):** 60 minutes
- **Total:** ~5 hours for full implementation (vs. 4 hours estimated before)

---

## Next Actions

1. **Get user approval** on this plan
2. **Create SKILL.md** with full workflow
3. **Implement search_api.py** with CrossRef → OpenAlex → arXiv
4. **Test end-to-end** with sample query
5. **Document API rate limits & fallback** in README
6. **Make skill discoverable** (auto-registration)
7. **Update MEMORY.md** with [LEARN:skills] entry for future devel
