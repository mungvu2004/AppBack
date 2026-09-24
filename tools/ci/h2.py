"""`python -m tools.ci.h2` — H2: schemathesis trên app thật, ASGI trong tiến trình (prompt B0-09 [6], [8]).

Không tham số dòng lệnh; `H2_MAX_EXAMPLES` (mặc định 25) là số ví dụ hypothesis tối đa cho **mỗi**
thao tác. Dựng Postgres, hai Redis (broker, cache) và MinIO thật bằng `testcontainers` (không nhập
`packages.testing` — mã không phải test, R-28); `upgrade head` rồi seed `APP_ENV`; `create_app` với
`FakeTokenVerifier` (chỉ nhận khi `APP_ENV=test`, BE-00 §2.2). Nguồn schema là chính `app.openapi()`
qua `schemathesis.openapi.from_asgi`; hai kiểm cho mỗi thao tác — không 5xx, 2xx khớp schema — và một
kiểm thêm: thao tác **được bảo vệ** mà mọi ví dụ chỉ nhận 401 là verifier nối sai (H2 xanh giả, K23).

`schemathesis.python.asgi` (4.27.3, đường nội bộ — API công khai của bản này không có cách khác để
lấy đúng vòng sự kiện dùng chung cho lifespan **và** mọi `Case.call()`; nâng bản kiểm lại module này)
giữ một vòng sự kiện nền dùng chung cho cả lifespan lẫn mọi lời gọi ASGI, nên engine asyncpg mà
`lifespan` mở không bị "gắn nhầm vòng lặp" giữa các lần gọi (packages/db/engine.py, docstring
`worker_sessionmaker`). `get_client(app)` khởi động lifespan ở lần vào đầu tiên (tự nhớ theo `id(app)`,
gọi lại là no-op) — đây là chỗ "chạy lifespan tường minh" của luật H2.
"""

import asyncio
import os
import secrets
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Final, cast

import schemathesis
from alembic import command
from fastapi import FastAPI
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from minio import Minio
from schemathesis import CheckFunction
from schemathesis.checks import not_a_server_error
from schemathesis.core.failures import FailureGroup
from schemathesis.core.result import Err
from schemathesis.python import asgi as asgi_client
from schemathesis.specs.openapi.checks import response_schema_conformance
from sqlalchemy.ext.asyncio import AsyncSession

# testcontainers 4.13 không có py.typed / gói stub (giống packages/testing/fixtures/services.py).
from testcontainers.minio import MinioContainer  # type: ignore[import-untyped]
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]
from testcontainers.redis import RedisContainer  # type: ignore[import-untyped]

from apps.api.core.app import create_app
from apps.api.core.auth import FakeTokenVerifier
from apps.api.core.openapi import operations
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.core.settings import reset_settings_cache
from packages.core.text import nfc, normalize_email
from packages.db.engine import GATE_CONNECT_TIMEOUT_S, create_engine, create_sessionmaker, session_scope
from packages.db.migrate_check import alembic_config
from packages.db.models import load_all_models
from packages.db.models.auth import User
from packages.db.seeds import apply_seeds
from packages.db.settings import get_database_settings, reset_database_settings_cache
from packages.messaging.settings import reset_messaging_settings_cache
from packages.storage.s3 import http_client
from packages.storage.settings import reset_storage_settings_cache
from tools.pinned_images import MINIO_IMAGE, POSTGRES_IMAGE, REDIS_IMAGE

MAX_EXAMPLES_ENV: Final = "H2_MAX_EXAMPLES"
DEFAULT_MAX_EXAMPLES: Final = 25
EXAMPLE_TIMEOUT_S: Final = 30.0
"""Trần đọc của mỗi ví dụ (R-24) — app trong tiến trình, 30 s chỉ để chặn một handler treo thật."""
EXCERPT_LEN: Final = 200
UNAUTHORIZED: Final = 401

