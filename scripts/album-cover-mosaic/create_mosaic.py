#!/usr/bin/env python3
"""
Photo Mosaic Generator

Creates a photo mosaic from tile images.

Optional cheating mode blends original image for better recognition.
Uses true tile matching based on color similarity.

Based on the approach from github.com/dvdtho/python-photo-mosaic

Usage:
    python create_mosaic.py --target logo.png --tiles ./album_covers/
    python create_mosaic.py --target logo.png --tiles ./album_covers/ --tile-size 50 --output mosaic.png
"""

import argparse
import os
import sys
import random
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from collections import defaultdict

import numpy as np
from PIL import Image
from tqdm import tqdm


# =============================================================================
# Constants
# =============================================================================

DEFAULT_TILE_SIZE = 40       # Size of each tile in final mosaic
DEFAULT_OUTPUT = "mosaic.png"
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


# =============================================================================
# Image Processing
# =============================================================================

def load_and_prepare_tile(path: Path, tile_size: int) -> Optional[np.ndarray]:
    """Load an image, crop to square, resize to tile_size."""
    try:
        img = Image.open(path).convert("RGB")
    except Exception as e:
        return None

    # Crop to square (center crop)
    w, h = img.size
    min_dim = min(w, h)
    left = (w - min_dim) // 2
    top = (h - min_dim) // 2
    img = img.crop((left, top, left + min_dim, top + min_dim))

    # Resize to tile size
    img = img.resize((tile_size, tile_size), Image.Resampling.LANCZOS)

    return np.array(img)


def get_average_color(img: np.ndarray) -> Tuple[int, int, int]:
    """Calculate average RGB color of an image."""
    avg = img.mean(axis=(0, 1))
    return tuple(int(c) for c in avg)


