-- 012: delete one duplicate TAL song row. Data fix, not DDL.
--
-- Episode 728 holds two rows for the same credit: id 4881 "Searching for a New Word" and
-- id 5650 'Searching for a New Word"' (a trailing quote), both by Con Brio. The title
-- cleanup that runs at the start of every TAL scrape strips that quote, which makes the
-- two rows identical under songs_episode_title_artist_unique (sql/008) — on 2026-09-07 that
-- UPDATE raised, the whole scrape step rolled back, and 25 freshly fetched songs were lost.
-- The cleanup now skips and reports such a row (fill_songs.cleanup_existing_songs); this
-- removes the one that exists. Precondition raises on a re-run. Kevin's paste (DELETE).
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM songs WHERE id = 5650 AND episode_id = 728 AND title = 'Searching for a New Word"') THEN
    RAISE EXCEPTION 'row 5650 is not the quoted duplicate — already deleted?';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM songs WHERE id = 4881 AND episode_id = 728 AND title = 'Searching for a New Word') THEN
    RAISE EXCEPTION 'row 4881 (the clean twin) is missing — stop';
  END IF;
END $$;
DELETE FROM songs WHERE id = 5650;
