# Task Types: Script vs LLM

*Created 2025-12-20*

## Overview

Tasks are split between Python scripts (automated, deterministic) and LLM (judgment, parsing, review).

## Task Classification

| Task | Type | Reason |
|------|------|--------|
| **Song matching** | SCRIPT | Pure API + SQL, same algorithm every time |
| **Metadata backfill** | SCRIPT | Fill missing columns from Spotify API |
| **Playlist sync** | SCRIPT | Add matched tracks to Spotify playlist |
| **Review LOW/NOT_FOUND** | LLM | Fuzzy search, judgment calls |
| **Episode scraping** | LLM | Different formats per show, HTML parsing |
| **Description extraction** | LLM | Different structures per show |
| **Quality checks** | LLM | Compare data, flag issues |
| **URL discovery** | SCRIPT | Pattern-based URL generation |

## When to Use Each

### Use Script When:
- Task is deterministic (same input → same output)
- Volume is high (hundreds/thousands of items)
- API calls with straightforward logic
- Resume/progress tracking is important

### Use LLM When:
- Task requires judgment or interpretation
- Format varies (parsing different HTML structures)
- Need to handle edge cases creatively
- Low volume with high complexity

## Scripts Available

| Script | Location | Usage |
|--------|----------|-------|
| `spotify_match.py` | `scripts/` | `python spotify_match.py --show-id 1 --yes` |

## Rate Limits

**Spotify (Development Mode):**
- Rolling 30-second window
- Script uses 0.3s delay between calls
- Handles 429 with Retry-After header

**Neon:**
- No practical limits for our usage
- Cold starts take ~2s (not an issue for batch ops)
