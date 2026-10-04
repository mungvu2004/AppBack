"""Fixture Postgres thật cho test (B0-03; K23: không SQLite, không mock).

- `db_template` (phiên): một database đã `upgrade head`, **không** seed; tên mang hậu tố
  tiến trình xdist (`template_db_name()`) nên `pytest -n` không giẫm lên nhau.
- `db_url` (mỗi test): **một** database dùng chung cho cả tiến trình, nhân bản từ bản trên một
  lần mỗi phiên; sau mỗi test đưa về trạng thái ngay-sau-`upgrade head` bằng **một giao dịch**
  `DELETE FROM` mọi bảng app + nạp lại dữ liệu gốc + `setval` mọi chuỗi về sau dòng lớn nhất (FIX-112,
  NO-277). Chữ ký không đổi: test vẫn chỉ thấy một URL và **dữ liệu** sạch như trước, kể cả bộ đếm
  `Identity()` lại từ 1 (từ sau dòng gốc với bảng có dữ liệu gốc). Phạm vi dọn chỉ là **dòng**: bảng,
  kiểu, chuỗi mà test tự tạo sống tới hết phiên của tiến trình (lượt dọn sau vẫn xoá dòng của chúng).
  Lượt dọn đi trên **một** kết nối giữ cả phiên, trên vòng sự kiện riêng của `SharedDb` (NO-267).
  Đo trên 26 bảng, n=50: `CREATE DATABASE … TEMPLATE` + `DROP` 162,0 ms/test,
  `TRUNCATE … RESTART IDENTITY CASCADE` 335-391 ms/test (chậm hơn: khoá ACCESS EXCLUSIVE + chạm
  file từng bảng/index), `DELETE` trong một giao dịch **17,2 ms** — nên chọn `DELETE`. Danh sách bảng
  do chính Postgres liệt kê lúc chạy (`_RESET_SQL`), không chụp sẵn: fixture của test có thể tạo thêm
  bảng sau khi phiên bắt đầu.
- `blank_db_url` (mỗi test): database rỗng, chưa migrate — cho test của `migrate_check`.
- `drop_after_commit()`: bỏ callback J09 để dựng J10 ("commit xong rồi chết").

Fixture async gắn `loop_scope="function"`: engine asyncpg thuộc về vòng sự kiện tạo ra
nó, mà test chạy ở vòng theo hàm.
"""

import asyncio
import os
import secrets
import sys
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from packages.db.engine import GATE_CONNECT_TIMEOUT_S, create_engine, create_sessionmaker
from packages.db.hooks import DROP_ENV
from packages.db.migrate_check import alembic_config
from packages.db.settings import DatabaseSettings, reset_database_settings_cache

# Một hằng, một chủ: `services.py` cũng đọc mã tiến trình này để chia dịch vụ dùng chung (R-07).
# Nhập từ `worker_id` chứ không từ `services`: module kia kéo theo testcontainers và một tác dụng
# phụ lúc nhập (`ryuk_disabled`), mà module CSDL không việc gì phải phụ thuộc vào đó (review F-3).
from packages.testing.fixtures.worker_id import xdist_worker_id

TEMPLATE_DB = "appback_template"
SHARED_DB = "appback_test"
ALEMBIC_TABLE = "alembic_version"
# Schema giữ bản chụp dữ liệu gốc do migration seed (`op.bulk_insert`), để nạp lại sau lượt dọn
RESET_SCHEMA = "appback_reset_seed"
# Trần chờ khoá của lượt dọn: một kết nối của test còn mở giữa giao dịch phải thành lỗi rõ ràng
# ngay, không phải treo cổng cho tới trần của Docker (K25: bước hỏng phải nhìn ra vì sao).
RESET_LOCK_TIMEOUT_MS = 10_000


