import { NextResponse } from 'next/server';
import { sql } from '@/lib/db';

export async function GET() {
  try {
    const shows = await sql`SELECT * FROM shows`;
    const episodeCount = await sql`SELECT COUNT(*) as count FROM episodes`;
    const songCount = await sql`SELECT COUNT(*) as count FROM songs`;
    const recentEpisodes = await sql`
      SELECT e.title, e.url, e.publish_date, COUNT(s.id) as song_count
      FROM episodes e
      LEFT JOIN songs s ON s.episode_id = e.id
      GROUP BY e.id, e.title, e.url, e.publish_date
      ORDER BY e.scraped_at DESC
      LIMIT 5
    `;
    const unmatchedSongs = await sql`SELECT COUNT(*) as count FROM songs WHERE spotify_track_id IS NULL`;

    return NextResponse.json({
      shows,
      episodeCount: episodeCount[0].count,
      songCount: songCount[0].count,
      unmatchedSongs: unmatchedSongs[0].count,
      recentEpisodes,
    });
  } catch (error) {
    console.error('Stats error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
