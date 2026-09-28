"""Bảng `measurements`: phép đo người dùng ghim trên mô hình 3D (B2-07 [5]).

Phép đo là hồ sơ của dự án, không phải hình học tầng: id do client sinh (`MS-0001`…) nên PK
là `(project_id, measurement_id)`; xoá **cứng** (BE-00 §6 ngoại lệ) nên PK không partial và
id được tái dùng sau khi xoá. `body_sha256` là dấu vân tay của thân đã chuẩn hoá để #17 phân
biệt "gửi lại đúng bản đã lưu" (200) với "trùng id khác thân" (409); không bao giờ ra dây.
"""

from typing import Any, Final

from sqlalchemy import CHAR, CheckConstraint, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin
from packages.db.models.auth import one_of
from packages.db.models.projects import PROJECTS

MEASUREMENTS: Final = "measurements"
ID_PATTERN: Final = "^MS-[0-9]{4,15}$"
NAME_MAX: Final = 120
MODES: Final = ("pointToPoint", "perpendicular", "height", "floorArea")
SHA256_LEN: Final = 64


class MeasurementRow(Base, TimestampMixin):
    """Một phép đo đã ghim; `created_by` là `sub` người tạo (K05), không FK (người có thể bị xoá)."""

    __tablename__ = MEASUREMENTS

    project_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{PROJECTS}.id", ondelete="CASCADE"), primary_key=True)
    measurement_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text)
    points: Mapped[Any] = mapped_column(JSONB)
    # Tên không đuôi `_mm`: test quy ước của B0-03 cấm số thực ở cột `*_mm`. `floorArea` lưu mm².
    raw_value: Mapped[float] = mapped_column(Float, info={"float_reason": "phép đo là số thực, HOP-DONG-MOI §7.1"})
    body_sha256: Mapped[str] = mapped_column(CHAR(SHA256_LEN))
    created_by: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(f"measurement_id ~ '{ID_PATTERN}'", name="measurement_id_format"),
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {NAME_MAX}", name="name_length"),
        CheckConstraint(one_of("mode", MODES), name="mode"),
        CheckConstraint("raw_value >= 0", name="raw_value_nonneg"),
    )
