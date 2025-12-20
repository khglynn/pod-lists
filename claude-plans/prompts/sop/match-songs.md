# Batch: Match Songs to Spotify (150/batch)

*Use after episode scraping is complete (or in parallel)*

## Context
- Neon Project: `summer-grass-52363332`
- Playlist ID: `0cEVeX4pdHf5RJOiTRzgxX`
- Songs table: id, episode_id, title, artist, spotify_track_id (NULL = unmatched)

## Task

1. **Query 150 unmatched songs:**
   ```sql
   SELECT id, title, artist FROM songs
   WHERE spotify_track_id IS NULL
   ORDER BY id LIMIT 150
   ```

2. **Format for batch search:**
   ```json
   [{"title": "Song Name", "artist": "Artist Name"}, ...]
   ```

3. **Call batch search:**
   ```
   mcp__spotify__batch_search_tracks with songs array
   ```

4. **Process results:**
   - HIGH confidence (90%+): Add to playlist + update DB
   - MEDIUM/LOW: Skip for now (future human review)

5. **Add HIGH matches to playlist:**
   ```
   mcp__spotify__add_tracks_to_playlist
   - playlist_id: "0cEVeX4pdHf5RJOiTRzgxX"
   - track_uris: ["spotify:track:xxx", ...]
   ```

6. **Update songs table:**
   ```sql
   UPDATE songs SET spotify_track_id = 'spotify:track:xxx' WHERE id = Y
   ```

7. **Report and pause:**
   ```
   Batch complete. Processed songs ID X to Y.
   - HIGH matches: A (added to playlist)
   - MEDIUM: B (skipped)
   - LOW: C (skipped)
   - NOT FOUND: D
   Remaining unmatched: Z songs.
   Ready for compact.
   ```

## Notes
- batch_search_tracks returns categorized results (HIGH/MEDIUM/LOW/NOT_FOUND)
- Only add HIGH confidence matches automatically
- Track URIs look like: spotify:track:4iV5W9uYEdYUVa79Axb7Rh
