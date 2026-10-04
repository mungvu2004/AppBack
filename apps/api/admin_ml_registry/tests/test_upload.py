"""N26 `ml_upload_version` — luồng multipart, byte đầu, checksum, giao dịch ngắn (B6-01 [6], [8]).

Ba nhóm khẳng định:

- **case A** của `ml_upload_version` (C01, C02, C03, C16, C17, C18); C07 đã có ở `test_contract.py`;
- **luật riêng của N26**: thứ tự và số phần, 9 byte đầu theo định dạng khai (M02), checksum đo
  lúc nhận (M03), trần `MODEL_UPLOAD_MAX_BYTES`, và "lỗi sau `put` thì xoá object";
- **K36/K17**: lượt nhận tệp không giữ kết nối DB, và task đánh giá chỉ bắn sau commit.

Kho object là kho **thật** (`local_storage`, `s3_storage`): K23 cấm mock kho, nên chỗ cần đếm
lời gọi `put` hay biết khoá vừa ghi dùng `_CountingStorage` — lớp **bọc** kho thật, không thay
nó. Khẳng định "không object" luôn theo đúng khoá của lượt ấy (`stat(key) is None`) chứ không
quét `list_prefix`: bucket MinIO dùng chung thì lượt quét thấy cả object của test khác.

Lỗi DB được tiêm bằng `monkeypatch` trên chính lời gọi của `upload.py`; Postgres vẫn là Postgres
thật, chỉ một lời gọi được thay để đi vào nhánh "hỏng sau khi đã ghi object".
"""

import asyncio
import json
import logging
import struct
import tracemalloc
import unicodedata
from collections import deque
from collections.abc import AsyncIterator, MutableMapping
from hashlib import sha256
from typing import Any, Final

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.admin_ml_registry import upload
from apps.api.admin_ml_registry.settings import reset_ml_registry_settings_cache
from apps.api.admin_ml_registry.tests._helpers import FAMILIES_PATH, ML_QUEUE, OPENING, VERSIONS_PATH
from apps.api.core.app import create_app
from apps.api.core.auth import FakeTokenVerifier, Principal
from packages.core.settings import get_core_settings
from packages.db.models.admin_ml_registry import ModelVersionRow
from packages.db.settings import reset_database_settings_cache
from packages.messaging.redis import broker_redis_sync
from packages.storage.keys import model_artifact
from packages.storage.port import ObjectInfo, ObjectStorage
from packages.testing.fixtures.access import assert_one_activity
from packages.testing.fixtures.api import auth_headers, make_api_client
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import queued_payloads

_log: Final = logging.getLogger(__name__)

BOUNDARY: Final = "b601Boundary"

ONNX_BYTES: Final = b"\x08\x01\x12\x06kiem\x00"
"""ONNX tí hon viết tay: byte 0 `0x08` (`ir_version`, trường 1 varint của protobuf)."""

_SAFETENSORS_HEADER: Final = b'{"__metadata__":{}}'
SAFETENSORS_BYTES: Final = struct.pack("<Q", len(_SAFETENSORS_HEADER)) + _SAFETENSORS_HEADER
SAFETENSORS_ZERO: Final = struct.pack("<Q", 0) + b"{}"
ZIP_BYTES: Final = b"PK\x03\x04" + b"\x00" * 16
PICKLE_BYTES: Final = b"\x80\x02" + b"\x00" * 16

MEGABYTE: Final = 1024 * 1024
OVER_LIMIT_BYTES: Final = b"\x08" + b"\x00" * (2 * MEGABYTE)
BIG_UPLOAD_BYTES: Final = 64 * MEGABYTE
MEMORY_CEILING_BYTES: Final = 32 * MEGABYTE
GET_DEADLINE_S: Final = 1.0


def _part_header(name: str, filename: str | None) -> bytes:
    """Header của một phần; `filename` có mặt để chứng minh N26 **không** tin tên tệp (K12)."""
    disposition = f'form-data; name="{name}"' + (f'; filename="{filename}"' if filename else "")
    return f"--{BOUNDARY}\r\nContent-Disposition: {disposition}\r\n\r\n".encode()


