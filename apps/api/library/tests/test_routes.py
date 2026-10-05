"""#14 `library_list_items` và #15 `library_read_item` qua app thật (B2-06 [8]): C01 C15 C17 C08, mine, URL."""

from collections.abc import Iterator, Sequence
from datetime import timedelta
from typing import Final

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.library.settings import reset_library_settings_cache
from apps.api.library.tests._helpers import (
    FILES_PATH,
    LIST_PATH,
    headers_of,
    item_path,
    seed_and_publish,
    spy,
    token_of,
)
from packages.domain.library import CATALOGUE, build_glb
from packages.storage.local import LocalDiskStorage
from packages.storage.port import SignedUrl, SignRequest
from packages.testing.factories.auth import make_user
from packages.testing.factories.library import make_library_item
from packages.testing.fixtures.clock import FakeClock

WIRE_KEYS: Final = {
    "id",
    "name",
    "group",
    "source",
    "widthMm",
    "depthMm",
    "heightMm",
    "triangleCount",
    "fileSizeBytes",
    "modelUrl",
    "previewUrl",
}


@pytest.fixture
def _list_max_3(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """C15 đặt `LIBRARY_LIST_MAX = 3`; cache xoá cả trước lẫn sau."""
    monkeypatch.setenv("LIBRARY_LIST_MAX", "3")
    reset_library_settings_cache()
    yield
    reset_library_settings_cache()


async def test_library_list_items__C01(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Seed thật + phát hành thật: đủ 16 mục, tải được `.glb` (byte = `build_glb`) và ảnh qua app."""
    admin = await make_user(db_session)
    report = await seed_and_publish(db_session, db_sessionmaker, local_storage, fake_clock)
    assert (report.published, report.failed) == (len(CATALOGUE), 0)

    response = await api_client.get(LIST_PATH, headers=headers_of(admin))
    assert response.status_code == 200
    items = response.json()
    assert [item["id"] for item in items] == [item.id for item in CATALOGUE]
    assert all(set(item) == WIRE_KEYS and item["source"] == "catalogue" for item in items)

    model = await api_client.get(FILES_PATH + token_of(items[0]["modelUrl"]))
    assert model.status_code == 200
    assert model.content == build_glb(CATALOGUE[0]).data
    assert model.headers["content-disposition"].startswith("attachment")
    preview = await api_client.get(FILES_PATH + token_of(items[0]["previewUrl"]))
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"


async def test_library_read_item__C01(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Đọc một mục: đúng khoá hợp đồng, số đo khớp bảng danh mục, tải được `.glb`."""
    admin = await make_user(db_session)
    await seed_and_publish(db_session, db_sessionmaker, local_storage, fake_clock)

    response = await api_client.get(item_path("table-desk"), headers=headers_of(admin))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == WIRE_KEYS
    assert (body["group"], body["widthMm"], body["depthMm"], body["heightMm"]) == ("table", 1400, 700, 750)
    glb = build_glb(next(item for item in CATALOGUE if item.id == "table-desk"))
    assert (body["triangleCount"], body["fileSizeBytes"]) == (glb.triangle_count, glb.size_bytes)
    model = await api_client.get(FILES_PATH + token_of(body["modelUrl"]))
    assert model.content == glb.data


@pytest.mark.usefixtures("_list_max_3")
async def test_library_list_items__C15(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Biên danh sách cũ: 0, 1 mục; 5 mục với trần 3 → đúng 3 mục đầu theo `(sort_order, id)`, hai lượt như nhau."""
    user = await make_user(db_session)
    headers = headers_of(user)
    assert (await api_client.get(LIST_PATH, headers=headers)).json() == []

    await make_library_item(db_session, local_storage, id="item-c", sort_order=2)
    assert [i["id"] for i in (await api_client.get(LIST_PATH, headers=headers)).json()] == ["item-c"]

    for item_id, order in (("item-b", 1), ("item-a", 1), ("item-e", 9), ("item-d", 3)):
        await make_library_item(db_session, local_storage, id=item_id, sort_order=order)
    first = [i["id"] for i in (await api_client.get(LIST_PATH, headers=headers)).json()]
    again = [i["id"] for i in (await api_client.get(LIST_PATH, headers=headers)).json()]
    assert first == again == ["item-a", "item-b", "item-c"]


async def test_library_list_items__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Mục không ảnh → vắng khoá `previewUrl` (không `null`); mục có ảnh → có."""
    user = await make_user(db_session)
    await make_library_item(db_session, local_storage, id="no-preview", preview=False, sort_order=1)
    await make_library_item(db_session, local_storage, id="with-preview", sort_order=2)
    items = (await api_client.get(LIST_PATH, headers=headers_of(user))).json()
    assert "previewUrl" not in items[0]
    assert items[1]["previewUrl"].startswith("https://")


async def test_library_read_item__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """#15: mục không ảnh vắng khoá `previewUrl`; số đo và `modelUrl` vẫn đủ."""
    user = await make_user(db_session)
    await make_library_item(db_session, local_storage, id="no-preview", preview=False)
    body = (await api_client.get(item_path("no-preview"), headers=headers_of(user))).json()
    assert "previewUrl" not in body
    assert set(body) == WIRE_KEYS - {"previewUrl"}


async def test_library_read_item__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """404 `libraryItem`: không có, sai mẫu (`A`, `a_b`, 65 ký tự), chưa phát hành, đã rút, `mine` của người khác."""
    me = await make_user(db_session)
    other = await make_user(db_session)
    await make_library_item(db_session, local_storage, id="unpublished", published=False)
    await make_library_item(db_session, local_storage, id="retired-one", retired=True)
    await make_library_item(db_session, local_storage, id="theirs", owner=other)
    ids = ["missing-one", "A", "a_b", "a" * 65, "unpublished", "retired-one", "theirs"]
    for item_id in ids:
        response = await api_client.get(item_path(item_id), headers=headers_of(me))
        assert response.status_code == 404, item_id
        assert response.json()["code"] == "NOT_FOUND"
        assert response.json()["resource"] == "libraryItem"


async def test_library_mine_source_and_visibility(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """`mine` của người gọi → `source: "mine"` ở cả hai route; của người khác vắng ở #14."""
    me = await make_user(db_session)
    other = await make_user(db_session)
    await make_library_item(db_session, local_storage, id="a-mine", owner=me, sort_order=1)
    await make_library_item(db_session, local_storage, id="b-theirs", owner=other, sort_order=2)
    await make_library_item(db_session, local_storage, id="c-shared", sort_order=3)
    items = (await api_client.get(LIST_PATH, headers=headers_of(me))).json()
    assert [(i["id"], i["source"]) for i in items] == [("a-mine", "mine"), ("c-shared", "catalogue")]
    assert (await api_client.get(item_path("a-mine"), headers=headers_of(me))).json()["source"] == "mine"


async def test_library_urls_absolute_stable_within_hour(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """URL tuyệt đối; cùng giờ giống hệt; qua mốc giờ khác; #14 không gọi `stat` (W23)."""
    user = await make_user(db_session)
    for n in range(16):
        await make_library_item(db_session, local_storage, id=f"item-{n:02d}", sort_order=n)
    stats = spy(monkeypatch, local_storage, "stat")
    headers = headers_of(user)

    first = (await api_client.get(LIST_PATH, headers=headers)).json()
    fake_clock.advance(timedelta(minutes=5))
    same_hour = (await api_client.get(LIST_PATH, headers=headers)).json()
    assert len(first) == 16
    assert all(i["modelUrl"].startswith("https://") and i["previewUrl"].startswith("https://") for i in first)
    assert same_hour == first
    fake_clock.advance(timedelta(hours=1))
    assert (await api_client.get(LIST_PATH, headers=headers)).json() != first
    assert stats == []


async def test_library_list_items__signs_every_url_in_one_batch(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NO-207: #14 với 16 mục (mô hình + ảnh xem trước) ký 32 URL trong đúng **một** lượt `signed_urls`."""
    user = await make_user(db_session)
    for n in range(16):
        await make_library_item(db_session, local_storage, id=f"item-{n:02d}", sort_order=n)
    batches: list[int] = []
    real = LocalDiskStorage.signed_urls

    async def counting(self: LocalDiskStorage, requests: Sequence[SignRequest]) -> list[SignedUrl]:
        """Ghi cỡ lô rồi ký bằng hàm thật (vá lớp: app dựng kho riêng, không dùng `local_storage`)."""
        batches.append(len(requests))
        return await real(self, requests)

    monkeypatch.setattr(LocalDiskStorage, "signed_urls", counting)

    items = (await api_client.get(LIST_PATH, headers=headers_of(user))).json()

    assert len(items) == 16
    assert batches == [32]
