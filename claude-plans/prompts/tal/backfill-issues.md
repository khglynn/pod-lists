# TAL: Backfill Issues

*Created 2025-12-20*
*Use AFTER initial scraping is complete*

## Purpose

Fix episodes with scrape failures or data quality issues discovered during the main scraping process.

## 1. Find Failed Scrapes (404s, timeouts, errors)

Query for episodes marked as scraped but missing core data:

```sql
SELECT id, url, episode_number, scraped_at
FROM episodes
WHERE show_id = 2
  AND scraped_at IS NOT NULL
  AND (title IS NULL OR publish_date IS NULL OR raw_content IS NULL)
ORDER BY id;
```

**Examples from Batch 1:**
- Episode 553: `/309/leaving-the-fold` (404)
- Episode 554: `/31/guitar` (404)
- Episode 555: `/311/the-nuclear-option` (404)
- Episode 556: `/312/this-american-life` (404)

**Fix approach:**
1. Try `/s/NUMBER` pattern (e.g., `/s/309`)
2. Search TAL archive manually
3. If truly doesn't exist, leave as-is (marked scraped, no data)

## 2. Fix Description Bodies with Markdown

Query for episodes with markdown syntax still in description_body:

```sql
SELECT id, episode_number,
  LENGTH(description_body) as length,
  LEFT(description_body, 100) as preview
FROM episodes
WHERE show_id = 2
  AND description_body LIKE '%[%](%' -- contains markdown links
  OR description_body LIKE '%##%'    -- contains markdown headers
  OR description_body LIKE '%**%'    -- contains bold
ORDER BY id;
```

**Clean description format:**
- Remove all markdown syntax (links, images, headers, bold)
- Keep act titles as plain text prefixes (e.g., "Prologue:", "Act One:")
- Remove "By" contributor sections
- Stop before "Related" section
- Keep only narrative text

**Example of clean description:**
```
Prologue: Paul was a cop. One night he was pulling second shift when he had a perfectly good idea: He'd stretch out in the back seat and take a little nap during his break...

Luck Of The Irish: It was two months into the tour. Katie Else and the rest of the Riverdance cast had been performing eight shows a week...
```

## 3. Backfill Process

**For failed scrapes:**
```sql
-- Get episodes to retry
SELECT id, url FROM episodes
WHERE show_id = 2
  AND scraped_at IS NOT NULL
  AND title IS NULL
LIMIT 20;
```
Then re-scrape using alternate URL methods.

**For description cleanup:**
```sql
-- Get episodes needing cleanup
SELECT id, url, raw_content FROM episodes
WHERE show_id = 2
  AND description_body LIKE '%[%](%'
LIMIT 20;
```
Then:
1. Extract description from `raw_content`
2. Clean markdown syntax
3. Update with clean description:
```sql
UPDATE episodes
SET description_body = 'CLEAN TEXT HERE'
WHERE id = X;
```

## Notes

- Run queries AFTER main scrape is complete
- Batch size: 20 episodes at a time
- Priority: Failed scrapes first, then description cleanup
- Keep raw_content unchanged (it's the source of truth)
