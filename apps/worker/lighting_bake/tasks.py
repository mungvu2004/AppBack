"""Task `bake.lighting.run`: nướng ánh sáng GLB của editor bằng Blender rồi lưu ba tệp kết quả (LB-01).

Luồng: `claim` (0 dòng = giao lặp, no-op J06) → tải `input.glb` về thư mục tạm → Blender trong
tiến trình con có session riêng (giữ `gpu:0` thì chạy GPU, bận thì CPU) → kiểm ba tệp bằng magic
bytes → `put` từng tệp theo luồng → `finish` → xoá `input.glb` và object của các lượt nướng cũ hơn
cùng dự án (dòng DB giữ lại). Hỏng → `on_failed` ghi `fail` rồi xoá cả tiền tố của lượt.

Session ngắn, không giữ khi chạm storage hay chờ Blender (K22, K36).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal
import tempfile
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.lighting_bake.state import (
    FAILURE_CODES,
    LIGHTING_BAKE_FAILED,
    LIGHTING_BAKE_OUTPUT_INVALID,
    LIGHTING_BAKE_TIMEOUT,
    claim,
    fail,
    finish,
)
from apps.worker.lighting_bake.blender import BAKE_SCRIPT, blender_argv
from apps.worker.lighting_bake.settings import get_bake_settings
from packages.core.clock import Clock, SystemClock
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.db.engine import session_scope, worker_sessionmaker
from packages.db.models.lighting_bake import LightingBakeRow
from packages.messaging import LockBusy, LockLost, PermanentError, SafeLock, define_task, runner, safe_redis
from packages.messaging.payloads.lighting_bake import (
    LIGHTING_BAKE_FILES,
    LIGHTING_BAKE_INPUT,
    LIGHTING_BAKE_TASK,
    LightingBakePayload,
)
from packages.messaging.tasks import TASK_TIMEOUT
from packages.storage.keys import lighting_bake_object, lighting_bake_prefix
from packages.storage.port import CHUNK_SIZE, ObjectStorage
from packages.storage.sniff import SNIFF_BYTES, sniff

__all__ = ["ArgvFor", "bake_lighting", "fail_lighting_bake", "file_chunks", "run_lighting_bake"]

_log: Final = logging.getLogger(__name__)

ArgvFor = Callable[[Path, Path], list[str]]
"""`(input.glb, thư mục ra) -> argv`; test thay Blender bằng `tests/fake_blender.py` qua tham số này."""

GPU_LOCK_NAME: Final = "gpu:0"
GPU_LOCK_TTL_MS: Final = 60_000
GPU_LOCK_RENEW_MS: Final = 20_000
MANIFEST_MAX_BYTES: Final = 64 * 1024
LOG_TAIL_BYTES: Final = 2048
_ENV_KEEP: Final = ("PATH", "LANG", "LC_ALL", "PYTHONPATH")
"""Không DSN, không khoá S3: Blender chỉ thấy thư mục tạm. `PYTHONPATH` để test chạy được bộ giả bằng
`-m`; Blender bỏ qua biến này khi không có `--python-use-system-env`."""

_CONTENT_TYPES: Final = {"glb": "model/gltf-binary", "png": "image/png", "json": "application/json"}


async def file_chunks(path: Path, chunk_size: int = CHUNK_SIZE) -> AsyncIterator[bytes]:
    """Đọc tệp theo khúc trong luồng phụ: `put` nhận luồng, RAM chỉ giữ một khúc."""
    handle = await asyncio.to_thread(path.open, "rb")
    try:
        while chunk := await asyncio.to_thread(handle.read, chunk_size):
            yield chunk
    finally:
        await asyncio.to_thread(handle.close)


async def _download(storage: ObjectStorage, key: str, path: Path) -> None:
    """Chép object `key` xuống `path` theo khúc, ghi đĩa trong luồng phụ."""
    handle = await asyncio.to_thread(path.open, "wb")
    try:
        async for chunk in storage.open_read(key):
            await asyncio.to_thread(handle.write, chunk)
    finally:
        await asyncio.to_thread(handle.close)


def _child_env(tmp: Path, *, gpu: bool) -> dict[str, str]:
    """Môi trường tối thiểu của Blender; `gpu=False` ẩn mọi GPU (`CUDA_VISIBLE_DEVICES=""`)."""
    env = {name: os.environ[name] for name in _ENV_KEEP if name in os.environ}
    env["HOME"] = env["TMPDIR"] = str(tmp)
    if not gpu:
        env["CUDA_VISIBLE_DEVICES"] = ""
    return env


def _kill_group(proc: asyncio.subprocess.Process) -> None:
    """Giết cả nhóm tiến trình của Blender (nó có session riêng) để không bỏ lại con mồ côi."""
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)


def _log_tail(log_path: Path, bake_id: str, returncode: int | None) -> None:
    """Ghi `LOG_TAIL_BYTES` byte cuối của log Blender khi lượt hỏng."""
    with contextlib.suppress(OSError):
        data = log_path.read_bytes()[-LOG_TAIL_BYTES:]
        _log.warning(
            "lighting_bake_blender_failed",
            extra={"bake_id": bake_id, "returncode": returncode, "tail": data.decode("utf-8", "replace")},
        )


async def _spawn(argv: list[str], tmp: Path, *, gpu: bool, timeout_s: float, bake_id: str) -> None:
    """Chạy một lượt Blender; mã thoát ≠ 0, quá hạn, bị giết → lỗi có mã. Mọi lối ra đều gặt con.

    `-SIGKILL` mà cha không giết là OOM của cgroup: lỗi tạm → `DEPENDENCY_UNAVAILABLE` (thử lại,
    khuôn `apps/ml/ml_eval/tasks.py`).
    """
    log_path = tmp / "blender.log"
    log = await asyncio.to_thread(log_path.open, "wb")
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=log,
            stderr=asyncio.subprocess.STDOUT,
            env=_child_env(tmp, gpu=gpu),
            start_new_session=True,
        )
        try:
            returncode = await asyncio.wait_for(proc.wait(), timeout=timeout_s)
        except TimeoutError:
            _kill_group(proc)
            await proc.wait()
            _log_tail(log_path, bake_id, None)
            raise PermanentError(LIGHTING_BAKE_TIMEOUT) from None
        except BaseException:
            _kill_group(proc)
            await asyncio.shield(proc.wait())
            raise
    finally:
        await asyncio.to_thread(log.close)
    if returncode == 0:
        return
    _log_tail(log_path, bake_id, returncode)
    if returncode == -signal.SIGKILL:
        raise DEPENDENCY_UNAVAILABLE.error(retry_after=5)
    raise PermanentError(LIGHTING_BAKE_FAILED)


async def _run_blender(argv: list[str], tmp: Path, *, timeout_s: float, bake_id: str) -> None:
    """Giữ `gpu:0` (như `apps/ml/runtime/gpu.py`) thì chạy GPU; khoá bận → chạy CPU, không chờ.

    Mất khoá giữa lượt (`LockLost`, Blender đã bị giết) → `DEPENDENCY_UNAVAILABLE`: lượt sau thử lại.
    """
    lock = SafeLock(safe_redis(), GPU_LOCK_NAME, GPU_LOCK_TTL_MS)
    try:
        async with lock.hold(GPU_LOCK_RENEW_MS):
            await _spawn(argv, tmp, gpu=True, timeout_s=timeout_s, bake_id=bake_id)
            return
    except LockBusy:
        _log.info("lighting_bake_gpu_busy", extra={"bake_id": bake_id})
    except LockLost:
        raise DEPENDENCY_UNAVAILABLE.error(retry_after=5) from None
    await _spawn(argv, tmp, gpu=False, timeout_s=timeout_s, bake_id=bake_id)


def _validate(out: Path, max_bytes: int) -> None:
    """Ba tệp có mặt, trong trần byte, đúng loại theo magic bytes; manifest là JSON object ≤ 64 KiB."""
    expected = {"baked.glb": "glb", "lightmap.png": "png"}
    for name in LIGHTING_BAKE_FILES:
        path = out / name
        if not path.is_file() or path.stat().st_size > max_bytes:
            raise PermanentError(LIGHTING_BAKE_OUTPUT_INVALID)
        if name in expected:
            with path.open("rb") as handle:
                if sniff(handle.read(SNIFF_BYTES)) != expected[name]:
                    raise PermanentError(LIGHTING_BAKE_OUTPUT_INVALID)
    manifest = out / "manifest.json"
    if manifest.stat().st_size > MANIFEST_MAX_BYTES:
        raise PermanentError(LIGHTING_BAKE_OUTPUT_INVALID)
    try:
        parsed = json.loads(manifest.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PermanentError(LIGHTING_BAKE_OUTPUT_INVALID) from None
    if not isinstance(parsed, dict):
        raise PermanentError(LIGHTING_BAKE_OUTPUT_INVALID)


async def _older_bakes(sessionmaker: async_sessionmaker[AsyncSession], project_id: str, bake_id: str) -> list[str]:
    """Id các lượt đã chốt khác của dự án — đều cũ hơn lượt này vì mỗi dự án chỉ một lượt `queued|running`.

    Lọc theo trạng thái chứ không theo thứ tự ULID: lượt mới xếp hàng sau `finish` còn cần `input.glb`.
    """
    stmt = select(LightingBakeRow.id).where(
        LightingBakeRow.project_id == project_id,
        LightingBakeRow.id != bake_id,
        LightingBakeRow.status.in_(("done", "failed")),
    )
    async with sessionmaker() as db:
        return list((await db.execute(stmt)).scalars().all())


async def _project_of(sessionmaker: async_sessionmaker[AsyncSession], bake_id: str) -> str | None:
    """Dự án của lượt nướng, `None` khi dòng không còn (dự án đã xoá, CASCADE)."""
    stmt = select(LightingBakeRow.project_id).where(LightingBakeRow.id == bake_id)
    async with sessionmaker() as db:
        return (await db.execute(stmt)).scalar_one_or_none()


async def bake_lighting(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    *,
    bake_id: str,
    argv_for: ArgvFor | None = None,
    timeout_s: float | None = None,
) -> None:
    """Một lượt nướng đầy đủ (lõi của task); `argv_for`/`timeout_s` chỉ để test thay Blender và trần."""
    async with session_scope(sessionmaker) as db:
        project_id = await claim(db, bake_id, clock)
    if project_id is None:
        _log.info("lighting_bake_not_claimable", extra={"bake_id": bake_id})
        return
    settings = get_bake_settings()
    build_argv = argv_for or (lambda src, out: blender_argv(settings, BAKE_SCRIPT, src, out))
    with tempfile.TemporaryDirectory(prefix="lighting-bake-") as tmp_name:
        tmp = Path(tmp_name)
        src, out = tmp / LIGHTING_BAKE_INPUT, tmp / "out"
        out.mkdir()
        await _download(storage, lighting_bake_object(project_id, bake_id, LIGHTING_BAKE_INPUT), src)
        await _run_blender(build_argv(src, out), tmp, timeout_s=timeout_s or settings.bake_timeout_s, bake_id=bake_id)
        _validate(out, settings.bake_max_output_bytes)
        for name in LIGHTING_BAKE_FILES:
            await storage.put(
                lighting_bake_object(project_id, bake_id, name),
                file_chunks(out / name),
                content_type=_CONTENT_TYPES[name.rsplit(".", 1)[-1]],
                max_bytes=settings.bake_max_output_bytes,
            )
    async with session_scope(sessionmaker) as db:
        done = await finish(db, bake_id, clock)
    if not done:
        # Lịch quét đã đóng lượt này (STALLED) trong lúc nướng: object vừa ghi không dòng nào dùng.
        _log.warning("lighting_bake_finish_skipped", extra={"bake_id": bake_id})
        await storage.delete_prefix(lighting_bake_prefix(project_id, bake_id))
        return
    await storage.delete(lighting_bake_object(project_id, bake_id, LIGHTING_BAKE_INPUT))
    for older in await _older_bakes(sessionmaker, project_id, bake_id):
        await storage.delete_prefix(lighting_bake_prefix(project_id, older))


async def fail_lighting_bake(
    sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage, clock: Clock, *, bake_id: str, code: str
) -> None:
    """Chốt `failed` rồi xoá cả tiền tố của lượt (input + đầu ra dở) — xoá **sau** commit.

    `fail` trả `False` (lượt đã `done`/`failed`) → không xoá gì: kết quả của một lượt đã xong không
    bao giờ bị lượt hỏng muộn dọn mất. Mã chung của `define_task` (`TASK_TIMEOUT`, `RETRY_EXHAUSTED`,
    `WORKER_LOST`, `INTERNAL`) không nằm trong `FAILURE_CODES` của bảng nên được đổi sang mã của module.
    """
    if code not in FAILURE_CODES:
        code = LIGHTING_BAKE_TIMEOUT if code == TASK_TIMEOUT else LIGHTING_BAKE_FAILED
    project_id = await _project_of(sessionmaker, bake_id)
    async with session_scope(sessionmaker) as db:
        failed = await fail(db, bake_id, code, clock)
    if failed and project_id is not None:
        await storage.delete_prefix(lighting_bake_prefix(project_id, bake_id))


def open_storage(clock: Clock) -> ObjectStorage:
    """Kho thật của tiến trình worker, nhập trễ (khuôn `apps/worker/datasets/tasks.py`)."""
    from packages.storage.factory import create_storage
    from packages.storage.settings import get_storage_settings

    return create_storage(get_storage_settings(), None, clock)


async def _fail_with_process_resources(bake_id: str, code: str) -> None:
    """Chốt `failed` bằng tài nguyên thật, dựng **trong** vòng sự kiện của `runner()`."""
    clock = SystemClock()
    await fail_lighting_bake(worker_sessionmaker(), open_storage(clock), clock, bake_id=bake_id, code=code)


def _on_failed(payload: LightingBakePayload, code: str) -> None:
    """`on_failed` của `define_task`: đánh `failed` và dọn tiền tố trên vòng sự kiện dùng chung."""
    _log.error("lighting_bake_failed", extra={"bake_id": payload.bake_id, "code": code})
    runner().run(_fail_with_process_resources(payload.bake_id, code))


@define_task(name=LIGHTING_BAKE_TASK, payload=LightingBakePayload, on_failed=_on_failed)
async def run_lighting_bake(payload: LightingBakePayload) -> None:
    """Hàm task mỏng: dựng tài nguyên thật rồi gọi lõi `bake_lighting`."""
    clock = SystemClock()
    await bake_lighting(worker_sessionmaker(), open_storage(clock), clock, bake_id=payload.bake_id)
