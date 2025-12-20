# Setup: Database-Driven URL Tracking

*Run this ONCE before starting batch scraping*

## Context
- Neon Project: `summer-grass-52363332`
- Currently: 135 episodes scraped, ~265 remaining
- Goal: Insert all episode URLs into DB so batches just query `WHERE scraped_at IS NULL`

## Task

1. **Map the full SOP site** to get all episode URLs:
   ```
   mcp__firecrawl__firecrawl_map on https://switchedonpop.com/episodes (limit 500)
   ```

2. **Get existing URLs** from database:
   ```sql
   SELECT url FROM episodes
   ```

3. **Find new URLs** (in map but not in DB)

4. **Insert new URLs** with minimal data (scraped_at = NULL):
   ```sql
   INSERT INTO episodes (show_id, url, scraped_at)
   VALUES (1, 'https://switchedonpop.com/episodes/...', NULL)
   ```

5. **Report:** "Setup complete. X new episode URLs added. Total unscraped: Y. Ready for batch scraping."

## After This

Use `scrape-episodes.md` prompt for batch scraping - it will query unscraped episodes automatically.