def template_db_name() -> str:
    """Tên database mẫu của tiến trình này — mỗi tiến trình xdist một bản riêng (FIX-112).

    Bước 5 chạy `pytest -n`, và `db_template` là fixture **phiên**: mỗi tiến trình con chạy nó một
    lần, nên tên cố định làm tiến trình sau `DROP DATABASE … WITH (FORCE)` cái mà tiến trình trước
    đang nhân bản. Hậu tố là `PYTEST_XDIST_WORKER` (`gw0`…, xdist đặt trong tiến trình con) —
    đọc biến môi trường chứ không lấy fixture `worker_id` để `-p no:xdist` vẫn chạy được. Ngoài
    xdist biến không có → tên cũ, không đổi hành vi chạy tay.
    """
    return _per_worker(TEMPLATE_DB)


def shared_db_name() -> str:
    """Tên database dùng chung của tiến trình — `db_url` trả URL của nó (FIX-112)."""
    return _per_worker(SHARED_DB)


def _per_worker(base: str) -> str:
    """`base` kèm hậu tố tiến trình xdist, hay chính `base` khi chạy ngoài xdist."""
    worker = xdist_worker_id()
    return f"{base}_{worker}" if worker else base


def _with_database(url: str, name: str) -> str:
    """Cùng URL nhưng trỏ sang database `name` (bỏ query/fragment)."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{name}", "", ""))


async def _admin(url: str, statements: list[str]) -> None:
    """Chạy các câu quản trị (AUTOCOMMIT) trên database `postgres` của máy chủ."""
    # Sau FIX-149 chỉ `blank_db_url` còn `CREATE`/`DROP DATABASE` mỗi test; template và database dùng
    # chung thì mỗi tiến trình một lần. Vẫn là đường bắt tay của cổng nên chịu trần cổng thay vì 60 s
    # mặc định của asyncpg (NO-002).
    engine = create_async_engine(
        _with_database(url, "postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"timeout": GATE_CONNECT_TIMEOUT_S},
    )
    try:
        async with engine.connect() as connection:
            for statement in statements:
                await connection.execute(text(statement))
    finally:
        await engine.dispose()


def _create_database(url: str, name: str, template: str | None = None) -> None:
    """Tạo lại database `name` (xoá bản cũ nếu có), tuỳ chọn nhân bản từ `template`."""
    suffix = f' TEMPLATE "{template}"' if template else ""
    asyncio.run(_admin(url, [f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', f'CREATE DATABASE "{name}"{suffix}']))


def _drop_database(url: str, name: str) -> None:
    """Xoá database `name` nếu có, cắt mọi kết nối đang mở."""
    asyncio.run(_admin(url, [f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)']))


def assert_reset_target(url: str) -> None:
    """Chặn cứng: lượt dọn `DELETE` chỉ chạy được trên database của chính tiến trình test này (FIX-114).

    Lượt dọn xoá **mọi** bảng, nên một URL lạc — `DATABASE_URL` của máy thật, fixture bị gọi
    ngoài pytest, tên database của tiến trình xdist khác — là mất dữ liệu không lùi được. Hai
    điều kiện phải đúng cả hai, không thì `RuntimeError` và **không** câu SQL nào chạy: tên
    database khớp đúng `shared_db_name()` của tiến trình, và tiến trình thật sự đang chạy dưới
    pytest (`PYTEST_CURRENT_TEST` pytest đặt quanh từng pha, hay chính gói `pytest` đã nhập).
    Fail-closed theo R-17: nghi ngờ thì không xoá.
    """
    name = urlsplit(url).path.lstrip("/")
    expected = shared_db_name()
    if name != expected:
        raise RuntimeError(f"lượt dọn test từ chối database '{name}': chỉ dọn được '{expected}' (FIX-114)")
    if not os.environ.get("PYTEST_CURRENT_TEST") and "pytest" not in sys.modules:
        raise RuntimeError("lượt dọn test chỉ chạy dưới pytest: không thấy dấu vết phiên pytest (FIX-114)")


async def _reset(engine: AsyncEngine, url: str, statements: list[str]) -> None:
    """Chạy `statements` trên database của test trong **một** giao dịch, có trần chờ khoá.

    Một giao dịch chứ không AUTOCOMMIT vì hai lẽ: `SET LOCAL session_replication_role` chỉ có
    hiệu lực trong giao dịch, và lượt dọn phải là tất-cả-hoặc-không (nửa vời để lại database lẫn
    dữ liệu của test trước cho test sau).

    `lock_timeout` (đặt trên kết nối của `engine`, `shared_db`) là lưới an toàn: một kết nối của
    test còn treo giữa giao dịch giữ khoá dòng sẽ chặn `DELETE`. Có trần thì lượt dọn hỏng ngay với
    `LockNotAvailable` nêu đúng bảng, thay vì cả bước 5 đứng im.

    `assert_reset_target` chạy **trước** khi lấy kết nối: đây là đường duy nhất chạy `DELETE`, nên
    chặn ở đây là chặn cho mọi người gọi (R-19).
    """
    assert_reset_target(url)
    async with engine.connect() as connection:
        for statement in statements:
            await connection.execute(text(statement))
        await connection.commit()


@dataclass(frozen=True, slots=True)
class SharedDb:
    """Database dùng chung của một tiến trình cùng kết nối dọn giữ cả phiên (NO-267).

    Kết nối asyncpg gắn với vòng sự kiện đã mở nó, mà mỗi test chạy trên vòng riêng; nên lượt dọn có
    vòng sự kiện **của nó** (`loop`, không đặt làm vòng hiện hành của luồng) và một engine một kết nối
    dùng lại qua mọi test — bỏ lượt bắt tay mỗi test. `pool_pre_ping`: test cắt kết nối của database
    (`pg_terminate_backend`) thì lượt dọn kế tự nối lại thay vì hỏng.
    """

    url: str
    plan: list[str]
    loop: asyncio.AbstractEventLoop
    engine: AsyncEngine

    def reset(self) -> None:
        """Đưa database về trạng thái ngay sau `upgrade head` — `db_url` gọi sau mỗi test."""
        self.loop.run_until_complete(_reset(self.engine, self.url, self.plan))


# Lượt xoá = **một** câu: khối PL/pgSQL tự liệt kê bảng lúc **chạy**, nên không bao giờ
# lệch. Liệt kê sẵn một lần rồi dùng lại là sai: fixture của test có thể `metadata.create_all` thêm
# bảng sau khi phiên đã bắt đầu (bảng `sample_*` của `apps/api/core`, bảng dựng tay của
# `packages/db/tests/test_engine.py`) — danh sách chụp lúc đầu phiên không có chúng, và dữ liệu của
# chúng rò sang test sau. `set_config(…, true)` = `SET LOCAL`: tắt trigger khoá ngoài trong **giao
# dịch này**, nên xoá rồi nạp lại dữ liệu gốc (vòng thứ hai: mỗi bản chụp trong `RESET_SCHEMA` mà
# `_SNAPSHOT_SQL` dựng) theo thứ tự bảng nào cũng được. Tên bảng chỉ vào SQL qua `format('%I')`.
_RESET_SQL = f"""
DO $$
DECLARE name text;
BEGIN
  PERFORM set_config('session_replication_role', 'replica', true);
  FOR name IN
    SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> '{ALEMBIC_TABLE}'
  LOOP
    EXECUTE format('DELETE FROM public.%I', name);
  END LOOP;
  FOR name IN SELECT tablename FROM pg_tables WHERE schemaname = '{RESET_SCHEMA}' LOOP
    EXECUTE format('INSERT INTO public.%I SELECT * FROM %I.%I', name, '{RESET_SCHEMA}', name);
  END LOOP;
