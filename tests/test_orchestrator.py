from pathlib import Path

import pytest

from quran_segmenter.models import ProcessingResult, VerseSegments, WordTimestamp
from quran_segmenter.pipeline.orchestrator import QuranSegmenterPipeline
from quran_segmenter.exceptions import TranslationNotPreparedError


class _StubLafzize:
    def __init__(self):
        self.calls = []

    def process(self, audio_path, verse_range, use_cache=True, start_server=True):
        self.calls.append((audio_path, verse_range, use_cache, start_server))
        return [
            WordTimestamp(surah=1, ayah=1, word_index=1, start_time=0.0, end_time=0.5),
            WordTimestamp(surah=1, ayah=1, word_index=2, start_time=0.5, end_time=1.0),
        ]

    def stop_server(self):
        self.calls.append(("stop",))


class _StubRabtize:
    def __init__(self, ready=True):
        self.ready = ready
        self.align_calls = []

    def is_ready(self, translation_id):
        return (self.ready, [] if self.ready else ["missing"])

    def align(self, translation_id, verse_range=None, use_cache=True):
        self.align_calls.append((translation_id, verse_range, use_cache))
        return {"1:1": {"segments": [{"word_range": {"start": 1, "end": 2}, "t": "hello"}]}}


class _StubAssembler:
    def __init__(self):
        self.calls = []

    def assemble(self, verse_range, timestamps, alignment):
        self.calls.append((verse_range, timestamps, alignment))
        result = ProcessingResult(verse_range=verse_range)
        result.verses["1:1"] = VerseSegments(verse_key="1:1", segments=[])
        return result


def _prep_ready_translation(cfg):
    trans_file = cfg.translations_dir / "en.json"
    trans_file.write_text('{"1:1": {"text": "x"}}')
    cfg.register_translation("en", "Test", "en", trans_file, copy_to_data_dir=False)
    cfg.update_translation("en", is_segmented=True)
    spans = cfg.spans_embeddings_path
    spans.parent.mkdir(parents=True, exist_ok=True)
    spans.write_text("spans")
    emb = cfg.embeddings_dir / "en.npz"
    emb.write_text("segments")
    cfg.update_translation("en", embeddings_path=emb)
    return trans_file


def test_process_calls_components(monkeypatch, temp_config, tmp_path):
    _prep_ready_translation(temp_config)
    pipeline = QuranSegmenterPipeline(config=temp_config)
    pipeline._lafzize = _StubLafzize()
    pipeline._rabtize = _StubRabtize(ready=True)
    pipeline._assembler = _StubAssembler()

    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"audio")

    result = pipeline.process(audio, "1:1", "en", output_path=None, use_cache=True, start_server=False)

    assert isinstance(result, ProcessingResult)
    assert pipeline.lafzize.calls[0][0] == audio
    assert pipeline.rabtize.align_calls[0][0] == "en"
    assert pipeline.assembler.calls


def test_process_raises_when_not_ready(monkeypatch, temp_config, tmp_path):
    _prep_ready_translation(temp_config)
    pipeline = QuranSegmenterPipeline(config=temp_config)
    pipeline._rabtize = _StubRabtize(ready=False)

    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"audio")

    with pytest.raises(TranslationNotPreparedError):
        pipeline.process(audio, "1:1", "en")


def test_list_translations_reports_status(monkeypatch, temp_config, make_translation_file):
    source = make_translation_file(segmented=True)
    tc = temp_config.register_translation("en", "Test", "en", source)
    pipeline = QuranSegmenterPipeline(config=temp_config)
    pipeline._rabtize = _StubRabtize(ready=True)

    translations = pipeline.list_translations()
    entry = translations[0]
    assert entry["id"] == tc.id
    assert entry["ready_for_processing"]
