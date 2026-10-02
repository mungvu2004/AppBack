"""Đọc dataset tách tường theo bố cục B5-01 `{split}/{sample_id}/image.png|walls.png|meta.json`.

Dữ liệu tải từ kho coi như không tin (khối [7]): ảnh chỉ qua `load_raster` có trần điểm ảnh
(K13), mặt nạ qua `decode_mask`; mọi lỗi giải mã hay lệch khổ là `DATASET_SAMPLE_INVALID`.
`sample_id` chỉ vào log máy chủ, không vào log job (bảng BE-00 §9 không có khoá nhận nó).

`WallSegDataset` giữ cả split trong RAM dạng uint8 và trả mảng numpy — `default_collate` của
`DataLoader` tự đổi sang tensor, nên module này không cần `torch` (`metrics`/`loop` mới cần).
"""

import logging
from pathlib import Path
from typing import Final

import numpy as np
from numpy.typing import NDArray

from apps.ml.training_segformer.errors import DATASET_SAMPLE_INVALID
from apps.ml.walls.spec import PAD_VALUE, WALL_CLASS, to_model_input
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.artifacts import decode_mask
from packages.ml_contracts.ports import RgbImage
from packages.vision.preprocess import DEFAULT_MAX_PIXELS, VisionError, load_raster

__all__ = ["WallSegDataset", "read_sample", "sample_dirs"]

_log: Final = logging.getLogger(__name__)


def sample_dirs(split_dir: Path) -> tuple[Path, ...]:
    """Thư mục mẫu của một split, sắp theo tên (tái lập); split không tồn tại → rỗng."""
    if not split_dir.is_dir():
        return ()
    return tuple(sorted(child for child in split_dir.iterdir() if child.is_dir()))


def read_sample(sample_dir: Path, *, max_pixels: int = DEFAULT_MAX_PIXELS) -> tuple[RgbImage, NDArray[np.bool_]]:
    """Ảnh RGB `(H, W, 3)` uint8 (mảng của `ports.RgbImage`, như `stitch_mask` nhận) và mặt nạ `(H, W)`, cùng khổ.

    Thiếu tệp, PNG hỏng, vượt `max_pixels`, mặt nạ khác khổ → `PermanentError(DATASET_SAMPLE_INVALID)`.
    """
    try:
        pixels = load_raster((sample_dir / "image.png").read_bytes(), max_pixels=max_pixels).pixels
        height, width = pixels.shape[:2]
        mask = decode_mask((sample_dir / "walls.png").read_bytes(), width_px=width, height_px=height)
    except (OSError, VisionError, ValueError) as exc:
        _log.warning("mẫu hỏng %s: %s", sample_dir.name, type(exc).__name__)
        raise PermanentError(DATASET_SAMPLE_INVALID) from exc
    return pixels, mask


def _random_crop(
    pixels: RgbImage, mask: NDArray[np.bool_], crop_px: int, rng: np.random.Generator
) -> tuple[NDArray[np.uint8], NDArray[np.int64]]:
    """Mảnh `crop_px` tại gốc ngẫu nhiên; cạnh thiếu đệm `PAD_VALUE` (ảnh) và lớp 0 (nhãn).

    Ảnh nhỏ hơn `crop_px` vẫn ra đúng khổ mảnh — mép đệm giống `stitch_mask` lúc suy luận,
    nên model không thấy phân bố lạ ở biên. Đệm bằng `np.full` + gán lát, không vòng điểm ảnh (K28).
    """
    height, width = pixels.shape[:2]
    top = int(rng.integers(0, max(height - crop_px, 0) + 1))
    left = int(rng.integers(0, max(width - crop_px, 0) + 1))
    view_h, view_w = min(crop_px, height - top), min(crop_px, width - left)
    tile = np.full((crop_px, crop_px, 3), PAD_VALUE, dtype=np.uint8)
    labels = np.zeros((crop_px, crop_px), dtype=np.int64)
    tile[:view_h, :view_w] = pixels[top : top + view_h, left : left + view_w]
    labels[:view_h, :view_w] = mask[top : top + view_h, left : left + view_w] * WALL_CLASS
    return tile, labels


def _augment(
    tile: NDArray[np.uint8], labels: NDArray[np.int64], rng: np.random.Generator
) -> tuple[NDArray[np.uint8], NDArray[np.int64]]:
    """Lật ngang, lật dọc, xoay 90° `k` lần — cùng phép cho ảnh và nhãn, nếu không nhãn lệch ảnh.

    Mặt bằng không có hướng ưu tiên, nên cả tám phép của nhóm nhị diện đều là mẫu hợp lệ.
    `np.flip`/`np.rot90` trả khung nhìn; người gọi cần mảng liền mạch thì tự `ascontiguousarray`.
    """
    if rng.random() < 0.5:
        tile, labels = np.flip(tile, axis=1), np.flip(labels, axis=1)
    if rng.random() < 0.5:
        tile, labels = np.flip(tile, axis=0), np.flip(labels, axis=0)
    turns = int(rng.integers(0, 4))
    return np.rot90(tile, turns), np.rot90(labels, turns)


class WallSegDataset:
    """Một split đã đọc sẵn, mỗi lần lấy mẫu trả một mảnh `crop_px` đã tăng cường (khối [6]).

    Đọc mọi mẫu **một lần lúc dựng**: vòng huấn luyện gọi `__getitem__` nhiều lần mỗi epoch,
    giải PNG lại mỗi lần sẽ chậm hơn huấn luyện. RNG dựng từ `(seed, epoch, index)` nên lượt
    chạy tái lập được (M06) mà không cần trạng thái dùng chung giữa các tiến trình `DataLoader`.

    `ponytail:` trần RAM ≈ Σ (H·W·4 byte) của split — dataset vi mô và dataset mặt bằng thật
    (vài trăm ảnh) vừa; split hàng chục nghìn ảnh thì phải chuyển sang đọc lười + cache đĩa.
    """

    def __init__(self, split_dir: Path, *, crop_px: int, seed: int, epoch: int) -> None:
        """Đọc mọi mẫu của split (`DATASET_SAMPLE_INVALID` nếu có mẫu hỏng) rồi giữ trong RAM."""
        self._samples = tuple(read_sample(sample_dir) for sample_dir in sample_dirs(split_dir))
        self._crop_px = crop_px
        self._seed = seed
        self._epoch = epoch

    def __len__(self) -> int:
        """Số mẫu của split — `DataLoader` chia lô theo nó."""
        return len(self._samples)

    def __getitem__(self, index: int) -> tuple[NDArray[np.float32], NDArray[np.int64]]:
        """Đầu vào `(3, crop, crop)` float32 đúng `to_model_input` của B5-02 và nhãn `(crop, crop)` int64.

        Trả mảng numpy, không tensor: `default_collate` tự đổi sang tensor, nhờ đó module này
        không nhập `torch` (`trainer` nhập `sample_dirs` từ đây lúc kiểm split rỗng).
        """
        rng = np.random.default_rng((self._seed, self._epoch, index))
        pixels, mask = self._samples[index]
        tile, labels = _augment(*_random_crop(pixels, mask, self._crop_px, rng), rng)
        return to_model_input(np.ascontiguousarray(tile))[0], np.ascontiguousarray(labels)
