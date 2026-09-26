"""Thời gian #31 ở đúng trần (B2-05b [6] "Thời gian", W11, K28): dưới 15 s, in thời gian từng bước.

Hai ca: PDF A1 200 DPI **có nội dung bản vẽ** (khung, tường, vạch kích thước — không phải trang
trắng) và ảnh quét ≈ 40 MP nhiễu Gauss (ca nặng nhất: PNG lớn phải giải mã). Các hàm nặng của
`processing` được bọc bằng đồng hồ nên mỗi bước (nạp/dựng trang, nắn, đo, mã hoá) đều in ra.
"""

import time
from collections.abc import Callable
from typing import Any, Final

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.quality import processing
from apps.api.quality.tests._images import a1_pdf, desk_shot, noisy_scan_png
from apps.api.quality.tests._route_helpers import (
    SHOT_H,
    SHOT_W,
    corners_body,
    corners_path,
    make_image_floor,
    make_stage,
)
from apps.api.quality.tests._route_helpers import (
    quality_env as quality_env,
)
from packages.storage.local import LocalDiskStorage

BUDGET_S: Final = 15.0
INSET: Final = ((0.05, 0.05), (0.95, 0.05), (0.95, 0.95), (0.05, 0.95))
STEPS: Final = ("render_pdf_page", "load_raster", "rectify", "assess", "encode_png")


def _instrument(monkeypatch: pytest.MonkeyPatch) -> dict[str, float]:
    """Bọc từng hàm nặng của `processing` bằng đồng hồ; trả bảng `tên -> giây` được điền khi chạy."""
    seconds: dict[str, float] = {}

    def timed(name: str, real: Callable[..., Any]) -> Callable[..., Any]:
        """Hàm bọc `real` cộng dồn thời gian vào `seconds[name]` (chạy trong luồng executor)."""

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Gọi `real` và ghi thời gian."""
            started = time.perf_counter()
            try:
                return real(*args, **kwargs)
            finally:
                seconds[name] = seconds.get(name, 0.0) + time.perf_counter() - started

        return wrapper

    for name in STEPS:
        monkeypatch.setattr(processing, name, timed(name, getattr(processing, name)))
    return seconds


async def _time_corners(
    client: httpx.AsyncClient,
    db: AsyncSession,
    storage: LocalDiskStorage,
    monkeypatch: pytest.MonkeyPatch,
    *,
    label: str,
    original: bytes,
    file_name: str,
) -> None:
    """Dựng tầng có `original`, gọi #31, in thời gian tổng và từng bước, khẳng định 200 và dưới trần."""
    stage = await make_stage(db, storage, floors=0)
    drawn = await make_image_floor(
        db,
        storage,
        project=stage.project,
        pixels=desk_shot(SHOT_W, SHOT_H).pixels,
        original=original,
        file_name=file_name,
    )
    stage.floors.append(drawn)
    await db.commit()
    steps = _instrument(monkeypatch)

    started = time.perf_counter()
    response = await client.post(
        corners_path(stage.project.id, stage.level()), json=corners_body(INSET), headers=stage.headers
    )
    elapsed = time.perf_counter() - started

    detail = "  ".join(f"{name}={value:.2f}s" for name, value in steps.items())
    print(f"#31 {label}: tổng={elapsed:.2f}s (trần {BUDGET_S:.0f}s)  {detail}")
    assert response.status_code == 200, response.text
    assert elapsed < BUDGET_S


@pytest.mark.perf
async def test_quality_set_corners__a1_pdf_under_budget(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gốc PDF khổ A1 có nội dung: dựng trang 200 DPI, nắn, đo, ghi PNG và đổi bản vẽ trong < 15 s."""
    await _time_corners(
        api_client,
        db_session,
        local_storage,
        monkeypatch,
        label="PDF A1 200 DPI",
        original=a1_pdf(),
        file_name="ban-ve.pdf",
    )


@pytest.mark.perf
async def test_quality_set_corners__noisy_40mp_scan_under_budget(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gốc PNG quét ≈ 40 MP nhiễu Gauss sigma 8: cả #31 trong < 15 s."""
    await _time_corners(
        api_client,
        db_session,
        local_storage,
        monkeypatch,
        label="quét 40 MP sigma=8",
        original=noisy_scan_png(),
        file_name="ban-ve.png",
    )
