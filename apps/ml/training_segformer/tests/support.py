"""Dữ liệu thử dùng chung của test SegFormer: model tí hon, bản ghim tiêm, dataset vi mô, reporter ghi lại.

Không `conftest.py` lồng (CLAUDE.md cấm), không `packages/testing` (ngoài `so_huu`): test nhập
thẳng module này. Model tí hon dựng bằng `transformers` thật trong test, không commit trọng số
(khối [5]); dataset vẽ bằng `render_plan` (B5-01) theo bố cục `{split}/{sample_id}/…`.
"""

import dataclasses
import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Literal

from packages.ml_contracts.artifacts import encode_mask
from packages.ml_contracts.datasets import SampleMeta, Split
from packages.ml_contracts.families import TrainableFamily
from packages.ml_contracts.payloads import MetricPoint
from packages.ml_contracts.pinned import PINNED, PinnedWeights
from packages.ml_contracts.ports import LogParam, TrainSpec
from packages.ml_contracts.synthetic import render_plan

if TYPE_CHECKING:
    from transformers import SegformerForSemanticSegmentation

    from apps.ml.walls.segformer import SegformerOnnxSegmenter

MICRO_WIDTH_PX: Final = 800
MICRO_HEIGHT_PX: Final = 600
"""Khối [8] ghi 640x480 nhưng `render_plan` hỏng ở khổ đó (đo 2026-10-02); 800x600 vẽ được mọi seed, vẫn một lát."""
type LogCall = tuple[Literal["info", "warning", "error"], str, Mapping[str, LogParam]]


def write_tiny_model(models_dir: Path, name: str = "mitB0", *, seed: int = 0) -> str:
    """Ghi model tí hon `save_pretrained(safe_serialization=True)` vào `models_dir/name`; trả SHA-256 safetensors.

    Bố cục giống `pinned fetch` (B5-01): `DIR/<name>/model.safetensors` + `config.json`. Cấu hình tí hon
    của khối [8] "Dựng chung" — đủ nhỏ cho 1 epoch CPU < 120 s.
    """
    import torch
    from transformers import SegformerConfig, SegformerForSemanticSegmentation

    torch.manual_seed(seed)
    config = SegformerConfig(
        depths=[1, 1, 1, 1], hidden_sizes=[8, 16, 32, 64], num_attention_heads=[1, 1, 1, 1], decoder_hidden_size=32
    )
    config.num_labels = 2
    target = models_dir / name
    model = SegformerForSemanticSegmentation(config)  # type: ignore[no-untyped-call]  # transformers không chú kiểu
    model.save_pretrained(target, safe_serialization=True)
    return hashlib.sha256((target / "model.safetensors").read_bytes()).hexdigest()


def pinned_for(sha256: str, name: str = "mitB0") -> Mapping[str, PinnedWeights]:
    """`PINNED` với `source_sha256` của `name` thay bằng SHA thật của tệp tí hon (tiêm vào trainer)."""
    patched = dataclasses.replace(PINNED[name], source_sha256=sha256)
    return MappingProxyType({**PINNED, name: patched})


def write_pinned_tiny_model(models_dir: Path, name: str = "mitB0") -> Mapping[str, PinnedWeights]:
    """Ghi model tí hon rồi trả bản ghim có SHA thật của nó — hai bước luôn đi cùng nhau.

    Mọi test cần một model nạp được đều dùng cặp này; tách riêng chỉ cần thiết cho ca checksum
    lệch (test tự gọi `pinned_for` với SHA khác).
    """
    return pinned_for(write_tiny_model(models_dir, name), name)


def onnx_segmenter(onnx_path: Path) -> "SegformerOnnxSegmenter":
    """ONNX đã xuất → `SegformerOnnxSegmenter`: khẳng định hợp đồng vào/ra của B5-02 còn đúng.

    `onnxruntime` nhập trong hàm để nhập `support` không kéo nó vào mọi test của gói.
    """
    import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed

    from apps.ml.walls.segformer import SegformerOnnxSegmenter

    return SegformerOnnxSegmenter(ort.InferenceSession(onnx_path.read_bytes(), providers=["CPUExecutionProvider"]))


