"""Nạp ONNX cho suy luận (BE-00 §9, K12, M02, M03): checksum trước, định dạng sau, phiên cuối.

Thứ tự trong `load_onnx` là hàng rào: không byte nào của model được **giải** trước khi
SHA-256 tự tính khớp checksum đã ghim; không byte nào được đưa cho `onnxruntime` trước
khi qua luật "ONNX không tin". Pickle, zip (`.pt`), safetensors bị chặn ở byte đầu,
không bao giờ tới bộ giải — kể cả khi checksum khớp.

Bản **ghim** (nhà cung cấp, `ML_MODELS_DIR/<name>.onnx`) miễn luật cấu trúc (hàm cục bộ,
miền op, `Loop`/`Scan`) nhưng vẫn qua luật dữ liệu ngoài: phiên nạp từ bytes không có thư
mục gốc, đường `external_data` sẽ được hiểu theo thư mục làm việc của tiến trình.
"""

import asyncio
import hashlib
import threading
from collections import OrderedDict
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Final

import onnx
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
from google.protobuf.message import DecodeError  # type: ignore[import-untyped]  # protobuf không kèm stub

from apps.ml.runtime.errors import MODEL_CHECKSUM_MISMATCH, MODEL_FORMAT_UNSUPPORTED, MODEL_NOT_FOUND, ORT_ERRORS
from apps.ml.runtime.settings import get_ml_settings
from packages.core.error_codes import NOT_FOUND
from packages.core.errors import AppError
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.payloads import ModelRef
from packages.ml_contracts.pinned import PINNED, PinnedWeights
from packages.storage.port import ObjectStorage

MODEL_MAX_BYTES: Final = 512 * 1024 * 1024
SESSION_CACHE_SIZE: Final = 3
ONNX_FIRST_BYTE: Final = 0x08
"""Byte đầu của mọi `ModelProto`: thẻ trường 1 (`ir_version`, varint)."""

TRUSTED_DOMAINS: Final = frozenset({"", "ai.onnx"})
FORBIDDEN_OPS: Final = frozenset({"Loop", "Scan"})


class _Sessions:
    """LRU phiên theo checksum, có khoá luồng: task đồng thời của một tiến trình dùng chung."""

    def __init__(self, size: int) -> None:
        """Bộ nhớ tối đa `size` phiên (mỗi phiên giữ cả trọng số trong RAM)."""
        self._size = size
        self._items: OrderedDict[str, ort.InferenceSession] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, checksum: str) -> ort.InferenceSession | None:
        """Phiên đã nạp của checksum, đánh dấu vừa dùng."""
        with self._lock:
            session = self._items.get(checksum)
            if session is not None:
                self._items.move_to_end(checksum)
            return session

    def put(self, checksum: str, session: ort.InferenceSession) -> None:
        """Nhớ phiên; quá `size` thì bỏ phiên lâu nhất chưa dùng."""
        with self._lock:
            self._items[checksum] = session
            self._items.move_to_end(checksum)
            while len(self._items) > self._size:
                self._items.popitem(last=False)

    def clear(self) -> None:
        """Quên mọi phiên."""
        with self._lock:
            self._items.clear()


_SESSIONS: Final = _Sessions(SESSION_CACHE_SIZE)


def clear_session_cache() -> None:
    """Chỉ cho test: bỏ mọi phiên đã nạp."""
    _SESSIONS.clear()


def _unsupported() -> PermanentError:
    """Lỗi chung cho mọi thứ không phải ONNX nạp được (không tiết lộ chi tiết ra kết quả bước)."""
    return PermanentError(MODEL_FORMAT_UNSUPPORTED)


type _Part = onnx.GraphProto | onnx.NodeProto | onnx.AttributeProto


