import { neon } from '@neondatabase/serverless';

// Create a SQL client using the DATABASE_URL
export const sql = neon(process.env.DATABASE_URL!);

// Types
export interface Show {
  id: number;
  name: string;
  slug: string;
  website_url: string | null;
  spotify_playlist_id: string | null;
  created_at: Date;
}

export interface Episode {
  id: number;
  show_id: number;
  title: string;
  url: string | null;
  publish_date: Date | null;
  scraped_at: Date | null;
  raw_content: string | null;
  has_songs_discussed: boolean | null;
  description_body: string | null;
  created_at: Date;
}

export interface Song {
  id: number;
  episode_id: number;
  title: string;
  artist: string;
  album: string | null;
  spotify_track_id: string | null;
  spotify_match_confidence: string | null;
  added_to_playlist: boolean;
  created_at: Date;
}

// Queries
export async function getShowBySlug(slug: string): Promise<Show | null> {
  const rows = await sql`SELECT * FROM shows WHERE slug = ${slug}`;
  return rows[0] as Show | null;
}

export async function getEpisodeByUrl(url: string): Promise<Episode | null> {
  const rows = await sql`SELECT * FROM episodes WHERE url = ${url}`;
  return rows[0] as Episode | null;
}

export async function insertEpisode(episode: {
  show_id: number;
  title: string;
  url: string;
  publish_date?: Date | null;
  raw_content?: string | null;
  has_songs_discussed?: boolean | null;
  description_body?: string | null;
}): Promise<Episode> {
  const rows = await sql`
    INSERT INTO episodes (show_id, title, url, publish_date, raw_content, has_songs_discussed, description_body, scraped_at)
    VALUES (${episode.show_id}, ${episode.title}, ${episode.url}, ${episode.publish_date || null}, ${episode.raw_content || null}, ${episode.has_songs_discussed ?? null}, ${episode.description_body || null}, NOW())
    ON CONFLICT (url) DO UPDATE SET
      title = EXCLUDED.title,
      raw_content = EXCLUDED.raw_content,
      has_songs_discussed = EXCLUDED.has_songs_discussed,
      description_body = EXCLUDED.description_body,
      scraped_at = NOW()
    RETURNING *
  `;
  return rows[0] as Episode;
}

export async function insertSong(song: {
  episode_id: number;
  title: string;
  artist: string;
  album?: string | null;
}): Promise<Song> {
  const rows = await sql`
    INSERT INTO songs (episode_id, title, artist, album)
    VALUES (${song.episode_id}, ${song.title}, ${song.artist}, ${song.album || null})
    RETURNING *
  `;
  return rows[0] as Song;
}

export async function getSongsByEpisodeId(episodeId: number): Promise<Song[]> {
  const rows = await sql`SELECT * FROM songs WHERE episode_id = ${episodeId}`;
  return rows as Song[];
}

export async function getAllEpisodes(showId: number): Promise<Episode[]> {
  const rows = await sql`SELECT * FROM episodes WHERE show_id = ${showId} ORDER BY publish_date DESC`;
  return rows as Episode[];
}

export async function getUnmatchedSongs(): Promise<Song[]> {
  const rows = await sql`SELECT * FROM songs WHERE spotify_track_id IS NULL`;
  return rows as Song[];
}
