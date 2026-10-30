"""Bốn bảng của lượt tải bản vẽ (B2-04 [5]): `uploads`, `upload_chunks`, `pipeline_runs`, `drawings`.

Không xoá mềm ở đây: vòng đời của một lượt tải kết thúc bằng `status` (`complete`,
`rejected`) hoặc bằng lịch dọn xoá hẳn dòng, nên `SoftDeleteMixin` chỉ thêm cột không ai
đọc. Mọi FK tới `projects.id`, `floors.pk`, `uploads.id` là `ON DELETE CASCADE`: xoá cứng
một dự án (lịch của B2-01) hay một tầng (B2-03) là **một** lệnh `DELETE`, không phải chuỗi
lệnh theo thứ tự bảng con.

`superseded_by` cố ý **không** FK tới chính `pipeline_runs`: lượt bị thay trỏ tới lượt mới,
nhưng lịch dọn có thể xoá lượt mới trước lượt cũ và FK sẽ chặn việc đó.

CHECK ở đây là tầng phòng thủ cuối (như `floors`): nơi báo lỗi cho người dùng là
`apps/api/drawings` (422 theo [2]). Tập bước và trọng số lấy từ `packages.core.pipeline`
(`PIPELINE_STEPS`), không chép hằng.
"""

from datetime import datetime
from typing import Final

from sqlalchemy import BigInteger, CheckConstraint, Float, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.pipeline import PIPELINE_STEPS
from packages.db.base import Base, TimestampMixin
from packages.db.models.auth import one_of
from packages.db.models.floors import FLOORS
from packages.db.models.projects import PROJECTS

UPLOADS: Final = "uploads"
UPLOAD_CHUNKS: Final = "upload_chunks"
PIPELINE_RUNS: Final = "pipeline_runs"
DRAWINGS: Final = "drawings"

UPLOAD_STATUSES: Final = ("receiving", "complete", "rejected")
"""Vòng đời một lượt tải — nguồn duy nhất cho CHECK, `progress_wire` và test."""

RUN_STATUSES: Final = ("pending", "running", "completed", "failed")
"""Vòng đời một lượt chạy pipeline; `completed`/`failed` là trạng thái cuối (không quay lại)."""

STEP_IDS: Final = tuple(step for step, _ in PIPELINE_STEPS)
"""6 id bước của FE (`src/lib/realtime/pipeline.ts:48-55`), suy từ `PIPELINE_STEPS`."""


class UploadRow(Base, TimestampMixin):
    """Một lượt tải tệp gốc lên cho một tầng; `created_by` là `sub` người tải (K05), không FK."""

    __tablename__ = UPLOADS

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{PROJECTS}.id", ondelete="CASCADE"))
    floor_pk: Mapped[int] = mapped_column(BigInteger, ForeignKey(f"{FLOORS}.pk", ondelete="CASCADE"))
    file_name: Mapped[str] = mapped_column(Text)
    declared_size_bytes: Mapped[int] = mapped_column(BigInteger)
    declared_type: Mapped[str] = mapped_column(Text)
    sniffed_kind: Mapped[str | None] = mapped_column(Text, default=None)
    page_index: Mapped[int] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    rejected_code: Mapped[str | None] = mapped_column(Text, default=None)
    original_key: Mapped[str | None] = mapped_column(Text, default=None)
    created_by: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(one_of("status", UPLOAD_STATUSES), name="status"),
        CheckConstraint("declared_size_bytes > 0", name="declared_size_bytes_positive"),
        CheckConstraint("chunk_count > 0", name="chunk_count_positive"),
        CheckConstraint("page_index >= 0", name="page_index_non_negative"),
        # Khử trùng thử lại của #5 tra "upload `receiving` của tầng này, người này, mới hơn
        # `UPLOAD_INIT_DEDUPE_S`" ở **mỗi** lượt init — câu nóng nhất của module. Index một
        # phần nên chỉ giữ số dòng đang dở (vài dòng mỗi tầng), không phải cả lịch sử tải.
        Index(
            f"ix_{UPLOADS}_floor_pk_created_by_created_at",
            "floor_pk",
            "created_by",
            "created_at",
            postgresql_where=text("status = 'receiving'"),
        ),
        # N7 (`drawings/latest.py`) join `uploads` theo tầng rồi xếp mới nhất trước; index một phần
        # ở trên chỉ phủ `receiving`, nên thiếu index này là quét tuần tự cả lịch sử tải (P16).
        Index(f"ix_{UPLOADS}_floor_pk_created_at", "floor_pk", text("created_at DESC"), text("id DESC")),
    )