def _parts(model: onnx.ModelProto) -> Iterator[_Part]:
    """Mọi đồ thị, node, thuộc tính của model ở mọi độ sâu — nguồn duy nhất cho các hàm duyệt.

    Gồm cả **giá trị mặc định thuộc tính của hàm cục bộ** (`FunctionProto.attribute_proto`):
    thân hàm dùng chúng qua `ref_attr_name`, ORT thay vào lúc nạp, còn bộ inline của `onnx`
    thì không. Bỏ sót chỗ này là để lọt `Loop`, op miền lạ hay tensor ngoài giấu trong đó.
    """
    pending: list[_Part] = [model.graph]
    for function in model.functions:
        pending.extend(function.node)
        pending.extend(function.attribute_proto)
    while pending:
        part = pending.pop()
        yield part
        if isinstance(part, onnx.GraphProto):
            pending.extend(part.node)
        elif isinstance(part, onnx.NodeProto):
            pending.extend(part.attribute)
        else:
            pending.extend(part.graphs)
            if part.HasField("g"):
                pending.append(part.g)


def iter_nodes(model: onnx.ModelProto) -> Iterator[onnx.NodeProto]:
    """Mọi node: đồ thị chính, thân hàm cục bộ, mọi đồ thị con (kể cả trong mặc định thuộc tính hàm)."""
    return (part for part in _parts(model) if isinstance(part, onnx.NodeProto))


def iter_graphs(model: onnx.ModelProto) -> Iterator[onnx.GraphProto]:
    """Đồ thị chính và mọi đồ thị con, ở cùng các chỗ `iter_nodes` duyệt."""
    return (part for part in _parts(model) if isinstance(part, onnx.GraphProto))


def iter_tensors(model: onnx.ModelProto) -> Iterator[onnx.TensorProto]:
    """Mọi `TensorProto`: initializer, sparse initializer, thuộc tính tensor của node và của hàm."""
    for part in _parts(model):
        if isinstance(part, onnx.GraphProto):
            yield from part.initializer
            sparse = list(part.sparse_initializer)
        elif isinstance(part, onnx.AttributeProto):
            if part.HasField("t"):
                yield part.t
            yield from part.tensors
            sparse = [*part.sparse_tensors, *([part.sparse_tensor] if part.HasField("sparse_tensor") else [])]
        else:
            continue
        for item in sparse:
            yield from (item.values, item.indices)


def has_external_data(model: onnx.ModelProto) -> bool:
    """Có tensor nào trỏ dữ liệu ra ngoài bytes của model (BE-00 §9)."""
    return any(
        tensor.data_location == onnx.TensorProto.EXTERNAL or len(tensor.external_data) > 0
        for tensor in iter_tensors(model)
    )


def _structure_allowed(model: onnx.ModelProto) -> bool:
    """Luật cấu trúc dạng storage (BE-00 §9): **không hàm cục bộ**, mọi node miền chuẩn, không `Loop`/`Scan`.

    Chặt hơn hiến chương (kiểm trên bản `inline_local_functions`): luật không thấy được thứ
    ORT chạy khi có hàm cục bộ — hàm trùng id op đã đăng ký thì ORT chạy kernel chứ không
    chạy thân hàm, và lời gọi lồng nở số node theo cấp số nhân (review 2026-09-22 #9, #10).
    Không có hàm thì bản inline chính là bản gốc. Model của hệ thống (`export_onnx`,
    `export_yolo`, ba bản ghim) không có hàm cục bộ nào.
    """
    if len(model.functions) > 0:
        return False
    return all(node.domain in TRUSTED_DOMAINS and node.op_type not in FORBIDDEN_OPS for node in iter_nodes(model))


