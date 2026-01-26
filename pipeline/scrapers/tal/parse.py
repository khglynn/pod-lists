#!/usr/bin/env python3
"""
TAL Episode Parser - Smart Parse for Dumb Fetch Strategy

Parses JSON files from tal_fetch.py and extracts structured data.
Used by Claude agents to process episodes in batches.

Usage:
    python tal_parse.py 901.json              # Parse single file
    python tal_parse.py 901.json 902.json     # Parse multiple files
    python tal_parse.py --range 901 1000      # Parse range of db_ids
"""

import json
import re
import sys
import argparse
from pathlib import Path

def clean_quotes(s):
    """Replace curly quotes with straight quotes"""
    # Use explicit Unicode escapes to ensure curly quotes are matched
    return s.replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")

def parse_episode(filepath):
    """Parse a single episode JSON file."""
    with open(filepath) as f:
        data = json.load(f)

    # Check for 404
    if "could not be found" in data.get("markdown", ""):
        return {
            "db_id": data["db_id"],
            "is_404": True,
            "url": data.get("url", "")
        }

    # Extract episode number from URL
    match = re.search(r'/(\d+)/', data["url"])
    ep_num = int(match.group(1)) if match else None

    # Extract title (remove suffix)
    title = data.get("metadata", {}).get("og:title", "")
    title = re.sub(r' - This American Life$', '', title)
    title = clean_quotes(title)

    # Extract date
    date_str = data.get("metadata", {}).get("article:published_time", "")
    date = date_str.split("T")[0] if date_str else None

    # Extract songs from markdown
    songs = []
    markdown = data.get("markdown", "")

    # Find all ## Song: sections
    song_pattern = r'## Song:\s*\n\n(.+?)(?=\n\n##|\Z)'
    song_sections = re.findall(song_pattern, markdown, re.DOTALL)

    for section in song_sections:
        section = clean_quotes(section.strip())

        # Format 1: ["Title" by Artist](url) or [Title by Artist](url)
        match = re.search(r'\[(["\']?)(.+?)\1\s+by\s+([^\]]+)\]', section)
        if match:
            song_title = clean_quotes(match.group(2).strip())
            artist = re.sub(r'\s*\([^)]+\)\s*$', '', match.group(3)).strip()
            songs.append({"title": song_title, "artist": artist})
            continue

        # Format 2: "Title" by Artist (plain text)
        match = re.search(r'"([^"]+)"\s+by\s+(.+?)(?:,\s*performed by|$)', section)
        if match:
            songs.append({
                "title": clean_quotes(match.group(1)),
                "artist": match.group(2).strip()
            })

    return {
        "db_id": data["db_id"],
        "is_404": False,
        "url": data.get("url", ""),
        "episode_number": ep_num,
        "title": title,
        "publish_date": date,
        "has_songs": len(songs) > 0,
        "songs": songs,
        "raw_content": markdown  # Full markdown for database
    }


def main():
    parser = argparse.ArgumentParser(description="Parse TAL episode JSON files")
    parser.add_argument("files", nargs="*", help="JSON files to parse")
    parser.add_argument("--range", nargs=2, type=int, metavar=("START", "END"),
                        help="Parse range of db_ids (e.g., --range 901 1000)")
    parser.add_argument("--dir", default="fetched/tal",
                        help="Directory containing JSON files")
    args = parser.parse_args()

    files = []
    base_dir = Path(__file__).parent / args.dir

    if args.range:
        start, end = args.range
        for db_id in range(start, end + 1):
            filepath = base_dir / f"{db_id}.json"
            if filepath.exists():
                files.append(filepath)
    elif args.files:
        files = [Path(f) for f in args.files]
    else:
        print("No files specified. Use positional args or --range.", file=sys.stderr)
        sys.exit(1)

    results = []
    for filepath in files:
        try:
            result = parse_episode(filepath)
            results.append(result)
        except Exception as e:
            results.append({
                "db_id": int(filepath.stem) if filepath.stem.isdigit() else None,
                "error": str(e)
            })

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
