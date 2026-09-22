"""Ghi nhật ký hoạt động trong cùng giao dịch của thao tác (C18, BE-00 §6).

`record_activity` không `commit`: dòng sống hay chết theo giao dịch của người gọi.
Kiểm tra chạy **trước** `db.add()` để lỗi lập trình (id/kind/project_id/độ dài sai) lộ ngay tại
chỗ gọi bằng `ValueError`, thay vì chờ CHECK của DB bật lên lúc `flush`. Module không
nhập `fastapi`/`starlette`: worker (dọn rác) và các route đều nhập được (BE-01 [9]).
"""

from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.access.kinds import ActivityKind
from packages.core.clock import Clock
from packages.core.ids import is_id
from packages.core.text import nfc
from packages.db.models.access import OBJECT_CODE_MAX, OBJECT_LABEL_MAX, ActivityLog

SYSTEM_PIPELINE: Final = "system:pipeline"


def _check_actor_id(actor_id: str) -> None:
    """`actor_id` phải là `usr_<ULID>` hoặc `SYSTEM_PIPELINE`; sai → `ValueError`."""
    if actor_id != SYSTEM_PIPELINE and not is_id("usr", actor_id):
        raise ValueError("actor_id phải là usr_<ULID> hoặc system:pipeline")


def _check_kind(kind: ActivityKind) -> None:
    """`kind` phải là một thành viên `ActivityKind` đã khai (chuỗi trùng giá trị vẫn sai)."""
    if not isinstance(kind, ActivityKind):
        raise ValueError("kind phải là một thành viên ActivityKind đã khai")


def _check_project_id(project_id: str | None) -> None:
    """`project_id` phải là `None` hoặc `prj_<ULID>`; sai → `ValueError`."""
    if project_id is not None and not is_id("prj", project_id):
        raise ValueError("project_id phải là prj_<ULID> hoặc None")


def _normalized(value: str, *, field: str, max_len: int) -> str:
    """`nfc(value).strip()`; rỗng hoặc quá `max_len` → `ValueError` (không lộ giá trị gốc)."""
    normalized = nfc(value).strip()
    if not normalized or len(normalized) > max_len:
        raise ValueError(f"{field} phải khác rỗng và tối đa {max_len} ký tự sau chuẩn hoá")
    return normalized


async def record_activity(
    db: AsyncSession,
    *,
    actor_id: str,
    kind: ActivityKind,
    object_code: str,
    object_label: str,
    clock: Clock,
    project_id: str | None = None,
) -> None:
    """Thêm một dòng `activity_log` vào giao dịch hiện tại của `db` (không `commit`)."""
    _check_actor_id(actor_id)
    _check_kind(kind)
    _check_project_id(project_id)
    code = _normalized(object_code, field="object_code", max_len=OBJECT_CODE_MAX)
    label = _normalized(object_label, field="object_label", max_len=OBJECT_LABEL_MAX)
    db.add(
        ActivityLog(
            actor_id=actor_id,
            kind=kind.value,
            object_code=code,
            object_label=label,
            project_id=project_id,
            at=clock.now(),
        )
    )
    await db.flush()
