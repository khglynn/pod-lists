# Spotify Song Matching

*Created 2025-12-20 - Shared across all shows*

## Overview

Song matching is now **scripted** via `scripts/spotify_match.py`. This doc covers the workflow and post-script LLM tasks.

## Script Usage

```bash
cd /Users/KevinHG/DevKev/personal/list-maker/scripts
source venv/bin/activate

# Dry run (no DB writes)
python spotify_match.py --show-id 1 --limit 10 --dry-run

# Full run for a show
python spotify_match.py --show-id 1 --yes

# All shows
python spotify_match.py --yes
```

**Show IDs:** 1 = SOP, 2 = TAL

## Confidence Levels

| Level | Threshold | Action |
|-------|-----------|--------|
| HIGH | >= 90% | Auto-save, sync to playlist |
| MEDIUM | 70-89% | Auto-save, sync to playlist |
| LOW | < 70% | Save but flag for review |
| NOT_FOUND | No results | Mark confidence, leave track ID NULL |

## Algorithm

Script uses same algorithm as Spotify MCP:
- Title similarity: 55% weight
- Artist similarity: 45% weight
- Uses `thefuzz` library for fuzzy matching

## Post-Script Tasks (LLM)

After script runs, these remain for Claude:

1. **Review LOW matches** - See `_spotify-review.md`
2. **Review NOT_FOUND** - Fuzzy search, find alternatives
3. **Playlist sync** - Add HIGH+MEDIUM to Spotify
4. **Quality checks** - Compare scraped vs Spotify data

## Progress Check Query

```sql
SELECT
  spotify_match_confidence,
  COUNT(*) as count
FROM songs s
JOIN episodes e ON s.episode_id = e.id
WHERE e.show_id = 1
GROUP BY spotify_match_confidence
```

## Playlist IDs

| Show | Playlist ID |
|------|-------------|
| SOP | `0cEVeX4pdHf5RJOiTRzgxX` |
| TAL | `3d7fjfrTTKvrl7VHv5JzIz` |
