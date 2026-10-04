"""Thân lỗi W7: `field` của Pydantic, `VERSION_CONFLICT`, `HTTPException`, lỗi lạ."""

import json
from datetime import UTC, datetime
from typing import Annotated, Final, Literal

import httpx
import pytest
from fastapi.exceptions import RequestValidationError
from pydantic import Field, TypeAdapter, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.core.auth import Principal
from apps.api.core.errors import (
    error_payload,
    error_response,
    field_of,
    http_exception_error,
    request_id,
    simple_error,
    translate_unknown,
    validation_error,
)
from apps.api.core.tests.sample import sample_app, sample_client
from apps.api.core.wire import WireModel
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE, NOT_FOUND, PAYLOAD_TOO_LARGE
from packages.core.errors import MISSING, AppError, RemoteFieldChange, VersionConflictError
from packages.db.errors import translate_db_error
from packages.testing.fixtures.api import auth_headers

__all__ = ["sample_app", "sample_client"]

RID: Final = "rid-0123456789"
CHANGED_AT: Final = datetime(2026, 1, 2, 3, 4, 5, 678000, tzinfo=UTC)


def _change(value: object) -> RemoteFieldChange:
    """Một `RemoteFieldChange` hợp lệ mang giá trị tuỳ ý."""
    return RemoteFieldChange(
        entity_id="W-ABCDEFGHIJ",
        entity_type="wall",
        field="thicknessMm",
        value=value,
        changed_at=CHANGED_AT,
        changed_by="system:pipeline",
        changed_by_name="hệ thống AI",
    )


def test_field_of_stops_at_dict_key() -> None:
    """`overrides.WALL-THICKNESS.severity` → `overrides` (khoá dict không phải tên trường)."""
    assert field_of(("body", "overrides", "WALL-THICKNESS", "severity")) == "overrides"


def test_field_of_converts_snake_case() -> None:
    """Tham số đường là snake_case, trên dây là camelCase (W21)."""
    assert field_of(("path", "floor_id")) == "floorId"


def test_field_of_drops_root_only() -> None:
    """Loc chỉ có đoạn gốc thì không có `field` nào để trả."""
    assert field_of(("body",)) is None
    assert field_of(()) is None


def test_field_of_stops_at_validator_name() -> None:
    """Tên validator của Pydantic không phải tên trường."""
    assert field_of(("body", "items", "function-after[check()]")) == "items"


def test_field_of_keeps_list_index() -> None:
    """Chỉ số mảng vẫn là đoạn hợp lệ; `AppError` mới là nơi từ chối `field` sai mẫu."""
    assert field_of(("body", "items", 0, "name")) == "items.0.name"
    assert field_of(("body", 0, "name")) == "0.name"


def test_error_payload_of_version_conflict_drops_missing_value() -> None:
    """`MISSING` → **vắng** khoá `value` trên dây (HOP-DONG-MOI §1.1)."""
    payload = error_payload(VersionConflictError(current_version=3, remote_changes=[_change(MISSING)]), RID)
    assert payload["currentVersion"] == 3
    change = payload["remoteChanges"][0]  # type: ignore[index]  # thân đã dựng ngay trên
    assert "value" not in change
    assert change["changedAt"] == "2026-01-02T03:04:05.678Z"


def test_error_payload_keeps_real_value() -> None:
    """Giá trị thật (khác `MISSING`) ra dây trong khoá `value`."""
    payload = error_payload(VersionConflictError(current_version=1, remote_changes=[_change(120)]), RID)
    assert payload["remoteChanges"][0]["value"] == 120  # type: ignore[index]  # như trên


def test_error_response_falls_back_when_body_is_unserializable() -> None:
    """Dựng thân hỏng → thân chỉ còn `code` và `requestId`, tuyệt đối không 500."""
    broken = VersionConflictError(current_version=1, remote_changes=[_change(object())])
    response = error_response(broken, RID)
    assert response.status_code == 409
    assert json.loads(bytes(response.body)) == {"code": "VERSION_CONFLICT", "requestId": RID}


