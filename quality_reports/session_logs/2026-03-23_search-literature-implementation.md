# Session: Implement /search-literature Skill (API-Driven Literature Search)

**Date:** 2026-03-23
**Status:** IN PROGRESS
**Plan Reference:** `quality_reports/plans/2026-03-23_search-literature-skill.md`

---

## Goal

Create a new `/search-literature` skill that:
- Searches academic databases (CrossRef, OpenAlex, arXiv) in parallel
- Implements local caching to avoid duplicate API calls
- Auto-exports BibTeX entries to Bibliography_base.bib
- Generates CSV tables for spreadsheet analysis
- Handles API failures gracefully with fallback

---

## Context

User prioritized this over continuing theoretical analysis because they want:
1. **Immediate literature search capability** — no need to manually browse academic databases
2. **Integrated workflow** — results automatically appear in project bibliography
3. **Efficient reuse** — cache prevents redundant API calls for repeated queries
4. **Analysis flexibility** — CSV export enables filtering and ranking in Excel

---

## Implementation Plan

| Step | File | Purpose | Dependency |
|------|------|---------|------------|
| 1 | `.claude/skills/search-literature/SKILL.md` | Skill definition + workflow specification | None |
| 2 | `.claude/skills/search-literature/search_api.py` | Python API client (CrossRef, OpenAlex, arXiv) | Step 1 |
| 3 | `.claude/skills/search-literature/README.md` | Setup docs + API reference | Step 2 |
| 4 | `.claude/state/search_cache.json` | Empty cache (auto-created on first use) | Step 2 |
| 5 | Test: Manual API calls | Verify each API works independently | Step 2 |
| 6 | Test: End-to-end workflow | Invoke skill, check outputs | Steps 1-4 |
| 7 | Test: Cache + export | Verify caching and auto-append to bib | Step 6 |

---

## Key Design Decisions

1. **Python over Bash:** Already allowed in settings.json, cleaner code, easier to maintain
2. **Parallel API calls:** Faster (1-2 threads), all three APIs queried simultaneously
3. **Cache location:** `~/.claude/state/search_cache.json` (local, gitignored, survives sessions)
4. **BibTeX merge strategy:** Append-only with duplicate detection (by DOI)
5. **CSV export:** Full results table, sortable in Excel/Sheets
6. **Error handling:** Cascade (try CrossRef → OpenAlex → arXiv, accumulate results)

---

## Progress Tracking

- [x] SKILL.md created (Step 1) — 2026-03-23 11:42
- [x] search_api.py created (Step 2) — 2026-03-23 11:45
- [x] README.md created (Step 3) — 2026-03-23 11:48
- [x] **Quality standards added** — 2026-03-23 12:15
  - Top-tier journal filtering (Top 5 + economics leaders)
  - Recent paper requirement (2021-2026) with exception for classics
  - Citation-based ranking (>100 for seminal works)
  - Automatic sorting by journal tier → citations → recency
- [ ] API testing complete (Step 5)
- [ ] End-to-end testing complete (Step 6)
- [ ] Cache/export testing complete (Step 7)
- [ ] Quality review passed (score ≥80/100)
- [ ] Feature ready for use

---

## Key Improvements (User-Specified)

**User requirements integrated:**
1. ✅ Top 5 economics journals (AER, Econometrica, JPolE, QJE, RES)
2. ✅ Field-specific top journals (other leading economics journals)
3. ✅ Year-aware filtering: recent 5 years + classics (>100 citations)
4. ✅ Auto-ranking by journal quality → citation count → publication year

**Implementation:**
- Added `TOP_TIER_JOURNALS` constant (30+ leading journals)
- Added `filter_by_quality()` function with strict mode
- Added `sort_by_relevance()` function (3-tier ranking)
- Metadata now shows: duplicates removed, quality-filtered count
- Markdown report displays quality standards applied

---

## Known Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| API rate limits | Use backoff + inform user, don't crash |
| Large result sets | Paginate/limit to 50 per database |
| Duplicate BibTeX keys in .bib | Check existing keys before append |
| CSV encoding issues | Use UTF-8 with BOM for Excel compatibility |
| Cache grows unbounded | Include metadata (timestamp); user can clear if needed |

---

## Next Actions

1. Create SKILL.md with full workflow description
2. Implement search_api.py with all four functions (CrossRef, OpenAlex, arXiv, cache)
3. Test manually with sample query
4. Verify outputs (BibTeX valid, CSV readable, cache working)
5. Run comprehensive verification checklist
