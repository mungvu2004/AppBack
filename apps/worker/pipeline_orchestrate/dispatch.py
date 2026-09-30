"""Xếp ba task suy luận ML sau khi ghim model và có trang đã nắn (B5-06a [2], [6]).

`queue_infer` là hàm worker nhập: chạy **trong** giao dịch (không commit), đăng ký gửi task
qua `on_after_commit` (J09) để rollback không để lại thông điệp mồ côi. Gọi lại được (`start`
và quét bù B5-06c): họ đã có trong `pins.used` bị bỏ qua nên không gửi lặp bước đã xong.
"""

from collections.abc import Mapping
from types import MappingProxyType

from sqlalchemy.ext.asyncio import AsyncSession

from apps.worker.pipeline_orchestrate.pins import RunPins
from packages.db.hooks import on_after_commit
from packages.messaging.celery_app import send_task
from packages.ml_contracts.families import FAMILY_STEP, ModelFamily
from packages.ml_contracts.payloads import InferStepPayload

INFER_TASKS: Mapping[ModelFamily, str] = MappingProxyType(
    {
        "wallSegmentation": "ml.infer.walls.segment",
        "openingAndFurnitureDetection": "ml.infer.objects.detect",
        "dimensionReading": "ml.infer.text.read",
    }
)
"""Tên task suy luận theo họ model (BE-00 §7 đặt tên task, K34: không chord/group/chain)."""


def queue_infer(
    db: AsyncSession,
    *,
    pins: RunPins,
    run_prefix: str,
    page_key: str,
    width_px: int,
    height_px: int,
    px_per_paper_mm: float | None = None,
) -> tuple[ModelFamily, ...]:
    """Đăng ký gửi `ml.infer.*` cho mọi họ chưa có trong `pins.used`; trả các họ đã xếp.

    Không commit, không gọi `send_task` trực tiếp: mỗi thông điệp qua `on_after_commit` với một
    closure bắt giá trị theo tham số mặc định (không bắt biến vòng lặp `family` muộn, K18).
    """
    queued: list[ModelFamily] = []
    for family, step in FAMILY_STEP.items():
        if family in pins.used:
            continue
        payload = InferStepPayload(
            run_id=pins.run_id,
            step=family,
            page_key=page_key,
            width_px=width_px,
            height_px=height_px,
            artifact_prefix=f"{run_prefix}{step}/",
            model=pins.pinned[family],
            px_per_paper_mm=px_per_paper_mm,
        )

        def _send(task: str = INFER_TASKS[family], body: InferStepPayload = payload) -> None:
            """Gửi một thông điệp; tham số mặc định bắt giá trị của lượt lặp này, không biến vòng lặp."""
            send_task(task, body)

        on_after_commit(db, _send)
        queued.append(family)
    return tuple(queued)
