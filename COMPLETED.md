# Completed Work

Work that's done. Newest at top.

---

## December 2025

### SOP Pipeline v1 Complete
**Completed:** Dec 19, 2025

- ✅ Neon database with shows, episodes, songs tables
- ✅ SOP scraper with "Songs Discussed" parsing
- ✅ Parser handles multiple formats (bullets, dashes, quotes, uppercase)
- ✅ Schema columns for `has_songs_discussed` and `description_body`
- ✅ 4 episodes scraped, 41 songs matched
- ✅ Spotify playlist created: [Every Song on Switched On Pop](https://open.spotify.com/playlist/0cEVeX4pdHf5RJOiTRzgxX)
- ✅ `update_playlist` tool added to Spotify MCP

**Files:**
- `src/lib/db.ts` - Neon client + queries
- `src/lib/scraper/sop.ts` - SOP website scraper
- `src/app/api/scrape/route.ts` - API endpoint

---

### Session Handoff Doc Created
**Completed:** Dec 12, 2025

Created `claude-plans/2025-12-12-session-handoff.md` for continuity between sessions.

---

## December 2024

### Spotify Bulk Actions MCP - Published
**Completed:** Dec 12, 2024
**Plan:** `claude-plans/2025-12-12-spotify-mcp-publish.md`

Moved Kevin's existing Spotify MCP to a public repo, updated it, and published to package registries. This tool powers the music → Spotify pipeline.

- ✅ Moved from festival-navigator to standalone repo
- ✅ Batch playlist creation with confidence scoring (HIGH/MEDIUM/LOW)
- ✅ Library exports (tracks, artists, albums)
- ✅ Human-in-the-loop CSV review workflow
- ✅ Published to PyPI: [spotify-bulk-actions-mcp](https://pypi.org/project/spotify-bulk-actions-mcp/)
- ✅ Listed on mcp.so
- ✅ Published to official MCP Registry (`io.github.khglynn/spotify-bulk-actions-mcp`)
- ✅ PR submitted to awesome-mcp-servers

**Repo:** [github.com/khglynn/spotify-bulk-actions-mcp](https://github.com/khglynn/spotify-bulk-actions-mcp)

---

### Project Planning & Setup
**Completed:** Dec 12, 2024
**Plan:** `claude-plans/2025-12-12-initial-plan.md`

- ✅ Created CLAUDE.md for project instructions
- ✅ Created project stack file at `~/DevKev/tools/helper/project-stacks/list-maker.md`
- ✅ Archived initial plan to `claude-plans/2025-12-12-initial-plan.md`
- ✅ Created context doc summarizing original research chats
- ✅ Decided on Vercel App (Next.js + Neon) over n8n
- ✅ Initialized Next.js project structure

---

### Original Research
**Completed:** Oct-Nov 2024 (before this repo)
**Docs:** `claude-plans/2025-12-12-project-context.md`

Two long chats with ChatGPT exploring:
- ✅ Scraping show notes vs transcription costs
- ✅ Destination platforms (Spotify, Notion, Trakt)
- ✅ Workflow orchestration options (n8n, Vercel, etc.)
- ✅ Show-specific extraction strategies
