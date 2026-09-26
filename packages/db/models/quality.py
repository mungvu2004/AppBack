"""Bảng `quality_assessments`: kết quả đo chất lượng của **trang đang dùng** của một tầng (B2-05b [5]).

`floor_pk` vừa là PK vừa là FK `ON DELETE CASCADE` nên mỗi tầng nhiều nhất một dòng và xoá
cứng tầng là một lệnh `DELETE`. `drawing_id` cố ý **không** FK tới `drawings`: bản vẽ bị
thay thì dòng đo thành cũ chứ không bị xoá theo — `read_view` so `drawing_id` và
`report.pageKey` với bản vẽ hiện tại để biết dòng còn dùng được hay không.

`report`, `corners`, `homography` là JSON theo hợp đồng [5]; hình dạng do
`apps/api/quality/assessments.py` dựng và đọc, DB không kiểm.
"""

from typing import Any, Final

from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin
from packages.db.models.floors import FLOORS

QUALITY_ASSESSMENTS: Final = "quality_assessments"


class QualityAssessmentRow(Base, TimestampMixin):
    """Một lần đo của một tầng; ghi đè tại chỗ (upsert theo `floor_pk`), không giữ lịch sử."""

    __tablename__ = QUALITY_ASSESSMENTS

    floor_pk: Mapped[int] = mapped_column(BigInteger, ForeignKey(f"{FLOORS}.pk", ondelete="CASCADE"), primary_key=True)
    drawing_id: Mapped[str] = mapped_column(Text)
    report: Mapped[Any] = mapped_column(JSONB)
    corners: Mapped[Any] = mapped_column(JSONB(none_as_null=True), nullable=True, default=None)
    homography: Mapped[Any] = mapped_column(JSONB)