def color_distance(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
    """Calculate Euclidean distance between two colors."""
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


def get_region_average(img: np.ndarray, x: int, y: int, w: int, h: int) -> Tuple[int, int, int]:
    """Get average color of a region in an image."""
    region = img[y:y+h, x:x+w]
    return get_average_color(region)


# =============================================================================
# Tile Pool
# =============================================================================

class TilePool:
    """
    Manages a pool of tile images for mosaic creation.

    Supports:
    - Preloading and caching tiles
    - Finding best color matches
    - Controlling tile reuse
    """

    def __init__(
        self,
        tiles_dir: str,
        tile_size: int,
        allow_reuse: bool = True,
        min_reuse_distance: int = 5,
        max_reuse: int = 0,  # 0 = unlimited
    ):
        self.tile_size = tile_size
        self.allow_reuse = allow_reuse
        self.min_reuse_distance = min_reuse_distance
        self.max_reuse = max_reuse

        self.tiles: List[np.ndarray] = []
        self.colors: List[Tuple[int, int, int]] = []
        self.names: List[str] = []

        # Track usage positions and counts for reuse control
        self.recent_usage: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
        self.usage_count: Dict[int, int] = defaultdict(int)

        self._load_tiles(tiles_dir)

    def _load_tiles(self, tiles_dir: str):
        """Load all tiles from directory."""
        tiles_path = Path(tiles_dir)

        if not tiles_path.exists():
            raise FileNotFoundError(f"Tiles directory not found: {tiles_dir}")

        image_files = [
            f for f in tiles_path.iterdir()
            if f.suffix.lower() in SUPPORTED_FORMATS
        ]

        if not image_files:
            raise ValueError(f"No image files found in {tiles_dir}")

        print(f"Loading {len(image_files)} tile images...")

        for path in tqdm(image_files, desc="Loading tiles"):
            tile = load_and_prepare_tile(path, self.tile_size)
            if tile is not None:
                self.tiles.append(tile)
                self.colors.append(get_average_color(tile))
                self.names.append(path.name)

        print(f"Loaded {len(self.tiles)} valid tiles")

        if len(self.tiles) < 50:
            print(f"WARNING: Only {len(self.tiles)} tiles loaded. "
                  "For best results, use 100+ tiles.", file=sys.stderr)

    def find_best_match(
        self,
        target_color: Tuple[int, int, int],
        position: Tuple[int, int],
        top_n: int = 10,
        randomize: bool = True,
    ) -> np.ndarray:
        """
        Find the best matching tile for a target color.

        If allow_reuse is False, excludes recently used tiles in nearby positions.
        If randomize is True, picks randomly from top N valid candidates to avoid patterns.
        """
        # Calculate distances to all tiles
        distances = [
            (i, color_distance(target_color, c))
            for i, c in enumerate(self.colors)
        ]

        # Sort by distance
        distances.sort(key=lambda x: x[1])

        # Find valid tile (respecting reuse rules)
        # Validate if: no-reuse mode, OR max_reuse limit set, OR min_distance set
        need_validation = (not self.allow_reuse) or (self.max_reuse > 0) or (self.min_reuse_distance > 0)

        if not need_validation:
            # Unlimited reuse, just pick the best match
            tile_idx = distances[0][0]
            self._record_usage(tile_idx, position)
            return self.tiles[tile_idx]

        # Collect valid candidates (up to top_n for randomization)
        valid_candidates = []
        for tile_idx, dist in distances:
            if self._is_valid_position(tile_idx, position):
                valid_candidates.append((tile_idx, dist))
                if len(valid_candidates) >= top_n:
                    break

        if valid_candidates:
            if randomize and len(valid_candidates) > 1:
                # Pick randomly from valid candidates, weighted toward better matches
                # Use exponential weights so best matches are more likely
                weights = [1.0 / (1 + i * 0.5) for i in range(len(valid_candidates))]
                total = sum(weights)
                weights = [w / total for w in weights]
                chosen_idx = random.choices(range(len(valid_candidates)), weights=weights, k=1)[0]
                tile_idx = valid_candidates[chosen_idx][0]
            else:
                tile_idx = valid_candidates[0][0]
            self._record_usage(tile_idx, position)
            return self.tiles[tile_idx]

        # Fallback: all tiles maxed out or too close - find least-used tile
        least_used_idx = min(range(len(self.tiles)), key=lambda i: self.usage_count[i])
        self._record_usage(least_used_idx, position)
        return self.tiles[least_used_idx]

    def _is_valid_position(self, tile_idx: int, position: Tuple[int, int]) -> bool:
        """Check if tile can be placed at position (respects max_reuse and min_distance)."""
        # Check max reuse limit
        if self.max_reuse > 0 and self.usage_count[tile_idx] >= self.max_reuse:
            return False

        # Check minimum distance from same tile
        for prev_pos in self.recent_usage[tile_idx]:
            dist = abs(position[0] - prev_pos[0]) + abs(position[1] - prev_pos[1])
            if dist < self.min_reuse_distance:
                return False
        return True

    def _record_usage(self, tile_idx: int, position: Tuple[int, int]):
        """Record that a tile was used at a position."""
        self.recent_usage[tile_idx].append(position)
        self.usage_count[tile_idx] += 1
        # Keep only recent history for distance checking
        if len(self.recent_usage[tile_idx]) > 100:
            self.recent_usage[tile_idx] = self.recent_usage[tile_idx][-50:]


# =============================================================================
# Mosaic Generation
# =============================================================================

def create_mosaic(
    target_path: str,
    tiles_dir: str,
    tile_size: int = DEFAULT_TILE_SIZE,
    output_path: str = DEFAULT_OUTPUT,
    allow_reuse: bool = True,
    enlargement: int = 1,
    max_reuse: int = 0,
    min_reuse_distance: int = 3,
    cheat_alpha: float = 0.0,
) -> str:
    """
    Create a photo mosaic from tile images.

    Args:
        target_path: Path to the target image to recreate
        tiles_dir: Directory containing tile images
        tile_size: Size of each tile in the output
        output_path: Where to save the mosaic
        allow_reuse: Whether tiles can be reused (disable for more variety)
        enlargement: Scale factor for output (1 = each tile is tile_size pixels)
        max_reuse: Max times a single tile can be reused (0 = unlimited)
        min_reuse_distance: Min grid distance before same tile can repeat
        cheat_alpha: Blend original image on top (0.0-1.0, 0 = no cheat)

    Returns:
        Path to the created mosaic
    """
    # Load target image
    print(f"\nLoading target image: {target_path}")
    target = Image.open(target_path).convert("RGB")
    target_array = np.array(target)

    target_h, target_w = target_array.shape[:2]
    print(f"Target size: {target_w}x{target_h}")

    # Calculate grid dimensions
    grid_w = target_w // tile_size
    grid_h = target_h // tile_size

    print(f"Mosaic grid: {grid_w}x{grid_h} = {grid_w * grid_h} tiles")

    # Load tile pool
    pool = TilePool(
        tiles_dir,
        tile_size * enlargement,
        allow_reuse=allow_reuse,
        min_reuse_distance=min_reuse_distance,
        max_reuse=max_reuse,
    )

    if grid_w * grid_h > len(pool.tiles) and not allow_reuse:
        # Calculate minimum reuse needed and set a reasonable limit
        tiles_needed = grid_w * grid_h
        min_reuse_per_tile = (tiles_needed // len(pool.tiles)) + 1
        print(f"WARNING: Need {tiles_needed} tiles but only have {len(pool.tiles)}. "
              f"Setting max_reuse to {min_reuse_per_tile}.", file=sys.stderr)
        pool.allow_reuse = True
        pool.max_reuse = min_reuse_per_tile

    # Create output image
    output_w = grid_w * tile_size * enlargement
    output_h = grid_h * tile_size * enlargement
    output = np.zeros((output_h, output_w, 3), dtype=np.uint8)

    print(f"Output size: {output_w}x{output_h}")
    print("\nGenerating mosaic...")

    # Fill mosaic
    total_tiles = grid_w * grid_h

    with tqdm(total=total_tiles, desc="Building mosaic") as pbar:
        for gy in range(grid_h):
            for gx in range(grid_w):
                # Get average color of this region in target
                x = gx * tile_size
                y = gy * tile_size
                target_color = get_region_average(target_array, x, y, tile_size, tile_size)

                # Find best matching tile
                tile = pool.find_best_match(target_color, (gx, gy))

                # Place tile in output
                out_x = gx * tile_size * enlargement
                out_y = gy * tile_size * enlargement
                tile_h, tile_w = tile.shape[:2]
                output[out_y:out_y+tile_h, out_x:out_x+tile_w] = tile

                pbar.update(1)

    # Convert to PIL Image
    output_img = Image.fromarray(output)

    # Apply cheat blend if requested
    if cheat_alpha > 0:
        print(f"\nApplying cheat blend (alpha={cheat_alpha})...")
        # Resize target to match output
        target_resized = target.resize((output_w, output_h), Image.Resampling.LANCZOS)
        # Blend: (1-alpha)*mosaic + alpha*target
        output_img = Image.blend(output_img, target_resized, cheat_alpha)

    # Save output
    print(f"\nSaving mosaic to: {output_path}")

    # Use high quality for JPEG
    if output_path.lower().endswith(('.jpg', '.jpeg')):
        output_img.save(output_path, quality=95)
    else:
        output_img.save(output_path)

    return output_path


# =============================================================================
# Main
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a photo mosaic from tile images (no overlay cheating)"
    )

    parser.add_argument(
        "--target", "-t",
        required=True,
        help="Target image to recreate as mosaic"
    )
    parser.add_argument(
        "--tiles", "-i",
        required=True,
        help="Directory containing tile images"
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT,
        help=f"Output path for mosaic. Default: {DEFAULT_OUTPUT}"
    )
    parser.add_argument(
        "--tile-size", "-s",
        type=int,
        default=DEFAULT_TILE_SIZE,
        help=f"Size of each tile in pixels. Default: {DEFAULT_TILE_SIZE}"
    )
    parser.add_argument(
        "--no-reuse",
        action="store_true",
        help="Don't allow tile reuse (requires many unique tiles)"
    )
    parser.add_argument(
        "--max-reuse",
        type=int,
        default=0,
        help="Max times a single tile can be used (0 = unlimited). Default: 0"
    )
    parser.add_argument(
        "--min-distance",
        type=int,
        default=3,
        help="Min grid distance before same tile can repeat. Default: 3"
    )
    parser.add_argument(
        "--cheat",
        type=float,
        default=0.0,
        help="Blend original image (0.0-1.0). 0.2 = subtle, 0.4 = obvious. Default: 0"
    )
    parser.add_argument(
        "--enlarge", "-e",
        type=int,
        default=1,
        help="Enlargement factor for output. Default: 1"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("Photo Mosaic Generator")
    print("=" * 60)

    if not os.path.exists(args.target):
        print(f"Error: Target image not found: {args.target}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(args.tiles):
        print(f"Error: Tiles directory not found: {args.tiles}", file=sys.stderr)
        sys.exit(1)

    result = create_mosaic(
        target_path=args.target,
        tiles_dir=args.tiles,
        tile_size=args.tile_size,
        output_path=args.output,
        allow_reuse=not args.no_reuse,
        enlargement=args.enlarge,
        max_reuse=args.max_reuse,
        min_reuse_distance=args.min_distance,
        cheat_alpha=args.cheat,
    )

    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60)
    print(f"Mosaic saved to: {os.path.abspath(result)}")


if __name__ == "__main__":
    main()
