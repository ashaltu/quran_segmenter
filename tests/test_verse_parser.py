import json
from pathlib import Path

import pytest

from quran_segmenter.models import VerseRange, QuranMetadata
from quran_segmenter.utils.verse_parser import (
    SURAH_VERSE_COUNTS,
    load_quran_metadata,
    parse_verse_spec,
    validate_verse_range,
)


def test_parse_verse_spec_with_prefixes_and_ranges():
    vr = parse_verse_spec("taawwudh+basmalah+2:1-3")
    assert vr.include_basmalah and vr.include_taawwudh
    assert vr.surah == 2 and vr.start_verse == 1 and vr.end_verse == 3
    assert str(vr) == "taawwudh+basmalah+2:1-3"


def test_parse_full_surah_with_metadata(tmp_path):
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(json.dumps({"2:1": {}, "2:2": {}, "2:3": {}}))
    metadata = load_quran_metadata(meta_path)

    vr = parse_verse_spec("2", metadata=metadata)
    assert vr.start_verse == 1 and vr.end_verse == 3


def test_parse_non_contiguous_rejected():
    with pytest.raises(ValueError):
        parse_verse_spec("1:1,1:3")


def test_parse_unknown_prefix_rejected():
    with pytest.raises(ValueError):
        parse_verse_spec("unknown+1:1")


def test_validate_verse_range_checks_bounds():
    vr = VerseRange(surah=1, start_verse=2, end_verse=1)
    ok, msg = validate_verse_range(vr)
    assert not ok and "Start verse must be <=" in msg

    vr2 = VerseRange(surah=114, start_verse=1, end_verse=SURAH_VERSE_COUNTS[114] + 1)
    ok, msg = validate_verse_range(vr2)
    assert not ok and "exceeds" in msg


def test_load_quran_metadata_fills_defaults(tmp_path):
    # Only supply partial data; loader should backfill missing surahs
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(json.dumps({"1:1": {}, "1:2": {}}))
    meta = load_quran_metadata(meta_path)

    assert meta.get_verse_count(1) == 2
    assert meta.get_verse_count(2) == SURAH_VERSE_COUNTS[2]
