"""Test hàm dùng chung của `support.py` mà test `gpu` dựa vào (máy không CUDA vẫn chạy được, NO-316)."""

from pathlib import Path

import pytest

from apps.ml.training_segformer import data, trainer
from apps.ml.training_segformer.tests.support import (
    load_pinned_base,
    pinned_for,
    write_split,
    write_tiny_model,
)
from packages.ml_contracts.datasets import SampleMeta


def test_write_split__custom_size(tmp_path: Path) -> None:
    """`width_px`/`height_px` quyết định khổ ảnh, mặt nạ và `meta.json`."""
    (sample_dir,) = write_split(tmp_path, "train", 1, seed=0, width_px=1600, height_px=1200)
    pixels, truth = data.read_sample(sample_dir)
    meta = SampleMeta.model_validate_json((sample_dir / "meta.json").read_text(encoding="utf-8"))
    assert (meta.width_px, meta.height_px) == (1600, 1200)
    assert pixels.shape[:2] == truth.shape == (1200, 1600)


def test_write_split__default_size_unchanged(tmp_path: Path) -> None:
    """Không đối số khổ → vẫn 800x600 như trước."""
    (sample_dir,) = write_split(tmp_path, "train", 1, seed=0)
    _pixels, truth = data.read_sample(sample_dir)
    assert truth.shape == (600, 800)


def test_load_pinned_base__reads_ml_models_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Model nạp từ `ML_MODELS_DIR` (không phải `Path(PINNED[x].name)` tương đối cwd) và qua kiểm checksum."""
    sha = write_tiny_model(tmp_path, "mitB1")
    monkeypatch.setenv("ML_MODELS_DIR", str(tmp_path))
    net = load_pinned_base("mitB1", pinned_for(sha, "mitB1"))
    assert net.config.num_labels == 2
    assert trainer._settings_models_dir() == tmp_path