def _part(name: str, data: bytes, *, filename: str | None = None) -> bytes:
    """Một phần multipart hoàn chỉnh."""
    return _part_header(name, filename) + data + b"\r\n"


def _closing() -> bytes:
    """Dòng boundary kết thúc thân multipart."""
    return f"--{BOUNDARY}--\r\n".encode()


def _body(*parts: bytes) -> bytes:
    """Thân multipart hoàn chỉnh của các phần đã dựng."""
    return b"".join(parts) + _closing()


def _metadata(weights: bytes = ONNX_BYTES, **overrides: Any) -> bytes:
    """Phần `metadata` JSON của `weights`; `overrides` ghi đè để dựng case sai một trường."""
    payload: dict[str, Any] = {
        "checksumSha256": sha256(weights).hexdigest(),
        "family": OPENING,
        "label": "bản tải lên",
        "weightsFormat": "onnx",
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False).encode()


def _upload_body(weights: bytes = ONNX_BYTES, **overrides: Any) -> bytes:
    """Thân hai phần đúng thứ tự `metadata` rồi `weights`."""
    return _body(_part("metadata", _metadata(weights, **overrides)), _part("weights", weights, filename="w.bin"))


def _headers(principal: Principal) -> dict[str, str]:
    """Header của một lượt N26: token `admin` cộng `Content-Type` multipart có boundary."""
    return {**auth_headers(principal), "content-type": f"multipart/form-data; boundary={BOUNDARY}"}


class _CountingStorage:
    """Kho **thật** có đếm lời gọi `put` và nhớ khoá đã ghi — K23 cấm mock kho, nên chỉ bọc.

    Mọi phương thức khác đi thẳng xuống kho bên dưới qua `__getattr__`: thêm một phương thức
    vào `ObjectStorage` không phải sửa thêm một bản chép ở đây.
    """

    def __init__(self, inner: ObjectStorage) -> None:
        """Bọc `inner`; `puts` là số lần `put` đã đi qua, `keys` là khoá của từng lần."""
        self.inner = inner
        self.puts = 0
        self.keys: list[str] = []

    async def put(self, key: str, data: Any, *, content_type: str, max_bytes: int) -> ObjectInfo:
        """Ghi nhận khoá rồi giao xuống kho thật."""
        self.puts += 1
        self.keys.append(key)
        return await self.inner.put(key, data, content_type=content_type, max_bytes=max_bytes)

    def __getattr__(self, name: str) -> Any:
        """`stat`, `delete`, `list_prefix`, … của kho bên dưới."""
        return getattr(self.inner, name)


def _counting(app: FastAPI, inner: ObjectStorage | None = None) -> _CountingStorage:
    """Đổi kho của app đã chạy `lifespan` sang lớp bọc đếm; `inner` để chạy trên `s3` nữa."""
    counting = _CountingStorage(inner if inner is not None else app.state.storage)
    app.state.storage = counting
    return counting


async def _assert_no_object(counting: _CountingStorage) -> None:
    """Không lượt `put` nào để lại object: khoá cuối đã ghi (nếu có) phải `stat` ra `None`."""
    for key in counting.keys:
        assert await counting.inner.stat(key) is None, f"object mồ côi: {key}"


