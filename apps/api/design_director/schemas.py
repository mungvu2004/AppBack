"""Model trên dây của AI chọn phong cách (HOP-DONG-AID-01, camelCase; trường tuỳ chọn **vắng**, không `null`, W2)."""

from typing import Any, Literal

from apps.api.core.wire import WireDatetime, WireModel, WireRequest

type DesignStyleId = Literal[
    "japandi",
    "scandinavian",
    "modern-min",
    "modern-lux",
    "indochine",
    "wabi-sabi",
    "industrial",
    "tropical",
    "korean-min",
    "neoclassic",
    "midcentury",
    "rustic",
]
type DesignConceptStatus = Literal["queued", "running", "done", "failed"]


class DesignConcept(WireModel):
    """Một concept: `styleId` vắng khi lượt AI-tự-chọn chưa chọn xong; `result` chỉ khi `done`."""

    id: str
    style_id: DesignStyleId | None = None
    suggested: bool
    status: DesignConceptStatus
    failure_code: str | None = None
    created_at: WireDatetime
    started_at: WireDatetime | None = None
    ended_at: WireDatetime | None = None
    result: dict[str, Any] | None = None


class DesignConceptState(WireModel):
    """N47: công tắc, kiểu AI đề xuất mới nhất, concept đang chọn."""

    enabled: bool
    suggested_style_id: DesignStyleId | None = None
    active: DesignConcept | None = None


class SelectDesignConceptIn(WireRequest):
    """Thân N48: `styleId` vắng hoặc `null` = quay về đề xuất AI."""

    style_id: DesignStyleId | None = None
