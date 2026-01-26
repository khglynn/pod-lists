import { NextResponse } from 'next/server';
import { scrapeAndStore, parseEpisodeList, parseSongsDiscussed } from '@/lib/scraper/sop';

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const limit = body.limit ?? 3;

    // Check for API key
    if (!process.env.FIRECRAWL_API_KEY) {
      return NextResponse.json(
        { error: 'FIRECRAWL_API_KEY not configured' },
        { status: 500 }
      );
    }

    const results = await scrapeAndStore({ limit, skipExisting: true });

    return NextResponse.json({
      success: true,
      results,
    });
  } catch (error) {
    console.error('Scrape error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}

// GET endpoint for testing parsing logic without Firecrawl
export async function GET() {
  // Sample data from actual SOP episode list page
  const sampleListMarkdown = `
# [Why pop songwriters break the rules (ft. Amy Allen)](https://switchedonpop.com/episodes/amy-allen-why-pop-songwriters-break-the-rules)

Charlie Harding12/12/25

# [How Sombr's bedroom recordings became his biggest hits](https://switchedonpop.com/episodes/how-sombrs-bedroom-recordings-became-his-biggest-hits)

Charlie Harding12/10/25
`;

  // Sample episode page with songs
  const sampleEpisodeMarkdown = `
# Rosalía's 'LUX' brings the symphony to the club

**Songs Discussed**

- Rosalía – Berghain
- Rosalía – Bizcochito
- Björk – Joga
- Caroline Shaw, Roomful of Teeth – Partita for 8 Voices
- The Police – Every Breath You Take

[Previous]
`;

  const episodeList = parseEpisodeList(sampleListMarkdown);
  const songs = parseSongsDiscussed(sampleEpisodeMarkdown);

  return NextResponse.json({
    message: 'Parser test (no Firecrawl needed)',
    parsedEpisodes: episodeList,
    parsedSongs: songs,
  });
}
