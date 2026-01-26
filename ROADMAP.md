# Roadmap

*Last updated: 2026-01-25*

What's next, in order. When done, move to `COMPLETED.md`.

---

## 1. Review TAL NOT_FOUND Songs

**214 songs** couldn't be matched to Spotify. Manual review needed.

**What:**
- [ ] Query NOT_FOUND songs: `SELECT * FROM songs WHERE spotify_match_confidence = 'NOT_FOUND' AND episode_id IN (SELECT id FROM episodes WHERE show_id = 2)`
- [ ] Use Spotify MCP fuzzy search for each
- [ ] Mark truly unavailable as UNAVAILABLE

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

## 4. Weekly Updates Automation

Scripts exist for ongoing updates. Full automation (cron) is future work.

**Current process (see `pipeline/README.md`):**
1. Scrape new episodes (Claude + Firecrawl)
2. Match songs: `python spotify_match.py --show-id 1`
3. Review LOW/NOT_FOUND if any
4. Sync to playlist: `python sync_playlist.py --show-id 1`

**Future automation:**
- [ ] Vercel Cron job to check for new episodes
- [ ] Automatic scraping without Claude
- [ ] Notification when new songs added

---

## 5. Expand: Pop Culture Happy Hour (PCHH)

More complex - needs transcripts + sentiment filtering.

**What:**
- [ ] Check if NPR provides free transcripts (in RSS?)
- [ ] If not, evaluate transcript APIs (Taddy, Podscribe)
- [ ] Extract "What's Making Me Happy" segment
- [ ] Sentiment filtering (positive only)
- [ ] Route to multiple destinations: music → Spotify, TV/movies → Notion + Trakt

---

## 6. Expand: AI Daily

Apps/platforms/tools recommendations.

**What:**
- [ ] Source transcripts (same research as PCHH)
- [ ] Extract app/tool mentions
- [ ] Sentiment filtering (endorsements only)
- [ ] Route to Notion

---

## 7. Trakt Integration (Movies/TV)

Cross-device watchlist sync for movie/TV recommendations.

**What:**
- [ ] Set up Trakt API integration
- [ ] Sync movie/TV items from Notion → Trakt
- [ ] Or direct pipeline: extract → Trakt (bypass Notion?)

---

## Future Ideas (Unprioritized)

Not committed - capture for later consideration.

- **Public database export** - Export to SQLite or build read-only API for public access. Neon is for dev/internal use, not public sharing.
- **Human review UI** - For low-confidence matches, quick approve/reject
- **Spotify metadata enrichment** - Backfill release year (from album API) and genre (from artist API). Not included in batch search response - requires additional API calls per track. Lower priority but nice for filtering/analytics.
- **Book audiobook availability** - No good API found, manual for now
- **One-click-play for TV** - Reelgood integration? (Likewise was buggy)
- **Public dashboard** - Stats on playlist, most-discussed songs
