"""`notify()` (B4-02 [6], [8]): kiểm đầu vào, làm sạch, khử trùng, J09, J10, một lần XADD (K32)."""

import logging
from collections.abc import Iterator
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any, Final

import pytest
from sqlalchemy import delete, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.redis import RedisContainer  # type: ignore[import-untyped]  # testcontainers chưa có py.typed

from apps.api.notifications.jobs import run_notification_publish
from apps.api.notifications.service import notify
from apps.api.notifications.tests.support import FLOOR, commit_notify, rows_of, seed_project, stream_ids
from packages.core.ids import is_id
from packages.core.text import nfc
from packages.db.hooks import after_commit_idle
from packages.db.models.notifications import NotificationRow
from packages.messaging.redis import AsyncRedis
from packages.messaging.settings import reset_messaging_settings_cache
from packages.messaging.streams import EventBus, user_stream
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.services import ephemeral_redis

KEY: Final = "test:notify:1"
RLO: Final = chr(0x202E)
LRI: Final = chr(0x2066)
PDI: Final = chr(0x2069)
ZWSP: Final = chr(0x200B)
BEL: Final = chr(0x07)
NEWLINE: Final = chr(0x0A)
TAB: Final = chr(0x09)
GRAVE: Final = chr(0x0300)
CIRCUMFLEX: Final = chr(0x0302)
ACUTE: Final = chr(0x0301)
BATCH: Final = 100


async def _fixture_pair(db: AsyncSession) -> tuple[Any, Any]:
    """(người nhận, dự án chứa họ)."""
    user = await make_user(db)
    return user, await seed_project(db, owner=user)


@pytest.mark.parametrize(
    "override",
    [
        {"place": "walls", "floor_level_id": None},
        {"place": "thickness", "floor_level_id": ""},
        {"kind": "projectInvite", "place": "walls"},
        {"kind": "commentMention"},
        {"place": "dashboard"},
        {"dedupe_key": ""},
        {"dedupe_key": "co dau cach"},
        {"dedupe_key": "x" * 201},
        {"message": "   "},
        {"object_label": RLO + BEL + "  "},
        {"project_name": ZWSP},
    ],
)
async def test_notify__invalid_input_raises(
    db_session: AsyncSession, fake_clock: FakeClock, override: dict[str, Any]
) -> None:
    """Sai luật của [6] bước 1-2 → `ValueError`, không dòng nào được chèn."""
    user, project = await _fixture_pair(db_session)
    fields: dict[str, Any] = {
        "user_id": user.id,
        "kind": "aiCompleted",
        "place": "walls",
        "project_id": project.id,
        "project_name": "Dự án",
        "floor_level_id": FLOOR,
        "object_label": "Tường",
        "message": "hệ thống AI đã xử lý xong bản vẽ",
        "dedupe_key": KEY,
        "clock": fake_clock,
    }
    fields.update(override)
    with pytest.raises(ValueError):  # noqa: PT011 — mỗi ca có thông điệp riêng, ca này chỉ cần đúng kiểu lỗi
        await notify(db_session, **fields)
    assert await rows_of(db_session) == []


async def test_notify__cleans_labels_and_returns_row(
    db_session: AsyncSession, fake_clock: FakeClock, streams_client: AsyncRedis
) -> None:
    """Tên chứa `U+202E`, `U+0007`, dạng NFD → lưu đã làm sạch, NFC; `excerpt` cũng vậy; id `ntf_`."""
    user, project = await _fixture_pair(db_session)
    row = await commit_notify(
        db_session,
        fake_clock,
        user_id=user.id,
        project_id=project.id,
        project_name="Chung  cư " + RLO + "Sông" + BEL + " Ha" + GRAVE + "n",  # `a` + dấu huyền rời
        object_label="ta" + CIRCUMFLEX + ACUTE + "ng" + ZWSP + "  2",
        excerpt="  " + LRI + "đoạn" + NEWLINE + TAB + "trích" + PDI + " ",
    )
    assert row is not None
    stored = (await rows_of(db_session, user.id))[0]
    assert (stored.project_name, stored.object_label, stored.excerpt) == (
        nfc("Chung cư Sông Hàn"),
        nfc("tấng 2"),
        "đoạn trích",
    )
    assert is_id("ntf", stored.id)
    assert stored.created_at == stored.updated_at == fake_clock.now()
    assert stored.is_read is False


