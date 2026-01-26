#!/usr/bin/env python3
"""
Download Album Art from Spotify Playlist

Downloads all unique album cover images from a Spotify playlist.
Uses the same spotipy OAuth setup as the main matching script.

Usage:
    python download_album_art.py --playlist "PLAYLIST_ID_OR_URL"
    python download_album_art.py --playlist "PLAYLIST_ID" --output ./covers
    python download_album_art.py --from-db --show-id 1  # From Neon database
"""

import argparse
import hashlib
import os
import sys
import time
import re
from pathlib import Path
from typing import Set, List, Dict, Optional
from urllib.request import urlretrieve
from urllib.error import URLError

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from dotenv import load_dotenv

# Optional: for database mode
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


# =============================================================================
# Constants
# =============================================================================

DEFAULT_OUTPUT_DIR = "./album_covers"
IMAGE_SIZE = 640  # Spotify provides 640x640, 300x300, 64x64
API_DELAY = 0.1   # Be nice to Spotify
DOWNLOAD_DELAY = 0.05  # Be nice when downloading images


# =============================================================================
# Spotify Client
# =============================================================================

def get_spotify_client() -> spotipy.Spotify:
    """Initialize Spotify client with OAuth."""
    cache_path = os.path.expanduser(
        "~/DevKev/personal/spotify-bulk-actions-mcp/.spotify_cache/.cache"
    )

    auth_manager = SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8080/callback"),
        scope="playlist-read-private playlist-read-collaborative",
        cache_path=cache_path,
    )

    return spotipy.Spotify(auth_manager=auth_manager)


