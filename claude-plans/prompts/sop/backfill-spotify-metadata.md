# Backfill: Spotify Metadata (Album, Artist, Title)

*Created 2025-12-20*

## Context
- Neon Project: `summer-grass-52363332`
- Show ID: 1 (SOP)
- **~449 songs** already matched but missing `album`, `spotify_title`, `spotify_artist`

## When to Run
Run this AFTER we finish the main batch matching, or during a pause if needed.

Batches 1-10 were processed before we added these columns. They have:
- ✅ `spotify_track_id`
- ✅ `spotify_match_confidence`
- ✅ `spotify_web_url` (added later, already backfilled)
- ✅ `spotify_popularity` (added later, already backfilled)
- ❌ `album` (NULL)
- ❌ `spotify_title` (NULL)
- ❌ `spotify_artist` (NULL)

## Task

1. **Query songs needing backfill** (50 at a time):
   ```sql
   SELECT id, title, artist FROM songs
   WHERE episode_id IN (SELECT id FROM episodes WHERE show_id = 1)
     AND spotify_track_id IS NOT NULL
     AND spotify_title IS NULL
   ORDER BY id
   LIMIT 50
   ```

2. **Run batch search:**
   ```
   mcp__spotify__batch_search_tracks with songs array
   ```

3. **Update with metadata:**
   ```sql
   UPDATE songs AS s SET
     album = v.album,
     spotify_title = v.spotify_title,
     spotify_artist = v.spotify_artist
   FROM (VALUES
     (62, 'Album Name', 'Spotify Song Title', 'Spotify Artist Name'),
     (63, 'Album 2', 'Song 2', 'Artist 2'),
     ...
   ) AS v(id, album, spotify_title, spotify_artist)
   WHERE s.id = v.id
   ```

4. **Report progress:**
   ```
   Backfill batch complete. Updated 50 songs.
   Remaining songs needing backfill: X
   ```

## Notes
- Only backfill songs with `spotify_track_id IS NOT NULL` (already matched)
- `NOT_FOUND` songs won't have metadata to backfill
- Run in batches of 50 to avoid rate limits
- Lower priority than new matching - run when you have spare cycles
