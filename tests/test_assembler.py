from quran_segmenter.pipeline.assembler import SegmentAssembler
from quran_segmenter.models import VerseRange, WordTimestamp


def test_assemble_segments_success(temp_config):
    assembler = SegmentAssembler(temp_config)
    vr = VerseRange.parse("1:1")
    timestamps = [
        WordTimestamp(surah=1, ayah=1, word_index=1, start_time=0.1, end_time=0.2),
        WordTimestamp(surah=1, ayah=1, word_index=2, start_time=0.25, end_time=0.5),
    ]
    alignment = {
        "1:1": {
            "segments": [
                {"word_range": {"start": 1, "end": 2}, "t": "hello"}
            ]
        }
    }

    result = assembler.assemble(vr, timestamps, alignment)

    assert "1:1" in result.verses
    seg = result.verses["1:1"].segments[0]
    assert seg.start == 0.1 and seg.end == 0.5
    assert seg.arabic == "alpha beta"
    assert seg.translation == "hello"
    assert seg.is_last
    assert not result.warnings


def test_assemble_missing_alignment_warns(temp_config):
    assembler = SegmentAssembler(temp_config)
    vr = VerseRange.parse("1:1")
    result = assembler.assemble(vr, [], {})
    assert "No alignment data for 1:1" in result.warnings


def test_assemble_missing_timing_warns(temp_config):
    assembler = SegmentAssembler(temp_config)
    vr = VerseRange.parse("1:1")
    alignment = {"1:1": {"segments": [{"word_range": {"start": 1, "end": 2}, "t": "x"}]}}

    result = assembler.assemble(vr, [], alignment)

    assert "No timing data for 1:1 words 1-2" in result.warnings
    assert "No valid segments for 1:1" in result.warnings
