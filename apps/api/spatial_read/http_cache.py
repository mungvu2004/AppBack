"""Trả model đọc lớn đã serialize **một lần**, kèm `ETag` yếu và 304 (PERF-03 P13/P27).

`FastAPI` mặc định validate lại giá trị trả về theo `response_model` rồi serialize — với
tài liệu 142 KB đó là vài ms CPU mỗi lượt. Route trả `Response` dựng sẵn thì FastAPI bỏ
qua cả hai bước; `response_model` vẫn khai ở decorator nên openapi không đổi.

`ETag` băm từ **thân** chứ không từ `revision`: thân N16 còn mang `level` (tên tầng, bản
vẽ), `readiness` (lượt chạy) và tỉ lệ trang — những thứ đổi mà `revision` không tăng. Băm
thân không bao giờ cho 304 sai; giá là vẫn phải dựng thân, chỉ tiết kiệm đường truyền.
"""

from hashlib import blake2b
from typing import Final

from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response

CACHE_CONTROL: Final = "private, no-cache"
"""Trình duyệt giữ bản sao nhưng luôn hỏi lại (`If-None-Match`); `private` để proxy chung không giữ."""


def etag_matches(if_none_match: str | None, etag: str) -> bool:
    """`If-None-Match` có khớp `etag` theo so sánh yếu (RFC 9110 §13.1.2) hay `*`."""
    if not if_none_match:
        return False
    bare = etag.removeprefix("W/")
    for tag in if_none_match.split(","):
        candidate = tag.strip()
        if candidate == "*" or candidate.removeprefix("W/") == bare:
            return True
    return False


def cached_json(request: Request, model: BaseModel) -> Response:
    """Thân JSON của `model` (`by_alias`, như FastAPI) với `ETag`; 304 không thân khi khớp."""
    body = model.model_dump_json(by_alias=True).encode()
    etag = f'W/"{blake2b(body, digest_size=16).hexdigest()}"'
    headers = {"ETag": etag, "Cache-Control": CACHE_CONTROL}
    if etag_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)
