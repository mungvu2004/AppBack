"""Bộ test hợp đồng `ObjectStorage` — chạy cho **cả hai** bộ điều hợp (BE-00 §8).

MinIO là container thật, không mock (K23).
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta

import pytest

from packages.core.errors import AppError
from packages.storage import keys
from packages.storage.port import SIGNED_URL_TTL, ObjectInfo, ObjectStorage, SignRequest
from packages.storage.sniff import ImageKind
from packages.testing.fixtures.clock import FakeClock

PROJECT = "prj_01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_PROJECT = "prj_01ARZ3NDEKTSV4RRFFQ69G5FAW"
FLOOR = "L-ABCDEFGHIJ"
UPLOAD = "upl_01ARZ3NDEKTSV4RRFFQ69G5FBW"
USER = "usr_01ARZ3NDEKTSV4RRFFQ69G5FDY"
ULID = "01ARZ3NDEKTSV4RRFFQ69G5FEZ"

PNG = b"\x89PNG\r\n\x1a\n" + b"pixels" * 8
PDF = b"%PDF-1.7\n" + b"pages" * 8
MAX_BYTES = 1024 * 1024


def page_key(project: str = PROJECT, index: int = 0) -> str:
    """Khoá trang đã nắn do server đặt tên, dùng chung cho mọi test hợp đồng."""
    return keys.upload_page(project, FLOOR, UPLOAD, index)


def avatar_key(ext: str = "png") -> str:
    """Khoá ảnh đại diện do server đặt tên, đuôi `ext`."""
    return keys.avatar(USER, ULID, ext)


async def read_all(storage: ObjectStorage, key: str) -> bytes:
    """Đọc trọn object qua `open_read` với khúc 8 byte để ép nhiều khúc."""
    return b"".join([chunk async for chunk in storage.open_read(key, chunk_size=8)])


async def listed(storage: ObjectStorage, prefix: str, older_than: datetime | None = None) -> list[ObjectInfo]:
    """Gom `list_prefix` thành danh sách để assert."""
    return [info async for info in storage.list_prefix(prefix, older_than=older_than)]


async def chunks(*parts: bytes) -> AsyncIterator[bytes]:
    """Phát các phần `bytes` như một luồng đầu vào không đồng bộ."""
    for part in parts:
        yield part


async def test_put_stat_open_read_delete_roundtrip(object_storage: ObjectStorage) -> None:
    """Ghi, `stat`, đọc rồi xoá một object: metadata và nội dung khớp, xoá xong thì `stat` ra `None`."""
    key = page_key()
    written = await object_storage.put(key, PNG, content_type="image/png", max_bytes=MAX_BYTES)

    assert written.size == len(PNG)
    assert written.kind == "png"
    stored = await object_storage.stat(key)
    assert stored is not None
    assert stored.size == len(PNG)
    assert stored.sha256 == written.sha256
    assert stored.content_type == "image/png"
    assert stored.kind == "png"
    assert stored.last_modified.utcoffset() is not None
    assert await read_all(object_storage, key) == PNG

    await object_storage.delete(key)
    assert await object_storage.stat(key) is None
    await object_storage.delete(key)  # xoá lần hai im lặng


async def test_put_overwrites_same_key(object_storage: ObjectStorage) -> None:
    """Ghi đè cùng khoá thay hẳn nội dung, sha256 và loại tệp."""
    key = page_key()
    await object_storage.put(key, PNG, content_type="image/png", max_bytes=MAX_BYTES)
    rewritten = await object_storage.put(key, PDF, content_type="application/pdf", max_bytes=MAX_BYTES)

    stored = await object_storage.stat(key)
    assert stored is not None
    assert stored.sha256 == rewritten.sha256
    assert stored.kind == "pdf"
    assert await read_all(object_storage, key) == PDF


async def test_put_reads_async_iterable_in_many_chunks(object_storage: ObjectStorage) -> None:
    """Nguồn `AsyncIterable` nhiều khúc vẫn ghép đúng nguyên nội dung và loại tệp."""
    key = page_key()
    written = await object_storage.put(
        key, chunks(PNG[:4], PNG[4:10], PNG[10:]), content_type="image/png", max_bytes=MAX_BYTES
    )

    assert written.size == len(PNG)
    assert written.kind == "png"
    assert await read_all(object_storage, key) == PNG


async def test_put_over_max_bytes_leaves_no_object(object_storage: ObjectStorage) -> None:
    """C12: vượt trần giữa luồng → 413, không còn object dở."""
    key = page_key()
    with pytest.raises(AppError, match="PAYLOAD_TOO_LARGE") as raised:
        await object_storage.put(key, chunks(b"a" * 8, b"b" * 8), content_type="image/png", max_bytes=10)

    assert raised.value.code.status == 413
    assert await object_storage.stat(key) is None


async def test_put_ignores_declared_content_type(object_storage: ObjectStorage) -> None:
    """U08, U09: loại luôn tính từ magic bytes, kể cả khi `content_type` rỗng hay lệch đuôi."""
    key = page_key()
    written = await object_storage.put(key, PDF, content_type="", max_bytes=MAX_BYTES)

    assert key.endswith(".png")
    assert written.kind == "pdf"
    assert written.content_type == ""


async def test_concurrent_writes_never_produce_a_torn_object(object_storage: ObjectStorage) -> None:
    """C14: hai lượt ghi song song cùng khoá → object là **một** trong hai bản, không trộn."""
    other = PDF + b"khac" * 64

    await asyncio.gather(
        object_storage.put(page_key(), PNG, content_type="image/png", max_bytes=MAX_BYTES),
        object_storage.put(page_key(), other, content_type="application/pdf", max_bytes=MAX_BYTES),
    )

    assert await read_all(object_storage, page_key()) in (PNG, other)


async def test_list_prefix_does_not_leak_sibling_prefix(object_storage: ObjectStorage) -> None:
    """`list_prefix` chỉ trả khoá dưới đúng tiền tố dự án, không lộ dự án anh em."""
    await object_storage.put(page_key(), PNG, content_type="image/png", max_bytes=MAX_BYTES)
    await object_storage.put(page_key(index=1), PNG, content_type="image/png", max_bytes=MAX_BYTES)
    await object_storage.put(page_key(project=OTHER_PROJECT), PNG, content_type="image/png", max_bytes=MAX_BYTES)

    found = await listed(object_storage, f"projects/{PROJECT}/")

    assert [info.key for info in found] == sorted([page_key(), page_key(index=1)])


async def test_list_prefix_older_than(object_storage: ObjectStorage) -> None:
    """Lọc theo mốc của **chính kho** (`stat` vừa đọc), không trộn giờ thật với `fake_clock` (NO-016)."""
    await object_storage.put(page_key(), PNG, content_type="image/png", max_bytes=MAX_BYTES)
    stored = await object_storage.stat(page_key())
    assert stored is not None
    modified = stored.last_modified

    newer = await listed(object_storage, f"projects/{PROJECT}/", older_than=modified + timedelta(seconds=1))
    assert [info.key for info in newer] == [page_key()]
    assert await listed(object_storage, f"projects/{PROJECT}/", older_than=modified) == []


async def test_delete_prefix(object_storage: ObjectStorage) -> None:
    """`delete_prefix` xoá mọi object dưới tiền tố và giữ nguyên object của dự án khác."""
    await object_storage.put(page_key(), PNG, content_type="image/png", max_bytes=MAX_BYTES)
    await object_storage.put(page_key(index=1), PNG, content_type="image/png", max_bytes=MAX_BYTES)
    kept = page_key(project=OTHER_PROJECT)
    await object_storage.put(kept, PNG, content_type="image/png", max_bytes=MAX_BYTES)

    await object_storage.delete_prefix(keys.project_prefix(PROJECT))

    assert await listed(object_storage, f"projects/{PROJECT}/") == []
    assert await object_storage.stat(kept) is not None


async def test_open_read_missing_key(object_storage: ObjectStorage) -> None:
    """Đọc khoá không có → 404 `NOT_FOUND`."""
    with pytest.raises(AppError, match="NOT_FOUND") as raised:
        await read_all(object_storage, page_key())

    assert raised.value.code.status == 404


async def test_signed_url_is_stable_within_the_hour(object_storage: ObjectStorage, fake_clock: FakeClock) -> None:
    """W23: hai lần đọc trong cùng một giờ nhận **cùng** URL (cache FE 10 phút)."""
    key = page_key()
    await object_storage.put(key, PNG, content_type="image/png", max_bytes=MAX_BYTES)

    fake_clock.set(datetime(2026, 1, 1, 9, 5, tzinfo=UTC))
    first = await object_storage.signed_url(key, disposition="attachment")
    fake_clock.set(datetime(2026, 1, 1, 9, 55, tzinfo=UTC))
    second = await object_storage.signed_url(key, disposition="attachment")
    fake_clock.set(datetime(2026, 1, 1, 10, 5, tzinfo=UTC))
    next_hour = await object_storage.signed_url(key, disposition="attachment")

    assert first == second
    assert next_hour.url != first.url
    assert next_hour.expires_at == first.expires_at + timedelta(hours=1)


@pytest.mark.parametrize("minute", [0, 5, 59])
async def test_signed_url_lives_between_60_and_120_minutes(
    object_storage: ObjectStorage, fake_clock: FakeClock, minute: int
) -> None:
    """URL ký sống 60-120 phút bất kể phút nào trong giờ (W23)."""
    key = page_key()
    await object_storage.put(key, PNG, content_type="image/png", max_bytes=MAX_BYTES)
    now = datetime(2026, 1, 1, 9, minute, tzinfo=UTC)
    fake_clock.set(now)

    signed = await object_storage.signed_url(key, disposition="attachment", filename="bản vẽ.png")

    assert timedelta(minutes=60) <= signed.expires_at - now <= SIGNED_URL_TTL


async def test_signed_url_inline_rejects_non_image(object_storage: ObjectStorage) -> None:
    """`inline` cho object không phải ảnh bị từ chối (K15)."""
    key = page_key()
    await object_storage.put(key, PDF, content_type="application/pdf", max_bytes=MAX_BYTES)

    with pytest.raises(ValueError, match="inline chỉ dành cho PNG/JPEG"):
        await object_storage.signed_url(key, disposition="inline")


async def test_signed_url_inline_reads_the_kind_from_metadata(object_storage: ObjectStorage) -> None:
    """Ảnh server sinh (trang bản vẽ) ký `inline` được vì metadata nói nó là PNG."""
    key = page_key()
    await object_storage.put(key, PNG, content_type="image/png", max_bytes=MAX_BYTES)

    signed = await object_storage.signed_url(key, disposition="inline")

    assert signed.url.startswith("http")


async def test_signed_url_inline_on_missing_object(object_storage: ObjectStorage) -> None:
    """`inline` không kèm `kind` cho object không tồn tại → `NOT_FOUND`."""
    with pytest.raises(AppError, match="NOT_FOUND"):
        await object_storage.signed_url(page_key(), disposition="inline")


def original_key() -> str:
    """Khoá `original.*` của lượt tải lên — không do server chọn đuôi nên không được dùng `kind` truyền sẵn."""
    return keys.upload_original(PROJECT, FLOOR, UPLOAD, "png")


@pytest.mark.parametrize("key_factory", [avatar_key, page_key])
async def test_signed_url_with_kind_does_not_stat(
    object_storage: ObjectStorage, monkeypatch: pytest.MonkeyPatch, key_factory: Callable[[], str]
) -> None:
    """`kind` truyền sẵn cho khoá server đặt tên (ảnh đại diện, ảnh trang) → không lượt `stat` nào (W23, NO-011)."""
    key = key_factory()
    await object_storage.put(key, PNG, content_type="image/png", max_bytes=MAX_BYTES)
    calls = 0
    original = object_storage.stat

    async def counting(key: str) -> ObjectInfo | None:
        """Đếm lượt `stat` rồi chuyển cho bản thật."""
        nonlocal calls
        calls += 1
        return await original(key)

    monkeypatch.setattr(object_storage, "stat", counting)
    signed = await object_storage.signed_url(key, disposition="inline", kind="png")

    assert calls == 0
    assert signed.url.startswith("http")


_KIND_CASES: list[tuple[Callable[[], str], ImageKind]] = [
    (lambda: avatar_key("jpg"), "png"),
    (original_key, "png"),
]


@pytest.mark.parametrize(("key_factory", "kind"), _KIND_CASES)
async def test_signed_url_rejects_kind_outside_server_named_keys(
    object_storage: ObjectStorage, key_factory: Callable[[], str], kind: ImageKind
) -> None:
    """Đuôi lệch `kind`, hay tệp gốc người dùng tải lên (`original.*`, K15) → phải để kho tự đọc metadata."""
    key = key_factory()
    await object_storage.put(key, PNG, content_type="image/png", max_bytes=MAX_BYTES)

    with pytest.raises(ValueError, match="chỉ hợp lệ cho khoá do server đặt tên"):
        await object_storage.signed_url(key, disposition="inline", kind=kind)


@pytest.mark.parametrize("bad", ["../etc/passwd", "a//b", "x.meta.json"])
async def test_every_entry_point_checks_the_key(object_storage: ObjectStorage, bad: str) -> None:
    """Mọi cửa vào của cổng (stat, put, delete, ký, đọc, xoá/duyệt tiền tố) từ chối khoá xấu bằng `ValueError`."""
    with pytest.raises(ValueError, match=r"khoá|đoạn"):
        await object_storage.stat(bad)
    with pytest.raises(ValueError, match=r"khoá|đoạn"):
        await object_storage.put(bad, PNG, content_type="image/png", max_bytes=MAX_BYTES)
    with pytest.raises(ValueError, match=r"khoá|đoạn"):
        await object_storage.delete(bad)
    with pytest.raises(ValueError, match=r"khoá|đoạn"):
        await object_storage.signed_url(bad, disposition="attachment")
    with pytest.raises(ValueError, match=r"khoá|đoạn"):
        await read_all(object_storage, bad)
    with pytest.raises(ValueError, match=r"tiền tố|khoá|đoạn"):
        await object_storage.delete_prefix(bad)
    with pytest.raises(ValueError, match=r"tiền tố|khoá|đoạn"):
        await listed(object_storage, bad)


async def test_list_prefix_orders_by_full_key(object_storage: ObjectStorage) -> None:
    """Thứ tự là thứ tự **khoá đầy đủ** như S3 (`a.b` < `a/b` < `a0`), không phải duyệt cây theo tên."""
    base = f"projects/{PROJECT}"
    names = [f"{base}/a0", f"{base}/a/b", f"{base}/a.b"]
    for key in names:
        await object_storage.put(key, PNG, content_type="image/png", max_bytes=MAX_BYTES)

    assert [info.key for info in await listed(object_storage, f"{base}/")] == sorted(names)


async def test_signed_urls_match_signed_url_one_by_one(object_storage: ObjectStorage, fake_clock: FakeClock) -> None:
    """NO-207: ký lô ra đúng URL và hạn của từng `signed_url`, cùng thứ tự, lô rỗng ra rỗng."""
    fake_clock.set(datetime(2026, 1, 1, 9, 5, tzinfo=UTC))
    first, second = page_key(), page_key()
    requests = [
        SignRequest(first, "attachment", filename="a.png"),
        SignRequest(second, "inline", kind="png"),
        SignRequest(first, "attachment"),
    ]

    batch = await object_storage.signed_urls(requests)
    single = [
        await object_storage.signed_url(r.key, disposition=r.disposition, filename=r.filename, kind=r.kind)
        for r in requests
    ]

    assert batch == single
    assert await object_storage.signed_urls([]) == []


async def test_signed_urls_reject_inline_non_image(object_storage: ObjectStorage) -> None:
    """NO-207: một phần tử sai luật `inline` làm hỏng cả lô, như `signed_url` đơn."""
    key = page_key()
    await object_storage.put(key, PDF, content_type="application/pdf", max_bytes=MAX_BYTES)

    with pytest.raises(ValueError, match="inline"):
        await object_storage.signed_urls([SignRequest(key, "inline")])
