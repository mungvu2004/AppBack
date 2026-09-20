"""Quy ước model (BE-00 §6, W3, K20).

`check_conventions` chạy trên `Base.metadata` sau `load_all_models()`, nên luật này tự
áp cho model của mọi prompt sau, không chỉ model mẫu khai trong file này.
"""

from datetime import datetime
from typing import Any, ClassVar, cast

import pytest
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, MetaData, Numeric, String, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from packages.db.base import (
    NAMING_CONVENTION,
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    area_column,
    mm_column,
    unique_active,
)
from packages.db.models import load_all_models

MM_SUFFIX = "_mm"
FLOAT_REASON_MIN = 10


def check_conventions(metadata: MetaData) -> list[str]:
    problems: list[str] = []
    for table in metadata.sorted_tables:
        for name in ("created_at", "updated_at"):
            column = table.columns.get(name)
            if column is None:
                problems.append(f"{table.name}: thiếu {name}")
            elif not isinstance(column.type, DateTime) or column.nullable:
                problems.append(f"{table.name}.{name}: phải là timestamptz NOT NULL")
        for column in table.columns:
            if isinstance(column.type, DateTime) and not column.type.timezone:
                problems.append(f"{table.name}.{column.name}: DateTime thiếu timezone=True")
            if column.name.endswith(MM_SUFFIX) and not isinstance(column.type, Integer | BigInteger):
                problems.append(f"{table.name}.{column.name}: mm phải là số nguyên")
            if isinstance(column.type, Float):
                reason = column.info.get("float_reason")
                if not isinstance(reason, str) or len(reason) < FLOAT_REASON_MIN:
                    problems.append(f"{table.name}.{column.name}: Float cần info['float_reason'] ≥ 10 ký tự")
    return problems


class SampleBase(DeclarativeBase):
    """Cùng quy ước với `Base`, nhưng metadata riêng: model mẫu không lọt vào migration."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = dict(Base.type_annotation_map)


class Good(SampleBase, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "good"
    __table_args__ = (unique_active("uq_good_code_active", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32))
    width_mm: Mapped[int] = mm_column()
    area_m2: Mapped[Any] = area_column()


class Child(SampleBase, TimestampMixin):
    __tablename__ = "child"

    id: Mapped[int] = mapped_column(primary_key=True)
    good_id: Mapped[int] = mapped_column(ForeignKey("good.id"))


GOOD: Table = cast("Table", Good.__table__)
CHILD: Table = cast("Table", Child.__table__)


def test_real_metadata_follows_conventions() -> None:
    load_all_models()
    assert check_conventions(Base.metadata) == []


def test_sample_models_follow_conventions() -> None:
    assert check_conventions(SampleBase.metadata) == []


def test_naming_convention_applies() -> None:
    assert GOOD.primary_key.name == "pk_good"
    assert {constraint.name for constraint in CHILD.foreign_key_constraints} == {"fk_child_good_id_good"}
    assert [index.name for index in GOOD.indexes] == ["uq_good_code_active"]


def test_unique_active_only_covers_live_rows() -> None:
    index = next(iter(GOOD.indexes))
    assert index.unique
    assert "deleted_at IS NULL" in str(index.dialect_options["postgresql"]["where"])


def test_column_helpers_types() -> None:
    assert isinstance(GOOD.c.width_mm.type, BigInteger)
    area = GOOD.c.area_m2.type
    assert isinstance(area, Numeric)
    assert (area.precision, area.scale) == (12, 2)


def test_timestamps_and_soft_delete_columns() -> None:
    created = GOOD.c.created_at
    assert isinstance(created.type, DateTime)
    assert created.type.timezone
    assert created.server_default is not None
    assert GOOD.c.updated_at.onupdate is not None
    assert GOOD.c.deleted_at.nullable


@pytest.mark.parametrize(
    ("column", "problem"),
    [
        (mapped_column("when_at", DateTime()), "thiếu timezone=True"),
        (mapped_column("width_mm", Float()), "mm phải là số nguyên"),
        (mapped_column("score", Float()), "float_reason"),
    ],
)
def test_conventions_catch_bad_columns(column: Any, problem: str) -> None:
    md = MetaData(naming_convention=NAMING_CONVENTION)

    class Bad(DeclarativeBase):
        metadata = md
        type_annotation_map: ClassVar[dict[Any, Any]] = dict(Base.type_annotation_map)

    class BadModel(Bad, TimestampMixin):
        __tablename__ = "bad"
        id: Mapped[int] = mapped_column(primary_key=True)
        extra: Mapped[Any] = column

    assert any(problem in line for line in check_conventions(md)), check_conventions(md)


def test_conventions_catch_missing_timestamps() -> None:
    md = MetaData(naming_convention=NAMING_CONVENTION)

    class Bare(DeclarativeBase):
        metadata = md

    class NoStamps(Bare):
        __tablename__ = "no_stamps"
        id: Mapped[int] = mapped_column(primary_key=True)

    problems = check_conventions(md)
    assert any("thiếu created_at" in line for line in problems)
    assert any("thiếu updated_at" in line for line in problems)


def test_conventions_allow_float_with_reason() -> None:
    md = MetaData(naming_convention=NAMING_CONVENTION)

    class Measured(DeclarativeBase):
        metadata = md
        type_annotation_map: ClassVar[dict[Any, Any]] = dict(Base.type_annotation_map)

    class Measurement(Measured, TimestampMixin):
        __tablename__ = "measurement"
        id: Mapped[int] = mapped_column(primary_key=True)
        length: Mapped[float] = mapped_column(
            Float(), info={"float_reason": "phép đo do client gửi, W3 cho phép số thực"}
        )

    assert check_conventions(md) == []


def test_created_at_nullable_is_a_problem() -> None:
    md = MetaData(naming_convention=NAMING_CONVENTION)

    class Loose(DeclarativeBase):
        metadata = md
        type_annotation_map: ClassVar[dict[Any, Any]] = dict(Base.type_annotation_map)

    class Nullable(Loose):
        __tablename__ = "nullable_stamps"
        id: Mapped[int] = mapped_column(primary_key=True)
        created_at: Mapped[datetime | None] = mapped_column(default=None)
        updated_at: Mapped[datetime | None] = mapped_column(default=None)

    assert all("timestamptz NOT NULL" in line for line in check_conventions(md))
