"""`GET /api/files/{token}` — phục vụ object của `LocalDiskStorage` (BE-00 §8, W23).

Token **là** quyền truy cập: nó mang MAC HMAC khoá `file` trên `object_key | exp |
disposition | filename`, nên route công khai. Ba hệ quả:

- token không bao giờ vào log (`AccessLogMiddleware` chỉ ghi `routeTemplate`, K11);
- mọi thất bại — token hỏng, giả mạo, hết hạn, object không có, backend là S3 —
  đều trả **cùng một** 404 `NOT_FOUND`, để endpoint không thành máy dò khoá;
- tệp người dùng luôn `attachment` + `nosniff`; chỉ PNG/JPEG đã kiểm magic bytes
  và token ghi `inline` mới được hiển thị thẳng (K15).
"""

from typing import Final

from starlette.requests import Request
from starlette.responses import StreamingResponse

from apps.api.core.routing import public_router
from packages.core.error_codes import NOT_FOUND
from packages.storage.local import LocalDiskStorage
from packages.storage.port import Disposition, ObjectInfo, content_disposition, content_type_of
from packages.storage.sniff import IMAGE_KINDS

CACHE_CONTROL: Final = "private, max-age=600"

router = public_router(tags=["files"])
ROUTERS: Final = (router,)


@router.get("/files/{token}", response_class=StreamingResponse, status_code=200)
async def files_read_object(token: str, request: Request) -> StreamingResponse:
    """Stream object theo token đã ký; mọi lỗi → 404 `NOT_FOUND`."""
    storage = request.app.state.storage
    if not isinstance(storage, LocalDiskStorage):
        # Backend S3/MinIO ký URL trỏ thẳng tới kho, endpoint này không tồn tại về nghiệp vụ.
        raise NOT_FOUND.error()
    grant = storage.verify_token(token)
    info = await storage.stat(grant.key)
    if info is None:
        raise NOT_FOUND.error()
    return StreamingResponse(
        storage.open_read(grant.key),
        media_type=_content_type(grant.disposition, info),
        headers={
            "Content-Disposition": content_disposition(_disposition(grant.disposition, info), grant.filename),
            "Cache-Control": CACHE_CONTROL,
        },
    )


def _disposition(requested: str, info: ObjectInfo) -> Disposition:
    """`inline` chỉ khi token ghi `inline` **và** magic bytes nói đó là PNG/JPEG (BE-00 §8)."""
    return "inline" if requested == "inline" and info.kind in IMAGE_KINDS else "attachment"


def _content_type(requested: str, info: ObjectInfo) -> str:
    """Loại nội dung: bản hiển thị thẳng lấy theo magic bytes, bản tải về giữ loại đã lưu.

    Hai nguồn khác nhau có chủ đích: `info.content_type` là chuỗi người gọi khai lúc
    `put`, chỉ an toàn khi đi kèm `attachment` + `nosniff` (K15).
    """
    return content_type_of(info.kind) if _disposition(requested, info) == "inline" else info.content_type