def extract_playlist_id(playlist_input: str) -> str:
    """Extract playlist ID from URL or return as-is if already an ID."""
    # Handle Spotify URLs
    patterns = [
        r'spotify\.com/playlist/([a-zA-Z0-9]+)',
        r'spotify:playlist:([a-zA-Z0-9]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, playlist_input)
        if match:
            return match.group(1)

    # Assume it's already a playlist ID
    return playlist_input


# =============================================================================
# Album Art Collection
# =============================================================================

def get_album_art_from_playlist(
    sp: spotipy.Spotify,
    playlist_id: str,
    progress_callback=None
) -> List[Dict]:
    """
    Fetch all unique album art URLs from a playlist.

    Returns list of dicts: {album_id, album_name, artist, image_url}
    """
    albums_seen: Set[str] = set()
    album_art: List[Dict] = []

    offset = 0
    limit = 100
    total = None

    while True:
        try:
            results = sp.playlist_tracks(
                playlist_id,
                offset=offset,
                limit=limit,
                fields="items(track(album(id,name,images),artists(name))),total"
            )
        except SpotifyException as e:
            print(f"Error fetching playlist tracks: {e}", file=sys.stderr)
            break

        if total is None:
            total = results.get("total", 0)
            print(f"Playlist has {total} tracks total")

        items = results.get("items", [])
        if not items:
            break

        for item in items:
            track = item.get("track")
            if not track:
                continue

            album = track.get("album", {})
            album_id = album.get("id")

            if not album_id or album_id in albums_seen:
                continue

            albums_seen.add(album_id)

            # Get the largest image (first in the list)
            images = album.get("images", [])
            if images:
                image_url = images[0].get("url")  # 640x640
                if image_url:
                    artists = track.get("artists", [])
                    artist_name = artists[0]["name"] if artists else "Unknown"

                    album_art.append({
                        "album_id": album_id,
                        "album_name": album.get("name", "Unknown"),
                        "artist": artist_name,
                        "image_url": image_url,
                    })

        offset += limit

        if progress_callback:
            progress_callback(offset, total)

        if offset >= total:
            break

        time.sleep(API_DELAY)

    return album_art


def get_album_art_from_database(show_id: int) -> List[Dict]:
    """
    Fetch album art URLs from Neon database.
    Uses spotify_track_id to reconstruct album info.
    """
    if not HAS_PSYCOPG2:
        print("Error: psycopg2 not installed. Run: pip install psycopg2-binary", file=sys.stderr)
        sys.exit(1)

    db_url = os.getenv("NEON_DATABASE_URL")
    if not db_url:
        print("Error: NEON_DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(db_url)

    # Get unique track IDs with HIGH confidence matches
    query = """
        SELECT DISTINCT spotify_track_id, spotify_title, spotify_artist, album
        FROM songs s
        JOIN episodes e ON s.episode_id = e.id
        WHERE s.spotify_track_id IS NOT NULL
          AND s.spotify_match_confidence = 'HIGH'
          AND e.show_id = %s
        ORDER BY spotify_artist, album
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (show_id,))
        rows = cur.fetchall()

    conn.close()

    print(f"Found {len(rows)} unique HIGH-confidence tracks in database")

    # Now we need to get album art from Spotify for these tracks
    # We'll batch fetch track info
    sp = get_spotify_client()

    albums_seen: Set[str] = set()
    album_art: List[Dict] = []

    track_ids = [row["spotify_track_id"] for row in rows]

    # Spotify allows up to 50 tracks per request
    batch_size = 50
    for i in range(0, len(track_ids), batch_size):
        batch = track_ids[i:i+batch_size]

        try:
            tracks = sp.tracks(batch)
        except SpotifyException as e:
            print(f"Error fetching tracks: {e}", file=sys.stderr)
            continue

        for track in tracks.get("tracks", []):
            if not track:
                continue

            album = track.get("album", {})
            album_id = album.get("id")

            if not album_id or album_id in albums_seen:
                continue

            albums_seen.add(album_id)

            images = album.get("images", [])
            if images:
                image_url = images[0].get("url")
                if image_url:
                    artists = track.get("artists", [])
                    artist_name = artists[0]["name"] if artists else "Unknown"

                    album_art.append({
                        "album_id": album_id,
                        "album_name": album.get("name", "Unknown"),
                        "artist": artist_name,
                        "image_url": image_url,
                    })

        print(f"  Fetched {min(i+batch_size, len(track_ids))}/{len(track_ids)} tracks...")
        time.sleep(API_DELAY)

    return album_art


# =============================================================================
# Image Download
# =============================================================================

def download_images(
    album_art: List[Dict],
    output_dir: str,
    skip_existing: bool = True,
) -> Dict[str, int]:
    """
    Download album art images to output directory.

    Returns stats: {downloaded, skipped, failed}
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stats = {"downloaded": 0, "skipped": 0, "failed": 0}
    total = len(album_art)

    print(f"\nDownloading {total} album covers to {output_dir}/")

    for i, album in enumerate(album_art):
        # Create filename from album_id (guaranteed unique)
        filename = f"{album['album_id']}.jpg"
        filepath = output_path / filename

        if skip_existing and filepath.exists():
            stats["skipped"] += 1
            continue

        try:
            urlretrieve(album["image_url"], filepath)
            stats["downloaded"] += 1

            if (i + 1) % 50 == 0 or i == total - 1:
                print(f"  Progress: {i+1}/{total} "
                      f"(downloaded: {stats['downloaded']}, skipped: {stats['skipped']})")

            time.sleep(DOWNLOAD_DELAY)

        except (URLError, OSError) as e:
            stats["failed"] += 1
            print(f"  Failed to download {album['album_name']}: {e}", file=sys.stderr)

    return stats


# =============================================================================
# Main
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download album art from Spotify playlist"
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--playlist", "-p",
        help="Spotify playlist ID or URL"
    )
    source.add_argument(
        "--from-db",
        action="store_true",
        help="Fetch tracks from Neon database instead of playlist"
    )

    parser.add_argument(
        "--show-id",
        type=int,
        default=1,
        help="Show ID when using --from-db (1=SOP, 2=TAL). Default: 1"
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for images. Default: {DEFAULT_OUTPUT_DIR}"
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Re-download existing images"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # Load environment
    env_path = os.path.expanduser("~/DevKev/personal/spotify-bulk-actions-mcp/.env")
    load_dotenv(env_path)

    print("=" * 60)
    print("Album Art Downloader")
    print("=" * 60)

    # Collect album art info
    if args.from_db:
        print(f"\nFetching tracks from database (show_id={args.show_id})...")
        album_art = get_album_art_from_database(args.show_id)
    else:
        playlist_id = extract_playlist_id(args.playlist)
        print(f"\nFetching tracks from playlist: {playlist_id}")

        sp = get_spotify_client()

        def progress(offset, total):
            print(f"  Scanned {offset}/{total} tracks...")

        album_art = get_album_art_from_playlist(sp, playlist_id, progress)

    print(f"\nFound {len(album_art)} unique albums")

    if not album_art:
        print("No album art to download!")
        return

    # Download images
    stats = download_images(
        album_art,
        args.output,
        skip_existing=not args.no_skip,
    )

    # Summary
    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"  Downloaded: {stats['downloaded']}")
    print(f"  Skipped:    {stats['skipped']}")
    print(f"  Failed:     {stats['failed']}")
    print(f"\nAlbum covers saved to: {os.path.abspath(args.output)}/")


if __name__ == "__main__":
    main()
