import json
from pathlib import Path

from quran_segmenter.utils.cache import CacheManager


def test_cache_timestamps_roundtrip(tmp_path):
    cache = CacheManager(tmp_path)
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"audio-bytes")

    data = [{"surah": 1, "ayah": 1, "word_index": 1, "start_time": 0.1, "end_time": 0.2}]
    cache_path = cache.cache_timestamps(audio, "1:1", data)

    assert cache_path.exists()
    loaded = cache.get_cached_timestamps(audio, "1:1")
    assert loaded == data


def test_cache_alignment_roundtrip_and_clear(tmp_path):
    cache = CacheManager(tmp_path)
    alignment = {"1:1": {"segments": []}}
    path = cache.cache_alignment("en-test", "1:1", alignment)
    assert path.exists()
    loaded = cache.get_cached_alignment("en-test", "1:1")
    assert loaded == alignment

    cache.clear("alignment")
    assert cache.get_cached_alignment("en-test", "1:1") is None


def test_clear_all_removes_entries(tmp_path):
    cache = CacheManager(tmp_path)
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"audio-bytes")
    cached_path = cache.cache_timestamps(audio, "1:1", [{"surah": 1}])

    cache.clear()
    assert not cached_path.exists()
    # Index file remains but cached content should be gone
    remaining = list(tmp_path.iterdir())
    assert all(p.name == "index.json" or p == audio for p in remaining)
