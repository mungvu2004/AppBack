"""`GET /api/files/{token}` — token là quyền, mọi thất bại là cùng một 404 (BE-00 §8)."""

from pathlib import Path
from typing import Final

import httpx
import pytest
from fastapi import FastAPI

from apps.api.files.router import CACHE_CONTROL
from packages.storage.local import LocalDiskStorage
from packages.testing.fixtures.clock import FakeClock

PNG: Final = b"\x89PNG\r\n\x1a\n" + b"0" * 64
PDF: Final = b"%PDF-1.7\n" + b"0" * 64
AVATAR_KEY: Final = "users/usr_01JABCDEFGHJKMNPQRSTVWXYZ0/avatar/01JABCDEFGHJKMNPQRSTVWXYZ0.png"
DOC_KEY: Final = "library/tai-lieu/ho-so.pdf"


def _token_of(url: str) -> str:
    """Phần token trong URL ký của `LocalDiskStorage`."""
    return url.rsplit("/", 1)[-1]


async def _put(app: FastAPI, key: str, data: bytes, content_type: str) -> None:
    """Ghi một object qua kho của app thử."""
    await app.state.storage.put(key, data, content_type=content_type, max_bytes=len(data) + 1)


async def test_files_read_object_streams_attachment(api_app: FastAPI, api_client: httpx.AsyncClient) -> None:
    """Tệp thường: `attachment` + `Content-Type` đã lưu + `Cache-Control` riêng (BE-00 §8)."""
    await _put(api_app, DOC_KEY, PDF, "application/pdf")
    signed = await api_app.state.storage.signed_url(DOC_KEY, disposition="attachment", filename="ho so.pdf")

    response = await api_client.get(f"/api/files/{_token_of(signed.url)}")
    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["cache-control"] == CACHE_CONTROL
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_inline_only_for_checked_images(api_app: FastAPI, api_client: httpx.AsyncClient) -> None:
    """K15: `inline` chỉ khi token ghi `inline` **và** magic bytes nói PNG/JPEG."""
    await _put(api_app, AVATAR_KEY, PNG, "image/png")
    signed = await api_app.state.storage.signed_url(AVATAR_KEY, disposition="inline", kind="png")

    response = await api_client.get(f"/api/files/{_token_of(signed.url)}")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == "inline"
    assert response.headers["content-type"] == "image/png"


async def test_inline_token_on_non_image_falls_back_to_attachment(
    api_app: FastAPI, api_client: httpx.AsyncClient, fake_clock: FakeClock
) -> None:
    """Token ghi `inline` nhưng nội dung là PDF → vẫn buộc tải về (K15)."""
    storage = api_app.state.storage
    assert isinstance(storage, LocalDiskStorage)
    await _put(api_app, DOC_KEY, PDF, "application/pdf")
    # Ký thẳng với `disposition="inline"`: `signed_url` từ chối, nên dựng token qua khoá ảnh.
    await _put(api_app, AVATAR_KEY, PDF, "application/pdf")
    signed = await storage.signed_url(AVATAR_KEY, disposition="inline", kind="png")

    response = await api_client.get(f"/api/files/{_token_of(signed.url)}")
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment")


@pytest.mark.parametrize(
    "token",
    ["khong-phai-token", "a.b", "", "x" * 200],
    ids=["rác", "base64 hỏng", "rỗng", "dài"],
)
async def test_bad_token_is_404(api_client: httpx.AsyncClient, token: str) -> None:
    """Token hỏng, giả mạo hay hết hạn đều trả cùng một 404, không nói lý do."""
    response = await api_client.get(f"/api/files/{token}")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


async def test_missing_object_is_404(api_app: FastAPI, api_client: httpx.AsyncClient) -> None:
    """Token đúng chữ ký mà object đã bị xoá → 404."""
    await _put(api_app, DOC_KEY, PDF, "application/pdf")
    signed = await api_app.state.storage.signed_url(DOC_KEY, disposition="attachment")
    await api_app.state.storage.delete(DOC_KEY)

    response = await api_client.get(f"/api/files/{_token_of(signed.url)}")
    assert response.status_code == 404


async def test_s3_backend_has_no_file_endpoint(api_app: FastAPI, api_client: httpx.AsyncClient, tmp_path: Path) -> None:
    """Backend S3 ký URL trỏ thẳng kho: endpoint này không tồn tại về nghiệp vụ."""
    await _put(api_app, DOC_KEY, PDF, "application/pdf")
    signed = await api_app.state.storage.signed_url(DOC_KEY, disposition="attachment")
    api_app.state.storage = object()

    response = await api_client.get(f"/api/files/{_token_of(signed.url)}")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


async def test_expired_token_is_404(api_app: FastAPI, api_client: httpx.AsyncClient, fake_clock: FakeClock) -> None:
    """Hạn ký hết → 404 (đồng hồ tiêm được nên không phải chờ thật)."""
    from datetime import timedelta

    await _put(api_app, DOC_KEY, PDF, "application/pdf")
    signed = await api_app.state.storage.signed_url(DOC_KEY, disposition="attachment")
    fake_clock.advance(timedelta(days=1))

    response = await api_client.get(f"/api/files/{_token_of(signed.url)}")
    assert response.status_code == 404
