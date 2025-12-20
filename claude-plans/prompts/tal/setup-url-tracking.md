# TAL URL Discovery (Batch Process)

*Created 2025-12-19, Updated 2025-12-20*

## Context
- **Neon Project:** `summer-grass-52363332`
- **Show ID:** 2 (TAL)
- **TAL Spotify Playlist:** `3d7fjfrTTKvrl7VHv5JzIz`
- **Current progress:** 558 URLs (as of 2025-12-20)
- **Remaining:** ~319 episode numbers to check

## The Method

TAL has `/s/NUMBER` short URLs that redirect to real slugged URLs.
- Example: `/s/692` → `/692/the-show-of-delights`
- Firecrawl scrape returns the real URL in `metadata.url`

## Task: Batch URL Discovery

### 1. Get next batch of missing episode numbers

**Recommended batch size:** 50 episodes (faster than 10, manageable size)

```sql
WITH existing AS (
  SELECT DISTINCT CAST(REGEXP_REPLACE(url, '.*/([0-9]+)/.*', '\\1') AS INTEGER) as ep_num
  FROM episodes WHERE show_id = 2
),
all_nums AS (SELECT generate_series(1, 877) as num)
SELECT num FROM all_nums
WHERE num NOT IN (SELECT ep_num FROM existing)
ORDER BY num LIMIT 50
```

### 2. Scrape short URLs in parallel (10 at a time)

For a batch of 50 episodes, scrape in 5 sub-batches of 10 URLs each.

Use `mcp__firecrawl__firecrawl_scrape` for each URL:
```
url: "https://www.thisamericanlife.org/s/NUMBER"
formats: ["markdown"]
```

Extract the real URL from `metadata.url` in the response.

**If 404:** That episode number doesn't exist - skip it, don't insert.

**Note:** 10 parallel scrapes work reliably despite basic Firecrawl plan technically limiting to 5.

### 3. Insert discovered URLs

Use `mcp__neon__run_sql_transaction`:
```sql
INSERT INTO episodes (show_id, url, scraped_at) VALUES
(2, 'https://www.thisamericanlife.org/161/real-url-slug', NULL),
(2, 'https://www.thisamericanlife.org/163/another-slug', NULL)
ON CONFLICT (url) DO NOTHING
```

### 4. Report progress

```sql
SELECT COUNT(*) FROM episodes WHERE show_id = 2;
```

Report: "Batch complete. X URLs total. Y remaining to check."

### 5. Repeat

Continue with next batch of 50 missing numbers until done.

## Notes
- Some episode numbers are skipped (not all 1-877 exist)
- Some episodes have year variants (e.g., `/256/living-without-2004`)
- `ON CONFLICT (url) DO NOTHING` handles duplicates safely
- When done: "URL discovery complete. Ready for scrape-episodes.md"

## Discovery History (for reference)

| Date | Method | URLs Found | Credits |
|------|--------|------------|---------|
| 2025-12-19 | firecrawl_crawl from main site | 296 | ~400 |
| 2025-12-19 | firecrawl_map (limit 1000) | 57 new | 1 |
| 2025-12-20 | /s/NUMBER pattern (batches 1-8, 10/batch) | 85 | 1 per ep |
| 2025-12-20 | /s/NUMBER pattern (batch 9, 50/batch) | 120+ | 1 per ep |

### Batch Process Evolution

**Initial approach (batches 1-8):**
- Batch size: 10 episodes
- Parallel scraping: 5 URLs at a time
- Effective but slow with ~369 episodes remaining

**Optimized approach (batch 9+):**
- Batch size: 50 episodes
- Parallel scraping: 10 URLs at a time (5 sub-batches of 10)
- 5x faster, proven reliable despite basic plan limits

### What doesn't work (don't try these):
- Archive pages (`/archive?year=YYYY`) - JS-rendered, no links
- Direct `/NUMBER` URLs - return 404
- Sitemap.xml - doesn't exist
- RSS feed - only ~15 recent episodes