END $$;
"""  # noqa: S608 — chỉ chèn hằng của module (`ALEMBIC_TABLE`, `RESET_SCHEMA`), không phải dữ liệu ngoài

# Chụp dữ liệu gốc của migration, chạy **một** lần mỗi phiên: bảng nào có dòng ngay sau `upgrade head`
# được sao sang `RESET_SCHEMA` (cùng tên) để `_RESET_SQL` nạp lại. Một khối thay N lượt hỏi-có-dòng
# từ Python; tên bảng chỉ vào SQL qua `format('%I')` nên tên chứa `"` cũng không thoát được.
_SNAPSHOT_SQL = f"""
DO $$
DECLARE name text; seeded boolean;
BEGIN
  FOR name IN
    SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> '{ALEMBIC_TABLE}'
  LOOP
    EXECUTE format('SELECT EXISTS (SELECT 1 FROM public.%I)', name) INTO seeded;
    IF seeded THEN
      EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', '{RESET_SCHEMA}');
      EXECUTE format('CREATE TABLE IF NOT EXISTS %I.%I AS TABLE public.%I', '{RESET_SCHEMA}', name, name);
    END IF;
  END LOOP;
END $$;
"""  # noqa: S608 — như `_RESET_SQL`: chỉ chèn hằng của module

# Chạy **sau** lượt nạp lại dữ liệu gốc (NO-277): `DELETE` không lùi bộ đếm `Identity()`, mà bản cũ
# (database mới mỗi test) cho bộ đếm chạy lại từ đầu — thiếu bước này thì test khẳng định id tự tăng đỏ
# theo thứ tự chạy. Đặt về `max(cột) + 1` chứ không về 1: dòng gốc nạp lại mang sẵn id, bộ đếm về 1 là
# dòng thêm đầu tiên của test sau đụng khoá chính. Bảng rỗng → `max` là NULL → lại từ 1 như cũ.
_RESEQUENCE_SQL = """
DO $$
DECLARE tbl text; col text; seq text;
BEGIN
  FOR tbl, col, seq IN
    SELECT table_name, column_name, pg_get_serial_sequence(format('%I.%I', table_schema, table_name), column_name)
    FROM information_schema.columns WHERE table_schema = 'public'
  LOOP
    IF seq IS NOT NULL THEN
      EXECUTE format('SELECT setval(%L, COALESCE((SELECT max(%I) FROM public.%I), 0) + 1, false)', seq, col, tbl);
    END IF;
  END LOOP;
