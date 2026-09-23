"""Dựng PDF và ảnh raster **trong bộ nhớ** cho test của `packages.vision.preprocess`.

Không commit tệp nhị phân (khối [9]): mọi mẫu thử sinh từ đây. PDF viết tay chứ
không qua thư viện vì test cần điều khiển chính xác `/Count`, `/Rotate`, khổ
trang và phần mã hoá RC4-40 — thứ không thư viện nào trong bảng khoá dựng được.
"""

import binascii
import hashlib
import io
import struct
import zlib
from collections.abc import Sequence
from typing import Final, Literal

from PIL import Image

Encryption = Literal["none", "owner_only", "user_password"]
Rect = tuple[float, float, float, float, tuple[float, float, float]]

A4_PT: Final = (595.0, 842.0)

# ISO 32000-1 bảng 3.2 — chuỗi đệm mật khẩu của bộ lọc Standard.
_PAD: Final = bytes.fromhex("28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A")
_KEY_BYTES: Final = 5  # V 1 / R 2 = RC4 40 bit
_PERMISSIONS: Final = -1
_FILE_ID: Final = b"AppBackVisionID!"
# (mật khẩu người dùng, mật khẩu chủ) cho từng kiểu mã hoá; rỗng nghĩa là không đặt.
_PASSWORDS: Final[dict[str, tuple[str, str]]] = {
    "none": ("", ""),
    "owner_only": ("", "owner-key"),
    "user_password": ("user-key", "owner-key"),
}
_PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"


def _md5(payload: bytes) -> bytes:
    """MD5 của thuật toán mã hoá PDF — thuật toán do ISO 32000-1 quy định, không phải lựa chọn."""
    return hashlib.md5(payload, usedforsecurity=False).digest()


def _rc4(key: bytes, data: bytes) -> bytes:
    """RC4 viết tay: không thư viện nào trong bảng khoá BE-00 §13.1 còn phơi nó ra."""
    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + key[i % len(key)]) % 256
        state[i], state[j] = state[j], state[i]
    out = bytearray(len(data))
    i = j = 0
    for index, byte in enumerate(data):
        i = (i + 1) % 256
        j = (j + state[i]) % 256
        state[i], state[j] = state[j], state[i]
        out[index] = byte ^ state[(state[i] + state[j]) % 256]
    return bytes(out)


def _pad_password(password: str) -> bytes:
    """Mật khẩu → 32 byte theo chuỗi đệm chuẩn (ISO 32000-1 thuật toán 2 bước a)."""
    raw = password.encode("latin-1")[:32]
    return raw + _PAD[: 32 - len(raw)]


def _standard_security(user: str, owner: str) -> tuple[bytes, bytes]:
    """`(khoá mã hoá, từ điển /Encrypt)` theo thuật toán 2-4 cho `R 2`."""
    owner_value = _rc4(_md5(_pad_password(owner))[:_KEY_BYTES], _pad_password(user))
    key = _md5(_pad_password(user) + owner_value + struct.pack("<i", _PERMISSIONS) + _FILE_ID)[:_KEY_BYTES]
    user_value = _rc4(key, _PAD)
    fields = (_hex(owner_value), _hex(user_value), _PERMISSIONS)
    return key, b"<</Filter/Standard/V 1/R 2/Length 40/O %s/U %s/P %d>>" % fields


def _object_key(key: bytes, number: int) -> bytes:
    """Khoá riêng của một đối tượng (thuật toán 1): khoá tệp + số hiệu + số thế hệ 0."""
    return _md5(key + number.to_bytes(3, "little") + b"\x00\x00")[: _KEY_BYTES + 5]


def _hex(data: bytes) -> bytes:
    """Chuỗi PDF dạng thập lục `<...>`."""
    return b"<" + binascii.hexlify(data) + b">"


def _number(value: float) -> bytes:
    """Số PDF không đuôi `.0` thừa (`595.0` → `595`, `4999.7` giữ nguyên)."""
    return f"{value:g}".encode("ascii")


def _content_stream(rects: Sequence[Rect]) -> bytes:
    """Nội dung trang: mỗi hình chữ nhật một lệnh `rg` + `re f`, toạ độ gốc dưới-trái."""
    parts = [
        b"%s %s %s rg %s %s %s %s re f\n"
        % (_number(r), _number(g), _number(b), _number(x), _number(y), _number(w), _number(h))
        for x, y, w, h, (r, g, b) in rects
    ]
    return b"".join(parts)