class UploadChunkRow(Base, TimestampMixin):
    """Một khúc đã nhận của lượt tải; PK `(upload_id, chunk_index)` nên gửi lại khúc là ghi đè."""

    __tablename__ = UPLOAD_CHUNKS

    upload_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{UPLOADS}.id", ondelete="CASCADE"), primary_key=True)
    chunk_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(Text)
    object_key: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="chunk_index_non_negative"),
        CheckConstraint("size_bytes > 0", name="size_bytes_positive"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
    )


class PipelineRunRow(Base, TimestampMixin):
    """Một lượt chạy pipeline cho một lượt tải; trạng thái pipeline sống ở đây, không ở broker.

    `progress_percent` chỉ tăng (`record_step` lấy `max`): FE vẽ thanh tiến độ thẳng từ số này
    nên một lần lùi là một lần người dùng thấy việc "chạy ngược".
    """

    __tablename__ = PIPELINE_RUNS

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    upload_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{UPLOADS}.id", ondelete="CASCADE"))
    floor_pk: Mapped[int] = mapped_column(BigInteger, ForeignKey(f"{FLOORS}.pk", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(Text)
    current_step: Mapped[str] = mapped_column(Text)
    progress_percent: Mapped[int] = mapped_column(Integer)
    requeue_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
    error_code: Mapped[str | None] = mapped_column(Text, default=None)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    ended_at: Mapped[datetime | None] = mapped_column(default=None)
    superseded_by: Mapped[str | None] = mapped_column(Text, default=None)

    __table_args__ = (
        CheckConstraint(one_of("status", RUN_STATUSES), name="status"),
        CheckConstraint(one_of("current_step", STEP_IDS), name="current_step"),
        CheckConstraint("progress_percent BETWEEN 0 AND 100", name="progress_percent_range"),
        CheckConstraint("requeue_count >= 0", name="requeue_count_non_negative"),
        # [5]: lịch quét bù quét `pending` quá hạn theo `updated_at`.
        Index(f"ix_{PIPELINE_RUNS}_status_updated_at", "status", "updated_at"),
        # `start_run` tra "lượt `pending|running` của tầng này" trước mỗi lượt tải mới, và N7
        # lấy lượt **mới nhất** của từng tầng (`DISTINCT ON (floor_pk) … ORDER BY created_at DESC`).
        # Cả hai là tra theo tầng + thứ tự thời gian, nên một index phục vụ cả hai.
        Index(f"ix_{PIPELINE_RUNS}_floor_pk_created_at", "floor_pk", "created_at"),
        # Lượt chạy mới nhất của **một lượt tải** (`drawings/latest.py`, `drawings/progress.py`:
        # `WHERE upload_id = … ORDER BY created_at DESC, id DESC LIMIT 1`) — trước đây quét tuần tự (P16).
        Index(f"ix_{PIPELINE_RUNS}_upload_id_created_at", "upload_id", text("created_at DESC"), text("id DESC")),
    )


class DrawingRow(Base, TimestampMixin):
    """Bản vẽ **đang dùng** của một tầng — `floor_pk` unique nên mỗi tầng nhiều nhất một dòng.

    `uploaded_at`, `uploader_id` chép từ lượt tải chứ không join: QC đọc chúng ở mỗi lượt mở
    màn, còn lượt tải cũ có thể đã bị lịch dọn xoá.
    """

    __tablename__ = DRAWINGS

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    floor_pk: Mapped[int] = mapped_column(BigInteger, ForeignKey(f"{FLOORS}.pk", ondelete="CASCADE"), unique=True)
    upload_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{UPLOADS}.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    page_key: Mapped[str] = mapped_column(Text)
    width_px: Mapped[int] = mapped_column(Integer)
    height_px: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column()
    uploader_id: Mapped[str] = mapped_column(Text)
    px_per_paper_mm: Mapped[float | None] = mapped_column(
        Float, default=None, info={"float_reason": "tỉ số px/mm giấy của trang PDF dựng ảnh, không phải độ dài"}
    )
    """px trên mỗi mm giấy thật (PDF biết khổ trang); ảnh raster `NULL`. Bước dựng đọc ghi chú `TL 1:N` (U01)."""

    __table_args__ = (
        CheckConstraint("width_px > 0", name="width_px_positive"),
        CheckConstraint("height_px > 0", name="height_px_positive"),
    )
