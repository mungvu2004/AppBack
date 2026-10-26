"""Payload vào/ra của task OCR chữ tiêu đề (PHASE-1-CONTRACT §3.4, thêm `model` theo người điều phối)."""

from typing import Annotated

from pydantic import Field

from packages.ml_contracts.payloads import MlPayload, ModelRef

Ratio = Annotated[float, Field(ge=0.0, le=1.0)]


class DocumentTitlesPayload(MlPayload):
    """Một trang tài liệu cần OCR quanh các hộp vùng; `model` là bản kích hoạt `dimensionReading` bên gửi tra."""

    project_id: str
    document_id: str
    page_index: Annotated[int, Field(ge=0)]
    preview_key: str
    boxes: tuple[tuple[Ratio, Ratio, Ratio, Ratio], ...]
    model: ModelRef


class TitlesReadyPayload(MlPayload):
    """Báo worker `documents.titles_ready`: artifact `titles.json` của trang đã có (kể cả `skipped`)."""

    document_id: str
    page_index: Annotated[int, Field(ge=0)]
