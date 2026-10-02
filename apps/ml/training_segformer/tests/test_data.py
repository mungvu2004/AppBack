"""`WallSegDataset`: mảnh cắt, đệm mép, tăng cường, tái lập (khối [8] `test_dataset_crop_augment`).

Không `torch` ở đây: dataset trả mảng numpy, nên test so trực tiếp với `to_model_input` của
B5-02 — nếu hai bên lệch thì model huấn luyện xong sẽ thấy phân bố khác lúc suy luận.
"""

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from apps.ml.training_segformer.data import WallSegDataset
from apps.ml.training_segformer.tests.support import write_split
from apps.ml.walls.spec import PAD_VALUE, to_model_input
from packages.ml_contracts.artifacts import encode_mask
from packages.ml_contracts.synthetic import render_plan
from packages.vision.preprocess import load_raster


def _tiny_sample(data_dir: Path, *, width_px: int, height_px: int) -> None:
    """Một mẫu `train` khổ nhỏ hơn `crop_px`, vẽ bằng `render_plan` rồi cắt về khổ cần."""
    plan = render_plan(0, width_px=800, height_px=600)
    sample = data_dir / "train" / "s0000"
    sample.mkdir(parents=True)
    pixels = np.ascontiguousarray(load_raster(plan.image_png).pixels[:height_px, :width_px])
    mask = np.ascontiguousarray(plan.walls_mask[:height_px, :width_px])
    (sample / "image.png").write_bytes(_png_of(pixels))
    (sample / "walls.png").write_bytes(encode_mask(mask))


def _png_of(pixels: NDArray[np.uint8]) -> bytes:
    """PNG RGB của mảng uint8 — qua `cv2.imencode`, không `PIL.Image.open` (K13)."""
    import cv2

    ok, buffer = cv2.imencode(".png", cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR))
    assert ok
    return bytes(buffer.tobytes())


def test_dataset_crop_augment(tmp_path: Path) -> None:
    """Ảnh nhỏ hơn `crop_px` → đệm `PAD_VALUE`/nhãn 0; cùng `(seed, epoch, index)` → cùng mảnh."""
    _tiny_sample(tmp_path, width_px=100, height_px=80)
    split_dir = tmp_path / "train"
    first = WallSegDataset(split_dir, crop_px=128, seed=7, epoch=1)
    assert len(first) == 1
    image, labels = first[0]
    assert image.shape == (3, 128, 128)
    assert labels.shape == (128, 128)
    assert set(np.unique(labels)) <= {0, 1}

    padded = to_model_input(np.full((128, 128, 3), PAD_VALUE, dtype=np.uint8))[0]
    pad_rows = np.isclose(image, padded).all(axis=0)
    assert pad_rows.any(), "ảnh 100x80 phải có vùng đệm trong mảnh 128"
    assert not labels[pad_rows].any(), "nhãn ở vùng đệm phải là 0"

    again = WallSegDataset(split_dir, crop_px=128, seed=7, epoch=1)[0]
    assert np.array_equal(image, again[0])
    assert np.array_equal(labels, again[1])


def test_dataset_crop_matches_to_model_input(tmp_path: Path) -> None:
    """Đầu vào đúng `to_model_input` trên cùng mảnh uint8; epoch hay seed khác → mảnh khác."""
    write_split(tmp_path, "train", 1, seed=0)
    split_dir = tmp_path / "train"
    image, _ = WallSegDataset(split_dir, crop_px=128, seed=0, epoch=1)[0]
    tile = (image * np.asarray([0.229, 0.224, 0.225], dtype=np.float32)[:, None, None]) + np.asarray(
        [0.485, 0.456, 0.406], dtype=np.float32
    )[:, None, None]
    recovered = np.clip(np.round(np.transpose(tile, (1, 2, 0)) * 255.0), 0, 255).astype(np.uint8)
    assert np.allclose(to_model_input(recovered)[0], image, atol=1e-2)

    other_epoch, _ = WallSegDataset(split_dir, crop_px=128, seed=0, epoch=2)[0]
    other_seed, _ = WallSegDataset(split_dir, crop_px=128, seed=99, epoch=1)[0]
    assert not np.array_equal(image, other_epoch)
    assert not np.array_equal(image, other_seed)
