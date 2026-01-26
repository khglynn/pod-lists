#!/usr/bin/env python3
"""
Download This American Life Episode Art

Reads fetched JSON files from scripts/fetched/tal/ and downloads
episode artwork. Episode numbers are extracted from the page URLs.

Usage:
    python download_tal_episode_art.py                    # Download all
    python download_tal_episode_art.py --dry-run          # Preview without downloading
    python download_tal_episode_art.py --output ./tal-art  # Custom output directory
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Default paths
FETCHED_DIR = Path(__file__).parent / "fetched" / "tal"
OUTPUT_DIR = Path(__file__).parent / "tal-episode-art"


def extract_episode_number(url: str) -> Optional[int]:
    """
    Extract episode number from TAL URL.

    URLs follow pattern: thisamericanlife.org/{episode_number}/{slug}
    Examples:
        https://www.thisamericanlife.org/347/matchmakers → 347
        https://www.thisamericanlife.org/1/new-beginnings → 1
    """
    match = re.search(r'thisamericanlife\.org/(\d+)/', url)
    if match:
        return int(match.group(1))
    return None


def get_image_url(metadata: dict) -> Optional[str]:
    """Extract og:image URL from metadata."""
    # Try different possible keys
    for key in ['og:image', 'ogImage', 'twitter:image']:
        if key in metadata and metadata[key]:
            return metadata[key]
    return None


def download_image(url: str, output_path: Path) -> Tuple[bool, str]:
    """
    Download image from URL to output path.

    Returns (success, message) tuple.
    """
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=30) as response:
            content = response.read()
            output_path.write_bytes(content)
            return True, f"Downloaded ({len(content) // 1024}KB)"
    except HTTPError as e:
        return False, f"HTTP {e.code}"
    except URLError as e:
        return False, f"URL Error: {e.reason}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def process_json_files(
    fetched_dir: Path,
    output_dir: Path,
    dry_run: bool = False,
    delay: float = 0.2,
) -> dict:
    """
    Process all JSON files and download episode art.

    Returns statistics dict.
    """
    stats = {
        'total_files': 0,
        'success': 0,
        'skipped_exists': 0,
        'skipped_no_episode': 0,
        'skipped_no_image': 0,
        'failed': 0,
        'errors': [],
    }

    if not fetched_dir.exists():
        print(f"Error: Fetched directory not found: {fetched_dir}", file=sys.stderr)
        return stats

    # Create output directory
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted(fetched_dir.glob("*.json"))
    stats['total_files'] = len(json_files)

    print(f"Found {len(json_files)} JSON files in {fetched_dir}")
    print(f"Output directory: {output_dir}")
    if dry_run:
        print("DRY RUN - no files will be downloaded")
    print()

    for i, json_path in enumerate(json_files, 1):
        try:
            with open(json_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            stats['failed'] += 1
            stats['errors'].append(f"{json_path.name}: {e}")
            continue

        # Extract episode number from URL
        url = data.get('url', '')
        episode_num = extract_episode_number(url)

        if episode_num is None:
            stats['skipped_no_episode'] += 1
            continue

        # Get image URL
        metadata = data.get('metadata', {})
        image_url = get_image_url(metadata)

        if not image_url:
            stats['skipped_no_image'] += 1
            continue

        # Determine output filename
        # Get extension from URL or default to jpg
        ext = Path(image_url).suffix.lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            ext = '.jpg'
        output_path = output_dir / f"ep_{episode_num}{ext}"

        # Check if already exists
        if output_path.exists():
            stats['skipped_exists'] += 1
            print(f"[{i}/{len(json_files)}] ep_{episode_num}: Exists, skipping")
            continue

        # Download or simulate
        if dry_run:
            print(f"[{i}/{len(json_files)}] ep_{episode_num}: Would download from {image_url[:60]}...")
            stats['success'] += 1
        else:
            success, msg = download_image(image_url, output_path)
            if success:
                stats['success'] += 1
                print(f"[{i}/{len(json_files)}] ep_{episode_num}: {msg}")
            else:
                stats['failed'] += 1
                stats['errors'].append(f"ep_{episode_num}: {msg}")
                print(f"[{i}/{len(json_files)}] ep_{episode_num}: FAILED - {msg}")

            # Rate limiting
            time.sleep(delay)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Download This American Life episode artwork from fetched JSON files"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=FETCHED_DIR,
        help=f"Directory containing fetched JSON files. Default: {FETCHED_DIR}"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory for downloaded images. Default: {OUTPUT_DIR}"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview what would be downloaded without actually downloading"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Delay between downloads in seconds. Default: 0.2"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("TAL Episode Art Downloader")
    print("=" * 60)

    stats = process_json_files(
        fetched_dir=args.input,
        output_dir=args.output,
        dry_run=args.dry_run,
        delay=args.delay,
    )

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total JSON files: {stats['total_files']}")
    print(f"Successfully {'would download' if args.dry_run else 'downloaded'}: {stats['success']}")
    print(f"Skipped (already exists): {stats['skipped_exists']}")
    print(f"Skipped (no episode number): {stats['skipped_no_episode']}")
    print(f"Skipped (no image URL): {stats['skipped_no_image']}")
    print(f"Failed: {stats['failed']}")

    if stats['errors']:
        print()
        print("Errors:")
        for err in stats['errors'][:10]:
            print(f"  - {err}")
        if len(stats['errors']) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more")


if __name__ == "__main__":
    main()
