"""Test thân ghi #25, #26 và `ProjectsSettings` (B2-01 [2], [5]).

Ranh độ dài, ký tự cấm, `null`, khoá bỏ qua — cùng file vì cả hai là "đầu vào" của module,
và whitelist của việc này không có file test riêng cho settings.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from apps.api.projects.parts import FloorDraft
from apps.api.projects.schemas import ProjectCreateIn, ProjectUpdateIn, floor_drafts
from apps.api.projects.settings import get_projects_settings, reset_projects_settings_cache


def _floor(**overrides: Any) -> dict[str, Any]:
    """Một tầng nháp hợp lệ như `toFloorWirePayload` gửi."""
    return {"name": "Tầng 1", "order": 0, "elevationMm": 0, "heightMm": 3000} | overrides


def _field_of(exc: ValidationError) -> str:
    """Tên trường của lỗi đầu — chính thứ `errors.validation_error` đem ra dây thành `field`."""
    return str(exc.errors()[0]["loc"][0])


@pytest.mark.parametrize(
    ("key", "length", "ok"),
    [
        ("name", 2, False),
        ("name", 3, True),
        ("name", 80, True),
        ("name", 81, False),
        ("code", 32, True),
        ("code", 33, False),
        ("address", 200, True),
        ("address", 201, False),
    ],
)
def test_length_bounds(key: str, length: int, ok: bool) -> None:
    """Ranh độ dài của ba trường chuỗi đúng `src/domain/project/limits.ts`."""
    body: dict[str, Any] = {"name": "Nhà A", key: "x" * length}
    if ok:
        assert getattr(ProjectCreateIn.model_validate(body), key) == "x" * length
    else:
        with pytest.raises(ValidationError) as caught:
            ProjectCreateIn.model_validate(body)
        assert _field_of(caught.value) == key


def test_length_is_measured_after_trim() -> None:
    """Trim chạy trước ràng buộc: `"  ab  "` là 2 ký tự nên rớt, không phải 6 nên đạt."""
    with pytest.raises(ValidationError):
        ProjectCreateIn.model_validate({"name": "  ab  "})


@pytest.mark.parametrize("key", ["name", "code", "address"])
@pytest.mark.parametrize("bad", ["‮", "‏", "⁦", "\x00", "\x1b"])
def test_control_and_bidi_characters_rejected(key: str, bad: str) -> None:
    """Ký tự định hướng và Cc bị chặn ở cả ba trường, kèm đúng `field`."""
    with pytest.raises(ValidationError) as caught:
        ProjectCreateIn.model_validate({"name": "Nhà A", key: f"Nhà{bad}A"})
    assert _field_of(caught.value) == key


def test_name_normalised_to_nfc() -> None:
    """NFD người dùng dán vào được chuẩn hoá NFC trước khi lưu (C16, K20)."""
    assert ProjectCreateIn.model_validate({"name": "Nhà A"}).name == "Nhà A"


@pytest.mark.parametrize("model", [ProjectCreateIn, ProjectUpdateIn])
@pytest.mark.parametrize("key", ["status", "members", "progress", "currentVersion"])
def test_ignored_keys_accepted(model: type[ProjectCreateIn] | type[ProjectUpdateIn], key: str) -> None:
    """Bốn khoá FE gửi lại nguyên `Project` được nhận rồi bỏ, không 422 (W18)."""
    body = model.model_validate({"name": "Nhà A", key: {"bất": ["kỳ", 1, None]}})
    assert body.name == "Nhà A"


def test_update_accepts_empty_body() -> None:
    """`{}` là thân hợp lệ của #26: FE bấm "Lưu" khi chưa đổi gì."""
    body = ProjectUpdateIn.model_validate({})
    assert body.model_fields_set == set()


@pytest.mark.parametrize("key", ["name", "code", "address"])
def test_update_rejects_explicit_null(key: str) -> None:
    """`null` không phải "không đổi": 422 kèm `field` (B2-01 [2])."""
    with pytest.raises(ValidationError) as caught:
        ProjectUpdateIn.model_validate({key: None})
    assert _field_of(caught.value) == key


def test_update_ignores_floors() -> None:
    """`floors` ở #26 nhận rồi bỏ: đổi tầng đi đường của B2-03."""
    assert ProjectUpdateIn.model_validate({"floors": [_floor()]}).name is None


def test_unknown_key_rejected() -> None:
    """Khoá lạ vẫn 422 `VALIDATION` (C03) — `extra="forbid"` của `WireRequest`."""
    with pytest.raises(ValidationError):
        ProjectCreateIn.model_validate({"name": "Nhà A", "lạ": 1})


def test_floor_draft_ignores_extra_contract_keys() -> None:
    """`drawings`, `areaM2`, `id` FE gửi thừa được nhận rồi bỏ."""
    body = ProjectCreateIn.model_validate({"name": "Nhà A", "floors": [_floor(drawings=[], areaM2=1.5, id="L-1")]})
    assert body.floors is not None
    assert floor_drafts(body.floors) == [FloorDraft(name="Tầng 1", order=0, elevation_mm=0, height_mm=3000)]


def test_floor_name_must_not_be_blank() -> None:
    """Tên tầng chỉ toàn khoảng trắng → 422 (min 1 **sau** trim)."""
    with pytest.raises(ValidationError):
        ProjectCreateIn.model_validate({"name": "Nhà A", "floors": [_floor(name="   ")]})


def test_non_string_name_falls_through_to_pydantic() -> None:
    """Giá trị không phải chuỗi đi thẳng cho Pydantic: lỗi kiểu, không `AttributeError`."""
    with pytest.raises(ValidationError) as caught:
        ProjectCreateIn.model_validate({"name": 7})
    assert _field_of(caught.value) == "name"


def test_projects_settings_defaults_and_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hạn mức mặc định đúng [5]; cache đọc lại sau `reset_projects_settings_cache()`."""
    reset_projects_settings_cache()
    settings = get_projects_settings()
    assert settings.projects_list_max == 500
    assert (settings.project_purge_after_days, settings.project_purge_batch) == (30, 20)
    assert settings.project_purge_lock_timeout_s == 30
    assert get_projects_settings() is settings

    monkeypatch.setenv("PROJECTS_LIST_MAX", "3")
    reset_projects_settings_cache()
    try:
        assert get_projects_settings().projects_list_max == 3
    finally:
        monkeypatch.undo()
        reset_projects_settings_cache()
