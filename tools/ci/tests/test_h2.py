"""Test `tools/ci/h2.py` (prompt B0-09 [8] "h2"): không có `operationId`, tên test tả việc.

Case đã liệt kê trước khi viết (R-13):
- **thường**: thao tác đạt cả hai kiểm (`/ok`), app thật hôm nay đạt hết (K23, R-29 — dịch vụ thật,
  không mock).
- **biên**: một thao tác nhiều ví dụ (tham số bắt buộc) để lỗi đầu tiên được giữ, các ví dụ sau không
  ghi đè (nhánh `state.failure is None` phải thấy cả hai giá trị).
- **lỗi**: ASGI tự ném (không `FinalErrorMiddleware`), 500 tường minh, 2xx sai schema, thao tác bảo vệ
  chỉ nhận 401 (verifier nối sai), schema hỏng khi dò, `H2_MAX_EXAMPLES` không hợp lệ, tham số dòng
  lệnh thừa.
- **đồng thời**: không áp dụng — CLI một lượt, không có trạng thái chia sẻ giữa các lượt gọi.
"""

import os
import time
from collections.abc import Iterator
from contextlib import nullcontext
from typing import cast

import pytest
import schemathesis
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from schemathesis.core.result import Err
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.openapi import Operation
from packages.core.clock import SystemClock
from packages.core.ids import is_id, new_id
from packages.core.settings import reset_settings_cache
from packages.db.models.auth import User
from packages.db.settings import reset_database_settings_cache
from packages.messaging.settings import reset_messaging_settings_cache
from packages.storage.settings import reset_storage_settings_cache
from packages.testing.fixtures import services
from tools.ci import h2


class _Out(BaseModel):
    value: int


def _sample_app() -> FastAPI:
    """App thử nhỏ: mỗi route cho đúng một kịch bản của bảng case ở đầu file."""
    app = FastAPI()

    @app.get("/ok", response_model=_Out)
    def ok() -> dict[str, int]:
        """Case thường: 2xx khớp schema, không 401 — cả hai kiểm đạt."""
        return {"value": 1}

    @app.get("/boom")
    def boom(x: str) -> None:
        """Case biên + lỗi: mọi giá trị của `x` đều ném — nhiều ví dụ, lỗi đầu tiên được giữ nguyên."""
        raise RuntimeError("boom")

    @app.get("/explicit500")
    def explicit500(x: str) -> JSONResponse:
        """Case lỗi + biên: 500 tường minh (không ném) với mọi `x` — nhiều ví dụ, chạm nhánh "lỗi đã có,
        bỏ qua kiểm lại" của `_run_operation` (khác `/boom`, vốn luôn thoát sớm ở nhánh ASGI tự ném)."""
        return JSONResponse(content={"detail": "boom"}, status_code=500)

    @app.get("/wrongshape", response_model=_Out)
    def wrongshape() -> JSONResponse:
        """Case lỗi: 200 nhưng sai schema đã khai (bỏ qua kiểm response_model của FastAPI)."""
        return JSONResponse(content={"totally": "different"})

    return app


def test_run_h2_rejects_app_without_openapi_url() -> None:
    """App không bật `openapi_url` → không có nguồn schema để dò, `run_h2` ném ngay (fail-closed, R-17)."""
    with pytest.raises(RuntimeError, match="openapi_url"):
        h2.run_h2(FastAPI(openapi_url=None), max_examples=5, auth_header={})


def test_run_h2_passes_healthy_operation() -> None:
    """Thao tác 2xx khớp schema, không 401 → không lỗi (case thường)."""
    outcomes = {o.label: o for o in h2.run_h2(_sample_app(), max_examples=5, auth_header={})}
    assert outcomes["GET /ok"].failure is None
    assert outcomes["GET /ok"].examples == 1


def test_run_h2_reports_asgi_exception_and_keeps_first_failure() -> None:
    """Ngoại lệ lọt ASGI (không `FinalErrorMiddleware`) → hỏng; nhiều ví dụ nhưng chỉ giữ lỗi đầu (case biên)."""
    outcomes = {o.label: o for o in h2.run_h2(_sample_app(), max_examples=5, auth_header={})}
    outcome = outcomes["GET /boom"]
    assert outcome.examples > 1, "cần nhiều ví dụ để chạm nhánh 'lỗi đã có, bỏ qua kiểm lại'"
    failure = outcome.failure
    assert failure is not None
    assert failure.check == "not_a_server_error"
    assert failure.status_code is None
    assert "RuntimeError" in failure.excerpt


def test_run_h2_reports_explicit_server_error() -> None:
    """500 trả tường minh (không ném) → kiểm `not_a_server_error` của schemathesis hỏng; nhiều ví dụ
    nhưng chỉ giữ lỗi đầu (case biên: nhánh 'đã có lỗi, bỏ qua kiểm lại' sau khi `case.call()` thành công)."""
    outcome = {o.label: o for o in h2.run_h2(_sample_app(), max_examples=5, auth_header={})}["GET /explicit500"]
    assert outcome.examples > 1, "cần nhiều ví dụ để chạm nhánh 'lỗi đã có, bỏ qua kiểm lại'"
    failure = outcome.failure
    assert failure is not None
    assert failure.check == "Server error"
    assert failure.status_code == 500


