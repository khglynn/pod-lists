#!/usr/bin/env python3
"""Detect text-card tiles (white background + black text) vs actual artwork."""

import os
from pathlib import Path
from PIL import Image
import numpy as np


def analyze_tile(filepath: Path) -> dict:
    """Analyze a tile and return metrics about its content."""
    try:
        img = Image.open(filepath).convert('RGB')
        arr = np.array(img)

        # Calculate white pixel ratio (pixels where R, G, B are all > 240)
        white_mask = np.all(arr > 240, axis=2)
        white_ratio = white_mask.sum() / white_mask.size

        # Calculate color diversity (unique colors sampled)
        # Quantize to reduce noise
        quantized = (arr // 32) * 32
        # Sample 1000 random pixels for speed
        flat = quantized.reshape(-1, 3)
        if len(flat) > 1000:
            indices = np.random.choice(len(flat), 1000, replace=False)
            sample = flat[indices]
        else:
            sample = flat
        unique_colors = len(np.unique(sample, axis=0))

        # Check for the specific pink line color (around #E8546C or similar)
        pink_mask = (arr[:,:,0] > 200) & (arr[:,:,1] < 120) & (arr[:,:,2] < 150)
        pink_ratio = pink_mask.sum() / pink_mask.size

        return {
            'white_ratio': white_ratio,
            'unique_colors': unique_colors,
            'pink_ratio': pink_ratio,
            'is_text_card': white_ratio > 0.85 and unique_colors < 15
        }
    except Exception as e:
        return {'error': str(e)}


def main():
    tiles_dir = Path(__file__).parent / 'sop' / 'tiles'

    text_cards = []
    artwork = []
    errors = []

    files = sorted(tiles_dir.glob('ep_*.*'))
    print(f"Analyzing {len(files)} tiles...")

    for f in files:
        result = analyze_tile(f)
        if 'error' in result:
            errors.append((f.name, result['error']))
        elif result['is_text_card']:
            text_cards.append((f.name, result['white_ratio'], result['unique_colors']))
        else:
            artwork.append((f.name, result['white_ratio'], result['unique_colors']))

    print(f"\n=== TEXT CARDS ({len(text_cards)}) ===")
    for name, white, colors in sorted(text_cards)[:20]:
        print(f"  {name}: white={white:.1%}, colors={colors}")
    if len(text_cards) > 20:
        print(f"  ... and {len(text_cards) - 20} more")

    print(f"\n=== ARTWORK ({len(artwork)}) ===")
    for name, white, colors in sorted(artwork)[:10]:
        print(f"  {name}: white={white:.1%}, colors={colors}")
    if len(artwork) > 10:
        print(f"  ... and {len(artwork) - 10} more")

    if errors:
        print(f"\n=== ERRORS ({len(errors)}) ===")
        for name, err in errors:
            print(f"  {name}: {err}")

    # Output list of text cards for easy removal
    print(f"\n=== TEXT CARD FILENAMES (copy to move) ===")
    print(' '.join(name for name, _, _ in sorted(text_cards)))


if __name__ == '__main__':
    main()