def _verify(data: bytes, ref: ModelRef, pinned: Mapping[str, PinnedWeights]) -> None:
    """Bước 3-5 của `load_onnx`, chạy ngoài vòng sự kiện (băm và giải model lớn là việc CPU)."""
    digest = hashlib.sha256(data).hexdigest()
    expected = {ref.checksum_sha256}
    if ref.pinned_name is not None:
        expected.add(str(pinned[ref.pinned_name].onnx_sha256))
    if expected != {digest}:
        raise PermanentError(MODEL_CHECKSUM_MISMATCH)
    if not data or data[0] != ONNX_FIRST_BYTE:
        raise _unsupported()
    try:
        model = onnx.load_model_from_string(data)
    except DecodeError as exc:
        raise _unsupported() from exc
    if has_external_data(model) or (ref.pinned_name is None and not _structure_allowed(model)):
        raise _unsupported()


def _read_file(path: Path) -> bytes:
    """Tệp ghim với trần byte; thiếu → `MODEL_NOT_FOUND`, vượt trần → `MODEL_FORMAT_UNSUPPORTED`."""
    try:
        with path.open("rb") as handle:
            data = handle.read(MODEL_MAX_BYTES + 1)
    except FileNotFoundError as exc:
        raise PermanentError(MODEL_NOT_FOUND) from exc
    if len(data) > MODEL_MAX_BYTES:
        raise _unsupported()
    return data


async def _read_object(storage: ObjectStorage, key: str) -> bytes:
    """Object trọng số: `stat` trước, đọc theo khúc và dừng ngay khi vượt trần (kho có thể khai sai cỡ)."""
    info = await storage.stat(key)
    if info is None:
        raise PermanentError(MODEL_NOT_FOUND)
    if info.size > MODEL_MAX_BYTES:
        raise _unsupported()
    data = bytearray()
    try:
        async for chunk in storage.open_read(key):
            data += chunk
            if len(data) > MODEL_MAX_BYTES:
                raise _unsupported()
    except AppError as exc:
        if exc.code is not NOT_FOUND:
            raise
        raise PermanentError(MODEL_NOT_FOUND) from exc
    return bytes(data)


def _session(data: bytes, threads: int) -> ort.InferenceSession:
    """Phiên CPU từ bytes; lỗi `onnxruntime` (lớp thật) → `MODEL_FORMAT_UNSUPPORTED`."""
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    try:
        return ort.InferenceSession(data, sess_options=options, providers=["CPUExecutionProvider"])
    except ORT_ERRORS as exc:
        raise _unsupported() from exc


async def load_onnx(
    storage: ObjectStorage,
    ref: ModelRef,
    *,
    models_dir: Path,
    pinned: Mapping[str, PinnedWeights] = PINNED,
) -> ort.InferenceSession:
    """Phiên `onnxruntime` cho model của một bước; mọi lỗi của model → `PermanentError` có mã.

    1. dạng cổ điển → `ValueError` (người gọi phải đi đường lùi); trúng cache → phiên cũ;
    2. đọc ≤ `MODEL_MAX_BYTES` (ghim: `models_dir/<name>.onnx`; storage: `weights_key`);
    3. SHA-256 tự tính ≠ checksum (ghim: cả `onnx_sha256` của bản ghim) → `MODEL_CHECKSUM_MISMATCH`;
    4-5. byte đầu, giải protobuf, luật ONNX không tin → `MODEL_FORMAT_UNSUPPORTED`;
    6. `InferenceSession` CPU với `ML_ORT_THREADS` luồng, ngoài vòng sự kiện.
    """
    if ref.is_classic:
        raise ValueError("model cổ điển không có gì để nạp")
    cached = _SESSIONS.get(ref.checksum_sha256)
    if cached is not None:
        return cached
    if ref.pinned_name is not None:
        if ref.pinned_name not in pinned:
            raise PermanentError(MODEL_NOT_FOUND)
        data = await asyncio.to_thread(_read_file, models_dir / f"{ref.pinned_name}.onnx")
    else:
        data = await _read_object(storage, str(ref.weights_key))
    await asyncio.to_thread(_verify, data, ref, pinned)
    session = await asyncio.to_thread(_session, data, get_ml_settings().ml_ort_threads)
    _SESSIONS.put(ref.checksum_sha256, session)
    return session