async def test_notify__blank_excerpt_is_dropped(
    db_session: AsyncSession, fake_clock: FakeClock, streams_client: AsyncRedis
) -> None:
    """`excerpt` rỗng sau làm sạch → bỏ (NULL), không lỗi."""
    user, project = await _fixture_pair(db_session)
    await commit_notify(
        db_session, fake_clock, user_id=user.id, project_id=project.id, project_name="A", excerpt=ZWSP + " "
    )
    assert (await rows_of(db_session, user.id))[0].excerpt is None


async def test_notify__label_is_capped(
    db_session: AsyncSession, fake_clock: FakeClock, streams_client: AsyncRedis
) -> None:
    """Nhãn dài hơn 200 ký tự bị cắt."""
    user, project = await _fixture_pair(db_session)
    await commit_notify(db_session, fake_clock, user_id=user.id, project_id=project.id, project_name="a" * 500)
    assert len((await rows_of(db_session, user.id))[0].project_name) == 200


async def test_notify__same_dedupe_key_returns_none(
    db_session: AsyncSession, fake_clock: FakeClock, streams_client: AsyncRedis
) -> None:
    """Cùng `dedupe_key` hai lần → một dòng; lần hai trả `None`, và không XADD thêm."""
    user, project = await _fixture_pair(db_session)
    common: dict[str, Any] = {"user_id": user.id, "project_id": project.id, "project_name": "A", "dedupe_key": KEY}
    first = await commit_notify(db_session, fake_clock, **common)
    second = await commit_notify(db_session, fake_clock, **common)
    assert first is not None
    assert second is None
    assert len(await rows_of(db_session, user.id)) == 1
    assert await streams_client.xlen(user_stream(user.id)) == 1


async def test_notify__J09(db_session: AsyncSession, fake_clock: FakeClock, streams_client: AsyncRedis) -> None:
    """`notify` rồi rollback → không dòng, `XLEN events:user:{u}` = 0 (K17: XADD chỉ sau commit)."""
    user, project = await _fixture_pair(db_session)
    user_id = user.id  # rollback làm hết hạn mọi đối tượng, đọc `user.id` sau đó là IO đồng bộ
    await notify(
        db_session,
        user_id=user.id,
        kind="aiCompleted",
        place="walls",
        project_id=project.id,
        project_name="A",
        floor_level_id=FLOOR,
        object_label="Tường",
        message="hệ thống AI đã xử lý xong bản vẽ",
        dedupe_key=KEY,
        clock=fake_clock,
    )
    await db_session.rollback()
    await after_commit_idle(db_session)
    assert await rows_of(db_session) == []
    xlen = await streams_client.xlen(user_stream(user_id))
    print(f"XLEN events:user:{{u}} sau rollback (J09) = {xlen}")  # số liệu cho báo cáo [11].4
    assert xlen == 0


async def test_notify__one_xadd_across_sweep_k32(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    streams_client: AsyncRedis,
    event_bus: EventBus,
) -> None:
    """K32: `notify` + commit → đúng 1 mục; +3 phút, quét bù → vẫn 1 mục và `stream_id` = id mục đó."""
    now = datetime.now(UTC)
    fake_clock.set(now)
    user, project = await _fixture_pair(db_session)
    await commit_notify(db_session, fake_clock, user_id=user.id, project_id=project.id, project_name="A")
    stream = user_stream(user.id)
    after_notify = await streams_client.xlen(stream)
    print(f"XLEN events:user:{{u}} sau notify + commit = {after_notify}")  # số liệu cho báo cáo [11].4
    assert after_notify == 1
    assert (await rows_of(db_session, user.id))[0].stream_id is None, "callback sau commit không ghi DB (K36)"

    fake_clock.set(now + timedelta(minutes=3))
    published = await run_notification_publish(db_sessionmaker, event_bus, fake_clock, batch=BATCH)

    after_sweep = await streams_client.xlen(stream)
    print(f"XLEN events:user:{{u}} sau quét bù = {after_sweep}")  # số liệu cho báo cáo [11].4
    assert (published, after_sweep) == (1, 1)
    entry_id = (await stream_ids(streams_client, stream))[0]
    assert (await rows_of(db_session, user.id))[0].stream_id == entry_id