async def _count_versions(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """Số dòng `model_versions` do test tạo — hai bản gốc của revision dữ liệu có `pinned_name`."""
    async with sessionmaker() as session:
        total = await session.scalar(
            select(func.count()).select_from(ModelVersionRow).where(ModelVersionRow.pinned_name.is_(None))
        )
    return total or 0


async def _broken_commit(*args: Any, **kwargs: Any) -> None:
    """`commit` hỏng vì mất kết nối — lỗi hạ tầng, `translate_db_error` đổi thành 503 (C13)."""
    raise OperationalError("COMMIT", None, ConnectionError("mất kết nối tới Postgres"))


async def _broken_activity(*args: Any, **kwargs: Any) -> None:
    """`record_activity` hỏng ở bước 6, sau khi object trọng số đã ghi xong."""
    raise OperationalError("INSERT activity_log", None, ConnectionError("mất kết nối tới Postgres"))


async def test_ml_upload_version__C01(
    api_client: AsyncClient, api_app: FastAPI, fake_principal: Principal, object_storage: ObjectStorage
) -> None:
    """ONNX tí hon → 201 bản `pending`, object trong kho có `sha256` đúng như khai (M03)."""
    _counting(api_app, object_storage)

    response = await api_client.post(VERSIONS_PATH, content=_upload_body(), headers=_headers(fake_principal))

    assert response.status_code == 201, response.text
    wire = response.json()
    assert wire["evaluationStatus"] == "pending"
    assert wire["creatorId"] == fake_principal.user_id
    assert wire["checksumSha256"] == sha256(ONNX_BYTES).hexdigest()
    info = await object_storage.stat(model_artifact(wire["id"], "weights.onnx"))
    assert info is not None
    assert (info.sha256, info.size) == (wire["checksumSha256"], len(ONNX_BYTES))


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"label": "x" * 81}, "label"),
        ({"checksumSha256": "A" * 64}, "checksumSha256"),
        ({"weightsFormat": "pt"}, "weightsFormat"),
    ],
)
async def test_ml_upload_version__C02(
    api_client: AsyncClient, fake_principal: Principal, overrides: dict[str, Any], field: str
) -> None:
    """Nhãn 81 ký tự, checksum chữ hoa, định dạng `pt` → 422 `VALIDATION` đúng `field`."""
    response = await api_client.post(VERSIONS_PATH, content=_upload_body(**overrides), headers=_headers(fake_principal))

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["field"] == field


async def test_ml_upload_version__C03(api_client: AsyncClient, fake_principal: Principal) -> None:
    """`metadata` mang khoá lạ `creatorId` → 422 `VALIDATION` (lớp strict của `schemas`)."""
    body = _upload_body(creatorId="usr_x")

    response = await api_client.post(VERSIONS_PATH, content=body, headers=_headers(fake_principal))

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["field"] == "creatorId"


async def test_ml_upload_version__C16(api_client: AsyncClient, fake_principal: Principal) -> None:
    """`label` gửi dạng NFD (có khoảng trắng hai đầu) → lưu và trả về dạng NFC."""
    label = unicodedata.normalize("NFD", "bản đã tách dấu")

    body = _upload_body(label=f"  {label}  ")

    response = await api_client.post(VERSIONS_PATH, content=body, headers=_headers(fake_principal))

    assert response.status_code == 201, response.text
    assert response.json()["label"] == unicodedata.normalize("NFC", "bản đã tách dấu")


async def test_ml_upload_version__C17(api_client: AsyncClient, fake_principal: Principal) -> None:
    """Bản vừa tải lên: `metrics`, `trainingJobId`, `datasetVersionId` **vắng**, không cột nội bộ (K01, K02)."""
    response = await api_client.post(VERSIONS_PATH, content=_upload_body(), headers=_headers(fake_principal))

    assert response.status_code == 201, response.text
    assert set(response.json()) == {
        "checksumSha256",
        "createdAt",
        "creatorId",
        "evaluationStatus",
        "family",
        "id",
        "label",
        "weightsFormat",
    }


