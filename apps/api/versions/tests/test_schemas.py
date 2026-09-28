"""Model dây của #36, N17-N20 và luật chuẩn hoá nhãn N20 (B3-04 [2], [6]).

Test thuần (không DB): khoá lạ bị từ chối, trường tuỳ chọn vắng khoá thay vì `null` (W2, C17),
số/chuỗi không bị ép kiểu, và `normalize_label` đo độ dài theo đơn vị UTF-16 như zod của FE.
"""

import unicodedata
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from apps.api.versions.schemas import (
    FloorVersionSummaryOut,
    VersionLabelIn,
    VersionOut,
    VersionRestoreIn,
)
from apps.api.versions.service import normalize_label
from packages.core.errors import AppError

NOW = datetime(2026, 1, 1, tzinfo=UTC)
VERSION_ID = "ver_01J00000000000000000000000"
USER_ID = "usr_01J00000000000000000000000"


def _summary(**overrides: Any) -> dict[str, Any]:
    """Các trường bắt buộc của `FloorVersionSummaryOut`, ghi đè được từng trường."""
    base: dict[str, Any] = {
        "id": VERSION_ID,
        "sequence": 1,
        "floor_revision": 0,
        "created_at": NOW,
        "creator_id": USER_ID,
        "creator_name": "An",
        "has_snapshot": True,
    }
    return base | overrides


def test_summary_drops_absent_optionals_and_keeps_pipeline_literal() -> None:
    """`note`/`label` `None` → vắng khoá; `creatorId` `system:pipeline` giữ nguyên; giờ đúng `.sssZ`."""
    dumped = FloorVersionSummaryOut(**_summary(creator_id="system:pipeline")).model_dump(mode="json", by_alias=True)

    assert "note" not in dumped
    assert "label" not in dumped
    assert dumped["creatorId"] == "system:pipeline"
    assert dumped["createdAt"] == "2026-01-01T00:00:00.000Z"
    assert dumped["floorRevision"] == 0


def test_summary_rejects_unknown_key_and_bad_numbers() -> None:
    """Khoá lạ, `sequence` 0 và `floorRevision` âm bị từ chối (zod `.strict()`, `positive`, `nonnegative`)."""
    for bad in ({"nonsense": 1}, {"sequence": 0}, {"floor_revision": -1}):
        with pytest.raises(ValidationError):
            FloorVersionSummaryOut(**_summary(**bad))


def test_version_out_has_the_six_old_fields_only() -> None:
    """#36: đúng sáu trường của `Version` cũ; thêm `label` là lỗi."""
    out = VersionOut(id=VERSION_ID, project_id="prj_x", sequence=2, created_at=NOW, creator_id=USER_ID, note="ghi chú")

    assert set(out.model_dump(by_alias=True)) == {"id", "projectId", "sequence", "createdAt", "creatorId", "note"}
    with pytest.raises(ValidationError):
        VersionOut.model_validate(
            {"id": "a", "projectId": "b", "sequence": 1, "createdAt": NOW, "creatorId": "c", "label": "x"}
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"baseVersion": "3", "body": {"floorId": "L-A"}},
        {"baseVersion": True, "body": {"floorId": "L-A"}},
        {"baseVersion": -1, "body": {"floorId": "L-A"}},
        {"baseVersion": 1, "body": {"floorId": ""}},
        {"baseVersion": 1, "body": {"floorId": "L-A", "extra": 1}},
        {"baseVersion": 1, "body": {"floorId": "L-A"}, "extra": 1},
        {"body": {"floorId": "L-A"}},
    ],
)
def test_restore_body_is_strict(payload: dict[str, Any]) -> None:
    """Số ép kiểu, `baseVersion` âm, `floorId` rỗng, khoá lạ ở hai tầng, thiếu `baseVersion` → từ chối."""
    with pytest.raises(ValidationError):
        VersionRestoreIn.model_validate(payload)


def test_restore_body_accepts_the_wire_shape() -> None:
    """Thân hợp lệ đọc ra `base_version` và `body.floor_id`."""
    parsed = VersionRestoreIn.model_validate({"baseVersion": 0, "body": {"floorId": "L-A"}})

    assert (parsed.base_version, parsed.body.floor_id) == (0, "L-A")


@pytest.mark.parametrize("payload", [{"label": 5}, {"label": None}, {}, {"label": "a", "extra": 1}])
def test_label_body_is_strict(payload: dict[str, Any]) -> None:
    """`label` phải là chuỗi thật (không ép số), bắt buộc, và không có khoá lạ."""
    with pytest.raises(ValidationError):
        VersionLabelIn.model_validate(payload)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  bản gửi chủ đầu tư  ", "bản gửi chủ đầu tư"),
        ("", None),
        ("   \t ", None),
        ("a" * 60, "a" * 60),
        ("ệ" * 60, "ệ" * 60),
        ("😀" * 30, "😀" * 30),
        (unicodedata.normalize("NFD", "Bản đẹp"), "Bản đẹp"),
    ],
)
def test_normalize_label_accepts(raw: str, expected: str | None) -> None:
    """Cắt khoảng trắng, NFC, rỗng → `None`; 60 đơn vị UTF-16 vẫn nhận (ký tự ngoài BMP tính 2)."""
    assert normalize_label(raw) == expected


@pytest.mark.parametrize("raw", ["a" * 61, "😀" * 31, "ệ" * 61, "x\u202ey", "x\u200by", "x\ny", "\x00", "a\u2066"])
def test_normalize_label_rejects(raw: str) -> None:
    """Quá 60 đơn vị UTF-16, ký tự `Cc`/`Cf` (U+202E, U+200B, xuống dòng, NUL, U+2066) → `VALIDATION` `label`."""
    with pytest.raises(AppError) as caught:
        normalize_label(raw)

    assert caught.value.code.code == "VALIDATION"
    assert dict(caught.value.params) == {"field": "label"}
