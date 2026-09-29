"""N26 — nhận trọng số qua multipart luồng, không giữ kết nối DB (B6-01 [6], K36, M02, M03).

Thứ tự bất biến của một lượt tải lên:

1. `await db.rollback()` ngay đầu handler: session của request đã mở nhưng lượt nhận tệp có thể
   kéo hàng chục giây, và pool có hạn (K36) — giữ kết nối trong lúc đọc luồng là khoá cả API;
2. đọc `request.stream()` qua parser luồng của `python-multipart`; **không** `UploadFile`,
   `request.form()`, `request.body()` (chúng gom cả 512 MiB vào RAM hay đĩa tạm);
3. phần một là `metadata` (≤ 16 KiB, JSON strict), phần hai là `weights`, không có phần ba;
4. gom **9 byte đầu** của `weights` rồi so với định dạng khai (K12, K14): không tin đuôi, tên
   tệp hay `Content-Type` của phần, và **không** nạp trọng số (không `torch.load`, không
   `pickle`, không `onnxruntime`);
5. `storage.put(..., max_bytes=MODEL_UPLOAD_MAX_BYTES)` băm trong lúc đọc; checksum lệch → xoá
   object rồi 422 `MODEL_CHECKSUM_MISMATCH`;
6. giao dịch **ngắn**: chèn dòng `pending`, ghi nhật ký, đăng ký task đánh giá sau commit, rồi
   handler tự `await db.commit()` (route khai `idempotency="off"` nên được phép, B0-06). Bất kỳ
   lỗi nào sau bước 5 → xoá object đã ghi rồi ném lại: object mồ côi là rác có phí lưu trữ.
"""

from collections import deque
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING

from pydantic import ValidationError
from python_multipart.multipart import MultipartParser, parse_options_header
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import ClientDisconnect, Request

from apps.api.access.activity import record_activity
from apps.api.access.kinds import ActivityKind
from apps.api.admin_ml_registry.errors import MODEL_CHECKSUM_MISMATCH, MODEL_FORMAT_UNSUPPORTED
from apps.api.admin_ml_registry.registry import enqueue_evaluation
from apps.api.admin_ml_registry.schemas import CreateModelVersionMetadata, ModelVersionOut, version_out
from apps.api.admin_ml_registry.settings import MlRegistrySettings
from apps.api.core.auth import Principal
from apps.api.core.errors import field_of
from packages.core.clock import Clock
from packages.core.error_codes import VALIDATION
from packages.core.errors import AppError
from packages.core.ids import new_id
from packages.db.models.admin_ml_registry import ModelVersionRow
from packages.storage.keys import model_artifact
from packages.storage.port import DEFAULT_CONTENT_TYPE, ObjectStorage

if TYPE_CHECKING:  # `MultipartCallbacks` chỉ tồn tại lúc kiểm kiểu, không xuất lúc chạy
    from python_multipart.multipart import MultipartCallbacks

METADATA_PART = "metadata"
WEIGHTS_PART = "weights"

METADATA_MAX_BYTES = 16 * 1024
"""`metadata` là bốn khoá ngắn: trần 16 KiB chặn một phần đầu dài vô hạn trước khi nó vào RAM."""

HEAD_BYTES = 9
"""8 byte độ dài header safetensors cộng dấu mở JSON — đủ nhận cả hai định dạng (M02)."""

SAFETENSORS_HEADER_MAX = 100 * 1024 * 1024
MULTIPART_CONTENT_TYPE = b"multipart/form-data"
_ONNX_FIRST_BYTE = b"\x08"
_CONTENT_DISPOSITION = b"content-disposition"


def _bad_part(name: str, expected: str) -> AppError:
    """422 `VALIDATION` `field` = tên phần nhận được; tên ngoài mẫu W7 → tên phần chờ đợi.

    Tên phần do client đặt nên có thể là chuỗi bất kỳ, mà `field` của W7 phải khớp mẫu tên
    trường (`packages/core/errors.py`): gọi lại bộ kiểm của lõi thay vì chép mẫu lần hai.
    """
    try:
        return VALIDATION.error(field=name)
    except ValueError:
        return VALIDATION.error(field=expected)


def _boundary(request: Request) -> bytes:
    """Boundary của thân multipart; `Content-Type` khác `multipart/form-data` → 422 `VALIDATION`."""
    content_type, options = parse_options_header(request.headers.get("content-type"))
    boundary = options.get(b"boundary")
    if content_type != MULTIPART_CONTENT_TYPE or not boundary:
        raise VALIDATION.error()
    return boundary


def _metadata_of(raw: bytes) -> CreateModelVersionMetadata:
    """Phần `metadata` → lớp strict của `schemas`; khoá lạ hay trường sai → 422 có `field` (C02, C03)."""
    try:
        return CreateModelVersionMetadata.model_validate_json(raw)
    except ValidationError as exc:
        field = field_of(exc.errors()[0].get("loc", ())) if exc.error_count() else None
        raise (VALIDATION.error(field=field) if field else VALIDATION.error()) from exc


