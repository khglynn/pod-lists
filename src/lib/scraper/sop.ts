/**
 * Switched On Pop (SOP) Scraper
 *
 * Scrapes the SOP website to extract episode info and songs discussed.
 * Uses Firecrawl via fetch for scraping.
 */

import { getShowBySlug, insertEpisode, insertSong, getEpisodeByUrl, getSongsByEpisodeId } from '../db';

const SOP_BASE_URL = 'https://switchedonpop.com';
const SOP_EPISODES_URL = `${SOP_BASE_URL}/episodes`;

// Firecrawl API (assumes FIRECRAWL_API_KEY is set)
const FIRECRAWL_API_URL = 'https://api.firecrawl.dev/v1';

interface ScrapedEpisode {
  title: string;
  url: string;
  publishDate: string | null;
}

interface ScrapedSong {
  artist: string;
  title: string;
}

interface ScrapeResult {
  markdown: string;
  metadata?: Record<string, unknown>;
}

/**
 * Scrape a URL using Firecrawl API
 */
async function scrapeUrl(url: string): Promise<ScrapeResult> {
  const apiKey = process.env.FIRECRAWL_API_KEY;
  if (!apiKey) {
    throw new Error('FIRECRAWL_API_KEY not set');
  }

  const response = await fetch(`${FIRECRAWL_API_URL}/scrape`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      url,
      formats: ['markdown'],
    }),
  });

  if (!response.ok) {
    throw new Error(`Firecrawl error: ${response.status} ${response.statusText}`);
  }

  const data = await response.json();
  return data.data as ScrapeResult;
}

/**
 * Parse episode list page to extract episode URLs and titles
 */
export function parseEpisodeList(markdown: string): ScrapedEpisode[] {
  const episodes: ScrapedEpisode[] = [];

  // Pattern: # [Title](URL) followed by date info
  // Example: # [Why pop songwriters break the rules (ft. Amy Allen)](https://switchedonpop.com/episodes/amy-allen...)
  const episodePattern = /# \[([^\]]+)\]\((https:\/\/switchedonpop\.com\/episodes\/[^)]+)\)/g;

  let match;
  while ((match = episodePattern.exec(markdown)) !== null) {
    const title = match[1];
    const url = match[2];

    // Try to extract date from text BEFORE the title (format: MM/DD/YY)
    // Pattern: "AuthorName MM/DD/YY" appears before "# [Title]"
    const beforeTitle = markdown.slice(Math.max(0, match.index - 100), match.index);
    const dateMatch = beforeTitle.match(/(\d{1,2}\/\d{1,2}\/\d{2})/);

    episodes.push({
      title,
      url,
      publishDate: dateMatch ? dateMatch[1] : null,
    });
  }

  return episodes;
}

/**
 * Parse an episode page to extract songs discussed
 * Handles multiple formats:
 * - "- Artist – Song Title" (bullet + en-dash)
 * - 'Artist "Song Title"' (quotes around song)
 * - "Artist – Song Title" (no bullet, just newlines - older episodes)
 */
