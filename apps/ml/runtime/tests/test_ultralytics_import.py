"""`import_ultralytics()` không để lại bản vá `PIL.Image.open` toàn tiến trình (FIX-116, NO-322).

Hai ca chính chạy trong **tiến trình con sạch**: một lượt `import ultralytics` là không thể hoàn
tác trong tiến trình test (package nằm lại `sys.modules`), nên chỉ tiến trình mới mới chứng minh
được bất biến. Tiến trình con không vào số độ phủ, nên các nhánh của hàm còn có test tại chỗ.

Dữ liệu ảnh dựng ở **tiến trình cha** rồi truyền xuống dưới dạng hex: nhúng byte thô vào mã nguồn
của tiến trình con là một lớp escape nữa, không đáng. Hai ca tại chỗ gọi `prepare_ultralytics()`
trước — cờ `YOLO_*` chỉ có tác dụng trước lần nhập `ultralytics` đầu tiên của tiến trình test.
"""

import io
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Final

import pytest
from PIL import Image

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
SUBPROCESS_TIMEOUT_S: Final = 300.0
BOMB_SIDE: Final = 50_000
_IHDR_DATA_OFFSET: Final = 16
"""Vị trí 4 byte width trong PNG: 8 byte chữ ký + 4 byte độ dài chunk + 4 byte `b"IHDR"`."""
_MARK: Final = "FIX116 "
"""Tiền tố mỗi dòng kết quả: `import ultralytics` in banner cấu hình ra stdout, phải lọc bỏ."""

_CHILD_PRELUDE: Final = '''
MARK = "FIX116 "


def say(value):
    """In một dòng kết quả có tiền tố, để tiến trình cha lọc khỏi banner của ultralytics."""
    print(MARK + str(value))


def vision_code(data):
    """Mã `VisionError` mà `load_raster` ném cho `data` (không ném là lỗi của ca kiểm)."""
    from packages.vision.preprocess.errors import VisionError
    from packages.vision.preprocess.raster import load_raster

    try:
        load_raster(data)
    except VisionError as exc:
        return exc.code
    raise AssertionError("load_raster khong nem VisionError")
'''


def _png_declaring(width: int, height: int) -> bytes:
    """PNG 4x4 thật nhưng IHDR khai `width`x`height` (CRC tính lại) → bom khai cỡ, byte vẫn ít.

    Phải là PNG **đủ chunk**: `Image.open` chỉ chạy `_decompression_bomb_check` sau khi plugin đọc
    xong tới `IDAT`, nên một tệp chỉ có IHDR hỏng ở chỗ khác (`FILE_CORRUPT`) chứ không ra bom.
    """
    data = bytearray(_real_png(4, 4))
    struct.pack_into(">II", data, _IHDR_DATA_OFFSET, width, height)
    chunk = bytes(data[_IHDR_DATA_OFFSET - 4 : _IHDR_DATA_OFFSET + 13])
    struct.pack_into(">I", data, _IHDR_DATA_OFFSET + 13, zlib.crc32(chunk))
    return bytes(data)


def _real_png(width: int, height: int) -> bytes:
    """PNG hợp lệ cỡ `width`x`height` do Pillow ghi (nguồn cho hai hàm dựng dữ liệu ca kiểm)."""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height)).save(buffer, format="PNG")
    return buffer.getvalue()


def _png_truncated() -> bytes:
    """PNG 4x4 thật bị cắt còn nửa đầu — mở được, `load()` ném `OSError` (U07)."""
    data = _real_png(4, 4)
    return data[: len(data) // 2]


def _run_child(body: str) -> list[str]:
    """Chạy `body` (đã có `vision_code`) trong tiến trình Python mới; trả các dòng stdout."""
    result = subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", _CHILD_PRELUDE + body],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=SUBPROCESS_TIMEOUT_S,
    )
    assert result.returncode == 0, result.stderr
    return [line[len(_MARK) :] for line in result.stdout.splitlines() if line.startswith(_MARK)]


def test_import_keeps_pillow_open_in_a_clean_process() -> None:
    """Tiến trình sạch: sau `import_ultralytics()`, `PIL.Image.open` là **đúng đối tượng** đã lưu.

    Ảnh bom và PNG cụt vẫn ra `IMAGE_TOO_LARGE`/`FILE_CORRUPT` chứ không `ModuleNotFoundError`
    (bản vá của ultralytics nuốt mọi lỗi rồi nhập `pi_heif`, thứ không có trong `uv.lock`).
    """
    bomb = _png_declaring(BOMB_SIDE, BOMB_SIDE).hex()
    cut = _png_truncated().hex()
    out = _run_child(
        f"""
import PIL.Image

from apps.ml.runtime.ultralytics_import import import_ultralytics

saved = PIL.Image.open
import_ultralytics()
say(PIL.Image.open is saved)
say(vision_code(bytes.fromhex({bomb!r})))
say(vision_code(bytes.fromhex({cut!r})))
"""
    )

    assert out == ["True", "IMAGE_TOO_LARGE", "FILE_CORRUPT"]


def test_import_repairs_an_already_patched_process() -> None:
    """`import ultralytics` trần trước → `import_ultralytics()` vẫn trả `PIL.Image.open` về Pillow."""
    bomb = _png_declaring(BOMB_SIDE, BOMB_SIDE).hex()
    out = _run_child(
        f"""
import ultralytics  # nhập trần: vá PIL.Image.open ngay tại đây
import PIL.Image

from apps.ml.runtime.ultralytics_import import import_ultralytics

say(PIL.Image.open.__module__)
import_ultralytics()
say(PIL.Image.open.__module__)
say(vision_code(bytes.fromhex({bomb!r})))
"""
    )

    assert out == ["ultralytics.utils.patches", "PIL.Image", "IMAGE_TOO_LARGE"]


def test_import_ultralytics_is_idempotent() -> None:
    """Gọi hai lần không lỗi và `PIL.Image.open` vẫn của Pillow (nhánh "chưa bị vá", tại chỗ)."""
    import PIL.Image

    from apps.ml.runtime.ultralytics_import import import_ultralytics
    from apps.ml.training_yolo.trainer import prepare_ultralytics

    prepare_ultralytics()  # cờ ngoại tuyến phải đặt trước lượt nhập đầu tiên của tiến trình test
    import_ultralytics()
    import_ultralytics()

    assert PIL.Image.open.__module__ == "PIL.Image"


def test_import_restores_from_the_ultralytics_copy() -> None:
    """Nhánh "đã bị vá": `PIL.Image.open` lạ → lấy lại bản gốc ultralytics giữ (`patches._image_open`)."""
    import PIL.Image

    from apps.ml.runtime.ultralytics_import import import_ultralytics
    from apps.ml.training_yolo.trainer import prepare_ultralytics

    def _foreign_open(*_args: object, **_kwargs: object) -> None:
        """Bản `open` giả mang `__module__` khác `PIL.Image` — đóng vai bản vá của ultralytics."""

    prepare_ultralytics()  # như trên; cũng bảo đảm `ultralytics.utils.patches` đã nạp
    from ultralytics.utils import patches

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(PIL.Image, "open", _foreign_open)
        import_ultralytics()
        assert PIL.Image.open is patches._image_open  # chính tên riêng mà hàm bám vào
        assert PIL.Image.open.__module__ == "PIL.Image"
