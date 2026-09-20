"""`Base` và các mảnh dùng chung của model (BE-00 §6).

- Mọi khoá, ràng buộc, index có tên theo quy ước → migration đặt tên ổn định.
- `datetime` luôn là `timestamptz` (K20).
- mm là số nguyên (`BigInteger`), diện tích `numeric(12,2)` (W3).
"""

from datetime import datetime
from typing import Any, ClassVar, Final

from sqlalchemy import BigInteger, DateTime, Index, MetaData, Numeric, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedColumn, mapped_column

NAMING_CONVENTION: Final = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: DateTime(timezone=True)}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)


def mm_column(**kwargs: Any) -> MappedColumn[int]:
    """Độ dài mm: số nguyên, không bao giờ `float` (W3, K20)."""
    return mapped_column(BigInteger, **kwargs)


def area_column(**kwargs: Any) -> MappedColumn[Any]:
    """Diện tích m²: `numeric(12,2)` (W3)."""
    return mapped_column(Numeric(12, 2), **kwargs)


def unique_active(name: str, *columns: str) -> Index:
    """Unique chỉ tính dòng chưa xoá mềm (BE-00 §6)."""
    return Index(name, *columns, unique=True, postgresql_where=text("deleted_at IS NULL"))
