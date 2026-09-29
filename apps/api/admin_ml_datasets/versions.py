"""Bốn hàm ghi `dataset_versions` (B6-02 [2]): nguồn duy nhất N31, worker, và lịch quét dùng.

"Hàm worker nhập" (BE-00 §7): không `fastapi`/`starlette` (`worker-no-web`). Không hàm nào
`commit` — người gọi (route, task, lịch) commit, để `record_activity` và gửi task nằm cùng
giao dịch với việc ghi trạng thái (K17: task gửi sau commit, không trong).

Bản `ready` bất biến ([6]): không hàm nào ở đây sửa được một bản đã `ready`/`failed` — cả
ba hàm `touch_version`/`finish_version`/`fail_version` đều lọc `status = 'building'` trong
câu `UPDATE`, nên chuyển trạng thái muộn (khoá đã mất, tin nhắn lặp) tự nhiên là no-op.
"""

from collections.abc import Mapping, Sequence
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.clock import Clock
from packages.core.ids import new_id
from packages.db.models.admin_ml_datasets import DatasetRow, DatasetVersionRow


async def start_version(
    db: AsyncSession,
    *,
    dataset_id: str,
    source: str,
    project_ids: Sequence[str] | None,
    created_by: str,
    clock: Clock,
) -> DatasetVersionRow | None:
    """Mở một phiên bản `building` mới; `None` khi dataset đã có một bản đang dựng (409, K18).

    Khoá dòng `datasets` bằng `FOR UPDATE` trước để hai lượt gọi song song cho **cùng**
    dataset tự xếp hàng ở Postgres (lượt hai chờ lượt một `commit`/`rollback` rồi mới đọc
    lại "có bản `building`"); unique partial `(dataset_id) WHERE status='building'` chỉ là
    lưới an toàn cuối (C14) cho trường hợp khoá dòng không đủ (ví dụ mức cô lập khác READ
    COMMITTED) — bắt `IntegrityError` trong một giao dịch lồng (`begin_nested`) để phiên
    làm việc còn dùng được sau khi thua.

    Dataset `dataset_id` không tồn tại là lỗi của người gọi (N31 đã kiểm 404 trước khi gọi
    hàm này, như `upsert_drawing` coi dữ liệu người gọi tự bịa là lỗi lập trình): ném
    `ValueError`, không trả `None` — `None` ở đây chỉ có một nghĩa, "đã có bản building".
    """
    locked = (await db.execute(select(DatasetRow.id).where(DatasetRow.id == dataset_id).with_for_update())).first()
    if locked is None:
        raise ValueError(f"dataset không tồn tại: {dataset_id!r}")
    building = (
        await db.execute(
            select(DatasetVersionRow.id).where(
                DatasetVersionRow.dataset_id == dataset_id, DatasetVersionRow.status == "building"
            )
        )
    ).first()
    if building is not None:
        return None
    sequence = (
        await db.execute(
            select(func.coalesce(func.max(DatasetVersionRow.sequence), 0) + 1).where(
                DatasetVersionRow.dataset_id == dataset_id
            )
        )
    ).scalar_one()
    now = clock.now()
    row = DatasetVersionRow(
        id=new_id("dsv", clock),
        dataset_id=dataset_id,
        sequence=sequence,
        status="building",
        source=source,
        project_ids=list(project_ids) if project_ids is not None else None,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    try:
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except IntegrityError:
        return None
    return row


async def touch_version(db: AsyncSession, *, version_id: str, clock: Clock) -> bool:
    """Cập nhật `updated_at` của một bản đang `building` (nhịp sống, [6] bước 7); `False` khi đã kết thúc."""
    result = cast(
        "CursorResult[Any]",
        await db.execute(
            update(DatasetVersionRow)
            .where(DatasetVersionRow.id == version_id, DatasetVersionRow.status == "building")
            .values(updated_at=clock.now())
        ),
    )
    return result.rowcount == 1


async def finish_version(
    db: AsyncSession,
    *,
    version_id: str,
    manifest_sha256: str,
    split_counts: Mapping[str, int],
    clock: Clock,
) -> bool:
    """`building` → `ready`, ghi manifest và số mẫu mỗi tập; `False` khi bản không còn `building`."""
    result = cast(
        "CursorResult[Any]",
        await db.execute(
            update(DatasetVersionRow)
            .where(DatasetVersionRow.id == version_id, DatasetVersionRow.status == "building")
            .values(
                status="ready",
                manifest_sha256=manifest_sha256,
                split_counts=dict(split_counts),
                updated_at=clock.now(),
            )
        ),
    )
    return result.rowcount == 1


async def fail_version(db: AsyncSession, *, version_id: str, failure_code: str, clock: Clock) -> bool:
    """`building` → `failed`, ghi mã hỏng; `False` khi bản không còn `building` (`on_failed` cũng gọi)."""
    result = cast(
        "CursorResult[Any]",
        await db.execute(
            update(DatasetVersionRow)
            .where(DatasetVersionRow.id == version_id, DatasetVersionRow.status == "building")
            .values(status="failed", failure_code=failure_code, updated_at=clock.now())
        ),
    )
    return result.rowcount == 1
