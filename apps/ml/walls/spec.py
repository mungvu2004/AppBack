"""Hợp đồng số của SegFormer tường (B5-02 §C, khối [2]): hằng lát và chuẩn hoá ảnh vào.

Chỉ `numpy` — không `onnxruntime`, `torch`, `cv2` — để ranh giới nhập `apps.ml.walls.spec`
kiểm được ngay cả khi hai gói đó bị chặn (test process con). Các hằng ở đây **là** hợp đồng
với model B6-04a huấn luyện: đổi giá trị là đổi hợp đồng, không phải tinh chỉnh nội bộ.
"""

from typing import Final

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "IMAGE_MEAN",
    "IMAGE_STD",
    "LOGITS_STRIDE",
    "PAD_VALUE",
    "TILE_OVERLAP_PX",
    "TILE_PX",
    "WALL_CLASS",
    "tile_origins",
    "to_model_input",
]

TILE_PX: Final = 1024
TILE_OVERLAP_PX: Final = 128
LOGITS_STRIDE: Final = 4
WALL_CLASS: Final = 1
PAD_VALUE: Final = 255
IMAGE_MEAN: Final = (0.485, 0.456, 0.406)
IMAGE_STD: Final = (0.229, 0.224, 0.225)

_STEP_PX: Final = TILE_PX - TILE_OVERLAP_PX


def tile_origins(length: int) -> tuple[int, ...]:
    """Gốc lát dọc một cạnh dài `length`: `0, 896, 1792, …` tới khi lát chạm mép.

    Lát cuối dời về `max(0, length - TILE_PX)` để luôn phủ hết cạnh (khối [2]); cạnh
    ngắn hơn `TILE_PX` chỉ có một lát tại gốc — `stitch_mask` đệm `PAD_VALUE` cho nó.
    """
    if length <= TILE_PX:
        return (0,)
    origins: list[int] = []
    origin = 0
    while origin + TILE_PX < length:
        origins.append(origin)
        origin += _STEP_PX
    origins.append(length - TILE_PX)
    return tuple(origins)


def to_model_input(tile: NDArray[np.uint8]) -> NDArray[np.float32]:
    """Lát `(T, T, 3)` uint8 → `(1, 3, T, T)` float32, `(x/255 - mean) / std` theo kênh.

    Đúng chuẩn hoá ImageNet mà B6-04a dùng lúc huấn luyện (khối [2]); đổi `IMAGE_MEAN`/
    `IMAGE_STD` là đổi hợp đồng model, không phải tinh chỉnh nội bộ của bước này.
    """
    mean = np.asarray(IMAGE_MEAN, dtype=np.float32)
    std = np.asarray(IMAGE_STD, dtype=np.float32)
    normalized = (tile.astype(np.float32) / 255.0 - mean) / std
    chw = np.transpose(normalized, (2, 0, 1))
    return chw[np.newaxis, ...].astype(np.float32)