PUBLIC_BASE_URL: Final = "https://h2.appback.test"
SECRET_KEY: Final = "h2-fake-secret-" * 3
S3_REGION: Final = "us-east-1"

_CHECKS: Final[list[CheckFunction]] = [
    cast(CheckFunction, not_a_server_error),
    cast(CheckFunction, response_schema_conformance),
]
"""`@schemathesis.check` gõ kiểu hàm đã đăng ký là hợp của `CheckFunction | type[ResponseCheck] |
type[RunCheck]`; cả hai hàm này là `CheckFunction` thật (không phải lớp check), ép kiểu để khớp
`Case.validate_response(checks=...)`."""


@dataclass(frozen=True, slots=True)
class OperationFailure:
    """Lỗi đầu tiên của một thao tác: tên kiểm hỏng, mã trạng thái (`None` khi ASGI tự ném), trích thân ngắn."""

    check: str
    status_code: int | None
    excerpt: str


@dataclass(frozen=True, slots=True)
class OperationOutcome:
    """Kết quả H2 của một thao tác đã mount: nhãn `METHOD path`, số ví dụ đã chạy, lỗi đầu (`None` = đạt)."""

    label: str
    examples: int
    failure: OperationFailure | None


@dataclass(slots=True)
class _RunState:
    """Sổ đếm của một lượt hypothesis trên một thao tác: ví dụ đã chạy, số lần 401, lỗi đầu tiên gặp."""

    examples: int = 0
    unauthorized: int = 0
    failure: OperationFailure | None = None


def _describe_call_exception(exc: Exception) -> OperationFailure:
    """ASGI tự ném khi ngoại lệ lọt hết middleware lỗi của app thử (không có `FinalErrorMiddleware`
    như app thật); vẫn là một dạng "5xx" cần báo — đổi hình dạng để báo cáo, không nuốt (R-16)."""
    excerpt = f"{type(exc).__name__}: {exc}"[:EXCERPT_LEN]
    return OperationFailure(check="not_a_server_error", status_code=None, excerpt=excerpt)


def _validate(case: "schemathesis.Case[Any]", response: schemathesis.Response) -> OperationFailure | None:
    """Đúng hai kiểm của luật H2 — không 5xx, 2xx khớp schema — trả lỗi **đầu tiên**, không hơn."""
    try:
        case.validate_response(response, checks=_CHECKS)
    except FailureGroup as group:
        exc = next(iter(group.exceptions))
        excerpt = (response.text or "")[:EXCERPT_LEN]
        return OperationFailure(check=exc.title, status_code=response.status_code, excerpt=excerpt)
    return None


