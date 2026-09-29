"""Test `apps.ml.walls.spec`: gốc lát, chuẩn hoá ảnh vào, ranh giới nhập (khối [2], [8])."""

import subprocess
import sys

import numpy as np

from apps.ml.walls.spec import IMAGE_MEAN, IMAGE_STD, TILE_PX, tile_origins, to_model_input


def test_tile_origins__short_edge_single_tile() -> None:
    assert tile_origins(600) == (0,)


def test_tile_origins__edge_equals_tile() -> None:
    assert tile_origins(TILE_PX) == (0,)


def test_tile_origins__long_edge_last_shifted() -> None:
    assert tile_origins(2000) == (0, 896, 976)


def test_to_model_input__shape_dtype_value() -> None:
    tile = np.zeros((TILE_PX, TILE_PX, 3), dtype=np.uint8)
    tile[..., 0] = 255
    out = to_model_input(tile)
    assert out.shape == (1, 3, TILE_PX, TILE_PX)
    assert out.dtype == np.float32
    expected_red = (1.0 - IMAGE_MEAN[0]) / IMAGE_STD[0]
    expected_green = (0.0 - IMAGE_MEAN[1]) / IMAGE_STD[1]
    assert np.isclose(out[0, 0, 0, 0], expected_red)
    assert np.isclose(out[0, 1, 0, 0], expected_green)


def test_spec_module__importable_when_onnxruntime_and_torch_blocked() -> None:
    """Ranh giới `apps.ml.walls.spec` chỉ `numpy`: chặn `onnxruntime`, `torch` ở tiến trình con vẫn nhập được."""
    script = "import sys; sys.modules['onnxruntime'] = None; sys.modules['torch'] = None; import apps.ml.walls.spec"
    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
