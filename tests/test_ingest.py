"""Tests for ingest_song's pure catalog helpers (no rendering)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest_song import slugify, fmt_dur, upsert_song


def test_slugify():
    assert slugify('Canon In D - Pachelbel') == 'canon_in_d_pachelbel'
    assert slugify('  Étude!! No.3  ') == 'tude_no_3'   # non-ascii/punct collapse
    assert slugify('') == 'song'


def test_fmt_dur():
    assert fmt_dur(5.4) == '0:05'
    assert fmt_dur(64) == '1:04'
    assert fmt_dur(59.6) == '1:00'      # rounds up across the minute
    assert fmt_dur(190.2) == '3:10'


def test_upsert_replaces_not_duplicates():
    songs = [{'id': 'a', 'title': 'A'}, {'id': 'b', 'title': 'B'}]
    out = upsert_song(songs, {'id': 'a', 'title': 'A2'})
    assert sum(1 for s in out if s['id'] == 'a') == 1
    assert [s for s in out if s['id'] == 'a'][0]['title'] == 'A2'
    assert {s['id'] for s in out} == {'a', 'b'}


def test_upsert_appends_new():
    out = upsert_song([{'id': 'a'}], {'id': 'c'})
    assert {s['id'] for s in out} == {'a', 'c'}
