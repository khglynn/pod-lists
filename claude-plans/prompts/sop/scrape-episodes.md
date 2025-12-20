# Batch: Scrape Episodes (20/batch)

*Use after running setup-url-tracking.md*
*Updated 2025-12-19: Now saves raw_content and description_body*

## Context
- Neon Project: `summer-grass-52363332`
- Show ID: 1 (SOP)
- Episodes table has URLs with `scraped_at = NULL` for unscraped

## Task

1. **Query 20 unscraped episodes:**
   ```sql
   SELECT id, url FROM episodes WHERE show_id = 1 AND scraped_at IS NULL LIMIT 20
   ```

2. **Scrape in parallel** (5 at a time):
   ```
   mcp__firecrawl__firecrawl_scrape with formats: ["markdown"]
   ```

3. **Parse each episode:**
   - Episode number: Look for "EPISODE XXX" in markdown
   - Title: First H1 heading
   - Date: Look for date near top (format varies)
   - Songs: Extract from "Songs Discussed" section (format: "Artist – Title")
   - Description body: Everything between title and "Songs Discussed" section

4. **Update episode record** (NOW INCLUDES raw_content and description_body):
   ```sql
   UPDATE episodes SET
     title = 'Episode Title',
     publish_date = 'YYYY-MM-DD',
     episode_number = XXX,
     has_songs_discussed = true/false,
     raw_content = $body$FULL MARKDOWN HERE$body$,
     description_body = $body$BODY TEXT BEFORE SONGS SECTION$body$,
     scraped_at = NOW()
   WHERE id = X
   ```

5. **Insert songs** (escape apostrophes with ''):
   ```sql
   INSERT INTO songs (episode_id, title, artist) VALUES (X, 'Song Title', 'Artist Name')
   ```

6. **Report and pause:**
   ```
   Batch complete. Scraped 20 episodes, added X songs.
   Total: Y episodes scraped, Z songs.
   Remaining unscraped: W episodes.
   Ready for compact.
   ```

## Notes
- Some episodes have no "Songs Discussed" section - set has_songs_discussed = false
- Escape apostrophes: `Don't` becomes `Don''t`
- For raw_content: use PostgreSQL dollar-quoting `$body$content$body$` to handle special chars
- If scrape fails (404), mark as scraped with has_songs_discussed = false

## Common Errors

### MCP Parameter Error with run_sql_transaction
**Error:** `Invalid arguments for tool run_sql_transaction: Expected object, received string at path ["params"]`

**Cause:** The Neon MCP expects parameters wrapped in a `params` object, but the nested JSON structure can cause parsing issues with the `run_sql_transaction` tool when handling complex SQL with dollar-quoting.

**Solution:** Use individual `run_sql` calls instead of `run_sql_transaction` for batch updates:
```javascript
// ❌ Don't use run_sql_transaction with complex SQL
mcp__neon__run_sql_transaction with multiple UPDATE/INSERT statements

// ✅ Do use individual run_sql calls
mcp__neon__run_sql for each UPDATE
mcp__neon__run_sql for each INSERT
```

**Example:**
```javascript
// Episode update
mcp__neon__run_sql({"params": {"projectId": "...", "sql": "UPDATE episodes SET ..."}})
// Songs insert
mcp__neon__run_sql({"params": {"projectId": "...", "sql": "INSERT INTO songs ..."}})
```
