"""Bản vẽ **đang dùng** của một tầng (B2-04 [6] "Bản vẽ"): ghi, đọc, khoá trang, URL ký.

Chỉ `upsert_drawing` ghi bảng `drawings`. Nó mở bằng `runs.lock_run` nên thừa hưởng cả
thứ tự khoá `floors` → lượt chạy (BE-00 §7) lẫn luật "không tin worker": lượt đã kết
thúc, bị thay, hay thuộc lượt tải khác thì hàm trả `None` và **không ghi gì**.

Ranh giới lỗi: dữ liệu người gọi tự bịa (khoá trang sai chỗ, kích thước ≤ 0, lượt tải
chưa `complete` hay khác tầng) là `ValueError` — lỗi lập trình của `apps/ml`, không phải
một trạng thái đua bình thường như `None`.

Module này là "hàm worker nhập" (BE-00 §7): không `fastapi`/`starlette`.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.runs import lock_run
from packages.core.clock import Clock
from packages.core.ids import new_id
from packages.core.object_keys import upload_prefix_of
from packages.db.models.drawings import DrawingRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.storage.keys import check_key, upload_prefix
from packages.storage.port import ObjectStorage

PAGES_SEGMENT = "pages/"
"""Thư mục con của trang **đã nắn** dưới `upload_prefix` ([5]); dùng cả lúc dựng và lúc kiểm."""


def new_page_key(*, project_id: str, level_id: str, upload_id: str, page_index: int, clock: Clock) -> str:
    """`…/pages/{i}-{ULID}.png` — **mỗi lần một khoá mới**, không bao giờ ghi đè ([5], W23).

    URL ký đứng yên trong một giờ, nên ghi đè cùng khoá sẽ để FE dùng ảnh cũ tới hết giờ;
    ULID mới mỗi lượt là cách rẻ nhất để URL cũ chết cùng object cũ. `page_index` < 0 hay
    id sai mẫu → `ValueError` (qua `upload_prefix`/`check_key`).
    """
    if page_index < 0:
        raise ValueError(f"page_index phải >= 0, nhận {page_index}")
    # Không có hàm ULID trần công khai (`new_id` luôn kèm tiền tố) — cắt tiền tố là đường
    # rẻ nhất; nâng cấp là thêm `new_ulid()` vào `packages/core/ids.py` (ngoài whitelist).
    ulid = new_id("drw", clock).removeprefix("drw_")
    return check_key(f"{upload_prefix(project_id, level_id, upload_id)}{PAGES_SEGMENT}{page_index}-{ulid}.png")


async def drawing_url(storage: ObjectStorage, page_key: str) -> str:
    """URL ký của một trang đã nắn: `attachment`, **không** `kind` (khoá không phải do server chọn)."""
    return (await storage.signed_url(page_key, disposition="attachment")).url


async def current_drawing(db: AsyncSession, floor_pk: int, *, for_update: bool = False) -> DrawingRow | None:
    """Bản vẽ đang dùng của một tầng (`floor_pk` unique nên nhiều nhất một dòng).

    `for_update=True` khi người gọi sắp ghi đè: khoá dòng trước khi đọc giữ hai lượt
    `upsert_drawing` của cùng tầng nối đuôi nhau thay vì cùng chèn.
    """
    stmt = select(DrawingRow).where(DrawingRow.floor_pk == floor_pk)
    if for_update:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


def _check_page_key(page_key: str, *, prefix: str) -> None:
    """Khoá trang phải nằm đúng dưới `…/uploads/{upload}/pages/` của lượt tải này.

    Dùng `upload_prefix_of` của lõi chứ không regex bố cục (NO-079, BE-00 §2.2); khoá
    ngoài mẫu lượt tải đã ném `ValueError` ngay ở đó.
    """
    if upload_prefix_of(page_key) != prefix or not page_key.removeprefix(prefix).startswith(PAGES_SEGMENT):
        raise ValueError(f"khoá trang {page_key!r} không thuộc {prefix!r}")


async def _checked_upload(
    db: AsyncSession, *, upload_id: str, floor_pk: int, page_key: str
) -> tuple[str, datetime, str]:
    """Kiểm lượt tải đích rồi trả `(name, uploaded_at, uploader_id)` của bản vẽ sắp ghi.

    Một truy vấn `uploads` ⋈ `floors`: `level_id` chỉ dùng để dựng tiền tố khoá đối chiếu.
    Upload chưa `complete` hay thuộc tầng khác → `ValueError` ([6] "Bản vẽ"). `.one()` chứ
    không `.first()`: `lock_run` đã khoá lượt chạy, mà FK `pipeline_runs.upload_id` là
    CASCADE, nên dòng `uploads` (và tầng của nó) chắc chắn còn — không có dòng là lỗi
    lược đồ, để `NoResultFound` nổi lên thay vì thêm một nhánh không test được (R-14).
    """
    stmt = (
        select(
            UploadRow.status,
            UploadRow.floor_pk,
            UploadRow.project_id,
            UploadRow.file_name,
            UploadRow.updated_at,
            UploadRow.created_by,
            FloorRow.level_id,
        )
        .join(FloorRow, FloorRow.pk == UploadRow.floor_pk)
        .where(UploadRow.id == upload_id)
    )
    status, upload_floor_pk, project_id, file_name, updated_at, created_by, level_id = (await db.execute(stmt)).one()
    if status != "complete":
        raise ValueError(f"lượt tải {upload_id!r} đang {status!r}, chưa có tệp gốc")
    if upload_floor_pk != floor_pk:
        raise ValueError(f"lượt tải {upload_id!r} thuộc tầng khác ({upload_floor_pk} != {floor_pk})")
    _check_page_key(page_key, prefix=upload_prefix(project_id, level_id, upload_id))
    return file_name, updated_at, created_by


async def upsert_drawing(
    db: AsyncSession,
    *,
    run_id: str,
    floor_pk: int,
    upload_id: str,
    page_key: str,
    width_px: int,
    height_px: int,
    clock: Clock,
) -> DrawingRow | None:
    """Đặt bản vẽ đang dùng của một tầng từ kết quả một lượt chạy ([6] "Bản vẽ").

    Trả `None` **không ghi gì** khi lượt chạy đã kết thúc, đã bị thay, hay thuộc lượt tải
    khác: kết quả muộn của một lượt cũ không được phép đè ảnh mới hơn (BE-00 §7).
    Cùng lượt tải → cập nhật tại chỗ, **giữ `id`** (QC đang mở màn không mất tham chiếu);
    lượt tải khác → xoá dòng cũ rồi chèn `id` mới, vì ảnh là một bản vẽ khác hẳn.
    """
    if width_px < 1 or height_px < 1:
        raise ValueError(f"kích thước bản vẽ phải >= 1, nhận {width_px}x{height_px}")
    run = await lock_run(db, run_id=run_id)
    if run is None or run.upload_id != upload_id:
        return None
    name, uploaded_at, uploader_id = await _checked_upload(
        db, upload_id=upload_id, floor_pk=floor_pk, page_key=page_key
    )

    existing = await current_drawing(db, floor_pk, for_update=True)
    if existing is not None and existing.upload_id == upload_id:
        existing.page_key, existing.width_px, existing.height_px = page_key, width_px, height_px
        existing.name, existing.uploaded_at, existing.uploader_id = name, uploaded_at, uploader_id
        await db.flush()
        return existing
    if existing is not None:
        await db.delete(existing)
        await db.flush()
    row = DrawingRow(
        id=new_id("drw", clock),
        floor_pk=floor_pk,
        upload_id=upload_id,
        name=name,
        page_key=page_key,
        width_px=width_px,
        height_px=height_px,
        uploaded_at=uploaded_at,
        uploader_id=uploader_id,
    )
    db.add(row)
    await db.flush()
    return row
