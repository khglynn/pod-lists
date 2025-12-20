# Batch: Spotify Song Matching

*Created 2025-12-20*

## Context
- Neon Project: `summer-grass-52363332`
- Show ID: 1 (SOP)
- Spotify MCP: `~/DevKev/personal/spotify-bulk-actions-mcp/`

## Confidence Levels

| Level | Threshold | Action |
|-------|-----------|--------|
| HIGH | ≥90% | Auto-save, sync to playlist |
| MEDIUM | 70-89% | Auto-save, sync to playlist |
| LOW | <70% | Save track ID but flag for review |
| NOT_FOUND | No results | Mark confidence, leave track ID NULL |

## Batch Matching Process

**Workflow:** Process 250 songs total (5 sub-batches of 50) before pausing for update.

### Sub-Batch (50 songs)

1. **Query unmatched songs** (50 at a time):
   ```sql
   SELECT id, title, artist FROM songs
   WHERE episode_id IN (SELECT id FROM episodes WHERE show_id = 1)
     AND spotify_track_id IS NULL AND spotify_match_confidence IS NULL
   ORDER BY id
   LIMIT 50
   ```

2. **Format for batch search:**
   ```json
   [{"title": "Song Title", "artist": "Artist Name"}, ...]
   ```

3. **Run batch search:**
   ```
   mcp__spotify__batch_search_tracks with songs array
   ```

4. **Process results:**

   **Bulk update (HIGH + MEDIUM + LOW):**
   ```sql
   UPDATE songs AS s SET
     spotify_track_id = v.track_id,
     spotify_match_confidence = v.confidence,
     album = v.album,
     spotify_web_url = v.url,
     spotify_popularity = v.popularity,
     spotify_title = v.spotify_title,
     spotify_artist = v.spotify_artist
   FROM (VALUES
     (123, 'track_id_1', 'HIGH', 'Album Name', 'https://open.spotify.com/track/track_id_1', 85, 'Spotify Song Title', 'Spotify Artist Name'),
     (124, 'track_id_2', 'MEDIUM', 'Album Name 2', 'https://open.spotify.com/track/track_id_2', 72, 'Song Title 2', 'Artist 2'),
     ...
   ) AS v(id, track_id, confidence, album, url, popularity, spotify_title, spotify_artist)
   WHERE s.id = v.id
   ```

   **NOT_FOUND:**
   ```sql
   UPDATE songs SET spotify_match_confidence = 'NOT_FOUND'
   WHERE id IN (126, 127, 128, ...)
   ```

5. **Repeat** for 5 sub-batches (250 songs total)

6. **Pause and report progress:**
   ```
   Batch complete. 250 songs processed.
   HIGH: X, MEDIUM: X, LOW: X, NOT_FOUND: X
   Total matched: Y / Z songs remaining
   ```

### Quality Check Query

Compare scraped vs Spotify data to catch mismatches:
```sql
SELECT id, title, spotify_title, artist, spotify_artist, spotify_match_confidence, spotify_web_url
FROM songs
WHERE spotify_track_id IS NOT NULL
  AND (title != spotify_title OR artist != spotify_artist)
ORDER BY spotify_match_confidence DESC
```

## Syncing to Spotify Playlist

Only sync confirmed matches:
```sql
SELECT spotify_track_id FROM songs
WHERE episode_id IN (SELECT id FROM episodes WHERE show_id = 1)
  AND spotify_track_id IS NOT NULL
  AND spotify_match_confidence IN ('HIGH', 'MEDIUM', 'MANUAL')
  AND added_to_playlist = false
```

After adding to playlist:
```sql
UPDATE songs SET added_to_playlist = true
WHERE id IN (...)
```

## Manual Review Query

For Kevin's end-of-project review:
```sql
SELECT
  id,
  title,
  spotify_title,
  artist,
  spotify_artist,
  album,
  spotify_track_id,
  spotify_match_confidence,
  spotify_popularity,
  spotify_web_url
FROM songs
WHERE episode_id IN (SELECT id FROM episodes WHERE show_id = 1)
  AND spotify_match_confidence IN ('LOW', 'NOT_FOUND')
ORDER BY spotify_match_confidence, artist, title
```

After manual fix:
```sql
UPDATE songs SET
  spotify_track_id = 'CORRECT_TRACK_ID',
  spotify_title = 'Spotify Title',
  spotify_artist = 'Spotify Artist',
  album = 'Album Name',
  spotify_web_url = 'https://open.spotify.com/track/CORRECT_TRACK_ID',
  spotify_popularity = 75,
  spotify_match_confidence = 'MANUAL'
WHERE id = X
```

## Common Issues

| Issue | Solution |
|-------|----------|
| "ft." in artist | Try without featuring artist |
| Classical pieces | Often have long formal titles, may need manual |
| Removed from Spotify | Gary Glitter, some older tracks - mark NOT_FOUND |
| Wrong attribution | Source data error - needs manual correction |

## Test Batch Results (2025-12-20)

25 songs tested:
- HIGH: 14 (56%)
- MEDIUM: 4 (16%)
- LOW: 3 (12%)
- NOT_FOUND: 4 (16%)

**Expected match rate: ~72% on first pass**