async def test_ml_upload_version__C18(
    api_client: AsyncClient, fake_principal: Principal, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đúng một dòng `activity_log` `model.upload` mang id bản và nhãn của nó."""
    response = await api_client.post(VERSIONS_PATH, content=_upload_body(), headers=_headers(fake_principal))

    assert response.status_code == 201, response.text
    row = await assert_one_activity(
        db_sessionmaker,
        actor_id=fake_principal.user_id,
        kind=ActivityKind.MODEL_UPLOAD,
        object_code=response.json()["id"],
    )
    assert row.object_label == "bản tải lên"


async def test_upload_version_rejects_a_checksum_mismatch(
    api_client: AsyncClient, api_app: FastAPI, fake_principal: Principal, object_storage: ObjectStorage
) -> None:
    """Checksum khai lệch băm đo lúc nhận → 422 `MODEL_CHECKSUM_MISMATCH`, `stat` trả `None` (M03)."""
    counting = _counting(api_app, object_storage)

    response = await api_client.post(
        VERSIONS_PATH,
        content=_upload_body(checksumSha256=sha256(b"khac").hexdigest()),
        headers=_headers(fake_principal),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "MODEL_CHECKSUM_MISMATCH"
    assert counting.puts == 1
    await _assert_no_object(counting)


@pytest.mark.parametrize(
    ("weights_format", "weights"),
    [
        ("onnx", ZIP_BYTES),
        ("onnx", PICKLE_BYTES),
        ("onnx", SAFETENSORS_BYTES),
        ("onnx", b""),
        ("safetensors", SAFETENSORS_ZERO),
        ("safetensors", ONNX_BYTES),
        ("safetensors", b""),
    ],
)
async def test_upload_version_refuses_bad_first_bytes_without_writing(
    api_client: AsyncClient, api_app: FastAPI, fake_principal: Principal, weights_format: str, weights: bytes
) -> None:
    """Byte đầu lệch định dạng khai → 422 `MODEL_FORMAT_UNSUPPORTED` và **không** gọi `put` (M02)."""
    counting = _counting(api_app)
    body = _body(
        _part("metadata", _metadata(weights, weightsFormat=weights_format)),
        _part("weights", weights, filename="trong-so.onnx"),
    )

    response = await api_client.post(VERSIONS_PATH, content=body, headers=_headers(fake_principal))

    assert response.status_code == 422
    assert response.json()["code"] == "MODEL_FORMAT_UNSUPPORTED"
    assert counting.puts == 0


@pytest.mark.parametrize(
    ("body", "field"),
    [
        (_body(_part("weights", ONNX_BYTES), _part("metadata", _metadata())), "weights"),
        (_body(_part("metadata", _metadata())), "weights"),
        (_body(), "metadata"),
        (_body(_part("khong hop le", _metadata())), "metadata"),
        (_body(_part("metadata", _metadata()), _part("weights", ONNX_BYTES), _part("extra", b"x")), "extra"),
        (_body(_part("metadata", b"{khong phai json}"), _part("weights", ONNX_BYTES)), None),
        (_body(_part("metadata", b"0" * (17 * 1024)), _part("weights", ONNX_BYTES)), "metadata"),
    ],
)
async def test_upload_version_enforces_the_part_rules(
    api_client: AsyncClient, api_app: FastAPI, fake_principal: Principal, body: bytes, field: str | None
) -> None:
    """Thứ tự phần, phần thiếu, thân rỗng, tên phần lạ, phần thứ ba, JSON hỏng, `metadata` > 16 KiB → 422."""
    counting = _counting(api_app)

    response = await api_client.post(VERSIONS_PATH, content=body, headers=_headers(fake_principal))

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert response.json().get("field") == field
    await _assert_no_object(counting)


async def test_upload_version_refuses_a_body_that_is_not_multipart(
    api_client: AsyncClient, fake_principal: Principal
) -> None:
    """`Content-Type` không phải `multipart/form-data` → 422 `VALIDATION`, không đọc thân."""
    response = await api_client.post(
        VERSIONS_PATH, content=_metadata(), headers={**auth_headers(fake_principal), "content-type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_upload_version_refuses_a_file_over_the_configured_ceiling(
    api_client: AsyncClient, api_app: FastAPI, fake_principal: Principal, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trần 1 MiB, tệp 2 MiB → 413 `PAYLOAD_TOO_LARGE` và kho không giữ object dở (C12)."""
    counting = _counting(api_app)
    body = _upload_body(OVER_LIMIT_BYTES)
    monkeypatch.setenv("MODEL_UPLOAD_MAX_BYTES", str(MEGABYTE))
    reset_ml_registry_settings_cache()
    try:
        response = await api_client.post(VERSIONS_PATH, content=body, headers=_headers(fake_principal))
    finally:
        monkeypatch.undo()
        reset_ml_registry_settings_cache()

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"
    await _assert_no_object(counting)


async def test_upload_version_leaves_nothing_when_the_client_disconnects(
    api_client: AsyncClient,
    api_app: FastAPI,
    fake_principal: Principal,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """Client ngắt giữa luồng `weights` → không object, không dòng `model_versions`.

    `httpx` không gửi được `http.disconnect` giữa thân, nên test gọi thẳng lớp ASGI của app —
    đúng thông điệp mà Starlette đổi thành `ClientDisconnect` trong `request.stream()`.
    """
    counting = _counting(api_app)
    prefix = _part("metadata", _metadata()) + _part_header("weights", None) + b"\x08" + b"\x00" * 1024
    messages: deque[dict[str, Any]] = deque(
        [{"type": "http.request", "body": prefix, "more_body": True}, {"type": "http.disconnect"}]
    )
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        """Phát lần lượt các thông điệp ASGI đã dựng; hết thì báo `http.disconnect`."""
        return messages.popleft() if messages else {"type": "http.disconnect"}

    async def send(message: MutableMapping[str, Any]) -> None:
        """Ghi lại thông điệp app gửi ra để test kiểm mã trạng thái phản hồi."""
        sent.append(dict(message))

    await api_app(_scope(_headers(fake_principal)), receive, send)

    assert sent[0]["status"] >= 500
    assert await _count_versions(db_sessionmaker) == 0
    await _assert_no_object(counting)


async def test_upload_version_returns_503_and_deletes_the_object_when_the_commit_fails(
    api_client: AsyncClient,
    api_app: FastAPI,
    fake_principal: Principal,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Commit hỏng (mất kết nối) → 503, object đã ghi bị xoá, không dòng nào còn lại."""
    counting = _counting(api_app)
    monkeypatch.setattr(AsyncSession, "commit", _broken_commit)

    response = await api_client.post(VERSIONS_PATH, content=_upload_body(), headers=_headers(fake_principal))
    monkeypatch.undo()

    assert response.status_code == 503
    assert response.json()["code"] == "DEPENDENCY_UNAVAILABLE"
    assert await _count_versions(db_sessionmaker) == 0
    await _assert_no_object(counting)


async def test_upload_version_sends_no_task_when_step_six_fails(
    api_client: AsyncClient,
    api_app: FastAPI,
    fake_principal: Principal,
    messaging_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lỗi DB ở bước 6 → hàng `ml.infer` rỗng (K17) và object đã ghi bị xoá."""
    counting = _counting(api_app)
    monkeypatch.setattr(upload, "record_activity", _broken_activity)
    broker = broker_redis_sync()
    broker.delete(ML_QUEUE)
    try:
        response = await api_client.post(VERSIONS_PATH, content=_upload_body(), headers=_headers(fake_principal))
        queued = queued_payloads(broker, ML_QUEUE)
    finally:
        broker.delete(ML_QUEUE)
        broker.close()
    monkeypatch.undo()

    assert response.status_code == 503
    assert queued == []
    await _assert_no_object(counting)


async def test_upload_version_queues_exactly_one_evaluation(
    api_client: AsyncClient, fake_principal: Principal, messaging_env: None
) -> None:
    """Lượt thành công → đúng **một** thông điệp đánh giá trên hàng `ml.infer` (Redis thật)."""
    broker = broker_redis_sync()
    broker.delete(ML_QUEUE)
    try:
        response = await api_client.post(VERSIONS_PATH, content=_upload_body(), headers=_headers(fake_principal))
        queued = queued_payloads(broker, ML_QUEUE)
    finally:
        broker.delete(ML_QUEUE)
        broker.close()

    assert response.status_code == 201, response.text
    assert len(queued) == 1
    assert queued[0]["version_id"] == response.json()["id"]


async def test_upload_version_streams_a_file_larger_than_the_sniffed_head(
    api_client: AsyncClient, api_app: FastAPI, fake_principal: Principal
) -> None:
    """Tệp dài hơn 9 byte đầu: khúc còn lại đi tiếp vào `put`, và header lạ của phần bị bỏ qua.

    Phần `weights` mang thêm `Content-Type`: N26 không tin header ấy (K12), nên nó chỉ là một
    header phải đọc rồi bỏ — đúng đường mà một tệp thật đi qua.
    """
    weights = b"\x08" + bytes(range(256)) * 16
    counting = _counting(api_app)
    header = f"--{BOUNDARY}\r\nContent-Type: application/octet-stream\r\n".encode()
    header += b'Content-Disposition: form-data; name="weights"\r\n\r\n'
    body = _part("metadata", _metadata(weights)) + header + weights + b"\r\n" + _closing()

    response = await api_client.post(VERSIONS_PATH, content=body, headers=_headers(fake_principal))

    assert response.status_code == 201, response.text
    info = await counting.inner.stat(counting.keys[0])
    assert info is not None
    assert (info.size, info.sha256) == (len(weights), sha256(weights).hexdigest())


@pytest.mark.perf
async def test_upload_version_keeps_the_pool_free_while_streaming(
    api_env: None, fake_clock: FakeClock, fake_principal: Principal, monkeypatch: pytest.MonkeyPatch
) -> None:
    """K36 — pool một kết nối: 64 MiB đang `put` không chặn một GET có DB, đỉnh RAM < 32 MiB.

    Pool cỡ 1 là phép thử thật: giữ kết nối trong lúc nhận tệp thì lượt GET song song hết chỗ
    và chờ tới `pool_timeout`, chứ không xong trong dưới một giây.
    """
    monkeypatch.setenv("DB_POOL_SIZE", "1")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "0")
    reset_database_settings_cache()
    app = create_app(get_core_settings(), token_verifier=FakeTokenVerifier(), clock=fake_clock)
    started = asyncio.Event()
    tracemalloc.start()
    try:
        async with make_api_client(app) as client:
            headers = _headers(fake_principal)
            task = asyncio.create_task(client.post(VERSIONS_PATH, content=_slow_body(started), headers=headers))
            await started.wait()
            checked_out = app.state.sessionmaker.kw["bind"].pool.checkedout()
            elapsed = await _time_get(client, fake_principal)
            response = await task
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
        monkeypatch.undo()
        reset_database_settings_cache()

    _log.info("k36_measured", extra={"getSeconds": elapsed, "peakBytes": peak, "checkedOut": checked_out})
    assert response.status_code == 201, response.text
    assert checked_out == 0
    assert elapsed < GET_DEADLINE_S
    assert peak < MEMORY_CEILING_BYTES


def _scope(headers: dict[str, str]) -> dict[str, Any]:
    """Scope ASGI của một POST N26 — dùng cho test gọi thẳng app (ngắt kết nối giữa luồng)."""
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": VERSIONS_PATH,
        "raw_path": VERSIONS_PATH.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
        "client": ("127.0.0.1", 45678),
        "server": ("testserver", 80),
    }


async def _time_get(client: AsyncClient, principal: Principal) -> float:
    """Thời gian một GET có DB chạy xong trong lúc N26 đang nhận tệp."""
    loop = asyncio.get_running_loop()
    at = loop.time()
    response = await client.get(FAMILIES_PATH, headers=auth_headers(principal))
    assert response.status_code == 200, response.text
    return loop.time() - at


def _big_checksum() -> str:
    """SHA-256 của tệp 64 MiB của test K36, băm theo khúc — dựng cả tệp trong RAM là phá phép đo."""
    digest = sha256()
    digest.update(b"\x08")
    remaining = BIG_UPLOAD_BYTES - 1
    chunk = b"\x00" * MEGABYTE
    while remaining > 0:
        taken = min(remaining, MEGABYTE)
        digest.update(chunk[:taken])
        remaining -= taken
    return digest.hexdigest()


async def _slow_body(started: asyncio.Event) -> AsyncIterator[bytes]:
    """Thân multipart 64 MiB phát theo khúc 1 MiB, nhường vòng lặp giữa các khúc.

    `started` được đặt sau khúc trọng số thứ hai: tới lúc ấy handler đã qua `metadata`, qua 9
    byte đầu và đang ở trong `storage.put`, nên phép đo pool và lượt GET rơi đúng giữa luồng.
    """
    chunk = b"\x00" * MEGABYTE
    yield _part("metadata", _metadata(checksumSha256=_big_checksum()))
    yield _part_header("weights", None)
    yield b"\x08"
    for index in range(BIG_UPLOAD_BYTES // MEGABYTE):
        await asyncio.sleep(0)
        if index == 1:
            started.set()
        yield chunk[: MEGABYTE - 1] if index == 0 else chunk
    yield b"\r\n" + _closing()
