"""Dữ liệu thử dùng chung của test runner: trainer tí hon CPU, dataset thật trên kho, payload, đọc hàng.

Dataset dựng bằng `render_plan` + `build_manifest` + `put` (B6-03b [3]); không nhập `apps.worker`.
Trainer tí hon không nhập `torch`: ONNX là đồ thị `Identity` dựng bằng `onnx.helper` (BE-00 §9).
"""

import base64
import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from onnx import TensorProto, helper

from apps.ml.training_runner.errors import TrainingStopped
from apps.ml.training_runner.keys import sample_key
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.messaging.redis import SyncRedis, sync_result
from packages.ml_contracts.datasets import ManifestEntry, Split, build_manifest, manifest_sha256, sample_path
from packages.ml_contracts.families import BASE_MODELS, FAMILY_METRIC, TrainableFamily
from packages.ml_contracts.payloads import MetricPoint, TrainJobPayload
from packages.ml_contracts.ports import TrainReporter, TrainResult, TrainSpec
from packages.ml_contracts.synthetic import render_plan
from packages.storage.keys import dataset_object
from packages.storage.port import ObjectStorage

# Nhập lại (không định nghĩa lại, R-02): test_runner/test_runtime nhập tên này từ đây.
from packages.testing.fixtures.ml_settings import ml_settings_cache as ml_settings_cache

TINY_METRIC_VALUE: Final = 0.5


def tiny_onnx() -> bytes:
    """ONNX hợp lệ nhỏ nhất: `y = Identity(x)`, `ir_version=10`, opset 17, không tensor ngoài."""
    graph = helper.make_graph(
        [helper.make_node("Identity", ["x"], ["y"])],
        "tiny",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])],
    )
    model = helper.make_model(graph, ir_version=10, opset_imports=[helper.make_opsetid("", 17)])
    return bytes(model.SerializeToString())


@dataclass
class TinyTrainer:
    """Trainer CPU tí hon: mỗi epoch `heartbeat` → `metric` → `log`, hỏi `cancelled()` cuối epoch.

    `on_epoch` chạy cuối mỗi epoch, trước khi hỏi huỷ: test chèn huỷ/vượt giờ "giữa epoch" qua nó.
    `ignore_cancel=True` bỏ qua huỷ và ngủ `stall_s` mỗi epoch (test luồng canh).
    """

    family: TrainableFamily = "wallSegmentation"
    ignore_cancel: bool = False
    stall_s: float = 0.0
    on_epoch: list[Callable[[], None]] = field(default_factory=list)
    calls: list[TrainSpec] = field(default_factory=list)

    def train(self, spec: TrainSpec, data_dir: Path, out_dir: Path, reporter: TrainReporter) -> TrainResult:
        """Chạy `spec.epochs` epoch giả, ghi `out_dir/model.onnx`, trả đúng một số đo của họ."""
        self.calls.append(spec)
        metric = FAMILY_METRIC[self.family]
        for epoch in range(1, spec.epochs + 1):
            reporter.heartbeat(epoch)
            point = {"step": epoch - 1, "epoch": epoch, "split": "validation", metric: TINY_METRIC_VALUE}
            reporter.metric(MetricPoint.model_validate({**point, "recorded_at_ms": int(time.time() * 1000)}))
            params = {"epoch": epoch, "loss": 0.1, "metric": metric, "value": TINY_METRIC_VALUE}
            reporter.log("info", "training_epoch_finished", params)
            for hook in self.on_epoch:
                hook()
            self._maybe_stop(reporter)
        onnx_path = out_dir / "model.onnx"
        onnx_path.write_bytes(tiny_onnx())
        return TrainResult(onnx_path=onnx_path, metrics={metric: TINY_METRIC_VALUE})

    def _maybe_stop(self, reporter: TrainReporter) -> None:
        """Nghĩa vụ trainer (BE-00 §9): huỷ → `TrainingStopped`; bản "lì" ngủ thay vì dừng."""
        if self.ignore_cancel:
            time.sleep(self.stall_s)
        elif reporter.cancelled():
            raise TrainingStopped