def test_error_response_sets_retry_after() -> None:
    """503 mang `Retry-After` theo đúng lỗi (W9)."""
    response = error_response(DEPENDENCY_UNAVAILABLE.error(retry_after=5), RID)
    assert response.headers["Retry-After"] == "5"


def test_simple_error_has_no_retry_after() -> None:
    """413 không đòi client thử lại, nên không có `Retry-After`."""
    response = simple_error(PAYLOAD_TOO_LARGE, RID)
    assert response.status_code == 413
    assert "Retry-After" not in response.headers


@pytest.mark.parametrize(
    ("status", "code"), [(400, "VALIDATION"), (404, "NOT_FOUND"), (405, "NOT_FOUND"), (413, "PAYLOAD_TOO_LARGE")]
)
def test_http_exception_mapping(status: int, code: str) -> None:
    """`HTTPException` của Starlette đổi sang mã W7 (BE-00 §4)."""
    response = http_exception_error(StarletteHTTPException(status_code=status), RID)
    assert json.loads(bytes(response.body))["code"] == code


def test_unmapped_http_exception_is_internal() -> None:
    """Status lạ không được lọt ra dây dưới dạng mã bịa: 500 `INTERNAL`."""
    response = http_exception_error(StarletteHTTPException(status_code=418), RID)
    assert response.status_code == 500
    assert json.loads(bytes(response.body))["code"] == "INTERNAL"


def test_translate_unknown_maps_db_failure() -> None:
    """Lỗi hạ tầng của Postgres → 503 (C13), không phải 500."""
    from sqlalchemy.exc import OperationalError

    failure = OperationalError("SELECT 1", {}, Exception("mất kết nối"))
    assert translate_db_error(failure) is not None
    translated = translate_unknown(failure)
    assert translated.code.code == "DEPENDENCY_UNAVAILABLE"
    assert translated.retry_after is not None


def test_translate_unknown_maps_redis_failure() -> None:
    """Redis mất kết nối → 503, không phải 500 (C13)."""
    from redis.exceptions import ConnectionError as RedisConnectionError

    assert translate_unknown(RedisConnectionError("đứt")).code.code == "DEPENDENCY_UNAVAILABLE"


def test_translate_unknown_is_internal_for_strange_error() -> None:
    """Lỗi lạ → 500 `INTERNAL`; stack chỉ vào log."""
    assert translate_unknown(ValueError("lạ")).code.code == "INTERNAL"


def test_request_id_outside_request_is_empty() -> None:
    """Ngoài vòng đời request không có id nào để gắn."""
    assert request_id() == ""


def test_app_error_keeps_params() -> None:
    """Tham số của lỗi giữ nguyên khoá dây."""
    assert NOT_FOUND.error(resource="project").wire_params() == {"resource": "project"}


async def test_method_not_allowed_becomes_404(sample_client: httpx.AsyncClient) -> None:
    """405 không lọt ra dây: FE chỉ biết 404 (BE-00 §4)."""
    response = await sample_client.delete("/api/sample/public")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


async def test_unknown_path_is_404(sample_client: httpx.AsyncClient) -> None:
    """Đường không có route → 404 `NOT_FOUND` theo thân W7."""
    response = await sample_client.get("/api/khong-co-dau")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


