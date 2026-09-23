"""Nạp PNG/JPEG thành `RgbImage` chuẩn hoá, và mã hoá ngược ra PNG.

Trần điểm ảnh kiểm **trước** `load()` bằng `w x h` đọc từ đầu tệp (K13, BE-00 §11):
đó là điểm duy nhất chặn được bom nén mà không tốn bộ nhớ. Không gán
`Image.MAX_IMAGE_PIXELS` hay `ImageFile.LOAD_TRUNCATED_IMAGES` — đó là biến toàn
cục của cả tiến trình, không an toàn luồng. Mọi biến đổi làm bằng numpy/Pillow,
không vòng lặp Python theo điểm ảnh (K28).
"""

import io
import math
from typing import Final

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps

from packages.vision.preprocess.errors import VisionError
from packages.vision.preprocess.sniff import sniff_kind
from packages.vision.preprocess.types import DEFAULT_MAX_PIXELS, RgbImage

_PIL_FORMATS: Final[dict[str, str]] = {"png": "PNG", "jpeg": "JPEG"}

# JPEG giải mã được ở 1/2 hay 1/4 kích thước ngay trong bộ giải DCT, nên ảnh tới
# 4 lần trần vẫn nạp được mà không bao giờ dựng mảng vượt trần. PNG không có cơ
# chế tương đương: vượt trần là hỏng.
_MAX_DRAFT_SCALE: Final = 4

_GRAY16_MODES: Final = frozenset(("I", "I;16", "I;16B", "I;16L"))
_WHITE: Final = (255, 255, 255)


def _draft_down(image: Image.Image, max_pixels: int) -> None:
    """Xin bộ giải JPEG trả ảnh nhỏ hơn khi `w x h` nằm trong `(trần, 4 x trần]`.

    Pillow chọn hệ số theo **phép chia nguyên**, nên truyền `(w // s, h // s)` với
    `s` nhỏ nhất đưa `ceil(w/s) x ceil(h/s)` về dưới trần; kích thước thật đọc lại
    từ `image.size` vì bộ giải làm tròn lên. Không cần kiểm `s = 4`: trong dải này
    `w x h <= 4 x trần` nên `ceil(w/4) x ceil(h/4)` luôn lọt (chỉ hụt với ảnh cạnh
    dưới 3 px, tức trần dưới 9 điểm ảnh — không phải khổ ảnh thật nào).
    """
    width, height = image.size
    if not max_pixels < width * height <= _MAX_DRAFT_SCALE * max_pixels:
        return
    scale = 2 if math.ceil(width / 2) * math.ceil(height / 2) <= max_pixels else _MAX_DRAFT_SCALE
    image.draft("RGB", (width // scale, height // scale))


def _open_within_limit(buffer: io.BytesIO, pil_format: str, max_pixels: int) -> Image.Image:
    """Mở tệp, hạ cỡ JPEG nếu được, rồi chặn ảnh vượt trần **trước** khi giải mã (U03).

    `DecompressionBombError` của Pillow (ảnh khai lớn hơn hai lần trần mặc định của
    nó) cũng là "ảnh quá lớn". `Image.open` đã đọc phần đầu tệp nên chính nó ném
    `UnidentifiedImageError` (chữ ký sai) hay `OSError("Truncated File Read")`
    (JPEG cụt giữa bảng marker) — cả hai là tệp hỏng (U07).
    """
    try:
        image = Image.open(buffer, formats=[pil_format])
    except Image.DecompressionBombError as exc:
        raise VisionError("IMAGE_TOO_LARGE") from exc
    except OSError as exc:  # `UnidentifiedImageError` là lớp con của `OSError`
        raise VisionError("FILE_CORRUPT") from exc
    if pil_format == "JPEG":
        _draft_down(image, max_pixels)
    width, height = image.size
    if width * height > max_pixels:
        raise VisionError("IMAGE_TOO_LARGE")
    return image


def _over_white(image: Image.Image) -> Image.Image:
    """Ghép ảnh có alpha lên nền **trắng** — nền bản vẽ là giấy, ghép lên đen làm đảo nét."""
    rgba = image.convert("RGBA")
    canvas = Image.new("RGB", rgba.size, _WHITE)
    canvas.paste(rgba, mask=rgba.getchannel("A"))
    return canvas


def _has_alpha(image: Image.Image) -> bool:
    """Ảnh mang kênh trong suốt, kể cả bảng màu `P` khai `transparency`."""
    return image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)


def _to_rgb_array(image: Image.Image) -> NDArray[np.uint8]:
    """Chuẩn hoá mọi mode Pillow về mảng RGB 8-bit (U02), bỏ mọi metadata.

    Xám 16-bit chia theo dải 16-bit (`>> 8`) chứ không cắt ở 255: cắt biến mọi
    điểm sáng hơn 255 thành trắng, mất hết nét của ảnh quét 16-bit.
    """
    if image.mode in _GRAY16_MODES:
        gray = (np.asarray(image, dtype=np.uint32) >> 8).astype(np.uint8)
        return np.repeat(gray[:, :, np.newaxis], 3, axis=2)
    if _has_alpha(image):
        image = _over_white(image)
    return np.asarray(image.convert("RGB"), dtype=np.uint8)


def load_raster(data: bytes, *, max_pixels: int = DEFAULT_MAX_PIXELS) -> RgbImage:
    """PNG/JPEG → `RgbImage` đã áp EXIF orientation và chuẩn hoá về RGB 8-bit.

    Định dạng lấy từ `sniff_kind` và truyền thẳng cho Pillow (`formats=[...]`) để
    một tệp không bao giờ được thử bằng bộ giải của định dạng khác (K14). Loại
    khác PNG/JPEG → `FILE_TYPE_MISMATCH`; vượt trần → `IMAGE_TOO_LARGE`; tệp cụt
    hay hỏng chunk → `FILE_CORRUPT` (U07). EXIF không đọc được thì Pillow trả thẻ
    rỗng, coi như orientation 1 — không phải lỗi dữ liệu (U01).
    """
    pil_format = _PIL_FORMATS.get(sniff_kind(data))
    if pil_format is None:
        raise VisionError("FILE_TYPE_MISMATCH")
    with io.BytesIO(data) as buffer:
        image = _open_within_limit(buffer, pil_format, max_pixels)
        try:
            image.load()
        except OSError as exc:
            # PNG cụt → "image file is truncated"; PNG sai CRC → "broken data stream";
            # JPEG cụt → "Truncated File Read". Pillow ném cả ba dưới dạng `OSError`.
            raise VisionError("FILE_CORRUPT") from exc
        return RgbImage(np.ascontiguousarray(_to_rgb_array(ImageOps.exif_transpose(image) or image)))


def encode_png(img: RgbImage, *, compress_level: int = 1) -> bytes:
    """`RgbImage` → byte PNG **không** chunk metadata (`eXIf`, `tEXt`).

    `compress_level=1` là mặc định vì ảnh trang đi vào kho object rồi bị đọc lại
    ngay; đổi lên 6+ tốn CPU gấp nhiều lần mà chỉ bớt vài phần trăm dung lượng.
    """
    buffer = io.BytesIO()
    Image.fromarray(np.array(img.pixels), mode="RGB").save(buffer, format="PNG", compress_level=compress_level)
    return buffer.getvalue()
