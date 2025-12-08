import json
from types import SimpleNamespace

import pytest

from quran_segmenter import cli


class DummyResult:
    def __init__(self, warnings=None):
        self.verses = {"1:1": SimpleNamespace(segments=[1, 2])}
        self.warnings = warnings or []

    def to_dict(self):
        return {"1:1": [{"start": 0, "end": 1}]}


class DummyPipeline:
    def __init__(self):
        self.calls = []
        self.cleanup_called = 0
        self.jumlize = SimpleNamespace(get_segmentation_status=lambda translation_id: {"is_segmented": True, "segmented_file": "file"})
        self.rabtize = SimpleNamespace(is_ready=lambda translation_id: (True, []))

    def register_translation(self, **kwargs):
        self.calls.append(("register", kwargs))

    def list_translations(self):
        return [
            {"id": "en", "language": "en", "ready_for_processing": True, "missing": [], "is_segmented": True, "has_embeddings": True, "name": "Test"}
        ]

    def prepare_translation(self, **kwargs):
        self.calls.append(("prepare", kwargs))
        return {"steps": {"segmentation": "done"}, "ready": True}

    def process(self, **kwargs):
        self.calls.append(("process", kwargs))
        return DummyResult()

    def cleanup(self):
        self.cleanup_called += 1


def test_cmd_register_invokes_pipeline(monkeypatch, tmp_path, capsys):
    pipeline = DummyPipeline()
    monkeypatch.setattr(cli, "QuranSegmenterPipeline", lambda: pipeline)

    args = SimpleNamespace(
        id="en",
        file=str(tmp_path / "file.json"),
        name="Name",
        language="en",
        spans_embeddings_filepath=None,
        segment_embeddings_filepath=None,
    )
    cli.cmd_register(args)

    assert pipeline.calls[0][0] == "register"


def test_cmd_list_outputs_translations(monkeypatch, capsys):
    pipeline = DummyPipeline()
    monkeypatch.setattr(cli, "QuranSegmenterPipeline", lambda: pipeline)

    cli.cmd_list(SimpleNamespace())
    out = capsys.readouterr().out
    assert "Registered Translations" in out
    assert "en" in out


def test_cmd_prepare_calls_pipeline_and_cleanup(monkeypatch, capsys):
    pipeline = DummyPipeline()
    monkeypatch.setattr(cli, "QuranSegmenterPipeline", lambda: pipeline)

    args = SimpleNamespace(translation="en", api_key=None, skip_segmentation=False, skip_embeddings=False, force=False)
    cli.cmd_prepare(args)

    assert pipeline.calls[0][0] == "prepare"
    assert pipeline.cleanup_called == 1


def test_cmd_process_prints_output(monkeypatch, capsys):
    pipeline = DummyPipeline()
    monkeypatch.setattr(cli, "QuranSegmenterPipeline", lambda: pipeline)

    args = SimpleNamespace(
        audio="audio.mp3",
        verses="1:1",
        translation="en",
        output=None,
        no_cache=False,
        start_server=False,
    )
    cli.cmd_process(args)
    out = capsys.readouterr().out
    assert "Processed" in out or "Output:" in out
    assert pipeline.cleanup_called == 1


def test_cmd_status_with_translation(monkeypatch, capsys):
    pipeline = DummyPipeline()
    monkeypatch.setattr(cli, "QuranSegmenterPipeline", lambda: pipeline)

    args = SimpleNamespace(translation="en")
    cli.cmd_status(args)
    out = capsys.readouterr().out
    assert "Translation: en" in out


def test_cmd_clear_cache(monkeypatch, temp_config, capsys):
    monkeypatch.setattr(cli, "get_config", lambda: temp_config)
    args = SimpleNamespace(category=None)
    cli.cmd_clear_cache(args)
    out = capsys.readouterr().out
    assert "Cache cleared" in out
