"""Factory dòng `pipeline_run_models` cho test (B5-06a), theo mẫu `factories/admin_ml_registry.py`.

Ghi thẳng bảng bằng `pins.pin_models` rồi các hàm ghi khác nếu cần — không tự viết `INSERT` thứ
hai, để factory và mã nghiệp vụ luôn cùng một luật cột (CHECK, `ON CONFLICT`).
"""

from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from apps.worker.pipeline_orchestrate.pins import mark_persisted, pin_models, record_used, set_step_requeue
from packages.ml_contracts.families import MODEL_FAMILIES, ModelFamily
from packages.ml_contracts.payloads import ModelRef


def classic_ref(family: ModelFamily) -> ModelRef:
    """`ModelRef` dạng cổ điển — cùng hình dạng `active_versions` trả khi họ chưa kích hoạt.

    Công khai vì mọi test `pins`/`dispatch` cần đúng hình dạng này để dựng `pinned` hợp lệ
    (R-02: một định nghĩa, không mỗi file một bản).
    """
    return ModelRef(version_id=None, family=family, weights_key=None, pinned_name=None, checksum_sha256="")


async def make_run_pins(
    db: AsyncSession,
    *,
    run_id: str,
    models: Mapping[ModelFamily, ModelRef] | None = None,
    used: Mapping[ModelFamily, str] | None = None,
    persisted_revision: int | None = None,
    step_requeue_count: int = 0,
) -> None:
    """Ghim ba họ (mặc định cổ điển) cho `run_id`, rồi áp `used`/`persisted_revision`/số đếm.

    Không `commit`: người gọi (test) tự quyết định giao dịch, giống mọi hàm `pins`.
    """
    pinned = models if models is not None else {family: classic_ref(family) for family in MODEL_FAMILIES}
    await pin_models(db, run_id=run_id, models=pinned)
    for family, value in (used or {}).items():
        await record_used(db, run_id=run_id, family=family, used=value)
    if persisted_revision is not None:
        await mark_persisted(db, run_id=run_id, revision=persisted_revision)
    if step_requeue_count:
        await set_step_requeue(db, run_id=run_id, count=step_requeue_count)
