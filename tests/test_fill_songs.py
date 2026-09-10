"""The TAL title cleanup must never take the scrape down with it.

On 2026-09-07 — the first Monday the TAL scrape ran on real work in eight months —
fill_songs.cleanup_existing_songs stripped a trailing quote from a title whose clean
twin already existed on the same episode (728: "Searching for a New Word" / Con Brio),
songs_episode_title_artist_unique (sql/008) refused the UPDATE, the exception rolled
back the whole step, and the 25 songs the run had just fetched were thrown away.

These tests pin the guard: a quoted title that would collide with a sibling is skipped,
counted and named, never renamed. The SQL is exercised through a fake cursor (the
suite has no database by policy); the same statements were run read-only against
production on 2026-09-10: 86 quoted titles, 85 cleanable, 1 uncleanable.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "pipeline" / "scrapers" / "tal"))

import fill_songs  # noqa: E402


class _Cursor:
    def __init__(self, rows=None, rowcount=0):
        self.executed: list[str] = []
        self._rows = list(rows or [])
        self.rowcount = rowcount

    def execute(self, sql, params=None):
        self.executed.append(" ".join(sql.split()))

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Conn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, *a, **k):
        return self._cursor


def test_a_quoted_title_whose_clean_twin_exists_is_not_renamed() -> None:
    cur = _Cursor(rowcount=85)
    assert fill_songs.cleanup_existing_songs(_Conn(cur)) == 85
    (sql,) = cur.executed
    assert sql.startswith("UPDATE songs SET title = REGEXP_REPLACE(")
    # The guard is the uniqueness key from sql/008, applied to the CLEANED title.
    assert "AND NOT EXISTS ( SELECT 1 FROM songs o WHERE o.episode_id = songs.episode_id AND o.id <> songs.id" in sql
    assert "lower(btrim(o.title)) = lower(btrim(REGEXP_REPLACE(" in sql
    assert "lower(btrim(o.artist)) = lower(btrim(songs.artist))" in sql


def test_the_guard_only_ever_narrows_the_original_predicate() -> None:
    """Every row the old cleanup touched is still a candidate; the guard removes rows,
    it never adds any — so the 85 clean-able titles still get cleaned."""
    cur = _Cursor()
    fill_songs.cleanup_existing_songs(_Conn(cur))
    (sql,) = cur.executed
    where = sql.split(" WHERE ", 1)[1]
    assert where.startswith("(title ~ E'^[")  # the original quote test, first
    assert " AND NOT EXISTS" in where


def test_uncleanable_rows_are_counted_from_either_row_shape() -> None:
    assert fill_songs.count_uncleanable_songs(_Conn(_Cursor(rows=[{"n": 1}]))) == 1
    assert fill_songs.count_uncleanable_songs(_Conn(_Cursor(rows=[(3,)]))) == 3


def test_the_count_asks_the_same_question_the_update_declines() -> None:
    """count and cleanup share one collision clause, so they cannot drift apart —
    a row the count reports is exactly a row the UPDATE leaves alone."""
    c1 = _Cursor(rows=[{"n": 0}])
    fill_songs.count_uncleanable_songs(_Conn(c1))
    c2 = _Cursor()
    fill_songs.cleanup_existing_songs(_Conn(c2))
    clause = " ".join(fill_songs._COLLIDES_WITH_A_SIBLING.split())
    assert clause in c1.executed[0]
    assert clause in c2.executed[0]
