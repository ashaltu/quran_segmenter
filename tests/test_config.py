import json
from pathlib import Path

import pytest

from quran_segmenter.config import Config


def test_register_translation_copies_and_detects_segmentation(temp_config, make_translation_file):
    source = make_translation_file(segmented=True)

    tc = temp_config.register_translation(
        translation_id="en-test",
        name="Test",
        language_code="en",
        source_file=source,
    )

    copied = temp_config.translations_dir / "en-test.json"
    assert copied.exists()
    assert tc.is_segmented
    assert Path(tc.segmented_file_path) == copied


def test_register_translation_detects_embeddings_and_spans(temp_config, make_translation_file):
    source = make_translation_file(segmented=False)
    emb_file = temp_config.embeddings_dir / "en-test.npz"
    emb_file.write_text("data")
    spans_path = temp_config.embeddings_dir / "spans.npz"
    spans_path.write_text("spans")

    tc = temp_config.register_translation(
        translation_id="en-test",
        name="Test",
        language_code="en",
        source_file=source,
        spans_embeddings_filepath=spans_path,
        segment_embeddings_filepath=emb_file,
    )

    assert tc.embeddings_path == str(emb_file)
    assert temp_config.spans_embeddings_generated
    assert temp_config.spans_embeddings_path == spans_path


def test_get_translation_invalid_raises(temp_config):
    with pytest.raises(ValueError):
        temp_config.get_translation("missing")


def test_detect_existing_assets(temp_config, make_translation_file):
    source = make_translation_file(segmented=False)
    tc = temp_config.register_translation(
        translation_id="en-test",
        name="Test",
        language_code="en",
        source_file=source,
    )

    # Create assets after registration so detect_existing_assets has work to do
    spans_path = temp_config.spans_embeddings_path
    spans_path.parent.mkdir(parents=True, exist_ok=True)
    spans_path.write_text("spans")
    emb_file = temp_config.embeddings_dir / f"{tc.id}.npz"
    emb_file.write_text("segments")

    temp_config.spans_embeddings_generated = False
    temp_config.detect_existing_assets()

    assert temp_config.spans_embeddings_generated
    assert temp_config.translations[tc.id].embeddings_path == str(emb_file)


def test_update_translation_and_persistence(temp_config, make_translation_file, tmp_path):
    source = make_translation_file(segmented=False)
    tc = temp_config.register_translation(
        translation_id="en-test",
        name="Test",
        language_code="en",
        source_file=source,
    )

    temp_config.update_translation(tc.id, is_segmented=True, segmented_file_path=source, embeddings_path=tmp_path / "emb.npz")
    updated = temp_config.get_translation(tc.id)
    assert updated.is_segmented
    assert Path(updated.segmented_file_path) == source
    assert Path(updated.embeddings_path).name == "emb.npz"

    # Persist and reload
    temp_config.save()
    reloaded = Config.load_or_create(temp_config.config_path)
    assert reloaded.translations[tc.id].is_segmented
    assert reloaded.translations[tc.id].embeddings_path.endswith("emb.npz")
