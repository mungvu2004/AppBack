"""Task `pipeline.build.run` (B5-05 [6] "Task"): đọc artifact ML, dựng `layer.json`, báo B5-06c.

Task không tự kiểm lượt chạy còn hiệu lực — chưa có bảng lượt chạy (B5-05 [1]); B5-06c kiểm
dưới khoá dòng khi nhận `pipeline.orchestrate.step_done`. Idempotent qua `stat(layer_key)`
(J06): thấy artifact đã có thì bỏ qua việc dựng lại, chỉ báo lại kết quả cũ.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Final

from apps.worker.pipeline_build.artifacts import input_key, layer_key
from apps.worker.pipeline_build.build import build_layer
from apps.worker.pipeline_build.errors import (
    PIPELINE_ARTIFACT_INVALID,
    PIPELINE_ARTIFACT_MISSING,
    PIPELINE_BUILD_INVALID,
)
from apps.worker.pipeline_build.settings import get_pipeline_build_settings
from packages.core.clock import SystemClock
from packages.messaging.celery_app import send_task
from packages.messaging.payloads.pipeline import BuildStepPayload
from packages.messaging.redis import ProcessLocal
from packages.messaging.tasks import PermanentError, define_task
from packages.ml_contracts.artifacts import (
    ObjectsResult,
    TextResult,
    WallsResult,
    objects_from_json,
    text_from_json,
    walls_from_json,
)
from packages.ml_contracts.payloads import StepResultPayload
from packages.storage.port import ObjectStorage, read_all_capped

_log: Final = logging.getLogger(__name__)

STEP_DONE_TASK: Final = "pipeline.orchestrate.step_done"
_STEP: Final = "spatialDataBuild"


@dataclass(frozen=True, slots=True)
class BuildContext:
    """Tài nguyên dùng chung của tiến trình worker cho bước dựng."""

    storage: ObjectStorage


def _build_context() -> BuildContext:
    """Kho thật dựng từ biến môi trường; `create_storage`, `get_storage_settings` nhập trễ (K22)."""
    from packages.storage.factory import create_storage
    from packages.storage.settings import get_storage_settings

    return BuildContext(storage=create_storage(get_storage_settings(), None, SystemClock()))


_CONTEXT: Final = ProcessLocal[BuildContext](_build_context)


def build_context() -> BuildContext:
    """Ngữ cảnh của tiến trình, dựng lười ở lần gọi đầu (và lại sau `fork`); test vá bằng kho tạm."""
    return _CONTEXT.get()


def reset_build_context() -> None:
    """Chỉ cho test: quên ngữ cảnh đã nhớ giữa các lượt (URL kho đổi giữa các lượt test)."""
    _CONTEXT.reset()


def _check_run_prefix(payload: BuildStepPayload) -> None:
    """Kiểm lại `run_prefix` như B5-05 [2] (BuildStepPayload đã kiểm lúc giải, đây là phòng thủ kép)."""
    suffix = f"/runs/{payload.run_id}/"
    segments = payload.run_prefix.split("/")
    ok = payload.run_prefix.startswith("projects/") and payload.run_prefix.endswith(suffix) and ".." not in segments
    if not ok:
        raise PermanentError(PIPELINE_ARTIFACT_INVALID)


async def _read_artifact(storage: ObjectStorage, key: str, max_bytes: int) -> bytes:
    """Gom bytes của một artifact tới `max_bytes`; vượt trần hay khoá vắng → `PermanentError` (B5-05 [6])."""
    # DEPENDENCY_UNAVAILABLE nổi lên nguyên cho `define_task` thử lại (J02)
    return await read_all_capped(
        storage,
        key,
        max_bytes=max_bytes,
        too_large=lambda: PermanentError(PIPELINE_ARTIFACT_INVALID),
        on_missing=lambda: PermanentError(PIPELINE_ARTIFACT_MISSING),
    )


async def _read_inputs(
    storage: ObjectStorage, payload: BuildStepPayload, max_bytes: int
) -> tuple[WallsResult, ObjectsResult, TextResult]:
    """Đọc ba artifact ML dưới `run_prefix`; JSON sai hợp đồng B5-01 → `PIPELINE_ARTIFACT_INVALID`."""
    walls_bytes = await _read_artifact(storage, input_key(payload.run_prefix, "wallSegmentation"), max_bytes)
    objects_bytes = await _read_artifact(
        storage, input_key(payload.run_prefix, "openingAndFurnitureDetection"), max_bytes
    )
    text_bytes = await _read_artifact(storage, input_key(payload.run_prefix, "dimensionReading"), max_bytes)
    try:
        return walls_from_json(walls_bytes), objects_from_json(objects_bytes), text_from_json(text_bytes)
    except ValueError as exc:
        raise PermanentError(PIPELINE_ARTIFACT_INVALID) from exc


async def _build_and_write(storage: ObjectStorage, payload: BuildStepPayload, key: str) -> None:
    """Dựng `BuiltLayer` (bước C) rồi ghi `layer.json`; đầu vào xấu (`ValueError`) → `PIPELINE_BUILD_INVALID`."""
    max_bytes = get_pipeline_build_settings().PIPELINE_ARTIFACT_MAX_BYTES
    walls, objects, text = await _read_inputs(storage, payload, max_bytes)
    try:
        built = await asyncio.to_thread(
            build_layer,
            level_id=payload.level_id,
            walls=walls,
            objects=objects,
            text=text,
            width_px=payload.width_px,
            height_px=payload.height_px,
            fallback_mm_per_px=payload.fallback_mm_per_px,
            clock=SystemClock(),
        )
    except ValueError as exc:
        raise PermanentError(PIPELINE_BUILD_INVALID) from exc
    await storage.put(key, built.to_json(), content_type="application/json", max_bytes=max_bytes)
    _log.info(
        "pipeline_build_dropped",
        extra={"run_id": payload.run_id, "dropped": dict(built.dropped), "scale_source": built.scale_source},
    )


def report_pipeline_build_failed(payload: BuildStepPayload, code: str) -> None:
    """`on_failed`: báo B5-06c bước `spatialDataBuild` đã hỏng, không artifact (B5-05 [6])."""
    result = StepResultPayload(
        run_id=payload.run_id,
        step=_STEP,
        status="failed",
        artifact_keys=(),
        error_code=code,
        model_version_id=None,
        duration_ms=0,
    )
    send_task(STEP_DONE_TASK, result)


@define_task(name="pipeline.build.run", payload=BuildStepPayload, on_failed=report_pipeline_build_failed)
async def build_pipeline_layer(payload: BuildStepPayload) -> None:
    """Đọc ba artifact, dựng lớp không gian, ghi `layer.json`, báo `step_done` (B5-05 [6] "Task").

    `stat(layer_key)` đã có → bỏ qua bước dựng (J06, id giữ nguyên), chỉ báo lại `completed`.
    """
    started = time.monotonic()
    _check_run_prefix(payload)
    storage = build_context().storage
    key = layer_key(payload.run_prefix)
    existing = await storage.stat(key)
    if existing is None:
        await _build_and_write(storage, payload, key)
    result = StepResultPayload(
        run_id=payload.run_id,
        step=_STEP,
        status="completed",
        artifact_keys=(key,),
        error_code=None,
        model_version_id=None,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    send_task(STEP_DONE_TASK, result)
