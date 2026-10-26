"""Task `ml.infer.document.titles`: OCR dải tiêu đề, `titles.json`, trả lời `documents.titles_ready`.

OCR được thay bằng bộ đọc ghi sẵn (K23: logic phía trên OCR); đường nạp model thật đi qua
`load_onnx` với model rec tí hon của `apps.ml.text.tests.helpers`. Kho là `LocalDiskStorage` thật.
"""

import asyncio
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import BaseModel

from apps.ml.document_titles import tasks
from apps.ml.document_titles.payloads import DocumentTitlesPayload, TitlesReadyPayload
from apps.ml.document_titles.tasks import READY_TASK, run_titles
from apps.ml.runtime.settings import MlSettings
from apps.ml.runtime.tasks_util import InferContext
from apps.ml.text.reader import RapidOcrReader
from apps.ml.text.tests.helpers import put_sync, read_sync, rec_model, some_id, storage_ref
from packages.ml_contracts.artifacts import BoxPx, TextPx
from packages.ml_contracts.fakes import FakeTextReader
from packages.ml_contracts.payloads import ModelRef
from packages.ml_contracts.ports import TextReader
from packages.storage import keys
from packages.storage.local import LocalDiskStorage

_CLASSIC = ModelRef(version_id=None, family="dimensionReading", weights_key=None, pinned_name=None, checksum_sha256="")
_TITLE = "MẶT BẰNG TẦNG 1"
Sent = list[tuple[str, BaseModel]]


class _Reader:
    """Bộ đọc ghi sẵn: mỗi dải trả một chữ ở góc trên-trái của dải."""

    def read(self, image: NDArray[np.uint8]) -> tuple[TextPx, ...]:
        """Một `TextPx` cố định theo toạ độ của ảnh dải."""
        return (TextPx(text=_TITLE, box=BoxPx(x_min=2, y_min=1, x_max=42, y_max=11), confidence=0.9),)


def _payload(storage: LocalDiskStorage, model: ModelRef = _CLASSIC, *, png: bytes | None = None) -> DocumentTitlesPayload:
    """Payload một trang 400x300 có một vùng; ghi ảnh xem trước (hay `png` cho sẵn) vào kho."""
    project, document = some_id("prj"), some_id("doc")
    key = keys.document_page_preview(project, document, 0)
    if png is None:
        png = cv2.imencode(".png", np.full((300, 400, 3), 255, np.uint8))[1].tobytes()
    put_sync(storage, key, png, "image/png")
    return DocumentTitlesPayload(
        project_id=project,
        document_id=document,
        page_index=0,
        preview_key=key,
        boxes=((0.1, 0.2, 0.9, 0.6),),
        model=model,
    )


def _run(storage: LocalDiskStorage, payload: DocumentTitlesPayload, reader: TextReader | None, sent: Sent) -> object:
    """Chạy lõi task với bộ ghi thay `send_task`; trả `titles.json` đã giải."""
    asyncio.run(run_titles(payload, storage=storage, reader=reader, send=lambda n, p: sent.append((n, p))))
    data = read_sync(storage, keys.document_titles(payload.project_id, payload.document_id, 0))
    assert data is not None
    return json.loads(data)


def _ready(payload: DocumentTitlesPayload) -> tuple[str, BaseModel]:
    """Thông điệp trả lời mong đợi của trang."""
    return READY_TASK, TitlesReadyPayload(document_id=payload.document_id, page_index=0)


def test_document_titles__J01(local_storage: LocalDiskStorage) -> None:
    """Chạy đúng: chữ ở dải trên và dưới vùng, hộp theo tỉ lệ TRANG; gửi đúng một `titles_ready` sau khi ghi."""
    payload = _payload(local_storage)
    sent: Sent = []
    out = _run(local_storage, payload, _Reader(), sent)
    # Dải trên bắt đầu ở pixel y=42, dải dưới ở y=180; x từ 40 (0,1 x 400).
    assert out == {
        "status": "ok",
        "texts": [
            {"text": _TITLE, "box": [0.105, round(43 / 300, 6), 0.205, round(53 / 300, 6)]},
            {"text": _TITLE, "box": [0.105, round(181 / 300, 6), 0.205, round(191 / 300, 6)]},
        ],
    }
    assert sent == [_ready(payload)]


