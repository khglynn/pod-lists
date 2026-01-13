#!/usr/bin/env python3
"""Process TAL episodes batch and output clean JSON for database insertion."""

import json
import sys
import subprocess

def main():
    # Run the parse script and capture output
    result = subprocess.run(
        ['python3', '/Users/KevinHG/DevKev/personal/list-maker/scripts/tal_parse.py', '--range', '901', '1000'],
        capture_output=True,
        text=True
    )

    data = json.loads(result.stdout)

    # Count statistics
    total = len(data)
    is_404 = sum(1 for d in data if d.get("is_404", False))
    valid = total - is_404
    has_songs = sum(1 for d in data if not d.get("is_404", False) and d.get("has_songs", False))
    total_songs = sum(len(d.get("songs", [])) for d in data if not d.get("is_404", False))

    print(f"Total episodes: {total}", file=sys.stderr)
    print(f"404 pages: {is_404}", file=sys.stderr)
    print(f"Valid pages: {valid}", file=sys.stderr)
    print(f"Episodes with songs: {has_songs}", file=sys.stderr)
    print(f"Total songs: {total_songs}", file=sys.stderr)
    print(file=sys.stderr)

    # Output the data without raw_content for processing
    clean_data = []
    for d in data:
        clean = {}
        for k, v in d.items():
            if k != "raw_content":
                clean[k] = v
        clean_data.append(clean)

    print(json.dumps(clean_data, indent=2))

if __name__ == "__main__":
    main()
