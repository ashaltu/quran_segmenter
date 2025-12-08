import json
from pathlib import Path

import pytest

from quran_segmenter.exceptions import TranslationNotPreparedError, RabtizeError
from quran_segmenter.models import VerseRange
from quran_segmenter.pipeline.rabtize import RabtizeProcessor
from quran_segmenter.utils.cache import CacheManager


def test_is_ready_reports_missing_items(temp_config):
    rp = RabtizeProcessor(temp_config, cache=CacheManager(temp_config.cache_dir))
    ready, missing = rp.is_ready("unknown")
    assert not ready and "translation not registered" in missing


def test_generate_spans_embeddings_creates_file(monkeypatch, temp_config, make_translation_file):
    source = make_translation_file(segmented=True)
    temp_config.register_translation("en-test", "Test", "en", source)
    rp = RabtizeProcessor(temp_config, cache=CacheManager(temp_config.cache_dir))

    def _fake_run(args, desc, timeout=0):
        output = Path(args[4])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("spans")
        return ""

    monkeypatch.setattr(rp, "_run_rabtize_with_progress", _fake_run)
    output_path = rp.generate_spans_embeddings(force=True)
    assert output_path.exists()
    assert temp_config.spans_embeddings_generated


def test_generate_segment_embeddings_creates_file(monkeypatch, temp_config, make_translation_file):
    source = make_translation_file(segmented=True)
    tc = temp_config.register_translation("en-test", "Test", "en", source)
    temp_config.update_translation(tc.id, is_segmented=True)
    rp = RabtizeProcessor(temp_config, cache=CacheManager(temp_config.cache_dir))

    def _fake_run(args, desc, timeout=0):
        output = Path(args[4])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("segments")
        return ""

    monkeypatch.setattr(rp, "_run_rabtize_with_progress", _fake_run)
    output_path = rp.generate_segment_embeddings(tc.id, force=True)
    assert output_path.exists()
    assert Path(temp_config.translations[tc.id].embeddings_path) == output_path


def test_align_runs_and_caches(monkeypatch, temp_config, make_translation_file):
    source = make_translation_file(segmented=True)
    tc = temp_config.register_translation("en-test", "Test", "en", source)
    temp_config.update_translation(tc.id, is_segmented=True)

    # prerequisites
    spans = temp_config.spans_embeddings_path
    spans.parent.mkdir(parents=True, exist_ok=True)
    spans.write_text("spans")
    emb = temp_config.embeddings_dir / f"{tc.id}.npz"
    emb.write_text("segments")
    temp_config.update_translation(tc.id, embeddings_path=emb)

    rp = RabtizeProcessor(temp_config, cache=CacheManager(temp_config.cache_dir))
    writes = []

    def _fake_run(args, desc, timeout=0):
        output = Path(args[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"1:1": {"segments": [{"word_range": {"start": 1, "end": 1}, "t": "x"}]}}))
        writes.append(output)
        return ""

    monkeypatch.setattr(rp, "_run_rabtize_with_progress", _fake_run)
    vr = VerseRange.parse("1:1")

    alignment = rp.align(tc.id, verse_range=vr, use_cache=True)
    assert alignment["1:1"]["segments"][0]["t"] == "x"

    # Second call should hit cache and not rewrite
    alignment2 = rp.align(tc.id, verse_range=vr, use_cache=True)
    assert alignment2 == alignment
    assert len(writes) == 1


def test_align_raises_when_not_prepared(temp_config, make_translation_file):
    source = make_translation_file(segmented=False)
    tc = temp_config.register_translation("en-test", "Test", "en", source)
    rp = RabtizeProcessor(temp_config, cache=CacheManager(temp_config.cache_dir))

    with pytest.raises(TranslationNotPreparedError):
        rp.align(tc.id, verse_range=VerseRange.parse("1:1"))
