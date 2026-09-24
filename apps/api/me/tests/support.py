"""Tiện ích dùng chung của test `apps/api/me` (không phải file test, pytest không thu thập).

Mẫu `apps/api/auth_recovery/tests/support.py` (R-07): gom dựng `Principal`/phiên thật và
dựng ảnh mẫu bằng Pillow — từng bị lặp giữa các file test của module này.
"""

import base64
import io
import random
from datetime import timedelta
from typing import Final, cast
from uuid import uuid4

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.auth import Principal, Role, fake_token
from packages.core.clock import Clock
from packages.db.models.auth import RefreshSession, User

IDLE: Final = timedelta(hours=12)
ABSOLUTE: Final = timedelta(hours=24)


def principal_of(user: User, *, session_id: str = "sid-thu-nghiem") -> Principal:
    """`Principal` khớp một `User` đã tạo, không đòi phiên thật trong `refresh_sessions`."""
    return Principal(user_id=user.id, session_id=session_id, role=cast("Role", user.role))


def headers_of(principal: Principal) -> dict[str, str]:
    """Header `Authorization: Bearer` mà `FakeTokenVerifier` nhận cho một `Principal`."""
    return {"Authorization": f"Bearer {fake_token(principal)}"}


async def seed_session(db: AsyncSession, user: User, clock: Clock) -> Principal:
    """`Principal` cùng một dòng `refresh_sessions` thật, sống — N13 cần `FOR SHARE` khớp `sid`."""
    sid = uuid4()
    now = clock.now()
    db.add(
        RefreshSession(
            id=sid,
            user_id=user.id,
            current_token_hash="0" * 64,
            remember=False,
            idle_expires_at=now + IDLE,
            absolute_expires_at=now + ABSOLUTE,
        )
    )
    await db.commit()
    return principal_of(user, session_id=str(sid))


def png_bytes(size: tuple[int, int] = (64, 64), mode: str = "RGB", color: str = "red") -> bytes:
    """PNG hợp lệ, không EXIF, kích thước tuỳ ý — dựng bằng Pillow, không commit tệp nhị phân."""
    buffer = io.BytesIO()
    Image.new(mode, size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def jpeg_bytes(size: tuple[int, int] = (64, 64), color: str = "blue") -> bytes:
    """JPEG hợp lệ RGB, không EXIF."""
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG")
    return buffer.getvalue()


def jpeg_with_exif_orientation(size: tuple[int, int] = (40, 20)) -> bytes:
    """JPEG rộng hơn cao, gắn EXIF `Orientation=6` (xoay 90°) — kiểm `exif_transpose` (U01)."""
    img = Image.new("RGB", size, "green")
    exif = img.getexif()
    exif[0x0112] = 6  # Orientation
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


FAKE_ICC_PROFILE: Final = b"appback-test-khong-phai-icc-that-01" * 4
"""Chuỗi byte giả — Pillow chỉ nhúng nguyên văn vào `iCCP`/APP2, không kiểm nội dung ICC thật."""


def png_with_icc_bytes(size: tuple[int, int] = (64, 64), color: str = "red") -> bytes:
    """PNG có `icc_profile` gắn kèm — kiểm mã hoá lại xoá sạch metadata (NO-166)."""
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG", icc_profile=FAKE_ICC_PROFILE)
    return buffer.getvalue()


def jpeg_with_icc_and_exif_bytes(size: tuple[int, int] = (64, 64), color: str = "blue") -> bytes:
    """JPEG có cả `icc_profile` và EXIF — kiểm mã hoá lại xoá sạch cả hai (NO-166)."""
    img = Image.new("RGB", size, color)
    exif = img.getexif()
    exif[0x0112] = 1  # Orientation bình thường, chỉ để có khối EXIF không rỗng
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", icc_profile=FAKE_ICC_PROFILE, exif=exif)
    return buffer.getvalue()


def png_16bit_bytes(size: tuple[int, int] = (4096, 4096), value: int = 1000) -> bytes:
    """PNG xám 16-bit (`mode="I;16"`), một giá trị đồng nhất nên nén cực nhanh dù kích thước lớn."""
    buffer = io.BytesIO()
    Image.new("I;16", size, value).save(buffer, format="PNG")
    return buffer.getvalue()


def noisy_jpeg_bytes(size: tuple[int, int] = (64, 64), seed: int = 1) -> bytes:
    """JPEG nhiễu ngẫu nhiên (không nén tốt như ảnh một màu) — đủ dài để cắt cụt **sau** phần đầu.

    `random.Random(seed)`: dữ liệu tất định (# noqa: S311 — không phải mật mã, chỉ để test)."""
    rng = random.Random(seed)  # noqa: S311 — dữ liệu tất định cho test, không phải bảo mật
    img = Image.new("RGB", size)
    pixels = img.load()
    assert pixels is not None
    for y in range(size[1]):
        for x in range(size[0]):
            pixels[x, y] = (rng.randrange(256), rng.randrange(256), rng.randrange(256))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def b64(data: bytes) -> str:
    """Base64 chuẩn (không URL-safe) — đúng dạng `contentBase64` của N14."""
    return base64.b64encode(data).decode("ascii")
