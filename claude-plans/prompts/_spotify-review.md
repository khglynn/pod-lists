# LLM Review: LOW and NOT_FOUND Songs

*Created 2025-12-20 - Shared across all shows*

## When to Use

After the matching script runs, use this prompt to review songs that need human judgment.

## Query Songs for Review

```sql
SELECT
  s.id,
  s.title,
  s.artist,
  s.spotify_title,
  s.spotify_artist,
  s.spotify_track_id,
  s.spotify_match_confidence,
  s.spotify_web_url
FROM songs s
JOIN episodes e ON s.episode_id = e.id
WHERE e.show_id = 1  -- Change for different shows
  AND s.spotify_match_confidence IN ('LOW', 'NOT_FOUND')
ORDER BY s.spotify_match_confidence, s.artist, s.title
LIMIT 50
```

## Review Process

### For LOW Matches

The script found something but confidence < 70%. Check if it's correct:

1. Compare `title` vs `spotify_title`
2. Compare `artist` vs `spotify_artist`
3. Open `spotify_web_url` to verify

**If correct:** Update to MANUAL
```sql
UPDATE songs SET spotify_match_confidence = 'MANUAL'
WHERE id = X
```

**If wrong:** Use fuzzy search to find correct track
```
mcp__spotify__search_track_fuzzy with title and artist
```

### For NOT_FOUND

No results from initial search. Try:

1. **Fuzzy search** - Simplified title, artist variations
2. **Check for covers/remixes** - May be listed under different artist
3. **Verify availability** - Some tracks removed from Spotify

**Common NOT_FOUND patterns:**
- Live performance versions
- Alternative tunings (432hz)
- TV theme songs
- Removed artists (Gary Glitter, etc.)
- Featured artist format mismatches

### Update After Manual Fix

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

## Batch Update for Confirmed Unavailable

If tracks are genuinely not on Spotify:
```sql
UPDATE songs SET
  spotify_match_confidence = 'UNAVAILABLE'
WHERE id IN (X, Y, Z)
```

## Report Format

After review session:
```
Reviewed X songs (LOW: A, NOT_FOUND: B)
- Fixed: C
- Confirmed unavailable: D
- Remaining: E
```
