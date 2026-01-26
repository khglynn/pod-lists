#!/usr/bin/env python3
"""
Photo Mosaic Generator

Creates a photo mosaic from tile images.

Optional cheating mode blends original image for better recognition.
Uses true tile matching based on color similarity.

Features:
- Background detection: Skip tile placement in background areas (fill with solid color)
- Diversity weight: Penalize frequently-used tiles to encourage variety
- Distance-based reuse control: Prevent same tile from appearing too close together

Based on the approach from github.com/dvdtho/python-photo-mosaic

Usage:
    python create_mosaic.py --target logo.png --tiles ./album_covers/
    python create_mosaic.py --target logo.png --tiles ./album_covers/ --tile-size 50 --output mosaic.png
    python create_mosaic.py --target logo.png --tiles ./album_covers/ --background auto --diversity 0.5
"""

import argparse
import json
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


def parse_hex_color(hex_str: str) -> Optional[Tuple[int, int, int]]:
    """
    Parse a hex color string to RGB tuple.

    Accepts: "02135B", "#02135B", "2,19,91"
    """
    if not hex_str:
        return None

    hex_str = hex_str.strip()

    # Try comma-separated RGB first
    if ',' in hex_str:
        try:
            parts = [int(x.strip()) for x in hex_str.split(',')]
            if len(parts) == 3 and all(0 <= x <= 255 for x in parts):
                return tuple(parts)
        except ValueError:
            pass

    # Try hex format
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 6:
        try:
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            return (r, g, b)
        except ValueError:
            pass

    return None


def apply_tint(
    tile: np.ndarray,
    tint_color: Tuple[int, int, int],
    alpha: float,
    blend_mode: str = "normal"
) -> np.ndarray:
    """
    Apply a color tint to a tile using various blend modes.

    Blend modes:
    - normal: Simple alpha blend (1-alpha)*tile + alpha*tint
    - multiply: Darkens, preserves shadows. Good for colorizing.
    - screen: Lightens, opposite of multiply.
    - overlay: Multiply darks, screen lights. High contrast colorization.
    - soft_light: Like overlay but gentler.
    - color: Applies tint hue/saturation while preserving tile luminosity.

    Args:
        tile: RGB tile array
        tint_color: RGB tint color
        alpha: Blend strength (0.0-1.0)
        blend_mode: One of "normal", "multiply", "screen", "overlay", "soft_light", "color"
    """
    tile_float = tile.astype(np.float32) / 255.0
    tint_norm = np.array(tint_color, dtype=np.float32) / 255.0

    if blend_mode == "normal":
        # Simple alpha blend
        result = (1 - alpha) * tile_float + alpha * tint_norm

    elif blend_mode == "multiply":
        # Multiply: result = base * blend (darkens)
        multiplied = tile_float * tint_norm
        result = (1 - alpha) * tile_float + alpha * multiplied

    elif blend_mode == "screen":
        # Screen: result = 1 - (1-base)*(1-blend) (lightens)
        screened = 1 - (1 - tile_float) * (1 - tint_norm)
        result = (1 - alpha) * tile_float + alpha * screened

    elif blend_mode == "overlay":
        # Overlay: multiply darks, screen lights
        # if base < 0.5: 2*base*blend, else: 1 - 2*(1-base)*(1-blend)
        dark_mask = tile_float < 0.5
        overlayed = np.where(
            dark_mask,
            2 * tile_float * tint_norm,
            1 - 2 * (1 - tile_float) * (1 - tint_norm)
        )
        result = (1 - alpha) * tile_float + alpha * overlayed

    elif blend_mode == "soft_light":
        # Soft light: gentler version of overlay
        # Formula: (1-2*blend)*base^2 + 2*blend*base
        soft = (1 - 2 * tint_norm) * (tile_float ** 2) + 2 * tint_norm * tile_float
        result = (1 - alpha) * tile_float + alpha * soft

    elif blend_mode == "color":
        # Color mode: apply tint hue/saturation, keep tile luminosity
        # Convert both to HSL, take H/S from tint, L from tile
        tile_lum = 0.299 * tile_float[:,:,0] + 0.587 * tile_float[:,:,1] + 0.114 * tile_float[:,:,2]
        tint_lum = 0.299 * tint_norm[0] + 0.587 * tint_norm[1] + 0.114 * tint_norm[2]

        # Scale tint to match tile luminosity
        if tint_lum > 0.001:
            scale = tile_lum[:,:,np.newaxis] / tint_lum
            colored = tint_norm * scale
            colored = np.clip(colored, 0, 1)
        else:
            # Tint is too dark, just use luminosity
            colored = np.stack([tile_lum, tile_lum, tile_lum], axis=2)

        result = (1 - alpha) * tile_float + alpha * colored

    else:
        # Unknown mode, fallback to normal
        result = (1 - alpha) * tile_float + alpha * tint_norm

    return np.clip(result * 255, 0, 255).astype(np.uint8)


