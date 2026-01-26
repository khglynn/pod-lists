# list-maker

Automated pipeline that extracts music recommendations from podcasts and routes them to Spotify playlists.

## What It Does

Scrapes podcast websites for song mentions, matches them to Spotify, and syncs to public playlists.

**Active Playlists:**
- [Every Song on Switched On Pop](https://open.spotify.com/playlist/0cEVeX4pdHf5RJOiTRzgxX) - 3,501 tracks
- [This American Life: Full Music Archive](https://open.spotify.com/playlist/3d7fjfrTTKvrl7VHv5JzIz) - 880 tracks

## Status

| Show | Episodes | Songs | Match Rate |
|------|----------|-------|------------|
| Switched On Pop | 462 | 4,544 | 91% |
| This American Life | 882 | 1,094 | 80% |

See [ROADMAP.md](ROADMAP.md) for what's next.

## Structure

```
pipeline/          # Song extraction and matching
marketing/         # Playlist cover art (mosaic generator)
src/               # Next.js app (future automation UI)
claude-plans/      # Session plans and prompts
```

## Running the Pipeline

```bash
cd pipeline
source venv/bin/activate

# Match unmatched songs
python spotify_match.py --show-id 1  # SOP
python spotify_match.py --show-id 2  # TAL

# Sync to playlist
python sync_playlist.py --show-id 1
```

See [pipeline/README.md](pipeline/README.md) for full documentation.

## Tech Stack

- **Database:** Neon (Postgres)
- **Matching:** Custom [Spotify MCP](https://github.com/khglynn/spotify-bulk-actions-mcp)
- **Scraping:** Firecrawl + Claude
