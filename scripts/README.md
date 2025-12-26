# list-maker Scripts

*Last updated: 2025-12-21*

## Quick Reference

| Script | Purpose | Run |
|--------|---------|-----|
| `spotify_match.py` | Match songs to Spotify | `python spotify_match.py --show-id 1` |
| `sync_playlist.py` | Sync matched songs to playlist | `python sync_playlist.py --show-id 1` |

## Setup

```bash
cd /Users/KevinHG/DevKev/personal/list-maker/scripts
source venv/bin/activate
```

## Weekly Update Process (SOP)

Run these steps when new episodes are published:

### Step 1: Scrape New Episodes

Use Claude to scrape new episodes from switchedonpop.com:
- Query unscraped episodes: `SELECT id, url FROM episodes WHERE scraped_at IS NULL`
- Scrape using Firecrawl
- Extract songs to `songs` table

### Step 2: Match New Songs

```bash
python spotify_match.py --show-id 1
```

This finds unmatched songs and searches Spotify. Results:
- HIGH (90%+): Auto-approved
- MEDIUM (70-89%): Auto-approved
- LOW (<70%): Needs review
- NOT_FOUND: Needs fuzzy search or mark unavailable

### Step 3: Review LOW/NOT_FOUND (if any)

Query songs needing review:
```sql
SELECT id, title, artist, spotify_match_confidence
FROM songs s JOIN episodes e ON s.episode_id = e.id
WHERE e.show_id = 1 AND spotify_match_confidence IN ('LOW', 'NOT_FOUND')
```

Use Claude + Spotify MCP to fuzzy search and fix.

### Step 4: Sync to Playlist

```bash
python sync_playlist.py --show-id 1
```

Adds new tracks, skips duplicates.

### Step 5: Update Playlist Description

After sync, update the description with latest episode:
```
Last updated [DATE] with "[EPISODE TITLE]" (Ep [NUMBER])
```

Use `mcp__spotify__update_playlist` or Spotify app.

---

## Show Configuration

Defined in `sync_playlist.py` → `SHOWS` dict:

| ID | Name | Playlist ID |
|----|------|-------------|
| 1 | Switched On Pop - All Songs Ever Discussed | `0cEVeX4pdHf5RJOiTRzgxX` |
| 2 | This American Life: Full Music Archive | `3d7fjfrTTKvrl7VHv5JzIz` |

**To add a new show:** Add entry to `SHOWS` dict with `name`, `playlist_id`, and `acronym`.

**Description template** (in `DESCRIPTION_TEMPLATE`):
> [X] songs across [X] [ACRONYM] episodes. Last updated [MM/YY]. Support: buymeacoffee.com/kevinhg. Requests: hi@kevinhg.com.

## Environment Variables

Scripts load from two `.env` files:
1. `~/DevKev/personal/spotify-bulk-actions-mcp/.env` - Spotify credentials
2. `../env.local` - DATABASE_URL, FIRECRAWL_API_KEY

## Logs

Match progress logged to `match_progress.log`
