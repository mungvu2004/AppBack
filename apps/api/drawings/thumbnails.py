"""Ảnh nhỏ từng trang PDF cho ô chọn trang (UX41 U05).

PDF nhiều trang chỉ được tải lên **sau** khi người dùng chọn trang (`pageIndex` nằm ở #5),
nên ảnh nhỏ không đọc được từ kho: FE gửi thẳng byte PDF, BE dựng rồi trả ngay, không ghi gì.
Ảnh trả dạng `data:` URL — CSP `img-src` đã có `data:` (`security_headers.conf`).
"""

import asyncio
import base64
from typing import Final

from pydantic import Field

from apps.api.core.wire import WireModel
from packages.vision.preprocess import VisionError, encode_png, render_pdf_thumbnails

THUMBNAIL_BODY_LIMIT: Final = 8 * 1024 * 1024
"""Trần thân = trần `client_max_body_size` của nginx cho `/api/`.

ponytail: PDF > 8 MiB không có ảnh nhỏ (FE lùi về danh sách chữ); muốn hơn thì dựng ảnh
từ lượt tải đã nhận đủ khúc thay vì gửi tệp hai lần.
"""

THUMBNAIL_MAX_PIXELS: Final = 240 * 340
"""~0,08 MP mỗi trang: đủ nhận ra mặt bằng ở ô 120 px, 20 trang vẫn dưới ~1 MB JSON."""

THUMBNAIL_MAX_PAGES: Final = 20
"""Cùng trần `PDF_PAGE_MAX` của #7: trang sau đó không bao giờ được chọn."""


class PageThumbnailsOut(WireModel):
    """`{pages: ["data:image/png;base64,…", …]}`, phần tử thứ i là trang i (đếm từ 0)."""

    pages: list[str] = Field(max_length=THUMBNAIL_MAX_PAGES)


def _render(data: bytes) -> list[str]:
    """Byte PDF → data URL PNG của từng trang; `VisionError` → `AppError` 422 cùng mã."""
    try:
        images = render_pdf_thumbnails(data, max_pixels=THUMBNAIL_MAX_PIXELS, max_pages=THUMBNAIL_MAX_PAGES)
    except VisionError as exc:
        raise exc.to_app_error() from exc
    return ["data:image/png;base64," + base64.b64encode(encode_png(img)).decode("ascii") for img in images]


async def page_thumbnails(data: bytes) -> PageThumbnailsOut:
    """Dựng ảnh nhỏ ngoài vòng lặp sự kiện (pdfium chặn luồng)."""
    return PageThumbnailsOut(pages=await asyncio.to_thread(_render, data))
