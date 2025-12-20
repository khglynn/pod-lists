# Batch: Match TAL Songs to Spotify (150/batch)

*Use after episode scraping is complete*
*Created 2025-12-19, Updated 2025-12-20*

## Context
- Neon Project: `summer-grass-52363332`
- Show ID: 2 (TAL)
- Spotify Playlist: `3d7fjfrTTKvrl7VHv5JzIz` (https://open.spotify.com/playlist/3d7fjfrTTKvrl7VHv5JzIz)

## Task

1. **Query unmatched songs:**
   ```sql
   SELECT s.id, s.title, s.artist, e.title as episode_title
   FROM songs s
   JOIN episodes e ON s.episode_id = e.id
   WHERE e.show_id = 2 AND s.spotify_track_id IS NULL
   LIMIT 150
   ```

2. **Batch search Spotify:**
   ```
   mcp__spotify__batch_search_tracks with songs array and delay_seconds: 0.2
   ```

3. **Process results by confidence:**
   - HIGH (90%+): Add to playlist automatically
   - MEDIUM (70-89%): Log for review
   - LOW (<70%): Skip
   - NOT_FOUND: Skip

4. **Add HIGH matches to playlist:**
   ```
   mcp__spotify__add_tracks_to_playlist
   ```

5. **Update database:**
   ```sql
   UPDATE songs SET
     spotify_track_id = 'spotify:track:xxx',
     spotify_match_confidence = 'HIGH',
     added_to_playlist = true
   WHERE id = X
   ```

6. **Report:**
   ```
   Batch complete.
   - HIGH matches added: X
   - MEDIUM (needs review): Y
   - LOW/NOT_FOUND skipped: Z
   Remaining unmatched: W songs.
   ```

## Notes
- TAL songs are often older/classic tracks - may have lower match rates
- Some songs may be obscure or no longer on Spotify
- MEDIUM matches can be manually reviewed in a future pass
