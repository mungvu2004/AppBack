from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from packages.core import error_codes
from packages.core.errors import (
    ERRORS,
    MISSING,
    AppError,
    ErrorCode,
    ErrorRegistry,
    RemoteFieldChange,
    VersionConflictError,
)

CORE_CODES = {
    "VALIDATION": 422,
    "PATH_BODY_MISMATCH": 422,
    "MALFORMED_JSON": 400,
    "CURSOR_INVALID": 422,
    "NOT_FOUND": 404,
    "FORBIDDEN": 403,
    "PAYLOAD_TOO_LARGE": 413,
    "RATE_LIMITED": 429,
    "DEPENDENCY_UNAVAILABLE": 503,
    "INTERNAL": 500,
    "UNAUTHENTICATED": 401,
    "INVALID_CREDENTIALS": 401,
    "SESSION_REVOKED": 401,
    "ACCOUNT_DISABLED": 403,
    "ORIGIN_MISMATCH": 403,
    "VERSION_CONFLICT": 409,
    "PRECONDITION_REQUIRED": 428,
    "IDEMPOTENCY_KEY_REUSED": 422,
    "IDEMPOTENCY_IN_PROGRESS": 503,
    "IMAGE_TOO_LARGE": 422,
    "PDF_UNREADABLE": 422,
    "FILE_CORRUPT": 422,
    "FILE_TYPE_MISMATCH": 422,
    "UPLOAD_INCOMPLETE": 422,
    "UPLOAD_SIZE_MISMATCH": 422,
    "CAD_NOT_SUPPORTED": 422,
}
USER_ID = "usr_01J" + "0" * 22 + "Z"


@pytest.fixture
def registry() -> ErrorRegistry:
    return ErrorRegistry()


# --- sổ mã -------------------------------------------------------------------


def test_error_codes_module_defines_exactly_core_codes() -> None:
    defined = {v.code: v.status for v in vars(error_codes).values() if isinstance(v, ErrorCode)}
    assert defined == CORE_CODES
    assert len(defined) == 26
    assert all(name == code.code for name, code in vars(error_codes).items() if isinstance(code, ErrorCode))


def test_errors_all_contains_core_codes() -> None:
    registered = {c.code: c.status for c in ERRORS.all()}
    assert CORE_CODES.items() <= registered.items()


def test_define_returns_code_and_lists_it(registry: ErrorRegistry) -> None:
    code = registry.define("FLOOR_ID_TAKEN", 409)
    assert code == ErrorCode("FLOOR_ID_TAKEN", 409)
    assert registry.all() == (code,)


def test_define_rejects_duplicate(registry: ErrorRegistry) -> None:
    registry.define("FLOOR_ID_TAKEN", 409)
    with pytest.raises(ValueError, match="đã khai"):
        registry.define("FLOOR_ID_TAKEN", 422)


def test_define_rejects_duplicate_core_code_in_global_registry() -> None:
    with pytest.raises(ValueError, match="đã khai"):
        ERRORS.define("NOT_FOUND", 404)


@pytest.mark.parametrize("code", ["floor_taken", "AB", "1ABC", "_ABC", "AB-C", "A" * 65, "ABC\n", "ÀBC"])
def test_define_rejects_bad_pattern(registry: ErrorRegistry, code: str) -> None:
    with pytest.raises(ValueError, match="sai mẫu"):
        registry.define(code, 422)


def test_define_accepts_pattern_bounds(registry: ErrorRegistry) -> None:
    registry.define("ABC", 422)
    registry.define("A" * 64, 422)


@pytest.mark.parametrize("status", [200, 402, 405, 410, 418, 500, 502, 504])
def test_define_rejects_unknown_status(registry: ErrorRegistry, status: int) -> None:
    with pytest.raises(ValueError, match="status"):
        registry.define("SOME_ERROR", status)


def test_define_allows_500_only_for_internal(registry: ErrorRegistry) -> None:
    assert registry.define("INTERNAL", 500).status == 500


