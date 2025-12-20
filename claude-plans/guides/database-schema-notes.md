# Database Schema Notes

*Created: 2025-12-19*
*Neon Project: `summer-grass-52363332`*

## Current Schema

```
┌─────────────────────────────────────────────────────────────────┐
│ shows                                                           │
├─────────────────────────────────────────────────────────────────┤
│ id              INTEGER      PK                                 │
│ name            VARCHAR      NOT NULL                           │
│ slug            VARCHAR      NOT NULL, UNIQUE  ← good for URLs  │
│ website_url     VARCHAR                                         │
│ spotify_playlist_id VARCHAR                                     │
│ created_at      TIMESTAMP                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ 1:many
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ episodes                                                        │
├─────────────────────────────────────────────────────────────────┤
│ id              INTEGER      PK                                 │
│ show_id         INTEGER      FK → shows.id                      │
│ title           VARCHAR                                         │
│ url             VARCHAR      UNIQUE  ← prevents duplicates      │
│ episode_number  INTEGER                                         │
│ publish_date    DATE                                            │
│ scraped_at      TIMESTAMP    ← NULL = not yet scraped           │
│ raw_content     TEXT         ← full markdown from scrape        │
│ description_body TEXT        ← parsed content before songs      │
│ has_songs_discussed BOOLEAN                                     │
│ created_at      TIMESTAMP                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ 1:many
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ songs                                                           │
├─────────────────────────────────────────────────────────────────┤
│ id              INTEGER      PK                                 │
│ episode_id      INTEGER      FK → episodes.id                   │
│ title           VARCHAR      NOT NULL                           │
│ artist          VARCHAR      NOT NULL                           │
│ album           VARCHAR                                         │
│ spotify_track_id VARCHAR     ← NULL = not yet matched           │
│ spotify_match_confidence VARCHAR  ← HIGH/MEDIUM/LOW             │
│ added_to_playlist BOOLEAN                                       │
│ created_at      TIMESTAMP                                       │
└─────────────────────────────────────────────────────────────────┘
```

## Current Shows

| ID | Name | Slug | Spotify Playlist |
|----|------|------|------------------|
| 1 | Switched On Pop | sop | (to be added) |
| 2 | This American Life | tal | `3d7fjfrTTKvrl7VHv5JzIz` |

## Query Support by Use Case

| Query | Supported? | How |
|-------|-----------|-----|
| Get all songs for a show | ✅ | `JOIN episodes ON show_id = X` |
| Find unscraped episodes | ✅ | `WHERE scraped_at IS NULL` |
| Find unmatched songs | ✅ | `WHERE spotify_track_id IS NULL` |
| Prevent duplicate episodes | ✅ | `UNIQUE(url)` constraint |
| Prevent duplicate songs | ⚠️ | No constraint - handled in prompts |
| Get episodes by date range | ✅ | `WHERE publish_date BETWEEN...` |
| Full-text search on content | ⚠️ | Works but no index - slow at scale |
| Cross-show song stats | ✅ | Can query across all shows |

## Common Queries

```sql
-- Unscraped episodes for a show
SELECT id, url FROM episodes WHERE show_id = 1 AND scraped_at IS NULL LIMIT 20;

-- Unmatched songs for a show
SELECT s.id, s.title, s.artist, e.title as episode_title
FROM songs s
JOIN episodes e ON s.episode_id = e.id
WHERE e.show_id = 1 AND s.spotify_track_id IS NULL
LIMIT 150;

-- Episode count by show
SELECT s.name, COUNT(e.id) as episode_count
FROM shows s
LEFT JOIN episodes e ON e.show_id = s.id
GROUP BY s.id;

-- Songs per episode average
SELECT s.name,
       COUNT(DISTINCT e.id) as episodes,
       COUNT(so.id) as songs,
       ROUND(COUNT(so.id)::numeric / NULLIF(COUNT(DISTINCT e.id), 0), 1) as songs_per_ep
FROM shows s
JOIN episodes e ON e.show_id = s.id
LEFT JOIN songs so ON so.episode_id = e.id
GROUP BY s.id;

-- Episodes missing raw_content (for backfill)
SELECT id, url, title FROM episodes
WHERE show_id = 1 AND scraped_at IS NOT NULL AND raw_content IS NULL;
```

## Indexes

**Current indexes:**
- `shows_pkey` - id
- `shows_slug_key` - slug (unique)
- `episodes_pkey` - id
- `episodes_url_key` - url (unique)
- `songs_pkey` - id

**Recommended additions (when needed):**

```sql
-- For filtering episodes by show (add when querying gets slow)
CREATE INDEX idx_episodes_show_id ON episodes(show_id);

-- For finding unscraped/unmatched (add when backlog is large)
CREATE INDEX idx_episodes_scraped ON episodes(scraped_at) WHERE scraped_at IS NULL;
CREATE INDEX idx_songs_unmatched ON songs(spotify_track_id) WHERE spotify_track_id IS NULL;

-- For full-text search (add if you want keyword search without embeddings)
CREATE INDEX idx_episodes_description_gin ON episodes USING gin(to_tsvector('english', description_body));
```

Not needed at current scale (~1,300 episodes). Add when you add embeddings or if queries slow down.

## Known Issues / Decisions

### 1. Duplicate Songs Not Prevented
No `UNIQUE(episode_id, title, artist)` constraint. Same song could be inserted twice.

**Current mitigation:** Prompts don't re-scrape already-scraped episodes.
**Future option:** Add constraint if it becomes a problem.

### 2. Nullable Foreign Keys
`show_id` and `episode_id` are nullable. Not ideal but not breaking anything.

### 3. No Soft Deletes
If an episode is removed from source site, we don't track that. Not needed for current use case.

## Future Schema: AI Daily (Transcripts)

When adding shows with full transcripts (too long for single embedding):

```sql
-- Chunked content for long transcripts
CREATE TABLE content_chunks (
  id SERIAL PRIMARY KEY,
  episode_id INTEGER REFERENCES episodes(id),
  chunk_index INTEGER,
  content TEXT,
  token_count INTEGER,
  embedding vector(1536),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chunks_episode ON content_chunks(episode_id);
CREATE INDEX idx_chunks_embedding ON content_chunks USING ivfflat (embedding vector_cosine_ops);
```

Don't add until needed - YAGNI.

## Adding Embeddings (Future)

See `embedding-with-neon.md` for full guide. Quick version:

```sql
-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add column
ALTER TABLE episodes ADD COLUMN embedding vector(1536);

-- Create index
CREATE INDEX idx_episodes_embedding ON episodes USING ivfflat (embedding vector_cosine_ops);
```

## Data Estimates

| Show | Episodes | Songs | raw_content Size |
|------|----------|-------|------------------|
| SOP | ~453 | ~2,800 | ~4.5 MB |
| TAL | ~876 | ~1,500 est | ~8.7 MB |
| **Total** | ~1,329 | ~4,300 | ~15 MB |

Well within Neon free tier (512 MB storage limit).