def _run_operation(
    operation: "schemathesis.APIOperation[Any, Any, Any, Any]",
    *,
    max_examples: int,
    auth_header: dict[str, str],
    protected: bool,
) -> OperationOutcome:
    """Sinh tới `max_examples` ví dụ tất định (`derandomize=True`, không lưu database, không trần thời
    gian) cho một thao tác; đếm hết mọi ví dụ để soát "chỉ nhận 401" dù đã có lỗi khác (K23)."""
    state = _RunState()

    @hypothesis_settings(max_examples=max_examples, derandomize=True, database=None, deadline=None)
    @given(case=operation.as_strategy())
    def _example(case: "schemathesis.Case[Any]") -> None:
        state.examples += 1
        try:
            response = case.call(headers=auth_header, timeout=EXAMPLE_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 — xem docstring `_describe_call_exception`
            if state.failure is None:
                state.failure = _describe_call_exception(exc)
            return
        if response.status_code == UNAUTHORIZED:
            state.unauthorized += 1
        if state.failure is None:
            state.failure = _validate(case, response)

    _example()
    failure = state.failure
    if failure is None and protected and state.examples and state.unauthorized == state.examples:
        failure = OperationFailure(
            check="verifier_wired",
            status_code=UNAUTHORIZED,
            excerpt="thao tác được bảo vệ nhưng mọi ví dụ chỉ nhận 401 — verifier có thể nối sai",
        )
    return OperationOutcome(label=operation.label, examples=state.examples, failure=failure)


def _operations_of(schema: schemathesis.BaseSchema) -> "list[schemathesis.APIOperation[Any, Any, Any, Any]]":
    """Mọi thao tác hợp lệ của `schema`; một thao tác hỏng khi dò ném ngay, không im lặng bỏ qua (R-16, R-17)."""
    found: list[schemathesis.APIOperation[Any, Any, Any, Any]] = []
    for result in schema.get_all_operations():
        if isinstance(result, Err):
            raise RuntimeError(f"schema của app hỏng: {result.err()}")
        found.append(result.ok())
    return found


def run_h2(app: FastAPI, *, max_examples: int, auth_header: dict[str, str]) -> tuple[OperationOutcome, ...]:
    """Hàm lõi: test gọi thẳng với app thử, không cần hạ tầng thật. Dò schema của chính `app`
    (`app.openapi_url`, không giả định `/api/...` — app thử của test không mang tiền tố đó), chạy H2
    trên mọi thao tác đã mount; tự quản lifespan qua `schemathesis.python.asgi` (docstring module)."""
    if app.openapi_url is None:
        raise RuntimeError("app không bật openapi_url — H2 cần nguồn schema để dò thao tác")
    protected = {(op.method, op.path): op.protected for op in operations(app)}
    schema = schemathesis.openapi.from_asgi(app.openapi_url, app)
    outcomes: list[OperationOutcome] = []
    # `get_client` gõ kiểu tham số ASGI bằng `dict` bất biến thay vì `MutableMapping` hiệp biến mà
    # `FastAPI.__call__` dùng — cùng một giao thức ASGI thật, chỉ lệch chữ ký tĩnh của bản 4.27.3.
    # try/finally: _operations_of hay _run_operation ném lỗi thì lifespan (kết nối DB/Redis/MinIO đã
    # mở ở startup) vẫn phải tắt — trước đó (/merge-review lượt 1 #14) shutdown_lifespans() đứng
    # ngoài mọi khối bảo vệ, ngăn dọn dẹp nếu có lỗi (vô hại hiện tại vì tiến trình CLI thoát ngay
    # sau, nhưng sai nếu run_h2 được gọi lại trong cùng tiến trình sau này).
    try:
        with asgi_client.get_client(cast(Any, app)):
            for operation in _operations_of(schema):
                key = (str(operation.method).upper(), operation.path)
                outcomes.append(
                    _run_operation(
                        operation,
                        max_examples=max_examples,
                        auth_header=auth_header,
                        protected=protected.get(key, False),
                    )
                )
    finally:
        asgi_client.shutdown_lifespans()
    return tuple(outcomes)


def _redis_container(policy: str) -> RedisContainer:
    """Redis ảnh ghim, `maxmemory-policy` theo vai (broker `noeviction`, cache `allkeys-lru`); chưa khởi động."""
    container = RedisContainer(REDIS_IMAGE)
    container.with_command(f"redis-server --maxmemory-policy {policy}")
    return container


def _redis_url(container: RedisContainer) -> str:
    """URL `redis://` của một `RedisContainer` đã khởi động."""
    host = container.get_container_host_ip()
    port = container.get_exposed_port(6379)
    return f"redis://{host}:{port}/0"


def _make_bucket(endpoint: str, access_key: str, secret_key: str) -> str:
    """Bucket MinIO riêng của lượt H2 này; tên ngẫu nhiên nên các lượt chạy song song không đụng nhau."""
    client = Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=False,
        region=S3_REGION,
        http_client=http_client(),
    )
    bucket = f"h2-{secrets.token_hex(6)}"
    client.make_bucket(bucket)
    return bucket


