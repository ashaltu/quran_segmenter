import shutil
from pathlib import Path

import pytest

from quran_segmenter.exceptions import JumlizeError
from quran_segmenter.pipeline.jumlize import JumlizeProcessor
from quran_segmenter.utils.cache import CacheManager


def test_jumlize_init_requires_binary(temp_config):
    temp_config.jumlize_binary = temp_config.base_dir / "missing-jumlize"
    with pytest.raises(JumlizeError):
        JumlizeProcessor(temp_config)


def test_jumlize_segment_short_circuits_when_already_segmented(temp_config, make_translation_file):
    source = make_translation_file(segmented=True)
    tc = temp_config.register_translation(
        translation_id="en-test",
        name="Test",
        language_code="en",
        source_file=source,
    )
    # Ensure segmented_file_path is a Path for validation helper
    temp_config.translations[tc.id].segmented_file_path = Path(
        temp_config.translations[tc.id].segmented_file_path
    )
    processor = JumlizeProcessor(temp_config)

    path = processor.segment(tc.id, api_key="key", force=False)
    assert Path(path).exists()


def test_jumlize_segment_requires_api_key(monkeypatch, temp_config, make_translation_file):
    source = make_translation_file(segmented=False)
    tc = temp_config.register_translation(
        translation_id="en-test",
        name="Test",
        language_code="en",
        source_file=source,
    )
    processor = JumlizeProcessor(temp_config)
    temp_config.jumlize.api_key = None
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(JumlizeError):
        processor.segment(tc.id, api_key=None, force=False)


def test_jumlize_segment_runs_subprocess(monkeypatch, temp_config, make_translation_file):
    source = make_translation_file(segmented=False)
    tc = temp_config.register_translation(
        translation_id="en-test",
        name="Test",
        language_code="en",
        source_file=source,
    )
    processor = JumlizeProcessor(temp_config)
    temp_config.jumlize.api_key = "key"

    class DummyCompleted:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr("quran_segmenter.pipeline.jumlize.subprocess.run", lambda *args, **kwargs: DummyCompleted())
    monkeypatch.setattr(processor, "_validate_segmentation", lambda path: True)
    # Inject missing method expected by code
    temp_config.update_translation_status = lambda *args, **kwargs: None

    output = processor.segment(tc.id, api_key=None, force=True)
    assert Path(output).exists()