def _head_matches(weights_format: str, head: bytes) -> bool:
    """9 byte đầu có đúng là định dạng khai? Không mở tệp, không nạp trọng số (K12, K14).

    `onnx` là protobuf: trường 1 varint nên byte đầu là `0x08`. `safetensors` là 8 byte LE độ
    dài header JSON rồi dấu mở JSON; `n = 0` hay `n` phi lý là tệp hỏng. Thân `.pt` (`PK…`),
    pickle (`0x80`) và tệp rỗng trượt cả hai nhánh, nên không cần liệt kê riêng từng loại.
    """
    if weights_format == "onnx":
        return head[:1] == _ONNX_FIRST_BYTE
    if len(head) < HEAD_BYTES:
        return False
    return 1 <= int.from_bytes(head[:8], "little") <= SAFETENSORS_HEADER_MAX and head[8:9] == b"{"


class _WeightsStream:
    """Parser luồng của hai phần `metadata`, `weights`: đọc tới đâu giao tới đó.

    Không dùng `FormParser`/`parse_form` của `python-multipart`: hai cái ấy dựng `Field`/`File`,
    tức gom cả phần vào RAM hay đĩa tạm — đúng thứ K36/M02 cấm. Ở đây `metadata` (có trần) là
    thứ duy nhất được gom; khúc của `weights` nằm trong `_chunks` đúng tới lượt `put` lấy ra,
    nên bộ nhớ phẳng theo kích thước tệp.

    Callback của parser ném thẳng `AppError` 422: chúng chạy bên trong `parser.write()`, nên
    lỗi phần sai tên hay phần thứ ba nổi lên ngay khúc phát hiện, không phải sau cả lượt đọc.
    """

    def __init__(self, stream: AsyncIterator[bytes], boundary: bytes) -> None:
        """Gắn callback vào một `MultipartParser`; `stream` là `request.stream()` chưa đọc byte nào."""
        callbacks: MultipartCallbacks = {
            "on_part_begin": self._on_part_begin,
            "on_header_field": self._on_header_field,
            "on_header_value": self._on_header_value,
            "on_header_end": self._on_header_end,
            "on_headers_finished": self._on_headers_finished,
            "on_part_data": self._on_part_data,
        }
        self._stream = stream
        self._parser = MultipartParser(boundary, callbacks)
        self._index = -1
        self._name = ""
        self._field = bytearray()
        self._value = bytearray()
        self._metadata = bytearray()
        self._chunks: deque[bytes] = deque()
        self._weights_started = False
        self._done = False

    def _on_part_begin(self) -> None:
        """Phần mới: đếm lên và quên tên của phần trước."""
        self._index += 1
        self._name = ""

    def _on_header_field(self, data: bytes, start: int, end: int) -> None:
        """Tên header tới theo lát cắt, có thể vắt qua nhiều khúc của luồng."""
        self._field += data[start:end]

    def _on_header_value(self, data: bytes, start: int, end: int) -> None:
        """Giá trị header tới theo lát cắt, như tên header."""
        self._value += data[start:end]

    def _on_header_end(self) -> None:
        """Hết một header: chỉ `Content-Disposition` mang tên phần, cái duy nhất N26 tin."""
        if bytes(self._field).lower() == _CONTENT_DISPOSITION:
            name = parse_options_header(bytes(self._value))[1].get(b"name", b"")
            self._name = name.decode("utf-8", "replace")
        self._field.clear()
        self._value.clear()

    def _on_headers_finished(self) -> None:
        """Luật phần: thứ nhất `metadata`, thứ hai `weights`, không có thứ ba (B6-01 [6] N26.2)."""
        expected = METADATA_PART if self._index == 0 else WEIGHTS_PART
        if self._index > 1 or self._name != expected:
            raise _bad_part(self._name, expected)
        self._weights_started = self._index == 1

    def _on_part_data(self, data: bytes, start: int, end: int) -> None:
        """Khúc dữ liệu: `metadata` gom có trần, `weights` vào hàng chờ cho `put` lấy ra."""
        if self._index == 0:
            if len(self._metadata) + end - start > METADATA_MAX_BYTES:
                raise VALIDATION.error(field=METADATA_PART)
            self._metadata += data[start:end]
        else:
            self._chunks.append(bytes(data[start:end]))

    async def _pump(self) -> bool:
        """Một khúc từ luồng vào parser; hết luồng → `finalize()` và `False`. Thân hỏng → 422."""
        try:
            chunk = await anext(self._stream)
        except StopAsyncIteration:
            self._done = True
            self._write(self._parser.finalize)
            return False
        self._write(lambda: self._parser.write(chunk))
        return True

    @staticmethod
    def _write(step: Callable[[], object]) -> None:
        """Một lượt vào parser; mọi lỗi parse của `python-multipart` là `ValueError` → 422."""
        try:
            step()
        except ValueError as exc:
            raise VALIDATION.error() from exc

    async def metadata(self) -> CreateModelVersionMetadata:
        """Đọc tới hết header của `weights` rồi giải `metadata` — chưa chạm byte trọng số nào."""
        while not self._weights_started and await self._pump():
            pass
        if not self._weights_started:
            raise VALIDATION.error(field=METADATA_PART if self._index < 0 else WEIGHTS_PART)
        return _metadata_of(bytes(self._metadata))

    async def head(self) -> bytes:
        """`HEAD_BYTES` byte đầu của `weights`, gom trước `put` để định dạng sai không ghi gì."""
        head = bytearray()
        while len(head) < HEAD_BYTES:
            while self._chunks and len(head) < HEAD_BYTES:
                chunk = self._chunks.popleft()
                taken = HEAD_BYTES - len(head)
                head += chunk[:taken]
                if len(chunk) > taken:
                    self._chunks.appendleft(chunk[taken:])
            if len(head) == HEAD_BYTES or self._done or not await self._pump():
                break
        return bytes(head)

    async def body(self, head: bytes) -> AsyncIterator[bytes]:
        """Byte đầu đã gom rồi phần còn lại của `weights`, khúc nào ra khúc ấy.

        Bơm tới **hết** luồng chứ không dừng ở cuối phần `weights`: phần thứ ba chỉ lộ ra khi
        header của nó được đọc, và phát hiện nó trong lúc `put` đang chạy nghĩa là kho tự dọn
        object dở của mình (`local.py` xoá file tạm, `s3.py` chưa gửi byte nào).
        """
        if head:
            yield head
        while not self._done:
            while self._chunks:
                yield self._chunks.popleft()
            await self._pump()
        while self._chunks:
            yield self._chunks.popleft()