# =============================================================================
# Region-Based Tinting
# =============================================================================

# Default region colors for SOP-style logos
REGION_COLORS = {
    'pink': (244, 114, 182),    # #F472B6 - SOP pink
    'black': (0, 0, 0),          # Black shadow
    'yellow': (255, 255, 0),     # Yellow background
    'white': (255, 255, 255),    # White background
}


def classify_region(
    cell_color: Tuple[int, int, int],
    tolerance: int = 80
) -> Optional[str]:
    """
    Classify a cell's color into a region type.

    Returns: 'pink', 'black', 'yellow', 'white', or None if no clear match.
    """
    best_match = None
    best_distance = float('inf')

    for region_name, region_color in REGION_COLORS.items():
        dist = color_distance(cell_color, region_color)
        if dist < best_distance and dist < tolerance:
            best_distance = dist
            best_match = region_name

    return best_match


def get_region_tint(
    region: str,
    region_tints: Dict[str, Tuple[int, int, int]]
) -> Optional[Tuple[int, int, int]]:
    """Get the tint color for a region, or None if no tint should be applied."""
    return region_tints.get(region)


# =============================================================================
# Background Detection
# =============================================================================

def detect_background_color(img: np.ndarray, sample_size: int = 20) -> Tuple[int, int, int]:
    """
    Auto-detect background color by sampling corners of the image.

    Samples pixels from all four corners and returns the most common color cluster.
    """
    h, w = img.shape[:2]

    # Sample from corners
    corners = []
    for cy, cx in [(0, 0), (0, w-sample_size), (h-sample_size, 0), (h-sample_size, w-sample_size)]:
        # Clamp to valid range
        cy = max(0, min(cy, h - sample_size))
        cx = max(0, min(cx, w - sample_size))
        corner_region = img[cy:cy+sample_size, cx:cx+sample_size]
        corners.append(corner_region.reshape(-1, 3))

    # Combine all corner samples
    all_samples = np.vstack(corners)

    # Find the most common color (simple: use average of samples)
    # For better accuracy, we could use k-means clustering
    avg_color = np.mean(all_samples, axis=0)
    return tuple(int(c) for c in avg_color)


def parse_background_color(bg_spec: str, img: np.ndarray) -> Optional[Tuple[int, int, int]]:
    """
    Parse background color specification.

    Args:
        bg_spec: One of:
            - "auto": auto-detect from corners
            - "white": (255, 255, 255)
            - "black": (0, 0, 0)
            - "R,G,B": specific RGB values (e.g., "255,128,0")
            - "none": no background detection (returns None)
        img: Image array for auto-detection

    Returns:
        RGB tuple or None if no background detection
    """
    if bg_spec is None or bg_spec.lower() == "none":
        return None

    bg_spec = bg_spec.lower().strip()

    if bg_spec == "auto":
        return detect_background_color(img)
    elif bg_spec == "white":
        return (255, 255, 255)
    elif bg_spec == "black":
        return (0, 0, 0)
    else:
        # Try parsing as R,G,B
        try:
            parts = [int(x.strip()) for x in bg_spec.split(",")]
            if len(parts) == 3 and all(0 <= x <= 255 for x in parts):
                return tuple(parts)
        except ValueError:
            pass

        print(f"WARNING: Could not parse background color '{bg_spec}', ignoring", file=sys.stderr)
        return None


