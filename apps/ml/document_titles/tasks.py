"""Task `ml.infer.document.titles`: OCR chữ tiêu đề quanh các vùng của một trang tài liệu.

Tên mang tiền tố `ml.infer.` để `queue_for` đưa vào hàng `ml.infer` của container ml (tên
`ml.document.titles` của CONTRACT §3.4 sẽ rơi vào hàng `default`). Không ghi DB: ghi
`titles.json` theo `keys.document_titles` rồi gửi `documents.titles_ready` cho worker. Không có
model (cổ điển, nạp lỗi) hay trang hỏng ⇒ artifact `status: "skipped"`, vẫn gửi trả lời (Q4):
phân loại khi ấy chạy không có T2 chứ không hỏng tài liệu.
"""

import asyncio
import logging
from pathlib import Path
from typing import Final, Literal

import cv2
import numpy as np
from numpy.typing import NDArray

from apps.ml.document_titles.payloads import DocumentTitlesPayload, TitlesReadyPayload
from apps.ml.document_titles.service import TitleItem, read_titles, titles_json
from apps.ml.runtime.errors import FILE_CORRUPT, IMAGE_TOO_LARGE, PIPELINE_ARTIFACT_MISSING
from apps.ml.runtime.loader import load_onnx
from apps.ml.runtime.tasks_util import PAGE_MAX_BYTES, Send, infer_context
from apps.ml.text.reader import RapidOcrReader
from packages.messaging.celery_app import send_task
from packages.messaging.tasks import PermanentError, define_task
from packages.ml_contracts.artifacts import MASK_MAX_PIXELS, read_png_header
from packages.ml_contracts.fakes import FakeTextReader
from packages.ml_contracts.ports import TextReader
from packages.storage import keys
from packages.storage.port import ObjectStorage, read_all_capped

__all__ = ["READY_TASK", "TASK", "document_titles", "run_titles"]

_log: Final = logging.getLogger(__name__)

TASK: Final = "ml.infer.document.titles"
READY_TASK: Final = "documents.titles_ready"
OCR_FAMILY: Final = "dimensionReading"
TITLES_MAX_BYTES: Final = 4 * 1024 * 1024


async def _reader(payload: DocumentTitlesPayload) -> TextReader | None:
    """Bộ đọc của lượt: bộ giả (`ML_BACKEND=fake`), `RapidOcrReader` trên model đã kiểm, hay `None` (bỏ T2)."""
    context = infer_context()
    if context.settings.ml_backend == "fake":
        return FakeTextReader()
    if payload.model.is_classic or payload.model.family != OCR_FAMILY:
        return None
    try:
        session = await load_onnx(context.storage, payload.model, models_dir=Path(context.settings.ml_models_dir))
    except PermanentError as exc:
        _log.warning("document_titles_model_unavailable", extra={"code": exc.code})
        return None
    return RapidOcrReader.from_session(session, pinned_name=payload.model.pinned_name)


def _decode(data: bytes) -> NDArray[np.uint8]:
    """PNG ảnh xem trước → RGB; kiểm khổ từ IHDR trước khi giải (K13); hỏng → `FILE_CORRUPT`."""
    try:
        header = read_png_header(data)
    except ValueError as exc:
        raise PermanentError(FILE_CORRUPT) from exc
    if header.width * header.height > MASK_MAX_PIXELS:
        raise PermanentError(IMAGE_TOO_LARGE)
    bgr = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise PermanentError(FILE_CORRUPT)
    return np.asarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), dtype=np.uint8)


def _ready(payload: DocumentTitlesPayload) -> TitlesReadyPayload:
    """Payload trả lời của trang."""
    return TitlesReadyPayload(document_id=payload.document_id, page_index=payload.page_index)


async def run_titles(
    payload: DocumentTitlesPayload,
    *,
    storage: ObjectStorage,
    reader: TextReader | None,
    send: Send = send_task,
) -> None:
    """Đọc ảnh xem trước, OCR dải tiêu đề, ghi đè `titles.json` **rồi mới** gửi `documents.titles_ready`.

    Ghi trước gửi sau: chết giữa hai bước thì lượt giao lại ghi đè cùng bytes rồi gửi (J06, J10).
    """
    status: Literal["ok", "skipped"] = "skipped"
    texts: list[TitleItem] = []
    if reader is not None:
        try:
            data = await read_all_capped(
                storage,
                payload.preview_key,
                max_bytes=PAGE_MAX_BYTES,
                too_large=lambda: PermanentError(IMAGE_TOO_LARGE),
                on_missing=lambda: PermanentError(PIPELINE_ARTIFACT_MISSING),
            )
            image = await asyncio.to_thread(_decode, data)
            texts = await asyncio.to_thread(read_titles, image, payload.boxes, reader)
            status = "ok"
        except PermanentError as exc:
            _log.warning("document_titles_skipped", extra={"code": exc.code, "document_id": payload.document_id})
    key = keys.document_titles(payload.project_id, payload.document_id, payload.page_index)
    await storage.put(key, titles_json(status, texts), content_type="application/json", max_bytes=TITLES_MAX_BYTES)
    await asyncio.to_thread(send, READY_TASK, _ready(payload))


def titles_failed(payload: DocumentTitlesPayload, code: str) -> None:
    """`on_failed` (hết lượt thử, quá giờ): vẫn báo worker để tài liệu không kẹt; thiếu artifact = không có T2."""
    _log.warning("document_titles_failed", extra={"code": code, "document_id": payload.document_id})
    send_task(READY_TASK, _ready(payload))


@define_task(name=TASK, payload=DocumentTitlesPayload, on_failed=titles_failed)
async def document_titles(payload: DocumentTitlesPayload) -> None:
    """OCR chữ tiêu đề quanh các vùng của một trang, ghi `titles.json`, báo `documents.titles_ready` (J01, J06)."""
    await run_titles(payload, storage=infer_context().storage, reader=await _reader(payload))
