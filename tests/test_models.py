import json
from pathlib import Path

from quran_segmenter.models import (
    ProcessingResult,
    Segment,
    VerseRange,
    VerseSegments,
    WordTimestamp,
)


def test_verse_range_formatting_and_segments():
    vr = VerseRange(surah=2, start_verse=1, end_verse=3, include_basmalah=True, include_taawwudh=True)

    assert str(vr) == "taawwudh+basmalah+2:1-3"
    assert vr.to_lafzize_format() == "taawwudh,basmalah,2:1,2:3"
    assert vr.to_lafzize_segments() == ["taawwudh", "basmalah", "2:1,2:3"]
    assert vr.verse_keys() == ["2:1", "2:2", "2:3"]


def test_verse_range_parse_and_from_surah():
    parsed = VerseRange.parse("10:5-7")
    assert parsed.surah == 10
    assert parsed.start_verse == 5
    assert parsed.end_verse == 7

    full = VerseRange.from_surah(3, 200)
    assert str(full) == "3:1-200"


def test_word_timestamp_parsing_and_key():
    ts = WordTimestamp.from_dict(
        {"surah": 1, "ayah": 2, "word_index": 3, "start_time": 0.5, "end_time": 1.25}
    )
    assert ts.key == (1, 2, 3)

    lafz_ts = WordTimestamp.from_lafzize_response(
        {"type": "word", "key": "4:5:6", "start": 1200, "end": 2500}
    )
    assert lafz_ts.start_time == 1.2
    assert lafz_ts.end_time == 2.5


def test_segment_and_result_serialization(tmp_path):
    segment = Segment(start=1.2345, end=2.7182, arabic="a b", translation="text", is_last=True)
    assert segment.to_dict() == {
        "start": 1.234,
        "end": 2.718,
        "arabic": "a b",
        "translation": "text",
        "is_last": True,
    }

    vs = VerseSegments(verse_key="1:1", segments=[segment])
    result = ProcessingResult(verse_range=VerseRange.parse("1:1"), verses={"1:1": vs})
    output_path = tmp_path / "result.json"
    result.save(output_path)

    saved = json.loads(output_path.read_text())
    assert saved == {"1:1": [segment.to_dict()]}