def is_background_cell(
    img: np.ndarray,
    x: int, y: int, w: int, h: int,
    bg_color: Tuple[int, int, int],
    threshold: float = 0.7,
    tolerance: int = 30,
) -> bool:
    """
    Check if a cell region is mostly background color.

    Args:
        img: Source image array
        x, y, w, h: Cell region bounds
        bg_color: Background color to match against
        threshold: Fraction of pixels that must match to be considered background (0.0-1.0)
        tolerance: Max color distance to still count as background match

    Returns:
        True if cell is background (should be skipped)
    """
    region = img[y:y+h, x:x+w]
    total_pixels = region.shape[0] * region.shape[1]

    # Calculate distance of each pixel to background color
    bg_array = np.array(bg_color)
    distances = np.sqrt(np.sum((region.astype(float) - bg_array) ** 2, axis=2))

    # Count pixels within tolerance
    matching_pixels = np.sum(distances <= tolerance)
    match_ratio = matching_pixels / total_pixels

    return match_ratio >= threshold


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
    - Diversity weighting to encourage variety
    """

    def __init__(
        self,
        tiles_dir: str,
        tile_size: int,
        allow_reuse: bool = True,
        min_reuse_distance: int = 5,
        max_reuse: int = 0,  # 0 = unlimited
        diversity_weight: float = 0.0,  # 0 = pure color match, higher = more variety
    ):
        self.tile_size = tile_size
        self.allow_reuse = allow_reuse
        self.min_reuse_distance = min_reuse_distance
        self.max_reuse = max_reuse
        self.diversity_weight = diversity_weight

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

        # For random mode: track unused tiles
        self.unused_tiles = set(range(len(self.tiles)))

    def find_random_tile(self, position: Tuple[int, int]) -> np.ndarray:
        """
        Pick a random tile, respecting reuse constraints.
        Prioritizes unused tiles to minimize repetition.
        """
        # First, try to pick from unused tiles
        if self.unused_tiles:
            # Filter unused tiles by position constraints
            valid_unused = [
                idx for idx in self.unused_tiles
                if self._is_valid_position(idx, position)
            ]
            if valid_unused:
                tile_idx = random.choice(valid_unused)
                self.unused_tiles.discard(tile_idx)
                self._record_usage(tile_idx, position)
                return self.tiles[tile_idx]

        # All tiles used at least once, find any valid tile
        valid_tiles = [
            idx for idx in range(len(self.tiles))
            if self._is_valid_position(idx, position)
        ]

        if valid_tiles:
            tile_idx = random.choice(valid_tiles)
            self._record_usage(tile_idx, position)
            return self.tiles[tile_idx]

        # Fallback: least-used tile
        least_used_idx = min(range(len(self.tiles)), key=lambda i: self.usage_count[i])
        self._record_usage(least_used_idx, position)
        return self.tiles[least_used_idx]

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
        Diversity weight penalizes frequently-used tiles to encourage variety.
        """
        # Calculate base color distances to all tiles
        base_distances = [color_distance(target_color, c) for c in self.colors]

        # Apply diversity penalty if enabled
        if self.diversity_weight > 0:
            # Calculate usage penalty: tiles used more get higher penalty
            # Normalize by max possible uses to keep scale reasonable
            max_usage = max(self.usage_count.values()) if self.usage_count else 1
            max_usage = max(max_usage, 1)  # Avoid division by zero

            # Penalty scales with diversity_weight and usage count
            # At diversity_weight=1.0, a tile at max_usage gets ~100 added to its distance
            adjusted_distances = []
            for i, base_dist in enumerate(base_distances):
                usage_penalty = (self.usage_count[i] / max_usage) * self.diversity_weight * 100
                adjusted_distances.append((i, base_dist + usage_penalty))
        else:
            adjusted_distances = [(i, d) for i, d in enumerate(base_distances)]

        # Sort by adjusted distance
        adjusted_distances.sort(key=lambda x: x[1])

        # Find valid tile (respecting reuse rules)
        # Validate if: no-reuse mode, OR max_reuse limit set, OR min_distance set
        need_validation = (not self.allow_reuse) or (self.max_reuse > 0) or (self.min_reuse_distance > 0)

        if not need_validation:
            # Unlimited reuse, just pick the best match
            tile_idx = adjusted_distances[0][0]
            self._record_usage(tile_idx, position)
            return self.tiles[tile_idx]

        # Collect valid candidates (up to top_n for randomization)
        valid_candidates = []
        for tile_idx, dist in adjusted_distances:
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
    background: str = None,
    bg_threshold: float = 0.7,
    diversity_weight: float = 0.0,
    tint: str = None,
    tint_alpha: float = 0.25,
    blend_mode: str = "normal",
    no_color_match: bool = False,
    region_tint: bool = False,
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
        background: Background color spec ("auto", "white", "black", "R,G,B", or None)
        bg_threshold: Fraction of cell that must match background to skip (0.0-1.0)
        diversity_weight: Weight for usage penalty (0 = pure color match, higher = more variety)
        tint: Color to tint each tile (hex like "02135B" or RGB like "2,19,91")
        tint_alpha: Strength of tile tint (0.0-1.0, default 0.25)
        blend_mode: How to blend tint with tile: normal, multiply, screen, overlay, soft_light, color
        no_color_match: If True, pick tiles randomly instead of by color similarity
        region_tint: If True, apply different tints based on target image color at each cell
                     (pink regions get pink tint, black regions get black tint, etc.)

    Returns:
        Path to the created mosaic
    """
    # Load target image
    print(f"\nLoading target image: {target_path}")
    target = Image.open(target_path).convert("RGB")
    target_array = np.array(target)

    target_h, target_w = target_array.shape[:2]
    print(f"Target size: {target_w}x{target_h}")

    # Parse background color
    bg_color = parse_background_color(background, target_array)
    if bg_color:
        print(f"Background color: RGB{bg_color} (threshold: {bg_threshold:.0%})")

    if diversity_weight > 0:
        print(f"Diversity weight: {diversity_weight}")

    # Parse tint color
    tint_color = parse_hex_color(tint) if tint else None
    if tint_color and tint_alpha > 0 and not region_tint:
        print(f"Tile tint: RGB{tint_color} at {tint_alpha:.0%} ({blend_mode} blend)")

    # Setup region tinting if enabled
    region_tints = None
    if region_tint:
        print(f"Region-based tinting enabled at {tint_alpha:.0%} ({blend_mode} blend)")
        region_tints = {
            'pink': REGION_COLORS['pink'],
            'black': REGION_COLORS['black'],
            'yellow': REGION_COLORS['yellow'],
            # 'white' intentionally omitted - white regions either skip or no tint
        }

    if no_color_match:
        print("Random tile selection (no color matching)")

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
        diversity_weight=diversity_weight,
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
    bg_cells_skipped = 0

    with tqdm(total=total_tiles, desc="Building mosaic") as pbar:
        for gy in range(grid_h):
            for gx in range(grid_w):
                # Get region bounds in target image
                x = gx * tile_size
                y = gy * tile_size

                # Check if this cell is background
                if bg_color and is_background_cell(
                    target_array, x, y, tile_size, tile_size,
                    bg_color, threshold=bg_threshold
                ):
                    # Fill with background color instead of tile
                    out_x = gx * tile_size * enlargement
                    out_y = gy * tile_size * enlargement
                    out_tile_size = tile_size * enlargement
                    output[out_y:out_y+out_tile_size, out_x:out_x+out_tile_size] = bg_color
                    bg_cells_skipped += 1
                    pbar.update(1)
                    continue

                # Get target color for this cell (used for matching and/or region detection)
                target_color = get_region_average(target_array, x, y, tile_size, tile_size)

                # Find tile - either by color matching or randomly
                if no_color_match:
                    tile = pool.find_random_tile((gx, gy))
                else:
                    tile = pool.find_best_match(target_color, (gx, gy))

                # Apply tint - either region-based or global
                if region_tints:
                    # Classify this cell's region and apply appropriate tint
                    region = classify_region(target_color)
                    region_tint_color = get_region_tint(region, region_tints) if region else None
                    if region_tint_color:
                        tile = apply_tint(tile, region_tint_color, tint_alpha, blend_mode)
                elif tint_color:
                    tile = apply_tint(tile, tint_color, tint_alpha, blend_mode)

                # Place tile in output
                out_x = gx * tile_size * enlargement
                out_y = gy * tile_size * enlargement
                tile_h, tile_w = tile.shape[:2]
                output[out_y:out_y+tile_h, out_x:out_x+tile_w] = tile

                pbar.update(1)

    if bg_cells_skipped > 0:
        print(f"Skipped {bg_cells_skipped} background cells ({bg_cells_skipped / total_tiles:.1%} of grid)")

    # Convert to PIL Image
    output_img = Image.fromarray(output)

    # Apply cheat blend if requested
    if cheat_alpha > 0:
        print(f"\nApplying cheat blend (alpha={cheat_alpha}, {blend_mode})...")
        # Resize target to match output
        target_resized = target.resize((output_w, output_h), Image.Resampling.LANCZOS)

        # Apply blend mode between mosaic (base) and target (overlay)
        mosaic_arr = np.array(output_img)
        target_arr = np.array(target_resized)

        # Use apply_tint logic but with full image overlay instead of solid color
        base = mosaic_arr.astype(np.float32) / 255.0
        overlay = target_arr.astype(np.float32) / 255.0

        if blend_mode == "normal":
            blended = (1 - cheat_alpha) * base + cheat_alpha * overlay
        elif blend_mode == "multiply":
            multiplied = base * overlay
            blended = (1 - cheat_alpha) * base + cheat_alpha * multiplied
        elif blend_mode == "screen":
            screened = 1 - (1 - base) * (1 - overlay)
            blended = (1 - cheat_alpha) * base + cheat_alpha * screened
        elif blend_mode == "overlay":
            dark_mask = base < 0.5
            overlayed = np.where(dark_mask, 2 * base * overlay, 1 - 2 * (1 - base) * (1 - overlay))
            blended = (1 - cheat_alpha) * base + cheat_alpha * overlayed
        elif blend_mode == "soft_light":
            soft = (1 - 2 * overlay) * (base ** 2) + 2 * overlay * base
            blended = (1 - cheat_alpha) * base + cheat_alpha * soft
        elif blend_mode == "color":
            # Apply overlay hue/saturation, keep base luminosity
            base_lum = 0.299 * base[:,:,0] + 0.587 * base[:,:,1] + 0.114 * base[:,:,2]
            overlay_lum = 0.299 * overlay[:,:,0] + 0.587 * overlay[:,:,1] + 0.114 * overlay[:,:,2]
            overlay_lum = np.maximum(overlay_lum, 0.001)
            scale = base_lum[:,:,np.newaxis] / overlay_lum[:,:,np.newaxis]
            colored = np.clip(overlay * scale, 0, 1)
            blended = (1 - cheat_alpha) * base + cheat_alpha * colored
        else:
            blended = (1 - cheat_alpha) * base + cheat_alpha * overlay

        blended = np.clip(blended * 255, 0, 255).astype(np.uint8)
        output_img = Image.fromarray(blended)

    # Save output
    print(f"\nSaving mosaic to: {output_path}")

    # Use high quality for JPEG
    if output_path.lower().endswith(('.jpg', '.jpeg')):
        output_img.save(output_path, quality=95)
    else:
        output_img.save(output_path)

    return output_path


# =============================================================================
# Config Loading
# =============================================================================

def load_config(config_path: str) -> dict:
    """Load settings from a JSON config file."""
    config_file = Path(config_path)
    if not config_file.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_file) as f:
        config = json.load(f)

    # Resolve relative paths in config relative to config file location
    config_dir = config_file.parent
    for key in ['tiles_dir', 'target', 'output_dir']:
        if key in config and not Path(config[key]).is_absolute():
            config[key] = str(config_dir / config[key])

    return config


def generate_output_filename(config: dict, output_dir: str) -> str:
    """Generate a unique output filename with timestamp."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = config.get('name', 'mosaic').lower().replace(' ', '_')
    return str(Path(output_dir) / f"{name}_{timestamp}.png")


