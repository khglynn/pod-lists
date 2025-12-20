# Backfill: Episode Descriptions

*Run AFTER completing the main scrape pass*
*Created 2025-12-19, Updated 2025-12-20*

## Context
- Neon Project: `summer-grass-52363332`
- Show ID: 1 (SOP)
- **188 episodes** need description_body refilled (NULL or clipped <75 chars)

## When to Run
Run this AFTER:
1. All episodes are scraped (scraped_at IS NOT NULL for all)
2. Songs are extracted and matched to Spotify
3. You have time for a cleanup pass

This is lower priority than TAL or song matching.

## Task

1. **Query episodes needing refill** (NULL or short descriptions):
   ```sql
   SELECT id, url, title FROM episodes
   WHERE show_id = 1
     AND (description_body IS NULL OR LENGTH(description_body) < 75)
   LIMIT 20
   ```

2. **Re-scrape each episode** (5 at a time):
   ```
   mcp__firecrawl__firecrawl_scrape with formats: ["markdown"]
   ```

3. **Parse description body:**
   - Everything between the title/date and "Songs Discussed" section
   - If no "Songs Discussed", use everything until footer/navigation
   - Strip markdown formatting artifacts (image links, nav links, etc.)

4. **Update episode record:**
   ```sql
   UPDATE episodes SET
     raw_content = $body$FULL MARKDOWN$body$,
     description_body = $body$PARSED BODY TEXT$body$
   WHERE id = X
   ```

5. **Report progress:**
   ```
   Backfill batch complete. Updated 20 episodes.
   Remaining to refill: X episodes.
   ```

## Why 75 Characters?

We analyzed the description_body lengths and found:
- **<60 chars**: Definitely clipped (e.g., Porter Robinson at 59 chars missing 4 paragraphs)
- **60-75 chars**: Mix of clipped and short-but-complete
- **75+ chars**: Almost all read as complete descriptions

75 chars is slightly aggressive but ensures we catch clipped descriptions without doing a manual review. Over-refilling a few complete short ones is acceptable.

## Notes
- This does NOT re-extract songs (already done)
- Use PostgreSQL dollar-quoting for content with apostrophes
- Lower priority than new scraping - run when you have spare cycles