@dataclass(frozen=True, slots=True)
class _Infra:
    """Địa chỉ hạ tầng thật vừa dựng — đủ để `_set_env` trỏ app vào."""

    postgres_url: str
    redis_broker_url: str
    redis_cache_url: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str


@contextmanager
def _provision() -> Iterator[_Infra]:
    """Dựng Postgres, hai Redis, MinIO thật bằng `testcontainers` (không qua `packages.testing`, R-28);
    mọi container được dừng ở `finally`, kể cả khi một cái dựng sau lỗi giữa chừng (R-24)."""
    stoppers: list[Callable[[], None]] = []
    try:
        postgres = PostgresContainer(POSTGRES_IMAGE, driver="asyncpg").start()
        stoppers.append(postgres.stop)
        broker = _redis_container("noeviction").start()
        stoppers.append(broker.stop)
        cache = _redis_container("allkeys-lru").start()
        stoppers.append(cache.stop)
        minio = MinioContainer(MINIO_IMAGE).start()
        stoppers.append(minio.stop)
        cfg = minio.get_config()
        bucket = _make_bucket(cfg["endpoint"], cfg["access_key"], cfg["secret_key"])
        yield _Infra(
            postgres_url=postgres.get_connection_url(),
            redis_broker_url=_redis_url(broker),
            redis_cache_url=_redis_url(cache),
            s3_endpoint=f"http://{cfg['endpoint']}",
            s3_access_key=cfg["access_key"],
            s3_secret_key=cfg["secret_key"],
            s3_bucket=bucket,
        )
    finally:
        for stop in reversed(stoppers):
            stop()


def _set_env(infra: _Infra) -> None:
    """Trỏ mọi cấu hình app vào hạ tầng vừa dựng; `APP_ENV=test` để `FakeTokenVerifier` được `create_app` nhận."""
    os.environ.update(
        {
            "APP_ENV": "test",
            "PUBLIC_BASE_URL": PUBLIC_BASE_URL,
            "SECRET_KEY": SECRET_KEY,
            "DATABASE_URL": infra.postgres_url,
            "DB_CONNECT_TIMEOUT_S": str(int(GATE_CONNECT_TIMEOUT_S)),
            "STORAGE_BACKEND": "s3",
            "S3_ENDPOINT": infra.s3_endpoint,
            "S3_PUBLIC_ENDPOINT": infra.s3_endpoint,
            "S3_BUCKET": infra.s3_bucket,
            "S3_ACCESS_KEY": infra.s3_access_key,
            "S3_SECRET_KEY": infra.s3_secret_key,
            "REDIS_BROKER_URL": infra.redis_broker_url,
            "REDIS_CACHE_URL": infra.redis_cache_url,
        }
    )
    reset_settings_cache()
    reset_database_settings_cache()
    reset_storage_settings_cache()
    reset_messaging_settings_cache()


async def _seed_admin_user(session: AsyncSession, admin_id: str) -> None:
    """Chèn dòng `users` vai `admin`, `active`, cho đúng id mà `_admin_header` sẽ dùng (NO-132).

    `FakeTokenVerifier` không tra DB nên id giả qua được xác thực, nhưng route ghi có FK tới `users`
    (vd `project_memberships.user_id`) — thiếu dòng thật là 500 lúc handler chạm FK, không phải lỗi
    của app đang kiểm.
    """
    email = f"h2-admin-{admin_id}@example.com"
    session.add(
        User(
            id=admin_id,
            email=nfc(email),
            email_normalized=normalize_email(email),
            name="H2 admin",
            password_hash=None,
            role="admin",
            status="active",
        )
    )


async def _seed(env: str, admin_id: str) -> None:
    """Seed `env` rồi chèn dòng admin, một lượt trong session riêng; seed thật (nếu có) phải idempotent
    (BE-00 §6.1, R-14) — admin giả chỉ chạy một lần mỗi tiến trình H2 nên không cần idempotent."""
    engine = create_engine(get_database_settings())
    try:
        async with session_scope(create_sessionmaker(engine)) as session:
            await apply_seeds(session, env)
            await _seed_admin_user(session, admin_id)
    finally:
        await engine.dispose()