# =============================================================================
# Main
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a photo mosaic from tile images. Use --config for show-specific presets."
    )

    parser.add_argument(
        "--config", "-c",
        help="Path to JSON config file (e.g., sop/config.json). Config values are used as defaults."
    )
    parser.add_argument(
        "--target", "-t",
        help="Target image to recreate as mosaic"
    )
    parser.add_argument(
        "--tiles", "-i",
        help="Directory containing tile images"
    )
    parser.add_argument(
        "--output", "-o",
        help=f"Output path for mosaic. Default: auto-generated in output_dir"
    )
    parser.add_argument(
        "--tile-size", "-s",
        type=int,
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
        help="Max times a single tile can be used (0 = unlimited). Default: 0"
    )
    parser.add_argument(
        "--min-distance",
        type=int,
        help="Min grid distance before same tile can repeat. Default: 3"
    )
    parser.add_argument(
        "--cheat",
        type=float,
        help="Blend original image (0.0-1.0). 0.2 = subtle, 0.4 = obvious. Default: 0"
    )
    parser.add_argument(
        "--enlarge", "-e",
        type=int,
        help="Enlargement factor for output. Default: 1"
    )
    parser.add_argument(
        "--background", "--bg",
        type=str,
        help="Background color to skip: 'auto' (detect from corners), 'white', 'black', 'R,G,B', or 'none'. Default: none"
    )
    parser.add_argument(
        "--bg-threshold",
        type=float,
        help="Fraction of cell that must match background to skip (0.0-1.0). Default: 0.7"
    )
    parser.add_argument(
        "--diversity",
        type=float,
        help="Diversity weight: 0 = pure color match, higher values penalize tile reuse. Try 0.3-0.5. Default: 0"
    )
    parser.add_argument(
        "--tint",
        type=str,
        help="Color tint for each tile (hex like '02135B' or RGB like '2,19,91'). Applied per-tile, not as overlay."
    )
    parser.add_argument(
        "--tint-alpha",
        type=float,
        help="Strength of tile tint (0.0-1.0). Default: 0.25"
    )
    parser.add_argument(
        "--blend-mode", "--blend",
        type=str,
        default=None,
        choices=["normal", "multiply", "screen", "overlay", "soft_light", "color"],
        help="How to blend tint with tile: normal (alpha), multiply (darken), screen (lighten), "
             "overlay (contrast), soft_light (gentle), color (preserve luminosity). Default: normal"
    )
    parser.add_argument(
        "--no-color-match",
        action="store_true",
        help="Disable color matching - pick tiles randomly instead of by color similarity"
    )
    parser.add_argument(
        "--region-tint",
        action="store_true",
        help="Apply different tints based on target image color at each cell "
             "(pink regions get pink tint, black get black tint, yellow get yellow tint)"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # Load config if provided
    config = {}
    if args.config:
        config = load_config(args.config)
        print(f"Loaded config: {config.get('name', args.config)}")

    # Merge config with CLI args (CLI wins)
    # Map config keys to CLI arg names
    key_map = {
        'tiles_dir': 'tiles',
        'target': 'target',
        'output_dir': 'output_dir',
        'tile_size': 'tile_size',
        'enlarge': 'enlarge',
        'max_reuse': 'max_reuse',
        'min_distance': 'min_distance',
        'cheat': 'cheat',
        'background': 'background',
        'bg_threshold': 'bg_threshold',
        'diversity': 'diversity',
    }

    # Get effective values (CLI overrides config)
    def get_val(cli_key, config_key=None, default=None):
        cli_val = getattr(args, cli_key, None)
        if cli_val is not None:
            return cli_val
        if config_key and config_key in config:
            return config[config_key]
        return default

    target = get_val('target', 'target')
    tiles = get_val('tiles', 'tiles_dir')
    tile_size = get_val('tile_size', 'tile_size', DEFAULT_TILE_SIZE)
    enlarge = get_val('enlarge', 'enlarge', 1)
    max_reuse = get_val('max_reuse', 'max_reuse', 0)
    min_distance = get_val('min_distance', 'min_distance', 3)
    cheat = get_val('cheat', 'cheat', 0.0)
    background = get_val('background', 'background', None)
    bg_threshold = get_val('bg_threshold', 'bg_threshold', 0.7)
    diversity = get_val('diversity', 'diversity', 0.0)
    tint = get_val('tint', 'tint', None)
    tint_alpha = get_val('tint_alpha', 'tint_alpha', 0.25)
    blend_mode = get_val('blend_mode', 'blend_mode', 'normal')

    # Handle output path
    output_path = args.output
    if not output_path:
        output_dir = config.get('output_dir', '.')
        os.makedirs(output_dir, exist_ok=True)
        output_path = generate_output_filename(config, output_dir)

    print("=" * 60)
    print("Photo Mosaic Generator")
    print("=" * 60)

    if not target:
        print("Error: No target image specified (use --target or config file)", file=sys.stderr)
        sys.exit(1)

    if not tiles:
        print("Error: No tiles directory specified (use --tiles or config file)", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(target):
        print(f"Error: Target image not found: {target}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(tiles):
        print(f"Error: Tiles directory not found: {tiles}", file=sys.stderr)
        sys.exit(1)

    result = create_mosaic(
        target_path=target,
        tiles_dir=tiles,
        tile_size=tile_size,
        output_path=output_path,
        allow_reuse=not args.no_reuse,
        enlargement=enlarge,
        max_reuse=max_reuse,
        min_reuse_distance=min_distance,
        cheat_alpha=cheat,
        background=background,
        bg_threshold=bg_threshold,
        diversity_weight=diversity,
        tint=tint,
        tint_alpha=tint_alpha,
        blend_mode=blend_mode,
        no_color_match=args.no_color_match,
        region_tint=args.region_tint,
    )

    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60)
    print(f"Mosaic saved to: {os.path.abspath(result)}")


if __name__ == "__main__":
    main()