def test_define_rejects_401_outside_session_group(registry: ErrorRegistry) -> None:
    with pytest.raises(ValueError, match="401"):
        registry.define("WRONG_CURRENT_PASSWORD", 401)


@pytest.mark.parametrize("code", ["UNAUTHENTICATED", "INVALID_CREDENTIALS", "SESSION_REVOKED"])
def test_define_allows_401_for_session_group(registry: ErrorRegistry, code: str) -> None:
    assert registry.define(code, 401).status == 401


# --- AppError ------------------------------------------------------------------


def test_error_maps_file_name_to_wire_key() -> None:
    err = error_codes.FILE_CORRUPT.error(file_name="plan.pdf", step="preprocess")
    assert err.params == {"fileName": "plan.pdf", "step": "preprocess"}
    assert err.wire_params() == {"fileName": "plan.pdf", "step": "preprocess"}
    assert err.code is error_codes.FILE_CORRUPT
    assert err.retry_after is None
    assert str(err) == "FILE_CORRUPT"


def test_error_accepts_every_param() -> None:
    err = error_codes.VALIDATION.error(
        step="qualityCheck",
        floor="L-0000010ABC",
        count=0,
        field="body.items.0",
        resource="libraryItem",
        file_name="a",
        layer="walls",
    )
    assert set(err.wire_params()) == {"step", "floor", "count", "field", "resource", "fileName", "layer"}


def test_wire_params_is_a_copy() -> None:
    err = error_codes.NOT_FOUND.error(resource="project")
    err.wire_params()["resource"] = "user"
    assert err.params["resource"] == "project"
    with pytest.raises(TypeError):
        err.params["resource"] = "user"  # type: ignore[index]  # kiểm Mapping chỉ đọc lúc chạy


def test_error_rejects_unknown_param() -> None:
    with pytest.raises(ValueError, match="tham số lỗi lạ"):
        error_codes.VALIDATION.error(message="nope")


def test_error_rejects_wire_key_spelling() -> None:
    with pytest.raises(ValueError, match="tham số lỗi lạ: fileName"):
        error_codes.VALIDATION.error(fileName="a.pdf")


@pytest.mark.parametrize("resource", ["projects", "Project", "floorPlan", "", ["project"], 1])
def test_error_rejects_resource_outside_list(resource: object) -> None:
    with pytest.raises(ValueError, match="resource"):
        error_codes.NOT_FOUND.error(resource=resource)


@pytest.mark.parametrize("field", ["", "1abc", "body..name", "body.", ".body", "body_name", "body-name", "bódy", 3])
def test_error_rejects_bad_field(field: object) -> None:
    with pytest.raises(ValueError, match="field"):
        error_codes.VALIDATION.error(field=field)


@pytest.mark.parametrize("field", ["name", "baseVersion", "body.items.0.name", "a.0"])
def test_error_accepts_field(field: str) -> None:
    assert error_codes.VALIDATION.error(field=field).params["field"] == field


@pytest.mark.parametrize("count", [-1, 1.0, "2", True])
def test_error_rejects_bad_count(count: object) -> None:
    with pytest.raises(ValueError, match="count"):
        error_codes.VALIDATION.error(count=count)


@pytest.mark.parametrize(
    ("name", "value"),
    [("step", "upload"), ("step", ["preprocess"]), ("floor", ""), ("file_name", 1), ("layer", None)],
)
def test_error_rejects_bad_value(name: str, value: object) -> None:
    params: dict[str, Any] = {name: value}
    with pytest.raises(ValueError, match=name):
        error_codes.VALIDATION.error(**params)


@pytest.mark.parametrize("code", [error_codes.RATE_LIMITED, error_codes.DEPENDENCY_UNAVAILABLE])
def test_error_requires_retry_after_for_429_503(code: ErrorCode) -> None:
    with pytest.raises(ValueError, match="retry_after"):
        code.error()


