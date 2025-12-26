# Batch: Scrape TAL Episodes (60/batch)

*Use after URL discovery is complete*
*Created 2025-12-19, Updated 2025-12-20*

## Context
- Neon Project: `summer-grass-52363332`
- Show ID: 2 (TAL)
- Episodes table has URLs with `scraped_at = NULL` for unscraped
- **Current progress:** 444 scraped, 438 remaining, 529 songs (as of 2025-12-20)

## Task

### 1. Query next 10 unscraped episodes (NO OFFSET!)
```sql
SELECT id, url FROM episodes WHERE show_id = 2 AND scraped_at IS NULL ORDER BY id LIMIT 10
```

**CRITICAL:** Always use `LIMIT 10` with **NO OFFSET**. The pool of unscraped episodes shrinks after each sub-batch, so using OFFSET will skip episodes!

### 2. Scrape 10 episodes in parallel
```
mcp__firecrawl__firecrawl_scrape
url: "https://www.thisamericanlife.org/XXX/slug"
formats: ["markdown"]
```

### 3. Parse each episode from response

| Field | Source | Example |
|-------|--------|---------|
| Title | `metadata.og:title` → remove ` - This American Life` | "New Beginnings" |
| Episode # | Extract from URL `/(\d+)/` | 1 |
| Date | `metadata.article:published_time` → first 10 chars | "1995-11-17" |
| Raw Content | Full `markdown` field from response | (entire page) |
| Description Body | Clean text from acts (see step 3.5) | (narrative only) |
| Songs | Find `## Song:` headers in markdown | see below |

### 3.5. Extract clean description_body

**Remove all markdown syntax:**
- Strip markdown links: `[text](url)` → `text`
- Remove images: `![](url)` → (delete)
- Remove headers: `## Act Title` → `Act Title:`
- Remove bold/italic: `**text**`, `_text_` → `text`
- Remove "By" contributor sections entirely
- Stop before "## Related" section

**Format:**
```
Prologue: [narrative text here]

Act Title: [narrative text here]

Another Act: [narrative text here]
```

**Example output:**
```
Prologue: Paul was a cop. One night he was pulling second shift when he had a perfectly good idea...

Luck Of The Irish: It was two months into the tour. Katie Else and the rest of the Riverdance cast had been performing eight shows a week...
```

### 4. Parse song formats

**Format 1 - With link:**
```markdown
## Song:

["Destination Moon" by Dinah Washington](https://itunes.apple.com/...)
```
→ title: "Destination Moon", artist: "Dinah Washington"

**Format 2 - Plain text:**
```markdown
## Song:

"(Uh-Oh) Get Out of the Car" by The Treniers
```
→ title: "(Uh-Oh) Get Out of the Car", artist: "The Treniers"

**Format 3 - With "performed by" note:**
```markdown
## Song:

"Who By Fire" by Leonard Cohen, performed by House of Love
```
→ title: "Who By Fire", artist: "Leonard Cohen" (use original artist for Spotify matching)

### 5. Update database per sub-batch (transaction)

Use `mcp__neon__run_sql_transaction` with array of statements:

```sql
-- Episode updates (escape apostrophes with '')
UPDATE episodes SET
  title = 'Valentine''s Day ''99',
  publish_date = '1999-02-12',
  episode_number = 122,
  has_songs_discussed = true,
  raw_content = 'Full markdown from response (escape apostrophes)',
  description_body = 'Content before ## Related section (escape apostrophes)',
  scraped_at = NOW()
WHERE id = 469

-- Song inserts (batch all songs from sub-batch)
INSERT INTO songs (episode_id, title, artist) VALUES
(457, 'Destination Moon', 'Dinah Washington'),
(457, '(Uh-Oh) Get Out of the Car', 'The Treniers'),
(459, 'Greyhound Theme in E-Minor', 'Ian Lynam and Paul Iannott')
```

**Important:** Use single quotes for content, escaping all apostrophes as `''`. For very long content, you can optionally use PostgreSQL dollar-quoting: `$body$content$body$`

### 6. After 35 episodes, report progress
```sql
SELECT COUNT(*) as scraped FROM episodes WHERE show_id = 2 AND scraped_at IS NOT NULL;
SELECT COUNT(*) as unscraped FROM episodes WHERE show_id = 2 AND scraped_at IS NULL;
SELECT COUNT(*) as total_songs FROM songs s JOIN episodes e ON s.episode_id = e.id WHERE e.show_id = 2;
```

Report: "Batch complete. Scraped 35 episodes, added X songs. Total: Y scraped, Z remaining."

## Notes

- **Songs are sparse:** TAL averages ~1.4 songs/episode (Batches 1-3: 86 songs from 60 episodes)
- **Many episodes have 0 songs** - set `has_songs_discussed = false`
- **Escape apostrophes:** `Don't` → `Don''t` in SQL strings
- **Use original artist** for "performed by" songs (better Spotify matching)
- **If 404 occurs:** mark as scraped with `has_songs_discussed = false`
- **Saving raw_content:** We're already loading the full markdown into context, so save it to the database (no extra cost)