def _migrate_and_seed(admin_id: str) -> None:
    """`upgrade head` rồi seed `APP_ENV` + dòng admin, dùng đúng cấu hình Alembic của B0-03 (`alembic_config()`)."""
    load_all_models()
    command.upgrade(alembic_config(), "head")
    asyncio.run(_seed(os.environ["APP_ENV"], admin_id))


def _max_examples() -> int:
    """`H2_MAX_EXAMPLES`, mặc định 25; không phải số nguyên dương → `ValueError` (fail-closed, R-17)."""
    raw = os.environ.get(MAX_EXAMPLES_ENV, str(DEFAULT_MAX_EXAMPLES))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{MAX_EXAMPLES_ENV} phải là số nguyên, nhận {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{MAX_EXAMPLES_ENV} phải dương, nhận {value}")
    return value


def _admin_header(admin_id: str) -> dict[str, str]:
    """Header `Authorization` của admin `admin_id`. `FakeTokenVerifier` không tra DB (BE-00 §2.2) nên
    id qua được xác thực mà không cần tồn tại thật — nhưng route ghi có FK tới `users` (NO-132), nên
    `_migrate_and_seed` phải chèn đúng dòng này trước khi H2 gọi route."""
    return {"Authorization": f"Bearer fake:{admin_id}:h2-session:admin"}


def _report(outcomes: tuple[OperationOutcome, ...]) -> bool:
    """In số thao tác, tổng ví dụ, lỗi đầu mỗi thao tác hỏng (không in header/bí mật, R-30); trả True nếu đạt hết."""
    total_examples = sum(o.examples for o in outcomes)
    sys.stdout.write(f"h2: {len(outcomes)} thao tác, {total_examples} ví dụ\n")
    failed = [o for o in outcomes if o.failure is not None]
    for outcome in failed:
        failure = outcome.failure
        assert failure is not None  # noqa: S101 — `failed` đã lọc theo đúng điều kiện này
        code = failure.status_code if failure.status_code is not None else "—"
        sys.stdout.write(f"  hỏng {outcome.label}: {failure.check} mã {code}: {failure.excerpt}\n")
    sys.stdout.write(f"h2: {'đạt' if not failed else 'hỏng'} ({len(failed)}/{len(outcomes)} thao tác hỏng)\n")
    return not failed


def main(argv: list[str] | None = None) -> int:
    """CLI: dựng hạ tầng thật, chạy H2 trên app thật, in bảng, thoát 0/1. Không nhận tham số (prompt B0-09 [8])."""
    if argv:
        sys.stderr.write(f"h2: không nhận tham số dòng lệnh: {' '.join(argv)}\n")
        return 2
    try:
        max_examples = _max_examples()
    except ValueError as exc:
        sys.stderr.write(f"h2: {exc}\n")
        return 1
    admin_id = new_id("usr", SystemClock())
    with _provision() as infra:
        _set_env(infra)
        _migrate_and_seed(admin_id)
        app = create_app(token_verifier=FakeTokenVerifier())
        outcomes = run_h2(app, max_examples=max_examples, auth_header=_admin_header(admin_id))
    return 0 if _report(outcomes) else 1


if __name__ == "__main__":
    # sys.argv[1:] tường minh: main(argv=None) không tự đọc sys.argv (đúng ý,
    # để test gọi main() không tham số), nhưng nghĩa là "python -m tools.ci.h2
    # x" trước đây chạy như KHÔNG có đối số — luật "không nhận tham số" chỉ có
    # tác dụng khi gọi qua đúng lối vào module (/merge-review lượt 1 #13).
    raise SystemExit(main(sys.argv[1:]))