async def test_pydantic_error_on_dict_key_is_422_with_short_field(
    sample_client: httpx.AsyncClient, fake_principal: Principal
) -> None:
    """loc `overrides.WALL-THICKNESS.severity` → 422 `field="overrides"` (không 500)."""
    response = await sample_client.post(
        "/api/sample/overrides",
        json={"overrides": {"WALL-THICKNESS": {"severity": 7}}},
        headers=auth_headers(fake_principal),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION"
    assert body["field"] == "overrides"
    assert body["count"] == 1


async def test_extra_key_is_422(sample_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """C03: khoá lạ trong thân → 422 `VALIDATION` (`extra="forbid"`)."""
    response = await sample_client.post(
        "/api/sample/items", json={"name": "a", "la": 1}, headers=auth_headers(fake_principal)
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


def test_app_error_response_status_matches_code() -> None:
    """Mọi `AppError` ra dây đúng status đã khai ở sổ mã (BE-00 §4)."""
    assert error_response(AppError(NOT_FOUND), RID).status_code == 404


class _WallFields(WireModel):
    """Trường của nhánh `wall`."""

    height_mm: int


class _Wall(WireModel):
    """Nhánh `wall` của thân union."""

    object_kind: Literal["wall"]
    fields: _WallFields


class _Door(WireModel):
    """Nhánh `door` của thân union."""

    object_kind: Literal["door"]
    width_mm: int


type _Draft = Annotated[_Wall | _Door, Field(discriminator="object_kind")]


class _Batch(WireModel):
    """Union lồng trong mảng."""

    items: list[_Draft]


def _field_of_body(adapter: TypeAdapter[object], payload: object) -> str | None:
    """`field` của 422 mà `validation_error` trả cho `payload` — lỗi Pydantic thật, loc có gốc `body` như FastAPI."""
    with pytest.raises(ValidationError) as caught:
        adapter.validate_python(payload)
    errors = [{**error, "loc": ("body", *error["loc"])} for error in caught.value.errors()]
    body = json.loads(bytes(validation_error(RequestValidationError(errors, body=payload), RID).body))
    assert body["code"] == "VALIDATION"
    field = body.get("field")
    return field if isinstance(field, str) else None


DRAFT: Final = TypeAdapter[object](_Draft)
BATCH: Final = TypeAdapter[object](_Batch)


def test_field_of__union_branch_tag_is_not_a_field() -> None:
    """NO-248: tag nhánh (`wall`) pydantic chèn vào loc không ra dây — `fields.heightMm`, đúng đường trong thân."""
    payload = {"objectKind": "wall", "fields": {"heightMm": "cao"}}
    assert _field_of_body(DRAFT, payload) == "fields.heightMm"


def test_field_of__missing_key_inside_a_union_branch_keeps_its_name() -> None:
    """NO-248: khoá **vắng** (không có trong thân) ở cuối loc vẫn là `field`."""
    assert _field_of_body(DRAFT, {"objectKind": "wall", "fields": {}}) == "fields.heightMm"
    assert _field_of_body(DRAFT, {"objectKind": "door"}) == "widthMm"


def test_field_of__unknown_union_tag_names_the_discriminator() -> None:
    """NO-248: `objectKind` lạ → `field` = tên khoá phân biệt, không bỏ trống."""
    assert _field_of_body(DRAFT, {"objectKind": "cua-so"}) == "objectKind"
    assert _field_of_body(DRAFT, {}) == "objectKind"


def test_field_of__union_inside_a_list_keeps_the_index() -> None:
    """NO-248: union lồng trong mảng — chỉ số giữ nguyên, chỉ tag bị bỏ."""
    payload = {"items": [{"objectKind": "door", "widthMm": 1}, {"objectKind": "wall", "fields": {"heightMm": "x"}}]}
    assert _field_of_body(BATCH, payload) == "items.1.fields.heightMm"
    assert _field_of_body(BATCH, {"items": [{"objectKind": "cua-so"}]}) == "items.0.objectKind"


class _Holder(WireModel):
    """Union ở một khoá snake_case — thân được gửi tên trường thay alias (`populate_by_name`)."""

    wall_draft: _Draft


HOLDER: Final = TypeAdapter[object](_Holder)


def test_field_of__body_sent_by_field_name_still_drops_only_the_tag() -> None:
    """NO-248: khoá thân `wall_draft` (tên trường) khớp loc alias `wallDraft`; chỉ tag `wall` bị bỏ."""
    payload = {"wall_draft": {"objectKind": "wall", "fields": {"heightMm": "x"}}}
    assert _field_of_body(HOLDER, payload) == "wallDraft.fields.heightMm"


def test_field_of__without_a_json_body_keeps_the_loc() -> None:
    """Người gọi không có thân JSON (form multipart, `admin_ml_registry/upload.py`) — loc giữ nguyên trạng."""
    assert field_of(("body", "wall", "fields", "height_mm")) == "wall.fields.heightMm"
    assert field_of(("body", "wall", "fields"), body="khong-phai-object") == "wall.fields"
