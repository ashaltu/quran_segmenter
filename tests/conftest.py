import json
from pathlib import Path

import pytest

from quran_segmenter.config import Config


@pytest.fixture
def temp_config(tmp_path):
    """
    Create an isolated Config with required paths and minimal resource files.
    """
    base_dir = tmp_path
    data_dir = base_dir / "data"
    cfg = Config(data_dir=data_dir, base_dir=base_dir)

    # Ensure expected external tool locations exist
    cfg.lafzize_dir.mkdir(parents=True, exist_ok=True)
    cfg.rabtize_dir.mkdir(parents=True, exist_ok=True)

    cfg.jumlize_binary = base_dir / "jumlize"
    cfg.jumlize_binary.write_text("#!/bin/sh\n")

    # Minimal words + metadata fixtures
    cfg.qpc_words_file = base_dir / "qpc-hafs-word-by-word.json"
    cfg.qpc_words_file.write_text(
        json.dumps(
            {
                "1:1:1": {"surah": 1, "ayah": 1, "word": 1, "text": "alpha"},
                "1:1:2": {"surah": 1, "ayah": 1, "word": 2, "text": "beta"},
                "1:2:1": {"surah": 1, "ayah": 2, "word": 1, "text": "gamma"},
            }
        )
    )

    cfg.quran_metadata_file = base_dir / "quran-metadata-misc.json"
    cfg.quran_metadata_file.write_text(json.dumps({"1:1": {}, "1:2": {}}))

    return cfg


@pytest.fixture
def make_translation_file(tmp_path):
    """Factory to create translation files with optional segments."""
    def _make(segmented: bool = False, name: str = "translation") -> Path:
        path = tmp_path / f"{name}.json"
        data = {
            "1:1": {"text": "hello world"},
            "1:2": {"text": "second verse"},
        }
        if segmented:
            data["1:1"]["segments"] = [{"t": "hello", "word_range": {"start": 1, "end": 1}}]
            data["1:2"]["segments"] = [{"t": "two", "word_range": {"start": 1, "end": 1}}]
        path.write_text(json.dumps(data))
        return path

    return _make