@pytest.mark.parametrize("retry_after", [0, 11, -1, True, 1.5])
def test_error_rejects_retry_after_out_of_range(retry_after: int) -> None:
    with pytest.raises(ValueError, match="retry_after"):
        error_codes.RATE_LIMITED.error(retry_after=retry_after)


@pytest.mark.parametrize("retry_after", [1, 10])
def test_error_accepts_retry_after_bounds(retry_after: int) -> None:
    assert error_codes.IDEMPOTENCY_IN_PROGRESS.error(retry_after=retry_after).retry_after == retry_after


def test_error_rejects_retry_after_on_other_status() -> None:
    with pytest.raises(ValueError, match="retry_after"):
        error_codes.NOT_FOUND.error(retry_after=1, resource="project")


def test_app_error_has_no_message_or_detail() -> None:
    err = AppError(error_codes.FORBIDDEN)
    assert not hasattr(err, "message")
    assert not hasattr(err, "detail")
    assert err.args == ("FORBIDDEN",)


# --- VersionConflictError ------------------------------------------------------


def _change(**overrides: object) -> RemoteFieldChange:
    fields: dict[str, object] = {
        "entity_id": "W-0000010ABC",
        "entity_type": "wall",
        "field": "thicknessMm",
        "value": 200,
        "changed_at": datetime(2026, 1, 1, tzinfo=UTC),
        "changed_by": USER_ID,
        "changed_by_name": "Ánh",
    } | overrides
    return RemoteFieldChange(**fields)  # type: ignore[arg-type]  # dựng từ dict để thử từng trường


def test_version_conflict_error() -> None:
    change = _change()
    err = VersionConflictError(current_version=3, remote_changes=[change])
    assert err.code is error_codes.VERSION_CONFLICT
    assert err.code.status == 409
    assert err.current_version == 3
    assert err.remote_changes == (change,)
    assert err.wire_params() == {}


def test_version_conflict_error_allows_empty_changes() -> None:
    assert VersionConflictError(current_version=0, remote_changes=()).remote_changes == ()


@pytest.mark.parametrize("version", [-1, True, 1.0])
def test_version_conflict_error_rejects_bad_version(version: int) -> None:
    with pytest.raises(ValueError, match="current_version"):
        VersionConflictError(current_version=version, remote_changes=())


def test_version_conflict_error_rejects_foreign_changes() -> None:
    with pytest.raises(ValueError, match="RemoteFieldChange"):
        VersionConflictError(current_version=1, remote_changes=[{"field": "x"}])  # type: ignore[list-item]  # kiểm lúc chạy


def test_remote_change_value_none_rejected() -> None:
    with pytest.raises(ValueError, match="None"):
        _change(value=None)


def test_remote_change_missing_value_allowed() -> None:
    assert _change(value=MISSING).value is MISSING
    assert repr(MISSING) == "MISSING"


def test_remote_change_system_pipeline_allowed() -> None:
    assert _change(changed_by="system:pipeline").changed_by == "system:pipeline"


def test_remote_change_other_timezone_allowed() -> None:
    at = datetime(2026, 1, 1, 7, tzinfo=timezone(timedelta(hours=7)))
    assert _change(changed_at=at).changed_at == at


@pytest.mark.parametrize(
    "changed_by", ["usr_123", "prj_01J" + "0" * 22 + "Z", "system", "system:worker", USER_ID.lower(), ""]
)
def test_remote_change_bad_changed_by_rejected(changed_by: str) -> None:
    with pytest.raises(ValueError, match="changed_by"):
        _change(changed_by=changed_by)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("entity_id", ""),
        ("field", ""),
        ("changed_by_name", ""),
        ("changed_by_name", None),
        ("entity_type", "vertexes"),
        ("changed_at", datetime(2026, 1, 1)),  # noqa: DTZ001 — kiểm datetime không múi giờ bị từ chối
    ],
)
def test_remote_change_bad_field_rejected(name: str, value: object) -> None:
    with pytest.raises(ValueError, match=name):
        _change(**{name: value})
