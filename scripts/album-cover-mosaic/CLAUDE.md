# Album Cover Mosaic Generator

Creates mosaic artwork from album covers - specifically designed for making the SOP podcast logo out of album art from the show's song recommendations.

## Quick Start

### Step 1: Install Dependencies

```bash
cd /home/user/pod-lists/scripts/album-cover-mosaic
pip install spotipy python-dotenv Pillow numpy tqdm psycopg2-binary
```

### Step 2: Download Album Covers

**Option A: From Neon database (SOP songs)**
```bash
python download_album_art.py --from-db --show-id 1 --output ./album_covers
```

**Option B: From a Spotify playlist URL**
```bash
python download_album_art.py --playlist "https://open.spotify.com/playlist/YOUR_PLAYLIST_ID" --output ./album_covers
```

This will download all unique album covers (640x640px) to `./album_covers/`.

### Step 3: Get Target Image

You need the SOP podcast logo/artwork to use as the target. Save it as `sop_logo.png` in this folder.

The SOP logo can be found at: https://switchedonpop.com (grab from their website or podcast apps)

### Step 4: Generate Mosaic

```bash
python create_mosaic.py --target sop_logo.png --tiles ./album_covers/ --output sop_mosaic.png
```

#### Optional Parameters

| Flag | Description | Default |
|------|-------------|---------|
| `--tile-size 50` | Size of each album tile in pixels | 40 |
| `--no-reuse` | Don't repeat any album cover | Off (allows reuse) |
| `--enlarge 2` | Scale factor for final image | 1 |

**Examples:**

```bash
# Higher resolution output (each tile is 80px)
python create_mosaic.py --target sop_logo.png --tiles ./album_covers/ --tile-size 40 --enlarge 2

# No tile repetition (needs 2500+ unique albums)
python create_mosaic.py --target sop_logo.png --tiles ./album_covers/ --no-reuse

# Smaller tiles = more detail (but tiles less recognizable)
python create_mosaic.py --target sop_logo.png --tiles ./album_covers/ --tile-size 20
```

## How It Works

1. **Download script** fetches album cover URLs from Spotify (either via playlist or from your Neon database of matched tracks)
2. **Mosaic script** divides target image into a grid, calculates average color of each cell, finds best-matching album cover by color similarity
3. **No cheating**: Unlike many mosaic tools, this does NOT overlay a transparent version of the target image. It's pure album covers arranged by color.

## Tips for Best Results

- **More tiles = better results**: 500+ unique albums recommended, 2000+ ideal
- **Tile size trade-off**: Smaller tiles = more detail in the mosaic, but individual albums harder to see
- **Target image**: Simple logos with solid colors work best. Complex photos need more tiles.
- **Color variety**: If your tile pool lacks certain colors, those areas will look off

## File Structure

```
album-cover-mosaic/
├── CLAUDE.md              # This file
├── download_album_art.py  # Downloads album covers from Spotify
├── create_mosaic.py       # Generates the mosaic image
├── album_covers/          # Downloaded album art (created by script)
├── sop_logo.png          # Target image (you provide this)
└── sop_mosaic.png        # Output mosaic (generated)
```

## Environment

Uses the same Spotify OAuth as the main `spotify_match.py` script:
- Reads `.env` from `~/DevKev/personal/spotify-bulk-actions-mcp/.env`
- Uses cached auth from `~/DevKev/personal/spotify-bulk-actions-mcp/.spotify_cache/`

Required env vars (already configured if you've used the Spotify MCP):
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `NEON_DATABASE_URL` (only for `--from-db` mode)