def write_split(
    data_dir: Path,
    split: Split,
    count: int,
    *,
    seed: int = 0,
    width_px: int = MICRO_WIDTH_PX,
    height_px: int = MICRO_HEIGHT_PX,
) -> tuple[Path, ...]:
    """Ghi `count` mẫu `render_plan` khổ `width_px` x `height_px` (mặc định 800x600) vào `data_dir/split/s<seed+i>`."""
    written: list[Path] = []
    for index in range(count):
        plan = render_plan(seed + index, width_px=width_px, height_px=height_px)
        sample_id = f"s{seed + index:04d}"
        target = data_dir / split / sample_id
        target.mkdir(parents=True)
        (target / "image.png").write_bytes(plan.image_png)
        (target / "walls.png").write_bytes(encode_mask(plan.walls_mask))
        meta = SampleMeta(
            sample_id=sample_id,
            group_key=f"synthetic:{seed + index}",
            width_px=width_px,
            height_px=height_px,
            mm_per_px=plan.mm_per_px,
            source="synthetic",
        )
        (target / "meta.json").write_text(meta.model_dump_json(), encoding="utf-8")
        written.append(target)
    return tuple(written)


def load_pinned_base(
    base_model: str, pinned: Mapping[str, PinnedWeights] = PINNED
) -> "SegformerForSemanticSegmentation":
    """Nạp `base_model` từ `ML_MODELS_DIR` thật (đường mà `trainer.train` dùng), kiểm checksum theo `pinned`.

    Dùng cho test `gpu`: `PinnedWeights.name` là tên bản ghim chứ không phải đường dẫn (NO-316).
    """
    from apps.ml.training_segformer import model as segformer_model
    from apps.ml.training_segformer import trainer

    return segformer_model.load_pretrained(trainer._settings_models_dir(), base_model, pinned)


def write_dataset(data_dir: Path, *, train: int = 4, validation: int = 2) -> Path:
    """Dataset vi mô của khối [8]: `train` + `validation` mẫu, seed không trùng giữa hai split."""
    write_split(data_dir, "train", train, seed=0)
    write_split(data_dir, "validation", validation, seed=1000)
    return data_dir


def train_spec(
    *,
    family: TrainableFamily = "wallSegmentation",
    base_model: str = "mitB0",
    epochs: int = 1,
    seed: int = 0,
) -> TrainSpec:
    """`TrainSpec` CPU cho test; mặc định 1 epoch `mitB0` seed 0 (khối [8] "Dựng chung")."""
    return TrainSpec(job_id="job_test", family=family, base_model=base_model, epochs=epochs, device="cpu", seed=seed)


@dataclass
class RecordingReporter:
    """`TrainReporter` giả: ghi mọi lời gọi; mỗi điểm số đo giải lại bằng `MetricPoint` (khối [8]).

    `cancel_when(n)` nhận số lần `cancelled()` đã được hỏi (tính cả lần này, từ 1) → đúng thì báo huỷ.
    """

    cancel_when: Callable[[int], bool] = lambda _calls: False
    heartbeats: list[int] = field(default_factory=list)
    metrics: list[MetricPoint] = field(default_factory=list)
    logs: list[LogCall] = field(default_factory=list)
    cancel_checks: int = 0

    def heartbeat(self, epoch: int) -> None:
        """Ghi một nhịp tim."""
        self.heartbeats.append(epoch)

    def metric(self, point: MetricPoint) -> None:
        """Ghi điểm sau khi giải lại qua schema — điểm sai luật làm test hỏng ngay ở đây."""
        self.metrics.append(MetricPoint.model_validate(point.model_dump()))

    def log(self, level: Literal["info", "warning", "error"], template: str, params: Mapping[str, LogParam]) -> None:
        """Ghi một dòng log job (bản sao `params`)."""
        self.logs.append((level, template, dict(params)))

    def cancelled(self) -> bool:
        """Đếm lần hỏi rồi hỏi `cancel_when`."""
        self.cancel_checks += 1
        return self.cancel_when(self.cancel_checks)