def test_document_titles__J06(local_storage: LocalDiskStorage) -> None:
    """Giao lặp: ghi đè cùng khoá cùng bytes, mỗi lượt một trả lời giống nhau, không nhân đôi chữ."""
    payload = _payload(local_storage)
    key = keys.document_titles(payload.project_id, payload.document_id, 0)
    sent: Sent = []
    first = _run(local_storage, payload, _Reader(), sent)
    raw = read_sync(local_storage, key)
    assert _run(local_storage, payload, _Reader(), sent) == first
    assert read_sync(local_storage, key) == raw
    assert isinstance(first, dict)
    assert len(first["texts"]) == 2
    assert sent == [_ready(payload), _ready(payload)]


def test_document_titles__J10(local_storage: LocalDiskStorage) -> None:
    """Ghi xong rồi chết trước khi gửi: lượt giao lại ghi đè đúng bytes và gửi trả lời đúng một lần."""
    payload = _payload(local_storage)

    def broken(name: str, body: BaseModel) -> None:
        """Broker chết sau khi artifact đã ghi."""
        raise ConnectionError(name)

    with pytest.raises(ConnectionError):
        asyncio.run(run_titles(payload, storage=local_storage, reader=_Reader(), send=broken))
    key = keys.document_titles(payload.project_id, payload.document_id, 0)
    raw = read_sync(local_storage, key)
    assert raw is not None
    sent: Sent = []
    _run(local_storage, payload, _Reader(), sent)
    assert read_sync(local_storage, key) == raw
    assert sent == [_ready(payload)]


def _context(monkeypatch: pytest.MonkeyPatch, storage: LocalDiskStorage, settings: MlSettings) -> None:
    """Trỏ `infer_context` của task vào kho và cấu hình của test."""
    monkeypatch.setattr(tasks, "infer_context", lambda: InferContext(storage=storage, settings=settings))


def _onnx(tmp_path: Path) -> MlSettings:
    """Cấu hình chạy ONNX thật, thư mục model ghim rỗng."""
    return MlSettings(ml_backend="onnx", ml_models_dir=str(tmp_path), ml_ort_threads=1)


def test_model_missing_skipped(local_storage: LocalDiskStorage, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Không có bản kích hoạt hoặc model nạp hỏng → không bộ đọc → `skipped`, vẫn gửi trả lời."""
    _context(monkeypatch, local_storage, _onnx(tmp_path))
    data = rec_model().SerializeToString()
    bad_ref, bad_key = storage_ref(data, checksum="0" * 64)
    put_sync(local_storage, bad_key, data)
    for model in (_CLASSIC, bad_ref):
        payload = _payload(local_storage, model)
        reader = asyncio.run(tasks._reader(payload))
        assert reader is None
        sent: Sent = []
        assert _run(local_storage, payload, reader, sent) == {"status": "skipped", "texts": []}
        assert sent == [_ready(payload)]


def test_reader_choice(local_storage: LocalDiskStorage, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Model storage hợp lệ → `RapidOcrReader`; `ML_BACKEND=fake` → bộ giả, không nạp model."""
    _context(monkeypatch, local_storage, _onnx(tmp_path))
    data = rec_model().SerializeToString()
    ref, key = storage_ref(data)
    put_sync(local_storage, key, data)
    assert isinstance(asyncio.run(tasks._reader(_payload(local_storage, ref))), RapidOcrReader)
    _context(monkeypatch, local_storage, MlSettings(ml_backend="fake"))
    assert isinstance(asyncio.run(tasks._reader(_payload(local_storage))), FakeTextReader)


def test_bad_preview_skipped(local_storage: LocalDiskStorage) -> None:
    """Ảnh xem trước hỏng hay đã mất → `skipped` thay vì hỏng task."""
    corrupt = _payload(local_storage, png=b"not a png")
    truncated = _payload(local_storage, png=b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    lost = keys.document_page_preview(corrupt.project_id, corrupt.document_id, 5)
    missing = corrupt.model_copy(update={"preview_key": lost})
    for payload in (corrupt, truncated, missing):
        out = _run(local_storage, payload, _Reader(), [])
        assert isinstance(out, dict)
        assert out["status"] == "skipped"


def test_titles_failed_reports(local_storage: LocalDiskStorage, monkeypatch: pytest.MonkeyPatch) -> None:
    """`on_failed` (hết lượt thử) vẫn gửi `titles_ready` để tài liệu không kẹt ở `analyzing`."""
    sent: Sent = []
    monkeypatch.setattr(tasks, "send_task", lambda n, p: sent.append((n, p)))
    payload = _payload(local_storage)
    tasks.titles_failed(payload, "TASK_TIMEOUT")
    assert sent == [_ready(payload)]
