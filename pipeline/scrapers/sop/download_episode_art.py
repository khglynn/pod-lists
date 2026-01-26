#!/usr/bin/env python3
"""
SOP Episode Art Downloader

Scrapes episode artwork from switchedonpop.com and downloads images locally.
Uses Firecrawl map to discover episode URLs, then fetches og:image from each page.

Usage:
    python download_sop_episode_art.py
    python download_sop_episode_art.py --output ./episode-art
"""

import argparse
import os
import re
import time
import requests
import psycopg2
from pathlib import Path
from typing import List, Optional, Set, Dict
from urllib.parse import unquote
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from tqdm import tqdm

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env.local")


# =============================================================================
# Constants
# =============================================================================

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY")
NEON_DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL")
BASE_URL = "https://switchedonpop.com"
DEFAULT_OUTPUT_DIR = "./episode-art"
DOWNLOAD_DELAY = 0.05  # seconds between requests
REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
SOP_SHOW_ID = 1  # SOP show ID in our database


# =============================================================================
# Database Functions
# =============================================================================

def load_url_to_episode_map() -> Dict[str, int]:
    """Load episode URLs from database and create URL -> episode_number map.

    Extracts episode numbers from URL patterns like:
        /episodes/001-heartbreak -> 1
        /episodes/72-taylor-constructs... -> 72
    """
    if not NEON_DATABASE_URL:
        print("Warning: NEON_DATABASE_URL not set, skipping DB lookup")
        return {}

    url_map = {}
    try:
        conn = psycopg2.connect(NEON_DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "SELECT url FROM episodes WHERE show_id = %s AND url IS NOT NULL",
            (SOP_SHOW_ID,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        for (url,) in rows:
            # Extract episode number from URL pattern: /episodes/XXX-title
            match = re.search(r'/episodes/(\d{1,3})-', url)
            if match:
                ep_num = int(match.group(1))
                # Normalize URL for matching (lowercase, no trailing slash)
                normalized = url.lower().rstrip('/')
                url_map[normalized] = ep_num

        print(f"Loaded {len(url_map)} episode URLs from database")
        return url_map

    except Exception as e:
        print(f"Warning: Could not load from database: {e}")
        return {}


def get_episode_from_db_url(page_url: str, url_map: Dict[str, int]) -> Optional[int]:
    """Look up episode number from our database URL map."""
    normalized = page_url.lower().rstrip('/')
    return url_map.get(normalized)


# =============================================================================
# URL Discovery
# =============================================================================

def get_episode_urls() -> List[str]:
    """Use Firecrawl map to discover all episode URLs."""
    print("Discovering episode URLs with Firecrawl map...")
    app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
    result = app.map(BASE_URL, limit=500)

    episode_urls = [
        link.url for link in result.links
        if '/episodes/' in link.url and link.url != f"{BASE_URL}/episodes"
    ]

    print(f"Found {len(episode_urls)} episode URLs")
    return episode_urls


# =============================================================================
# Image Extraction
# =============================================================================

def extract_og_image(html: str) -> Optional[str]:
    """Extract og:image URL from HTML content."""
    # Pattern for og:image meta tag
    patterns = [
        r'<meta\s+property="og:image"\s+content="([^"]+)"',
        r'<meta\s+content="([^"]+)"\s+property="og:image"',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            url = match.group(1)
            # Filter out Substack embed images
            if 'squarespace' in url.lower():
                return url

    return None


def parse_episode_number_from_filename(url: str) -> Optional[int]:
    """Extract episode number from image URL/filename.

    Examples:
        '453+Cher.jpg' -> 453
        '452+ca7riel+%2B+paco+amoroso+ver2.jpg' -> 452
        'Image+from+iOS+%284%29.jpg' -> None (no episode number)
    """
    # Get the filename from URL
    filename = url.split("/")[-1].split("?")[0]
    filename = unquote(filename)  # Decode URL encoding

    # Try to extract leading number
    match = re.match(r'^(\d+)[+_\s]', filename)
    if match:
        return int(match.group(1))

    # Also try pattern like "318+daft+punk" in the middle of path
    match = re.search(r'/(\d{1,3})[+_\s]', url)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 500:  # Reasonable episode number range
            return num

    return None


def parse_episode_number_from_content(html: str) -> Optional[int]:
    """Extract episode number from page content.

    Looks for patterns like:
        'EPISODE 435'
        '**EPISODE 123**'
        'Episode 42'
    """
    # Pattern for "EPISODE XXX" in content (case insensitive)
    patterns = [
        r'\*\*EPISODE\s+(\d+)\*\*',  # **EPISODE 435**
        r'EPISODE\s+(\d+)',  # EPISODE 435
        r'>EPISODE\s+(\d+)<',  # HTML tags
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            num = int(match.group(1))
            if 1 <= num <= 500:  # Reasonable episode number range
                return num

    return None


def fetch_page_html(url: str, full_page: bool = False) -> Optional[str]:
    """Fetch HTML content from a page.

    Args:
        url: The URL to fetch
        full_page: If True, fetch up to 150KB (for episode number in body).
                   If False, fetch up to 50KB (just head/meta tags).
    """
    try:
        max_size = 150000 if full_page else 50000
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            stream=True
        )
        response.raise_for_status()

        # Read content up to max_size
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > max_size:
                break
            # Early exit if we only need head
            if not full_page and b"</head>" in content:
                break

        return content.decode("utf-8", errors="ignore")
    except Exception as e:
        return None


# =============================================================================
# Download Functions
# =============================================================================

def download_image(url: str, output_path: Path) -> bool:
    """Download an image from URL to local path."""
    try:
        response = requests.get(
            url,
            timeout=30,
            headers={"User-Agent": USER_AGENT}
        )
        response.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(response.content)

        return True
    except Exception as e:
        return False


def get_file_extension(url: str) -> str:
    """Get file extension from URL."""
    filename = url.split("/")[-1].split("?")[0]
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in ["jpg", "jpeg", "png", "gif", "webp"]:
            return f".{ext}"
    return ".jpg"  # Default


# =============================================================================
# Main Pipeline
# =============================================================================

def download_episode_art(output_dir: Path):
    """Main function to discover and download all episode art."""

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 0: Load URL -> episode number map from database
    url_map = load_url_to_episode_map()

    # Step 1: Discover all episode URLs
    episode_urls = get_episode_urls()

    # Step 2: Fetch og:image from each page
    print(f"\nFetching artwork URLs from {len(episode_urls)} episode pages...")

    image_data = []  # (image_url, episode_number)
    no_image = []
    no_number = []
    from_filename = 0
    from_content = 0
    from_db = 0

    for url in tqdm(episode_urls, desc="Fetching metadata"):
        # First pass: get head section for og:image
        html = fetch_page_html(url, full_page=False)
        if not html:
            continue

        img_url = extract_og_image(html)
        if not img_url:
            no_image.append(url)
            continue

        # Try to get episode number from image filename first
        ep_num = parse_episode_number_from_filename(img_url)
        if ep_num is not None:
            from_filename += 1
            image_data.append((img_url, ep_num))
            time.sleep(DOWNLOAD_DELAY)
            continue

        # Fallback 1: fetch more content and look for "EPISODE XXX" in body
        full_html = fetch_page_html(url, full_page=True)
        if full_html:
            ep_num = parse_episode_number_from_content(full_html)
            if ep_num is not None:
                from_content += 1
                image_data.append((img_url, ep_num))
                time.sleep(DOWNLOAD_DELAY)
                continue

        # Fallback 2: look up episode number from database URL
        ep_num = get_episode_from_db_url(url, url_map)
        if ep_num is not None:
            from_db += 1
            image_data.append((img_url, ep_num))
            time.sleep(DOWNLOAD_DELAY)
            continue

        # Still no number found
        no_number.append((url, img_url))
        time.sleep(DOWNLOAD_DELAY)

    print(f"\nFound {len(image_data)} episodes with numbered artwork")
    print(f"  - From filename: {from_filename}")
    print(f"  - From page content: {from_content}")
    print(f"  - From database URL: {from_db}")
    print(f"No og:image: {len(no_image)}")
    print(f"No episode number found: {len(no_number)}")

    # Step 3: Download images
    print(f"\nDownloading to {output_dir}/...")

    downloaded = 0
    skipped = 0
    errors = 0

    for img_url, ep_num in tqdm(image_data, desc="Downloading"):
        ext = get_file_extension(img_url)
        output_path = output_dir / f"ep_{ep_num}{ext}"

        # Skip if already downloaded
        if output_path.exists():
            skipped += 1
            continue

        if download_image(img_url, output_path):
            downloaded += 1
        else:
            errors += 1

        time.sleep(DOWNLOAD_DELAY)

    # Summary
    print(f"\n{'='*50}")
    print(f"Download complete!")
    print(f"  Downloaded: {downloaded}")
    print(f"  Already existed: {skipped}")
    print(f"  Errors: {errors}")

    # List images without episode numbers
    if no_number:
        print(f"\nImages without episode numbers ({len(no_number)}):")
        for url, img_url in no_number[:5]:
            filename = img_url.split('/')[-1].split('?')[0][:40]
            print(f"  - {filename}")
        if len(no_number) > 5:
            print(f"  ... and {len(no_number) - 5} more")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Download SOP episode artwork for mosaic"
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})"
    )

    args = parser.parse_args()
    output_dir = Path(args.output)

    if not FIRECRAWL_API_KEY:
        print("Error: FIRECRAWL_API_KEY environment variable not set")
        print("Set it with: export FIRECRAWL_API_KEY=your_key")
        return 1

    download_episode_art(output_dir)
    return 0


if __name__ == "__main__":
    exit(main())