def test_run_h2_reports_response_schema_mismatch() -> None:
    """2xx nhưng thân sai schema đã khai → kiểm `response_schema_conformance` hỏng."""
    outcomes = {o.label: o for o in h2.run_h2(_sample_app(), max_examples=5, auth_header={})}
    failure = outcomes["GET /wrongshape"].failure
    assert failure is not None
    assert failure.check == "Response violates schema"
    assert failure.status_code == 200


def test_run_h2_flags_protected_operation_stuck_at_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """Thao tác được bảo vệ mà mọi ví dụ chỉ nhận 401 → hỏng thêm (verifier nối sai làm H2 xanh giả, K23)."""
    app = FastAPI()

    @app.get("/deny")
    def deny() -> None:
        raise HTTPException(status_code=401, detail="no")

    fake_operation = Operation(
        op="deny",
        method="GET",
        path="/deny",
        protected=True,
        versioned=False,
        idempotency="off",
        body_limit=0,
        has_body=False,
        has_query=False,
        returns_list=False,
        has_optional_response_fields=False,
        body_mirrors_path=False,
        permission_key="admin",
    )
    monkeypatch.setattr(h2, "operations", lambda app=None: [fake_operation])

    outcomes = h2.run_h2(app, max_examples=5, auth_header={})
    assert len(outcomes) == 1
    failure = outcomes[0].failure
    assert failure is not None
    assert failure.check == "verifier_wired"
    assert failure.status_code == h2.UNAUTHORIZED


class _FailingSchema:
    """Schema giả chỉ để kiểm `_operations_of`; không cần dựng schemathesis thật cho một nhánh phòng thủ."""

    def get_all_operations(self) -> Iterator[Err[Exception]]:
        """Một thao tác luôn hỏng khi dò — mô phỏng `InvalidSchema` của schemathesis."""
        yield Err(RuntimeError("mẫu hỏng"))


def test_operations_of_raises_on_invalid_schema() -> None:
    """Schema hỏng khi dò → `_operations_of` ném ngay, không bỏ qua thao tác đó (R-16, R-17)."""
    with pytest.raises(RuntimeError, match="mẫu hỏng"):
        h2._operations_of(cast(schemathesis.BaseSchema, _FailingSchema()))


@pytest.mark.parametrize("raw", ["abc", "0", "-1", "1.5"])
def test_max_examples_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    """Không phải số nguyên dương → `ValueError` (fail-closed, R-17)."""
    monkeypatch.setenv(h2.MAX_EXAMPLES_ENV, raw)
    with pytest.raises(ValueError, match=h2.MAX_EXAMPLES_ENV):
        h2._max_examples()


def test_max_examples_defaults_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Không đặt biến môi trường → mặc định 25."""
    monkeypatch.delenv(h2.MAX_EXAMPLES_ENV, raising=False)
    assert h2._max_examples() == h2.DEFAULT_MAX_EXAMPLES


def test_max_examples_reads_valid_custom_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Giá trị nguyên dương hợp lệ được dùng nguyên văn."""
    monkeypatch.setenv(h2.MAX_EXAMPLES_ENV, "7")
    assert h2._max_examples() == 7


def test_admin_header_matches_fake_token_pattern() -> None:
    """Header admin đúng mẫu `fake:<usr_ULID>:<sid>:admin` mà `FakeTokenVerifier` nhận, cho đúng id truyền vào."""
    admin_id = new_id("usr", SystemClock())
    token = h2._admin_header(admin_id)["Authorization"].removeprefix("Bearer ")
    prefix, user_id, session_id, role = token.split(":")
    assert prefix == "fake"
    assert user_id == admin_id
    assert is_id("usr", user_id)
    assert session_id
    assert role == "admin"


async def test_seed_admin_user_inserts_a_real_row(db_session: AsyncSession) -> None:
    """`_seed_admin_user` chèn đúng dòng `users` vai admin, active, cho id truyền vào (NO-132): route
    ghi có FK tới `users` cần dòng này tồn tại thật, không chỉ id đúng mẫu qua được `FakeTokenVerifier`."""
    admin_id = new_id("usr", SystemClock())
    await h2._seed_admin_user(db_session, admin_id)
    await db_session.commit()
    row = await db_session.get(User, admin_id)
    assert row is not None
    assert row.role == "admin"
    assert row.status == "active"


def test_report_pass_prints_summary(capsys: pytest.CaptureFixture[str]) -> None:
    """Không thao tác nào hỏng → in "đạt", trả `True`."""
    outcomes = (h2.OperationOutcome(label="GET /ok", examples=3, failure=None),)
    assert h2._report(outcomes) is True
    out = capsys.readouterr().out
    assert "1 thao tác, 3 ví dụ" in out
    assert "h2: đạt" in out


