"""Nhập `ultralytics` mà không để lại bản vá `PIL.Image.open` toàn tiến trình (FIX-116, NO-322).

`ultralytics` 8.4.155 gán đè `PIL.Image.open` bằng `ultralytics.utils.patches.image_open`
**ngay lúc nhập package**. Bản bọc đó bắt mọi lỗi của `open` gốc (`except Exception`) rồi
`from pi_heif import register_heif_opener`; `pi_heif` không nằm trong `uv.lock`, nên mọi lỗi
thật — `DecompressionBombError`, `UnidentifiedImageError`, `OSError` — biến thành
`ModuleNotFoundError`. `packages.vision.preprocess.raster._open_within_limit` bắt đúng hai lớp
đó để ra `VisionError`, nên sau một lượt nhập `ultralytics` trần thì mọi `load_raster` trong
**cùng tiến trình** ném `ModuleNotFoundError` thay cho `IMAGE_TOO_LARGE`/`FILE_CORRUPT`.

Mọi đường nhập `ultralytics` của repo đi qua `import_ultralytics()` (B5-01 `export_yolo`,
B6-04b `prepare_ultralytics`, và test). Bất biến: **sau khi hàm trả về, `PIL.Image.open` là
bản của Pillow**. Hệ quả: HEIF không bao giờ được đăng ký — ta chỉ nhận PNG/JPEG qua
`sniff_kind`, nên không mất gì.

`ultralytics` còn gán `torch.save = ultralytics.utils.patches.torch_save`
(`ultralytics/utils/__init__.py`): không đường nào của ta đi qua `torch.save`, để nguyên.
"""

from typing import Any, Final

_PILLOW_MODULE: Final = "PIL.Image"


def _pillow_image_open() -> Any:
    """Bản `Image.open` gốc mà `ultralytics` giữ lại khi vá.

    ponytail: bám tên riêng `ultralytics.utils.patches._image_open` của bản 8.4.155 (ghim trong
    `uv.lock`); test `test_ultralytics_import.py` khoá tên này, đổi bản mà tên đổi thì test đỏ.
    """
    from ultralytics.utils import patches

    # Tên riêng là điểm neo duy nhất của bản `Image.open` gốc; không có API công khai.
    return patches._image_open


def import_ultralytics() -> None:
    """Nhập `ultralytics` rồi trả `PIL.Image.open` về bản của Pillow. Gọi bao nhiêu lần cũng được.

    `PIL.Image.open` lúc vào hàm còn là của Pillow → lưu rồi đặt lại trong `finally` (kể cả khi
    lượt nhập hỏng). Đã bị vá sẵn (ai đó nhập `ultralytics` trần trước) → lấy lại bản gốc từ
    `ultralytics.utils.patches._image_open`.
    """
    import PIL.Image

    saved = PIL.Image.open
    try:
        import ultralytics  # noqa: F401 — chỉ cần tác dụng phụ: nạp package vào `sys.modules`
    finally:
        PIL.Image.open = saved if saved.__module__ == _PILLOW_MODULE else _pillow_image_open()
