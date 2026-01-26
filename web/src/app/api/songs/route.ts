import { NextResponse } from 'next/server';
import { sql } from '@/lib/db';

export async function GET() {
  try {
    const songs = await sql`
      SELECT s.id, s.title, s.artist, s.spotify_track_id, e.title as episode_title
      FROM songs s
      JOIN episodes e ON s.episode_id = e.id
      ORDER BY e.publish_date DESC, s.id
    `;

    return NextResponse.json({
      total: songs.length,
      songs,
    });
  } catch (error) {
    console.error('Songs error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