def test_report_fail_prints_first_failure_per_operation(capsys: pytest.CaptureFixture[str]) -> None:
    """Có thao tác hỏng → in đúng thao tác, kiểm, mã trạng thái, trích thân; trả `False`."""
    failure = h2.OperationFailure(check="not_a_server_error", status_code=500, excerpt="boom")
    outcomes = (
        h2.OperationOutcome(label="GET /ok", examples=1, failure=None),
        h2.OperationOutcome(label="GET /boom", examples=1, failure=failure),
    )
    assert h2._report(outcomes) is False
    out = capsys.readouterr().out
    assert "hỏng GET /boom: not_a_server_error mã 500: boom" in out
    assert "h2: hỏng (1/2 thao tác hỏng)" in out


def test_report_fail_without_status_code(capsys: pytest.CaptureFixture[str]) -> None:
    """Lỗi từ ASGI tự ném không có mã trạng thái → in "—" thay vì `None`."""
    failure = h2.OperationFailure(check="not_a_server_error", status_code=None, excerpt="RuntimeError: boom")
    outcomes = (h2.OperationOutcome(label="GET /boom", examples=1, failure=failure),)
    h2._report(outcomes)
    assert "mã —:" in capsys.readouterr().out


def test_main_rejects_extra_argv() -> None:
    """CLI không nhận tham số dòng lệnh (prompt B0-09 [8])."""
    assert h2.main(["--unexpected"]) == 2


def test_pinned_service_images_match_packages_testing() -> None:
    """Ảnh Postgres/Redis/MinIO của H2 phải khớp `packages.testing.fixtures.services` — h2.py chép
    tay ba hằng này vì `R-28` cấm nhập `packages.testing` từ mã không phải test (chính `h2.py`), nên
    không tự gom về một chỗ được; test này (được phép nhập `packages.testing`) chống lệch bản khi
    `services.py` nâng ảnh mà quên sửa theo ở `h2.py` (/merge-review lượt 1 #10)."""
    assert h2.POSTGRES_IMAGE == services.POSTGRES_IMAGE
    assert h2.REDIS_IMAGE == services.REDIS_IMAGE
    assert h2.MINIO_IMAGE == services.MINIO_IMAGE


def test_main_returns_1_for_invalid_max_examples(monkeypatch: pytest.MonkeyPatch) -> None:
    """`H2_MAX_EXAMPLES` sai → thoát 1 **trước** khi dựng hạ tầng (không cần Testcontainers ở test này)."""
    monkeypatch.setenv(h2.MAX_EXAMPLES_ENV, "abc")
    assert h2.main() == 1


def test_main_returns_1_when_report_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nhánh `else 1` của `main()`: hạ tầng và app được giả (không cần Testcontainers), chỉ soát kết nối hai phần."""
    monkeypatch.setattr(h2, "_provision", lambda: nullcontext(None))
    monkeypatch.setattr(h2, "_set_env", lambda infra: None)
    monkeypatch.setattr(h2, "_migrate_and_seed", lambda admin_id: None)
    monkeypatch.setattr(h2, "create_app", lambda **kwargs: FastAPI())
    failing = (
        h2.OperationOutcome(
            label="GET /x", examples=1, failure=h2.OperationFailure(check="c", status_code=500, excerpt="e")
        ),
    )
    monkeypatch.setattr(h2, "run_h2", lambda app, *, max_examples, auth_header: failing)
    assert h2.main() == 1


def _reset_all_settings_caches() -> None:
    """Bốn cache cấu hình mà `_set_env` đụng tới — đọc lại biến môi trường ở lần gọi sau."""
    reset_settings_cache()
    reset_database_settings_cache()
    reset_storage_settings_cache()
    reset_messaging_settings_cache()


@pytest.mark.ci_integration
def test_main_real_app_passes(capsys: pytest.CaptureFixture[str]) -> None:
    """App thật hôm nay, Testcontainers thật (K23, R-29) → H2 đạt hết, thoát 0.

    `ci_integration` khai tường minh: `main()` tự dựng hạ tầng bằng `testcontainers` trực tiếp,
    không qua fixture dịch vụ (`postgres_url`…) — suy luận theo bao đóng fixture của
    `packages/testing/fixtures/ci_split.py` sẽ xếp nhầm test này vào `unit` nếu không có marker.

    `H2_MAX_EXAMPLES` nhỏ để giữ thời lượng test hợp lý; `os.environ` được chụp lại và phục hồi
    sau lượt chạy vì `_set_env` ghi thẳng `os.environ` (không qua `monkeypatch`, để giống hệt lượt
    chạy CLI thật) — test khác trong cùng tiến trình pytest không thấy biến môi trường của lượt này.
    Số giây đo được in ra để báo cáo nghiệm thu trích lại (bảng E.10 của prompt).
    """
    snapshot = dict(os.environ)
    os.environ[h2.MAX_EXAMPLES_ENV] = "3"
    started = time.monotonic()
    try:
        assert h2.main() == 0
    finally:
        elapsed_s = time.monotonic() - started
        os.environ.clear()
        os.environ.update(snapshot)
        _reset_all_settings_caches()
    with capsys.disabled():
        print(f"test_main_real_app_passes: {elapsed_s:.1f}s")