@pytest.fixture
def dead_redis(monkeypatch: pytest.MonkeyPatch, redis_broker_url: str) -> Iterator[tuple[RedisContainer, str]]:
    """Redis `noeviction` riêng đã trỏ `REDIS_BROKER_URL` vào; trả (container, URL Redis dùng chung để chuyển về)."""
    container = ephemeral_redis("noeviction")
    url = f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"
    monkeypatch.setenv("REDIS_BROKER_URL", url)
    reset_messaging_settings_cache()
    try:
        yield container, redis_broker_url
    finally:
        with suppress(Exception):  # test có thể đã tự dừng container
            container.stop()
        reset_messaging_settings_cache()


async def test_notify__J10(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    streams_client: AsyncRedis,
    event_bus: EventBus,
    dead_redis: tuple[RedisContainer, str],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """J10: Redis chết trước commit → dòng còn, 0 mục, `stream_id` rỗng; task giao lại → 1 mục; quét bù không thêm."""
    container, shared_url = dead_redis
    now = datetime.now(UTC)
    fake_clock.set(now)
    user, project = await _fixture_pair(db_session)
    common: dict[str, Any] = {"user_id": user.id, "project_id": project.id, "project_name": "A", "dedupe_key": KEY}
    stream = user_stream(user.id)

    container.stop()
    with caplog.at_level(logging.WARNING, logger="apps.api.notifications.service"):
        assert await commit_notify(db_session, fake_clock, **common) is not None
    row = (await rows_of(db_session, user.id))[0]
    assert row.stream_id is None
    assert any(record.getMessage() == "notification_publish_failed" for record in caplog.records)
    assert await streams_client.xlen(stream) == 0

    monkeypatch.setenv("REDIS_BROKER_URL", shared_url)
    reset_messaging_settings_cache()
    assert await commit_notify(db_session, fake_clock, **common) is None  # task giao lại cùng `dedupe_key`
    assert await streams_client.xlen(stream) == 1
    assert len(await rows_of(db_session, user.id)) == 1

    fake_clock.set(now + timedelta(minutes=3))
    assert await run_notification_publish(db_sessionmaker, event_bus, fake_clock, batch=BATCH) == 1
    assert await streams_client.xlen(stream) == 1
    entry_id = (await stream_ids(streams_client, stream))[0]
    assert (await rows_of(db_session, user.id))[0].stream_id == entry_id


async def test_notify__row_trimmed_between_insert_and_select_returns_none(
    db_session: AsyncSession, fake_clock: FakeClock, streams_client: AsyncRedis
) -> None:
    """Dòng trùng bị xoá giữa `INSERT … DO NOTHING` và `SELECT` đọc lại → `None`, không XADD thêm."""
    user, project = await _fixture_pair(db_session)
    common: dict[str, Any] = {"user_id": user.id, "project_id": project.id, "project_name": "A", "dedupe_key": KEY}
    assert await commit_notify(db_session, fake_clock, **common) is not None

    connection = await db_session.connection()
    fired: list[str] = []

    def _trim_before_select(conn: Any, _cursor: Any, statement: str, *_rest: Any) -> None:
        """Ngay trước câu `SELECT` đọc lại: xoá dòng đang xung đột (như lượt dọn đồng thời)."""
        if statement.lstrip().upper().startswith("SELECT") and not fired:
            fired.append(statement)
            conn.execute(delete(NotificationRow).where(NotificationRow.dedupe_key == KEY))

    event.listen(connection.sync_connection, "before_cursor_execute", _trim_before_select)
    try:
        second = await commit_notify(db_session, fake_clock, **common)
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", _trim_before_select)

    assert fired
    assert second is None
    assert await rows_of(db_session, user.id) == []
    assert await streams_client.xlen(user_stream(user.id)) == 1
