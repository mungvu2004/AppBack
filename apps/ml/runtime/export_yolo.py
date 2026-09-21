"""Xuất ONNX từ trọng số YOLO `.pt` (bản ghim lúc build; B6-04b dùng lại sau huấn luyện).

Một trong hai nơi duy nhất được nhập `ultralytics` (BE-00 §9; test AST khoá). `.pt` là
pickle: SHA-256 được so **trước** khi nhập `ultralytics`, nên tệp lạ không bao giờ tới
bộ giải pickle (K12). `ultralytics` chạy ngoại tuyến, cấu hình và thư mục làm việc
tạm; `YOLO_OFFLINE=1` không chặn được mạng, nên ảnh `ml` chạy trong mạng `internal`.
"""

import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from apps.ml.runtime.errors import MODEL_CHECKSUM_MISMATCH
from apps.ml.runtime.export import normalize_onnx, write_atomic
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.pinned import file_sha256

_OFFLINE_ENV: Final = {"YOLO_OFFLINE": "1", "YOLO_AUTOINSTALL": "false"}


@contextmanager
def _offline_env(config_dir: Path) -> Iterator[None]:
    """Cờ ngoại tuyến của BE-00 §9 và thư mục cấu hình tạm, trả lại giá trị cũ khi xong."""
    wanted = {**_OFFLINE_ENV, "YOLO_CONFIG_DIR": str(config_dir)}
    previous = {name: os.environ.get(name) for name in wanted}
    os.environ.update(wanted)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def export_yolo(
    pt_path: Path,
    out_path: Path,
    *,
    source_sha256: str,
    imgsz: int = 640,
    opset: int = 17,
    device: str = "cpu",
) -> str:
    """`.pt` đã ghim → ONNX chuẩn hoá ở `out_path`; trả SHA-256 của ONNX.

    SHA-256 của `.pt` khác `source_sha256` → `PermanentError(MODEL_CHECKSUM_MISMATCH)`,
    trước khi nhập `ultralytics`. Không `simplify`, không trục động: đầu ra tất định.
    """
    with tempfile.TemporaryDirectory() as workdir, _offline_env(Path(workdir) / "config"):
        work_pt = Path(workdir) / pt_path.name
        shutil.copyfile(pt_path, work_pt)
        # Băm **bản chép** — đúng byte sẽ được giải pickle, không phải tệp nguồn có thể bị thay.
        if file_sha256(work_pt) != source_sha256:
            raise PermanentError(MODEL_CHECKSUM_MISMATCH)
        # Nhập sau khi đã so SHA và đặt cờ ngoại tuyến: ultralytics đọc cấu hình lúc nhập.
        from ultralytics import YOLO  # type: ignore[attr-defined]  # ultralytics không khai __all__ cho YOLO

        exported = YOLO(str(work_pt)).export(
            format="onnx", opset=opset, imgsz=imgsz, simplify=False, dynamic=False, device=device
        )
        data = normalize_onnx(Path(exported).read_bytes())
    return write_atomic(out_path, data)
