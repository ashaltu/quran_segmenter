from pathlib import Path

import pytest

from quran_segmenter.models import VerseRange
from quran_segmenter.pipeline.lafzize import LafzizeProcessor
from quran_segmenter.utils.cache import CacheManager
from quran_segmenter.exceptions import ServerNotRunningError


def test_lafzize_processor_returns_cached_timestamps(temp_config, tmp_path):
    cache = CacheManager(temp_config.cache_dir)
    processor = LafzizeProcessor(temp_config, cache)
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"audio")
    vr = VerseRange.parse("1:1")

    cached = [
        {"surah": 1, "ayah": 1, "word_index": 1, "start_time": 0.0, "end_time": 0.5}
    ]
    cache.cache_timestamps(audio, str(vr), cached)

    result = processor.process(audio, vr, use_cache=True, start_server=False)
    assert len(result) == 1
    assert result[0].key == (1, 1, 1)


def test_lafzize_processor_calls_api_and_caches(monkeypatch, temp_config, tmp_path):
    cache = CacheManager(temp_config.cache_dir)
    processor = LafzizeProcessor(temp_config, cache)
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"audio")
    vr = VerseRange.parse("1:1")

    processor.server.start = lambda wait=True, timeout=120: True
    processor.server.is_running = lambda: True
    processor.server.get_log = lambda last_n_chars=5000: ""

    class DummyResponse:
        status_code = 200

        def json(self):
            return [{"type": "word", "key": "1:1:1", "start": 0, "end": 1000}]

    monkeypatch.setattr("quran_segmenter.pipeline.lafzize.requests.post", lambda *args, **kwargs: DummyResponse())

    result = processor.process(audio, vr, use_cache=True, start_server=True)
    assert len(result) == 1
    cached = cache.get_cached_timestamps(audio, str(vr))
    assert cached is not None


def test_lafzize_processor_errors_when_server_not_running(temp_config, tmp_path):
    cache = CacheManager(temp_config.cache_dir)
    processor = LafzizeProcessor(temp_config, cache)
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"audio")
    vr = VerseRange.parse("1:1")

    processor.server.is_running = lambda: False
    processor.server.get_log = lambda last_n_chars=5000: "log"

    with pytest.raises(ServerNotRunningError):
        processor.process(audio, vr, use_cache=False, start_server=False)
