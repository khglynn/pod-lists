# Roadmap

*Last updated: 2025-12-26*

What's next, in order. When done, move to `COMPLETED.md`.

---

## 1. SOP Backfill ✅ COMPLETE

**Final status (Dec 21, 2025):**
- **462 episodes** scraped
- **4,544 songs** extracted
- **3,501 tracks** in playlist
- Neon Project: `summer-grass-52363332`
- Playlist: [Every Song on Switched On Pop](https://open.spotify.com/playlist/0cEVeX4pdHf5RJOiTRzgxX)

**Final match results:**
| Confidence | Count | % |
|------------|-------|---|
| HIGH | 3,251 | 71.5% |
| MEDIUM | 566 | 12.5% |
| MANUAL | 333 | 7.3% |
| NOT_FOUND | 376 | 8.3% |
| UNAVAILABLE | 18 | 0.4% |

**Match rate: 91.3%** (4,150 of 4,544)

**Phase 1: Scrape all episodes** ✅ COMPLETE

**Phase 2: Match songs to Spotify** ✅ COMPLETE
- [x] Built Python script `scripts/spotify_match.py`
- [x] Matched all 4,544 songs
- [x] Reviewed LOW matches (200 → 181 approved, 19 fixed/rejected)
- [x] Reviewed NOT_FOUND (534 → fixed 158, marked 18 unavailable)
- [x] Synced to Spotify playlist (3,501 tracks)
- [x] Built `scripts/sync_playlist.py` for ongoing updates

### Database-Driven Scraping Approach

To reduce context usage and avoid repeated work, we use the database to track progress:

1. **One-time setup:** Map full site, insert ALL episode URLs into `episodes` table with `scraped_at = NULL`
2. **Each batch:** Query `WHERE scraped_at IS NULL LIMIT 25`, scrape, update with content
3. **No more:** Re-mapping site, comparing URL lists, risk of duplicates

**SQL patterns:**
```sql
-- Find unscraped episodes
SELECT id, url FROM episodes WHERE scraped_at IS NULL LIMIT 25

-- After scraping, update the episode
UPDATE episodes SET
  title = '...',
  publish_date = 'YYYY-MM-DD',
  episode_number = XXX,
  has_songs_discussed = true/false,
  scraped_at = NOW()
WHERE id = X
```

### Prompts & Scripts

**Scraping (25 eps/batch):** See `claude-plans/prompts/sop/scrape-episodes.md`
**Spotify matching:** Scripted - run `python scripts/spotify_match.py --show-id 1`
**Review LOW/NOT_FOUND:** See `claude-plans/prompts/_spotify-review.md`

---

## 2. Enhanced Song Extraction

Extract songs mentioned in episode body text (not just "Songs Discussed" section).

**What:**
- [ ] LLM-based extraction from `description_body` column
- [ ] Handle mentions like "we discuss [song] by [artist]"
- [ ] Handle album mentions → pull top tracks from Spotify
- [ ] Deduplication against "Songs Discussed" results

**Why:** Some episodes discuss songs in the body text that aren't listed in the formal section.

---

## 3. Transcript Integration

For podcasts without song lists on their websites (PCHH, AI Daily).

**Strategy (cascading, cheapest first):**
1. Website scraping (FREE) - SOP, TAL have structured data
2. Free transcripts - Check RSS feeds, show websites
3. Transcript API - Taddy, Podscribe, Podchaser (research needed)
4. Whisper - Last resort (~$0.006/min)

**What:**
- [ ] Research transcript API options and pricing
- [ ] Build adapter interface for multiple sources
- [ ] Store full transcripts in Neon `episodes.transcript` column
- [ ] Document process in `helper/guides/`

---

## 4. Weekly Updates (Manual for Now)

Scripts exist for ongoing updates. Full automation (cron) is future work.

**Current process (see `scripts/README.md`):**
1. Scrape new episodes (Claude + Firecrawl)
2. Match songs: `python spotify_match.py --show-id 1`
3. Review LOW/NOT_FOUND if any
4. Sync to playlist: `python sync_playlist.py --show-id 1`
   - Auto-updates description with latest episode

**Future automation:**
- [ ] Vercel Cron job to check for new episodes
- [ ] Automatic scraping without Claude
- [ ] Notification when new songs added

---

## 5. Expand: This American Life (TAL) (IN PROGRESS)

Similar approach to SOP - website has song credits.

**Current status (Dec 20, 2025):**
- Show ID: 2
- Playlist: [TAL Songs](https://open.spotify.com/playlist/3d7fjfrTTKvrl7VHv5JzIz)

**What:**
- [x] Set up TAL show and playlist in database
- [ ] Scrape TAL website for song credits
- [ ] Run matching script: `python scripts/spotify_match.py --show-id 2`

---

## 6. Expand: Pop Culture Happy Hour (PCHH)

More complex - needs transcripts + sentiment filtering.

**What:**
- [ ] Check if NPR provides free transcripts (in RSS?)
- [ ] If not, evaluate transcript APIs (Taddy, Podscribe)
- [ ] Extract "What's Making Me Happy" segment
- [ ] Sentiment filtering (positive only)
- [ ] Route to multiple destinations: music → Spotify, TV/movies → Notion + Trakt

---

## 7. Expand: AI Daily

Apps/platforms/tools recommendations.

**What:**
- [ ] Source transcripts (same research as PCHH)
- [ ] Extract app/tool mentions
- [ ] Sentiment filtering (endorsements only)
- [ ] Route to Notion

---

## 8. Trakt Integration (Movies/TV)

Cross-device watchlist sync for movie/TV recommendations.

**What:**
- [ ] Set up Trakt API integration
- [ ] Sync movie/TV items from Notion → Trakt
- [ ] Or direct pipeline: extract → Trakt (bypass Notion?)

---

## 9. Episode Artwork Scraping

Scrape episode cover images for SOP and TAL to use in mosaic artwork and other visuals.

**What:**
- [ ] Scrape episode artwork URLs from SOP website
- [ ] Scrape episode artwork URLs from TAL website
- [ ] Add `artwork_url` column to episodes table
- [ ] Download and store images (or just URLs?)
- [ ] Use for playlist cover mosaics, visualizations

**Context:** Built album cover mosaic for SOP playlist (Dec 2025) - see `scripts/album-cover-mosaic/`. Episode artwork would add another visual dimension.

---

## Future Ideas (Unprioritized)

Not committed - capture for later consideration.

- **Public database export** - Export to SQLite or build read-only API for public access. Neon is for dev/internal use, not public sharing.
- **Human review UI** - For low-confidence matches, quick approve/reject
- **Spotify metadata enrichment** - Backfill release year (from album API) and genre (from artist API). Not included in batch search response - requires additional API calls per track. Lower priority but nice for filtering/analytics.
- **Book audiobook availability** - No good API found, manual for now
- **One-click-play for TV** - Reelgood integration? (Likewise was buggy)
- **Public dashboard** - Stats on playlist, most-discussed songs
