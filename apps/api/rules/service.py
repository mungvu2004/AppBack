"""Nghiệp vụ N21/N22 (B3-05 [6]): đọc (lọc theo danh mục khi trả), kiểm danh mục tầng 2, ghi có version.

Ghi không bao giờ đọc-so-ghi `revision` trong Python (K07): `INSERT … ON CONFLICT DO NOTHING` rồi
`UPDATE … WHERE revision = :base RETURNING` quyết định thắng thua, kể cả khi hai người ghi song song. Chỉ khi
`UPDATE` trả 0 dòng mới đọc hiện trạng để phân biệt lượt lặp (C09b) với xung đột thật (409). Không `commit`.
"""

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import Select, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.access.activity import record_activity
from apps.api.access.kinds import ActivityKind
from apps.api.projects.access import ProjectAccess
from apps.api.projects.summaries import touch_project
from apps.api.rules.catalog import GENERAL_CODE, RULE_CODES, THRESHOLD_SPECS
from apps.api.rules.errors import (
    RULE_CODE_UNKNOWN,
    RULE_GENERAL_NOT_TOGGLEABLE,
    RULE_THRESHOLD_OUT_OF_RANGE,
    RULE_THRESHOLD_UNKNOWN,
)
from apps.api.rules.schemas import ProjectRuleConfigOut, RuleConfigBodyIn, RuleConfigOverrideOut
from packages.core.clock import Clock
from packages.core.errors import VersionConflictError
from packages.db.models.rules import RuleConfigRow

_OVERRIDES_FIELD = "body.overrides"


def filter_overrides(overrides: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Bỏ mã, khoá ngưỡng ngoài danh mục và trường ngoài `RuleConfigOverrideOut`; `thresholds`/override rỗng thì bỏ.

    Chỉ lọc khi trả (dữ liệu lưu trước một FIX thu hẹp danh mục); không ghi lại dòng jsonb.
    """
    kept: dict[str, dict[str, Any]] = {}
    for code, override in overrides.items():
        if code != GENERAL_CODE and code not in RULE_CODES:
            continue
        item = {
            name: value
            for name, value in override.items()
            if name != "thresholds" and name in RuleConfigOverrideOut.model_fields
        }
        thresholds = {
            key: value
            for key, value in override.get("thresholds", {}).items()
            if key in THRESHOLD_SPECS and THRESHOLD_SPECS[key].rule_code == code
        }
        if thresholds:
            item["thresholds"] = thresholds
        if item:
            kept[code] = item
    return kept


def check_catalog(overrides: Mapping[str, Mapping[str, Any]]) -> None:
    """Tầng 2 (B3-05 [6]): mã theo thứ tự chữ, khoá theo thứ tự chữ, lỗi đầu tiên thắng.

    Nhận `overrides` đã `model_dump(mode="json", exclude_none=True)`. Ném `AppError` 422 với mã riêng của module.
    """
    for code in sorted(overrides):
        override = overrides[code]
        if code == GENERAL_CODE:
            for name in ("enabled", "severity"):
                if name in override:
                    raise RULE_GENERAL_NOT_TOGGLEABLE.error(field=f"{_OVERRIDES_FIELD}.{GENERAL_CODE}.{name}")
        elif code not in RULE_CODES:
            raise RULE_CODE_UNKNOWN.error(field=_OVERRIDES_FIELD)
        for key in sorted(override.get("thresholds", {})):
            spec = THRESHOLD_SPECS.get(key)
            if spec is None or spec.rule_code != code:
                raise RULE_THRESHOLD_UNKNOWN.error(field=_OVERRIDES_FIELD)
            if not spec.min <= override["thresholds"][key] <= spec.max:
                raise RULE_THRESHOLD_OUT_OF_RANGE.error(field=_OVERRIDES_FIELD)


def _stored_row(project_id: str) -> Select[tuple[int, dict[str, Any], str | None, str | None]]:
    """Câu `SELECT` `(revision, overrides, last_writer_id, last_body_sha256)`; chọn cột nên không qua identity map."""
    return select(
        RuleConfigRow.revision, RuleConfigRow.overrides, RuleConfigRow.last_writer_id, RuleConfigRow.last_body_sha256
    ).where(RuleConfigRow.project_id == project_id)


async def get_config(db: AsyncSession, project_id: str) -> ProjectRuleConfigOut:
    """N21: cấu hình đã lưu (đã lọc theo danh mục), hoặc `{revision: 0, overrides: {}}`; không tạo dòng."""
    found = (await db.execute(_stored_row(project_id))).one_or_none()
    if found is None:
        return ProjectRuleConfigOut.of(0, {})
    return ProjectRuleConfigOut.of(found.revision, filter_overrides(found.overrides))


async def replace_config(
    db: AsyncSession, access: ProjectAccess, *, base_version: int, body: RuleConfigBodyIn, clock: Clock
) -> ProjectRuleConfigOut:
    """N22: thay toàn bộ `overrides` nếu `base_version` còn khớp; lượt lặp của chính người ghi → 200 không đổi gì.

    Ném `VersionConflictError` (409, `remoteChanges: []`) khi ai đó đã ghi trước hoặc `base_version > revision`.
    Thắng thì ghi nhật ký rồi `touch_project` (lời khoá cuối, BE-00 §7). Người ghi chỉ lấy từ `Principal` (K05).
    """
    dumped = body.model_dump(mode="json", exclude_none=True)
    overrides: dict[str, Any] = dumped["overrides"]
    check_catalog(overrides)
    digest = hashlib.sha256(
        json.dumps(dumped, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    writer = access.principal.user_id
    await db.execute(
        pg_insert(RuleConfigRow)
        .values(project_id=access.project_id, revision=0, overrides={})
        .on_conflict_do_nothing(index_elements=["project_id"])
    )
    written = (
        await db.execute(
            update(RuleConfigRow)
            .where(RuleConfigRow.project_id == access.project_id, RuleConfigRow.revision == base_version)
            .values(
                revision=RuleConfigRow.revision + 1,
                overrides=overrides,
                last_writer_id=writer,
                last_body_sha256=digest,
                updated_at=clock.now(),
            )
            .returning(RuleConfigRow.revision, RuleConfigRow.overrides)
        )
    ).one_or_none()
    if written is not None:
        await record_activity(
            db,
            actor_id=writer,
            kind=ActivityKind.RULES_CONFIG_UPDATE,
            object_code=access.project_id,
            object_label=access.project_name,
            clock=clock,
            project_id=access.project_id,
        )
        await touch_project(db, project_id=access.project_id, clock=clock)
        return ProjectRuleConfigOut.of(written.revision, filter_overrides(written.overrides))
    # `INSERT` ở trên bảo đảm dòng đã có (của ta hoặc của người thắng), nên `.one()` không ném.
    current = (await db.execute(_stored_row(access.project_id))).one()
    if current.last_writer_id == writer and current.last_body_sha256 == digest and base_version == current.revision - 1:
        return ProjectRuleConfigOut.of(current.revision, filter_overrides(current.overrides))
    raise VersionConflictError(current_version=current.revision, remote_changes=[])