TRAINER: Final = TinyTrainer()
"""Đích của `TRAINING_TRAINER_OVERRIDE=apps.ml.training_runner.tests.support:TRAINER` (J01_smoke)."""


@dataclass(frozen=True, slots=True)
class Dataset:
    """Phiên bản dataset đã ghi lên kho: id, SHA-256 manifest, tổng byte mẫu, các mục manifest (đã sắp)."""

    version_id: str
    manifest_sha256: str
    total_bytes: int
    entries: tuple[ManifestEntry, ...]


async def put_dataset(storage: ObjectStorage, *, train: int = 2, validation: int = 1) -> Dataset:
    """Ghi `image.png` của `train` + `validation` mẫu tổng hợp và `manifest.jsonl` theo bố cục B6-02."""
    version_id = new_id("dsv", SystemClock())
    entries: list[ManifestEntry] = []
    splits: tuple[tuple[Split, int], ...] = (("train", train), ("validation", validation))
    for split, count in splits:
        for index in range(count):
            data = render_plan(index).image_png
            path = sample_path(split, f"s{index}", "image.png")
            await put_bytes(storage, sample_key(version_id, path), data)
            entries.append(ManifestEntry(path=path, sha256=sha256_hex(data), bytes=len(data)))
    manifest = build_manifest(entries)
    await put_bytes(storage, dataset_object(version_id, "manifest.jsonl"), manifest)
    ordered = tuple(sorted(entries, key=lambda entry: entry.path))
    return Dataset(version_id, manifest_sha256(manifest), sum(entry.bytes for entry in entries), ordered)


async def read_object(storage: ObjectStorage, key: str) -> bytes:
    """Toàn bộ byte của một object (test đọc lại để so sha, kiểm ONNX) — cổng kho, không đụng đĩa."""
    chunks = [chunk async for chunk in storage.open_read(key)]
    return b"".join(chunks)


async def put_bytes(storage: ObjectStorage, key: str, data: bytes) -> None:
    """Ghi (đè) một object thử, trần đúng cỡ của nó — test M02 ghi lại mẫu lệch một byte bằng hàm này."""
    await storage.put(key, data, content_type="application/octet-stream", max_bytes=len(data) + 1)


def sha256_hex(data: bytes) -> str:
    """SHA-256 hex của byte."""
    return hashlib.sha256(data).hexdigest()


def train_payload(
    dataset: Dataset, *, family: TrainableFamily = "wallSegmentation", epochs: int = 1
) -> TrainJobPayload:
    """Payload `ml.training.runner.start` hợp lệ cho `dataset`, `job_id` mới mỗi lần gọi."""
    return TrainJobPayload(
        job_id=new_id("job", SystemClock()),
        family=family,
        base_model=BASE_MODELS[family][0],
        epochs=epochs,
        dataset_version_id=dataset.version_id,
        manifest_sha256=dataset.manifest_sha256,
    )


type Message = tuple[str, dict[str, object]]


def queued_messages(client: SyncRedis, queue: str = "default") -> list[Message]:
    """`(tên task, payload)` mọi thông điệp trên hàng, theo thứ tự gửi (`LRANGE`, BE-00 §7 "Test task").

    Như `queued_payloads` (B0-05) nhưng giữ tên task: J01 đếm bốn loại thông điệp của cầu nối.
    kombu `LPUSH` thông điệp mới vào đầu danh sách, nên đảo lại để có thứ tự gửi.
    """
    messages: list[Message] = []
    for raw in reversed(sync_result(client.lrange(queue, 0, -1), list)):
        envelope = json.loads(raw)
        args, _kwargs, _embed = json.loads(base64.b64decode(envelope["body"]))
        messages.append((envelope["headers"]["task"], args[0]))
    return messages


def for_job(messages: list[Message], job_id: str) -> list[Message]:
    """Chỉ thông điệp của `job_id` (broker là fixture phiên, test khác có thể để lại thông điệp)."""
    return [(task, payload) for task, payload in messages if payload.get("job_id") == job_id]
