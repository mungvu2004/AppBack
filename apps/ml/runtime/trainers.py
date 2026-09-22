"""Dò trainer theo họ: `apps.ml.<module>.trainer.TRAINER` (B6-04a SegFormer, B6-04b YOLO).

Dò một cấp bằng `pkgutil` theo thứ tự tên, như `discover_submodules` của B0-05: thêm
module huấn luyện mới không phải sửa file nào khác. Mọi sai khai báo (thiếu `TRAINER`,
thiếu `family`/`train`, họ lạ, hai trainer một họ) hỏng ngay lúc dò, không im lặng bỏ.
"""

import importlib
import importlib.util
import pkgutil
from collections.abc import Mapping
from types import MappingProxyType
from typing import cast

from packages.ml_contracts.families import TRAINABLE_FAMILIES, TrainableFamily
from packages.ml_contracts.ports import Trainer


def _trainer_of(module_name: str) -> Trainer:
    """`TRAINER` của module, đã kiểm có `family` thuộc họ huấn luyện được và `train` gọi được."""
    module = importlib.import_module(module_name)
    trainer = getattr(module, "TRAINER", None)
    family = getattr(trainer, "family", None)
    if trainer is None or family is None or not callable(getattr(trainer, "train", None)):
        raise RuntimeError(f"{module_name}.TRAINER thiếu family hay train")
    if family not in TRAINABLE_FAMILIES:
        raise RuntimeError(f"{module_name}.TRAINER khai họ lạ: {family!r}")
    return cast("Trainer", trainer)


def discover_trainers(*, package: str = "apps.ml") -> Mapping[TrainableFamily, Trainer]:
    """Họ → trainer, từ mọi `<package>.<gói con>.trainer` có thật; lỗi nhập nổi lên nguyên trạng."""
    root = importlib.import_module(package)
    found: dict[TrainableFamily, Trainer] = {}
    for info in sorted(pkgutil.iter_modules(root.__path__), key=lambda module: module.name):
        name = f"{package}.{info.name}.trainer"
        if not info.ispkg or importlib.util.find_spec(name) is None:
            continue
        trainer = _trainer_of(name)
        if trainer.family in found:
            raise RuntimeError(f"hai trainer cho họ {trainer.family}")
        found[trainer.family] = trainer
    return MappingProxyType(found)
