"""Dataset vi mô dùng chung của test YOLO (khối [8]): `render_plan` → `image.png` + `objects.json`.

Không `conftest.py` lồng, không `packages/testing` (ngoài `so_huu`): test nhập thẳng module này.
Reporter ghi lại, `train_spec`, `pinned_for` dùng lại của `apps.ml.training_segformer.tests.support`
(chung hợp đồng `TrainReporter`, không chép). Seed 0..5 không giao `EVAL_SET_SEEDS` (100..139, M06).
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Final

from packages.ml_contracts.artifacts import ObjectsResult, objects_to_json
from packages.ml_contracts.datasets import Split
from packages.ml_contracts.synthetic import render_plan

MICRO_WIDTH_PX: Final = 800
MICRO_HEIGHT_PX: Final = 600
"""Khối [8] ghi 640x480 nhưng `render_plan` hỏng ở khổ đó (đo B6-04a, 2026-10-02); 800x600 vẽ được seed 0..5."""
TRAIN_SEEDS: Final = range(4)
VALIDATION_SEEDS: Final = range(4, 6)


def write_objects_split(data_dir: Path, split: Split, seeds: Iterable[int]) -> tuple[Path, ...]:
    """Ghi mỗi seed một mẫu `data_dir/split/s<seed>/{image.png, objects.json}`; trả thư mục mẫu đã sắp."""
    written: list[Path] = []
    for seed in seeds:
        plan = render_plan(seed, width_px=MICRO_WIDTH_PX, height_px=MICRO_HEIGHT_PX)
        target = data_dir / split / f"s{seed:04d}"
        target.mkdir(parents=True)
        (target / "image.png").write_bytes(plan.image_png)
        (target / "objects.json").write_bytes(objects_to_json(ObjectsResult(detections=plan.detections)))
        written.append(target)
    return tuple(written)


def write_micro_dataset(data_dir: Path) -> Path:
    """Seed 0..3 `train`, 4..5 `validation` (khối [8]); không ghi `test/` — trainer không được đọc nó."""
    write_objects_split(data_dir, "train", TRAIN_SEEDS)
    write_objects_split(data_dir, "validation", VALIDATION_SEEDS)
    return data_dir