END $$;
"""


async def _build_reset_plan(url: str) -> list[str]:
    """Câu lệnh đưa database về đúng trạng thái ngay sau `upgrade head` — dựng một lần mỗi phiên.

    `DELETE` từng bảng, **không** `TRUNCATE`: đo trên 26 bảng, n=50, TRUNCATE tốn 335-391 ms/test
    (khoá ACCESS EXCLUSIVE + chạm file từng bảng và từng index) còn cả loạt DELETE trong một giao
    dịch tốn 17,2 ms — bảng của test rỗng hoặc vài dòng, nên DELETE gần như không có việc gì làm.

    Phần **duy nhất** chụp một lần là dữ liệu gốc của migration (`op.bulk_insert`): `_SNAPSHOT_SQL`
    sao bảng có dòng sang `RESET_SCHEMA` bằng `CREATE TABLE … AS TABLE`, rồi `_RESET_SQL` nạp lại
    bằng `INSERT … SELECT *` sau mỗi lượt xoá. Thuần SQL: không phản chiếu kiểu cột, không giữ dòng
    nào trong Python. Chụp một lần là đúng vì migration không đổi giữa phiên, còn danh sách **bảng**
    thì đổi được nên `_RESET_SQL` tự liệt kê lúc chạy.
    """
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT", connect_args={"timeout": GATE_CONNECT_TIMEOUT_S})
    try:
        async with engine.connect() as connection:
            await connection.execute(text(_SNAPSHOT_SQL))
    finally:
        await engine.dispose()
    return [_RESET_SQL, _RESEQUENCE_SQL]


def _alembic_upgrade(url: str) -> None:
    """`alembic upgrade head` trên `url`; trả lại `DATABASE_URL` cũ và cache cấu hình sau đó."""
    from alembic import command  # nhập tại chỗ: giữ thời gian thu thập test thấp

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    reset_database_settings_cache()  # env.py đọc `DatabaseSettings`, mà nó có cache
    try:
        command.upgrade(alembic_config(), "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        reset_database_settings_cache()


@pytest.fixture(scope="session")
def db_template(postgres_url: str) -> Iterator[str]:
    """Database mẫu đã migrate; `db_url` nhân bản từ nó."""
    template = template_db_name()
    _create_database(postgres_url, template)
    template_url = _with_database(postgres_url, template)
    _alembic_upgrade(template_url)
    yield template_url
    _drop_database(postgres_url, template)


@pytest.fixture(scope="session")
def shared_db(postgres_url: str, db_template: str) -> Iterator[SharedDb]:
    """Database dùng chung một tiến trình — nhân bản template một lần — cùng kết nối dọn của nó."""
    name = shared_db_name()
    _create_database(postgres_url, name, template=template_db_name())
    url = _with_database(postgres_url, name)
    plan = asyncio.run(_build_reset_plan(url))
    loop = asyncio.new_event_loop()
    # Dựng engine **trong** `try`: dựng hỏng thì vòng sự kiện vẫn được đóng và database vẫn bị xoá.
    try:
        engine = create_async_engine(
            url,
            pool_size=1,
            max_overflow=0,
            pool_pre_ping=True,
            connect_args={
                "timeout": GATE_CONNECT_TIMEOUT_S,
                "server_settings": {"lock_timeout": str(RESET_LOCK_TIMEOUT_MS)},
            },
        )
        try:
            yield SharedDb(url=url, plan=plan, loop=loop, engine=engine)
        finally:
            loop.run_until_complete(engine.dispose())
    finally:
        loop.close()
        _drop_database(postgres_url, name)


@pytest.fixture
def db_url(shared_db: SharedDb) -> Iterator[str]:
    """Dữ liệu sạch cho một test (FIX-112: dọn bằng `DELETE`, không nhân bản database mỗi test).

    Chữ ký cũ: test nhận đúng một URL và thấy các bảng rỗng (trừ dữ liệu gốc của migration) như
    trước, bộ đếm `Identity()` cũng lại từ đầu. Khác là bản thân database dùng chung cả tiến trình —
    bảng/kiểu do test tạo sống tới hết phiên (NO-277) — và lượt dọn chạy **sau** test —
    test đầu tiên của tiến trình thấy bản vừa nhân bản từ template, test sau thấy bản vừa dọn.
    `finally` nên test hỏng giữa đường vẫn dọn.

    Dọn chạy ở finalizer của `db_url`, mà `db_sessionmaker` phụ thuộc `db_url`: pytest gỡ fixture
    theo thứ tự ngược, nên engine của test đã `dispose` xong trước khi lượt dọn xin khoá.
    """
    try:
        yield shared_db.url
    finally:
        shared_db.reset()


@pytest.fixture
def blank_db_url(postgres_url: str) -> Iterator[str]:
    """Database rỗng, chưa chạy Alembic (test của `migrate_check`)."""
    name = f"b_{secrets.token_hex(8)}"
    _create_database(postgres_url, name)
    yield _with_database(postgres_url, name)
    _drop_database(postgres_url, name)


@pytest_asyncio.fixture(loop_scope="function")
async def db_sessionmaker(db_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Sessionmaker trên engine riêng của test, nối vào database của `db_url`."""
    # Pool nhỏ: mỗi tiến trình một database dùng chung, Postgres không phải giữ hàng trăm kết nối.
    # Trần bắt tay của đường cổng, không phải 10 s của đường request (NO-036, cùng lý do `_admin`).
    settings = DatabaseSettings(
        database_url=db_url, db_pool_size=5, db_max_overflow=0, db_connect_timeout_s=int(GATE_CONNECT_TIMEOUT_S)
    )
    engine = create_engine(settings)
    try:
        yield create_sessionmaker(engine)
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(loop_scope="function")
async def db_session(db_sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """Một `AsyncSession` của test, đóng sau test."""
    async with db_sessionmaker() as session:
        yield session


@contextmanager
def drop_after_commit() -> Iterator[None]:
    """J10: commit vẫn bền vững nhưng callback sau commit **không** chạy.

    Cờ cấp tiến trình (biến môi trường) nên có hiệu lực cả trong luồng `celery_worker`.
    """
    if os.environ.get("APP_ENV") != "test":
        raise RuntimeError("drop_after_commit() chỉ dùng khi APP_ENV=test")
    previous = os.environ.get(DROP_ENV)
    os.environ[DROP_ENV] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(DROP_ENV, None)
        else:
            os.environ[DROP_ENV] = previous
