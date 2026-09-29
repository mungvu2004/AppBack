"""Dữ liệu gốc của revision `r20260928_b6_01` (B6-01 [5], [8] "Dữ liệu gốc").

Ba lớp kiểm khác nhau, cố ý không gộp:

- `seed_rows` là hàm **thuần**, nên bảng hằng giả (checksum `"0" * 64`) kiểm được nhánh "chưa
  ghim" mà không cần đổi `PINNED` thật;
- dòng thật sau `upgrade head` so với `PINNED[BASELINE[f]].onnx_sha256` — nếu ai đổi `PINNED`
  mà quên revision dữ liệu mới (DEBT NO-061) thì test này đỏ;
- `downgrade base` → `upgrade head` phải ra **cùng id**: id bản gốc đi vào `ModelRef` của mọi
  lượt pipeline, nên nó là hằng của hệ thống, không phải số sinh lúc migrate.
"""

import asyncio
from collections.abc import Sequence
from typing import Any, Final

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from apps.api.admin_ml_registry.tests._helpers import WALL
from packages.db.migrate_check import alembic_config
from packages.db.models.admin_ml_registry import ModelFamilyRow, ModelVersionRow
from packages.db.settings import reset_database_settings_cache
from packages.ml_contracts.families import MODEL_FAMILIES
from packages.ml_contracts.pinned import BASELINE, PINNED

REVISION_ID: Final = "r20260928_b6_01"

# `packages/db/migrations/versions/` **không** là gói Python (`coverage_gate` miễn `__init__.py`
# cho nó), nên revision nạp qua chính bộ nạp của Alembic thay vì câu `import`.
_SCRIPTS: Final = ScriptDirectory.from_config(alembic_config())
_REVISION: Final[dict[str, Any]] = vars(_SCRIPTS.get_revision(REVISION_ID).module)
BASELINE_SEED: Final[Sequence[tuple[str, str, str, str]]] = _REVISION["BASELINE_SEED"]
NOT_PINNED_CODE: Final[str] = _REVISION["NOT_PINNED_CODE"]
SEED_CREATOR: Final[str] = _REVISION["SEED_CREATOR"]
SEED_LABEL: Final[str] = _REVISION["SEED_LABEL"]
UNPINNED: Final[str] = _REVISION["UNPINNED"]
seed_rows = _REVISION["seed_rows"]

BASELINE_BY_FAMILY: Final[dict[str, str]] = {str(family): name for family, name in BASELINE.items()}
"""`BASELINE` với khoá nới về `str`: `row.family` của DB là chuỗi, không `Literal`."""


async def _versions(db: AsyncSession) -> list[ModelVersionRow]:
    """Mọi bản trong registry, xếp theo họ để so không phụ thuộc thứ tự chèn."""
    rows = (await db.scalars(select(ModelVersionRow).order_by(ModelVersionRow.family))).all()
    return list(rows)


async def _seed_ids(url: str) -> list[tuple[str, str]]:
    """`(họ, id)` của dữ liệu gốc đọc bằng kết nối riêng — dùng cho vòng downgrade/upgrade."""
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT family, id FROM model_versions ORDER BY id"))
            return [(row[0], row[1]) for row in result]
    finally:
        await engine.dispose()


def test_seed_rows_marks_an_unpinned_baseline_failed() -> None:
    """Checksum `"0" * 64` ⇔ bản `failed` `MODEL_NOT_PINNED`, và họ ấy **không** kích hoạt."""
    fake: Sequence[tuple[str, str, str, str]] = (
        ("openingAndFurnitureDetection", "mdl_01KB6010000000000000000009", "yolov8n", UNPINNED),
    )
    versions, families = seed_rows(fake)

    assert [(row["evaluation_status"], row["evaluation_error_code"]) for row in versions] == [
        ("failed", NOT_PINNED_CODE)
    ]
    assert all(row["active_version_id"] is None for row in families)
    assert {row["family"] for row in families} == set(MODEL_FAMILIES)


def test_seed_rows_activates_only_pinned_baselines() -> None:
    """Bảng hằng thật: hai bản `pending` không mã, hai họ kích hoạt, họ tường thì không."""
    versions, families = seed_rows(BASELINE_SEED)
    active = {row["family"]: row["active_version_id"] for row in families}

    assert [(row["evaluation_status"], row["evaluation_error_code"]) for row in versions] == [
        ("pending", None),
        ("pending", None),
    ]
    assert all(row["revision"] == 0 for row in families)
    assert active[WALL] is None
    assert {family: active[family] for family in BASELINE_BY_FAMILY} == {
        family: version_id for family, version_id, _pinned, _sha in BASELINE_SEED
    }


def test_seed_rows_copies_the_pinned_onnx_checksums() -> None:
    """Checksum chép tay trong revision vẫn khớp `PINNED[BASELINE[f]].onnx_sha256`."""
    assert {family: sha for family, _id, _pinned, sha in BASELINE_SEED} == {
        family: PINNED[name].onnx_sha256 for family, name in BASELINE_BY_FAMILY.items()
    }
    assert {pinned for _f, _id, pinned, _sha in BASELINE_SEED} == set(BASELINE_BY_FAMILY.values())


async def test_migrated_database_holds_exactly_two_baseline_versions(db_session: AsyncSession) -> None:
    """Sau `upgrade head`: đúng 2 bản `label "gốc"` ghim, không bản nào của `wallSegmentation`."""
    rows = await _versions(db_session)

    assert [row.family for row in rows] == sorted(BASELINE_BY_FAMILY)
    assert {row.checksum_sha256 for row in rows} == {PINNED[BASELINE_BY_FAMILY[row.family]].onnx_sha256 for row in rows}
    assert all(row.label == SEED_LABEL and row.creator_id == SEED_CREATOR for row in rows)
    assert all(row.weights_format == "onnx" and row.weights_key is None for row in rows)
    assert all(row.evaluation_status == "pending" and row.evaluation_attempts == 0 for row in rows)
    assert all(row.metrics is None and row.evaluation_requested_at is None for row in rows)
    assert all(row.training_job_id is None and row.dataset_version_id is None for row in rows)


async def test_migrated_database_activates_the_two_baseline_families(db_session: AsyncSession) -> None:
    """Ba dòng họ `revision 0`; hai họ của `BASELINE` kích hoạt bản gốc, họ tường vắng."""
    families = {row.family: row for row in (await db_session.scalars(select(ModelFamilyRow))).all()}
    versions = {row.family: row.id for row in await _versions(db_session)}

    assert set(families) == set(MODEL_FAMILIES)
    assert all(row.revision == 0 for row in families.values())
    assert all(row.last_writer_id is None and row.last_body_sha256 is None for row in families.values())
    assert families[WALL].active_version_id is None
    assert {f: families[f].active_version_id for f in BASELINE_BY_FAMILY} == versions


def test_baseline_ids_survive_a_downgrade_and_upgrade(blank_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """`downgrade base` → `upgrade head` dựng lại **cùng** id: id bản gốc là hằng, không sinh."""
    monkeypatch.setenv("DATABASE_URL", blank_db_url)
    expected = sorted(
        ((family, version_id) for family, version_id, _pinned, _sha in BASELINE_SEED),
        key=lambda row: row[1],  # `_seed_ids` đọc theo `id`, không theo họ
    )
    try:
        reset_database_settings_cache()
        config = alembic_config()
        command.upgrade(config, "head")
        assert asyncio.run(_seed_ids(blank_db_url)) == expected
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        assert asyncio.run(_seed_ids(blank_db_url)) == expected
    finally:
        monkeypatch.undo()
        reset_database_settings_cache()