export function parseSongsDiscussed(markdown: string): { songs: ScrapedSong[]; hasSongsSection: boolean } {
  const songs: ScrapedSong[] = [];

  // Find the "Songs Discussed" section (case-insensitive)
  const songsSection = markdown.match(/\*\*Songs Discussed\*\*([\s\S]*?)(?=\n\n\[|$)/i);
  if (!songsSection) {
    return { songs, hasSongsSection: false };
  }

  const songsText = songsSection[1];

  // Pattern 1: - Artist – Song Title (bullet + en-dash or hyphen)
  const dashPattern = /- ([^–\-\n]+)[–-]\s*([^\n]+)/g;

  // Pattern 2: Artist "Song Title" (quotes around song, one per line)
  // Handle both straight quotes " and curly quotes "" (U+201C, U+201D)
  const quotePattern = /^([^"\u201c\u201d\n]+)\s+["\u201c]([^"\u201c\u201d]+)["\u201d]$/gm;

  // Try dash pattern first
  let match;
  while ((match = dashPattern.exec(songsText)) !== null) {
    const artist = match[1].trim();
    const title = match[2].trim();

    if (artist && title && !title.includes('Previous') && !title.includes('Next')) {
      songs.push({ artist, title });
    }
  }

  // If no songs found with dash pattern, try quote pattern
  if (songs.length === 0) {
    while ((match = quotePattern.exec(songsText)) !== null) {
      const artist = match[1].trim();
      const title = match[2].trim();

      // Skip albums (marked with italics _Album_ or "(Album)")
      if (artist && title && !title.includes('(Album)') && !artist.startsWith('_')) {
        songs.push({ artist, title });
      }
    }
  }

  return { songs, hasSongsSection: true };
}

/**
 * Extract the description body (main content before "Songs Discussed" section)
 * This is useful for future extraction of songs mentioned in the body text
 */
export function parseDescriptionBody(markdown: string): string {
  // Remove header/navigation elements (everything before the main content)
  // Main content typically starts after the date line
  let body = markdown;

  // Remove everything up to and including the episode title header
  const titleMatch = body.match(/^#\s+[^\n]+\n/m);
  if (titleMatch && titleMatch.index !== undefined) {
    body = body.slice(titleMatch.index + titleMatch[0].length);
  }

  // Remove the "Songs Discussed" section and everything after
  const songsIndex = body.search(/\*\*Songs Discussed\*\*/i);
  if (songsIndex > 0) {
    body = body.slice(0, songsIndex);
  }

  // Remove footer elements (Substack embed, copyright, etc.)
  const footerPatterns = [
    /\[Previous[\s\S]*$/,
    /\[!\[Apple-Podcasts[\s\S]*$/,
    /Switched On Pop \\\| Substack[\s\S]*$/,
  ];

  for (const pattern of footerPatterns) {
    body = body.replace(pattern, '');
  }

  return body.trim();
}

/**
 * Parse date string (MM/DD/YY) to Date object
 */
function parseDate(dateStr: string | null): Date | null {
  if (!dateStr) return null;

  const parts = dateStr.split('/');
  if (parts.length !== 3) return null;

  const month = parseInt(parts[0], 10) - 1;
  const day = parseInt(parts[1], 10);
  const year = 2000 + parseInt(parts[2], 10); // Assumes 20xx

  return new Date(year, month, day);
}

/**
 * Scrape the SOP episodes list page
 */
export async function scrapeEpisodeList(): Promise<ScrapedEpisode[]> {
  console.log('Scraping SOP episode list...');
  const result = await scrapeUrl(SOP_EPISODES_URL);
  return parseEpisodeList(result.markdown);
}

/**
 * Scrape a single episode page and extract songs
 */
export async function scrapeEpisode(url: string): Promise<{
  markdown: string;
  songs: ScrapedSong[];
  hasSongsSection: boolean;
  descriptionBody: string;
}> {
  console.log(`Scraping episode: ${url}`);
  const result = await scrapeUrl(url);
  const { songs, hasSongsSection } = parseSongsDiscussed(result.markdown);
  const descriptionBody = parseDescriptionBody(result.markdown);
  return { markdown: result.markdown, songs, hasSongsSection, descriptionBody };
}

/**
 * Main function: Scrape episodes and store in database
 */
export async function scrapeAndStore(options?: { limit?: number; skipExisting?: boolean }) {
  const limit = options?.limit ?? 5;
  const skipExisting = options?.skipExisting ?? true;

  // Get the SOP show record
  const show = await getShowBySlug('sop');
  if (!show) {
    throw new Error('SOP show not found in database. Run schema setup first.');
  }

  // Get episode list
  const episodes = await scrapeEpisodeList();
  console.log(`Found ${episodes.length} episodes on list page`);

  const results = {
    processed: 0,
    skipped: 0,
    songsFound: 0,
    errors: [] as string[],
  };

  // Process episodes (with limit)
  for (const ep of episodes.slice(0, limit)) {
    try {
      // Check if already scraped
      if (skipExisting) {
        const existing = await getEpisodeByUrl(ep.url);
        if (existing) {
          const existingSongs = await getSongsByEpisodeId(existing.id);
          if (existingSongs.length > 0) {
            console.log(`Skipping (already has songs): ${ep.title}`);
            results.skipped++;
            continue;
          }
        }
      }

      // Scrape the episode page
      const { markdown, songs, hasSongsSection, descriptionBody } = await scrapeEpisode(ep.url);

      // Store episode
      const episode = await insertEpisode({
        show_id: show.id,
        title: ep.title,
        url: ep.url,
        publish_date: parseDate(ep.publishDate),
        raw_content: markdown,
        has_songs_discussed: hasSongsSection,
        description_body: descriptionBody,
      });

      // Store songs
      for (const song of songs) {
        await insertSong({
          episode_id: episode.id,
          title: song.title,
          artist: song.artist,
        });
        results.songsFound++;
      }

      console.log(`✓ ${ep.title}: ${songs.length} songs`);
      results.processed++;

      // Small delay to be nice to the server
      await new Promise(resolve => setTimeout(resolve, 500));

    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.error(`✗ Error processing ${ep.title}: ${errorMsg}`);
      results.errors.push(`${ep.title}: ${errorMsg}`);
    }
  }

  return results;
}
