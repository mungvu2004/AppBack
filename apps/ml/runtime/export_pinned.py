"""Xuất ONNX của bản ghim lúc build ảnh `ml`: `python -m apps.ml.runtime.export_pinned --dest DIR`.

Chạy sau `python -m packages.ml_contracts.pinned fetch --dest DIR`. Mỗi bản có ONNX ghi
`DIR/<name>.onnx` rồi so với `onnx_sha256`: YOLO qua `export_yolo` (so lại SHA nguồn trước),
`rapidocrRec` chép **nguyên** ONNX nhận dạng trong wheel `rapidocr_onnxruntime` (giữ
`metadata_props` `character` cho B5-04); SegFormer không xuất (B6-04a nạp safetensors).
Mã thoát như `fetch`: 2 = lệch hay chưa ghim (tệp lệch bị xoá), 3 = thiếu tệp/IO.
"""

import argparse
import importlib.util
import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Final

from apps.ml.runtime.export import write_atomic
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.pinned import (
    EXIT_IO,
    EXIT_MISMATCH,
    PINNED,
    UNPINNED,
    FetchError,
    PinnedWeights,
    file_sha256,
)

_log: Final = logging.getLogger(__name__)

WHEEL_FILES: Final[Mapping[str, tuple[str, str]]] = {
    "rapidocrRec": ("rapidocr_onnxruntime", "models/ch_PP-OCRv4_rec_infer.onnx"),
}
"""Bản ghim có nguồn nằm sẵn trong wheel đã khoá: (gói, đường trong gói)."""

type Exporter = Callable[..., str]


def wheel_file(name: str) -> Path:
    """Đường tệp nguồn của bản ghim trong wheel, tìm **không** nhập gói (nhập nó kéo onnxruntime, cv2)."""
    package, relative = WHEEL_FILES[name]
    spec = importlib.util.find_spec(package)
    if spec is None or not spec.submodule_search_locations:
        raise FileNotFoundError(f"không tìm thấy gói {package}")
    return Path(spec.submodule_search_locations[0]) / relative


def _yolo_exporter() -> Exporter:
    """`export_yolo` nhập lười: module đó kéo torch, CLI chỉ cần nó khi có bản YOLO."""
    from apps.ml.runtime.export_yolo import export_yolo

    return export_yolo


def _export_one(weights: PinnedWeights, dest: Path, exporter: Exporter | None) -> str:
    """Ghi `dest/<name>.onnx`, trả SHA-256; SHA nguồn lệch → thoát 2, thiếu tệp → thoát 3."""
    out = dest / f"{weights.name}.onnx"
    try:
        if weights.source_url:
            source = dest / weights.name / weights.files[0].filename
            return (exporter or _yolo_exporter())(source, out, source_sha256=weights.source_sha256)
        bundled = wheel_file(weights.name)
        if file_sha256(bundled) != weights.source_sha256:
            raise FetchError(EXIT_MISMATCH, f"SHA-256 nguồn lệch bản ghim: {weights.name}")
        return write_atomic(out, bundled.read_bytes())
    except PermanentError as exc:
        raise FetchError(EXIT_MISMATCH, f"SHA-256 nguồn lệch bản ghim: {weights.name}") from exc
    except OSError as exc:
        raise FetchError(EXIT_IO, f"thiếu tệp nguồn của {weights.name}: {type(exc).__name__}") from exc


def export_all(
    dest: Path, *, pinned: Mapping[str, PinnedWeights] = PINNED, exporter: Exporter | None = None
) -> dict[str, str]:
    """Xuất mọi bản có `onnx_sha256`; trả `{name: sha}`. Ném `FetchError` (xoá ONNX lệch)."""
    unpinned = sorted(
        weights.name
        for weights in pinned.values()
        if UNPINNED in (weights.source_sha256, weights.onnx_sha256, *(pin.sha256 for pin in weights.files))
    )
    if unpinned:
        raise FetchError(EXIT_MISMATCH, f"chưa ghim: {', '.join(unpinned)}")
    digests: dict[str, str] = {}
    for weights in pinned.values():
        if weights.onnx_sha256 is None:
            continue
        digest = _export_one(weights, dest, exporter)
        if digest != weights.onnx_sha256:
            (dest / f"{weights.name}.onnx").unlink()
            raise FetchError(EXIT_MISMATCH, f"ONNX của {weights.name} lệch bản ghim: {digest}")
        digests[weights.name] = digest
    return digests


def main(argv: Sequence[str] | None = None) -> int:
    """Điểm vào CLI; in SHA từng bản để đối chiếu giữa hai lượt build."""
    parser = argparse.ArgumentParser(prog="python -m apps.ml.runtime.export_pinned")
    parser.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        digests = export_all(args.dest)
    except FetchError as exc:
        _log.error("export_pinned_failed: %s", exc)
        return exc.exit_code
    for name, digest in digests.items():
        _log.info("export_pinned: %s %s", name, digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