def _serialize(objects: Sequence[bytes], trailer_extra: bytes) -> bytes:
    """Ghép thân, bảng `xref` đúng offset và trailer; `startxref` trỏ vào `xref`."""
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % index + body + b"\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<</Size %d/Root 1 0 R/ID[%s %s]%s>>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        _hex(_FILE_ID),
        _hex(_FILE_ID),
        trailer_extra,
        xref_offset,
    )
    return bytes(out)


def make_pdf(
    pages: int,
    *,
    encrypt: Encryption = "none",
    rotate: int = 0,
    size: tuple[float, float] = A4_PT,
    rects: Sequence[Rect] = (),
) -> bytes:
    """PDF tối giản `pages` trang cùng khổ `size` (point), cùng `/Rotate`, cùng nội dung.

    `pages=0` cho `/Count 0` (tài liệu hợp lệ nhưng không trang). `encrypt` chọn
    bộ lọc Standard RC4-40: `owner_only` mở được bằng mật khẩu người dùng rỗng,
    `user_password` thì không. `rects` là `(x, y, rộng, cao, (r, g, b))` với màu
    trong `[0, 1]` và gốc toạ độ ở góc **dưới**-trái như PDF quy định.
    """
    key, encrypt_dict = (None, b"") if encrypt == "none" else _standard_security(*_PASSWORDS[encrypt])
    content = _content_stream(rects)
    width, height = size
    kids = b" ".join(b"%d 0 R" % (3 + i) for i in range(pages))
    objects = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[%s]/Count %d>>" % (kids, pages)]
    objects += [
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 %s %s]/Rotate %d/Contents %d 0 R/Resources<<>>>>"
        % (_number(width), _number(height), rotate, 3 + pages + i)
        for i in range(pages)
    ]
    for i in range(pages):
        payload = content if key is None else _rc4(_object_key(key, 3 + pages + i), content)
        objects.append(b"<</Length %d>>\nstream\n" % len(payload) + payload + b"\nendstream")
    if key is not None:
        objects.append(encrypt_dict)
        return _serialize(objects, b"/Encrypt %d 0 R" % len(objects))
    return _serialize(objects, b"")


def encode(image: Image.Image, image_format: str, **options: object) -> bytes:
    """Ảnh Pillow → byte của định dạng `image_format` (không chạm đĩa)."""
    buffer = io.BytesIO()
    image.save(buffer, format=image_format, **options)
    return buffer.getvalue()


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    """Một chunk PNG hoàn chỉnh: độ dài, tên, dữ liệu, CRC32."""
    return len(payload).to_bytes(4, "big") + kind + payload + binascii.crc32(kind + payload).to_bytes(4, "big")


def png_declaring(width: int, height: int) -> bytes:
    """PNG khai `width x height` ở IHDR nhưng chỉ có một IDAT vụn.

    Đủ để `Image.open` đọc ra kích thước mà không tốn bộ nhớ: dùng kiểm trần điểm
    ảnh phải chặn **trước** `load()` (U03).
    """
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunks = (_png_chunk(b"IHDR", ihdr), _png_chunk(b"IDAT", zlib.compress(b"\x00")), _png_chunk(b"IEND", b""))
    return _PNG_SIGNATURE + b"".join(chunks)


def corrupt_png_crc(data: bytes) -> bytes:
    """Lật một byte trong IDAT đầu tiên: độ dài giữ nguyên nên chỉ CRC và dữ liệu sai."""
    offset = data.index(b"IDAT") + 8
    return data[:offset] + bytes((data[offset] ^ 0xFF,)) + data[offset + 1 :]


def jpeg_with_orientation(width: int, height: int, orientation: int) -> bytes:
    """JPEG `width x height` có nửa trên đỏ, nửa dưới lam, kèm thẻ EXIF `Orientation`."""
    image = Image.new("RGB", (width, height), (0, 0, 255))
    image.paste(Image.new("RGB", (width, height // 2), (255, 0, 0)), (0, 0))
    exif = Image.Exif()
    exif[0x0112] = orientation
    return encode(image, "JPEG", exif=exif, quality=95)