def _pending_row(
    version_id: str, metadata: CreateModelVersionMetadata, *, key: str, creator_id: str, clock: Clock
) -> ModelVersionRow:
    """Dòng `pending` của bản vừa nhận: một lần thử đánh giá đã được yêu cầu ngay lúc này.

    `created_at`/`updated_at` đặt tường minh (như factory) để `version_out` đọc được sau commit
    mà không phải `refresh` — một lượt đọc DB nữa chỉ để lấy `now()` của server.
    """
    now = clock.now()
    return ModelVersionRow(
        id=version_id,
        family=metadata.family,
        label=metadata.label,
        weights_format=metadata.weights_format,
        checksum_sha256=metadata.checksum_sha256,
        weights_key=key,
        evaluation_status="pending",
        metrics=None,
        evaluation_attempts=1,
        evaluation_requested_at=now,
        creator_id=creator_id,
        created_at=now,
        updated_at=now,
    )


async def _commit_version(db: AsyncSession, row: ModelVersionRow, *, actor_id: str, clock: Clock) -> None:
    """Giao dịch ngắn của bước 6: chèn dòng, ghi nhật ký, đăng ký task sau commit, rồi commit.

    `enqueue_evaluation` đăng ký **trong** giao dịch đang mở (K17): gọi sau `commit()` thì
    callback rơi vào giao dịch sau và task bắn lệch lượt.
    """
    db.add(row)
    await record_activity(
        db, actor_id=actor_id, kind=ActivityKind.MODEL_UPLOAD, object_code=row.id, object_label=row.label, clock=clock
    )
    enqueue_evaluation(db, row)
    await db.commit()


async def upload_version(
    request: Request,
    *,
    db: AsyncSession,
    storage: ObjectStorage,
    principal: Principal,
    clock: Clock,
    settings: MlRegistrySettings,
) -> ModelVersionOut:
    """N26 — 201 với bản vừa ghi; hàm tự `rollback` đầu lượt và tự `commit` cuối lượt.

    Nhận `Request` thô vì thân là multipart đọc theo luồng; nhận `db` (chứ không tự mở session)
    vì `AppRoute` đã mở nó cho request này và cùng session ấy phải mang dòng mới, nhật ký và
    callback sau commit.
    """
    await db.rollback()
    parts = _WeightsStream(request.stream(), _boundary(request))
    metadata = await parts.metadata()
    head = await parts.head()
    if not _head_matches(metadata.weights_format, head):
        raise MODEL_FORMAT_UNSUPPORTED.error()
    version_id = new_id("mdl", clock)
    key = model_artifact(version_id, f"weights.{metadata.weights_format}")
    info = await storage.put(
        key, parts.body(head), content_type=DEFAULT_CONTENT_TYPE, max_bytes=settings.model_upload_max_bytes
    )
    if info.sha256 != metadata.checksum_sha256:
        await storage.delete(key)
        raise MODEL_CHECKSUM_MISMATCH.error(field="checksumSha256")
    row = _pending_row(version_id, metadata, key=key, creator_id=principal.user_id, clock=clock)
    try:
        await _commit_version(db, row, actor_id=principal.user_id, clock=clock)
    except (SQLAlchemyError, ClientDisconnect, ValueError, AppError):
        await storage.delete(key)
        raise
    return version_out(row)
