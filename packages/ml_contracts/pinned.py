"""Trọng số nhà cung cấp ghim SHA-256 (BE-00 §9 "nhà cung cấp", K12, M03) và lệnh tải chúng.

Mỗi bản ghim trỏ URL `https://` cố định theo tag hay commit; SHA-256 là số **đo thật**
trên tệp đã tải (không mạng thì để `UNPINNED` và ghi nợ, không bịa). Ảnh `ml` tải lúc
build bằng `python -m packages.ml_contracts.pinned fetch --dest DIR` rồi xuất ONNX bằng
`python -m apps.ml.runtime.export_pinned` — lúc chạy, `ml` không ra mạng.

**Chỉ thư viện chuẩn**: lệnh tải chạy trước khi ảnh có numpy/pydantic. Tệp của bản
`<name>` nằm ở `DIR/<name>/<tệp>`; ONNX đã xuất ở `DIR/<name>.onnx`.
Đổi `onnx_sha256` của bản gốc là đổi `checksum` bản gốc do B6-01 seed: phải kèm revision.
"""

import argparse
import hashlib
import http.client
import logging
import os
import sys
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Final, Protocol
from urllib.parse import urlsplit

from packages.ml_contracts.families import ModelFamily

_log: Final = logging.getLogger(__name__)

UNPINNED: Final = "0" * 64
"""SHA-256 của bản chưa đo được; `fetch` và `export_pinned` gặp nó thì thoát 2."""

FETCH_MAX_BYTES: Final = 600 * 1024 * 1024
FETCH_TIMEOUT_S: Final = 60.0
EXIT_MISMATCH: Final = 2
EXIT_IO: Final = 3
_CHUNK_BYTES: Final = 1024 * 1024
_PART_SUFFIX: Final = ".part"


@dataclass(frozen=True, slots=True)
class PinnedFile:
    """Một tệp tải về: tên trong `DIR/<name>/`, URL cố định, SHA-256 đã đo."""

    filename: str
    url: str
    sha256: str


@dataclass(frozen=True, slots=True)
class PinnedWeights:
    """Một bản ghim. `source_url` rỗng = tệp nguồn đi kèm wheel đã khoá (không tải).

    `onnx_sha256` là SHA của ONNX đã xuất ở `DIR/<name>.onnx`; `None` khi bản này không
    xuất ONNX (SegFormer: B6-04a nạp safetensors để huấn luyện, BE-00 §9).
    """

    name: str
    family: ModelFamily
    source_url: str
    source_sha256: str
    onnx_sha256: str | None
    license: str
    extra_files: tuple[PinnedFile, ...] = ()

    @property
    def files(self) -> tuple[PinnedFile, ...]:
        """Tệp `fetch` phải có: nguồn (tên = đoạn cuối URL) rồi tệp kèm."""
        if not self.source_url:
            return self.extra_files
        name = PurePosixPath(urlsplit(self.source_url).path).name
        return (PinnedFile(name, self.source_url, self.source_sha256), *self.extra_files)


_YOLO_TAG: Final = "https://github.com/ultralytics/assets/releases/download/v8.3.0"
_MIT_B0: Final = "https://huggingface.co/nvidia/mit-b0/resolve/25ce79d97e6d9d509ed12e17cb2eb89b0a83a2dc"
_MIT_B1: Final = "https://huggingface.co/nvidia/mit-b1/resolve/44575a0572f5374ed1e5b4e46ec8276222f6ffe8"

PINNED: Final[Mapping[str, PinnedWeights]] = MappingProxyType(
    {
        "mitB0": PinnedWeights(
            name="mitB0",
            family="wallSegmentation",
            source_url=f"{_MIT_B0}/model.safetensors",
            source_sha256="3e5ad9cd1dd8ecf8305c23fcdf01ef241f08c7b2dddacb6ec7de5a887188798a",
            onnx_sha256=None,
            license="other",
            extra_files=(
                PinnedFile(
                    "config.json",
                    f"{_MIT_B0}/config.json",
                    "e2378ac7c7a6981d6bdd1d9ccf29b611264c382afce89c561f39c9291164ff91",
                ),
            ),
        ),
        "mitB1": PinnedWeights(
            name="mitB1",
            family="wallSegmentation",
            source_url=f"{_MIT_B1}/model.safetensors",
            source_sha256="4c19537dff32bbaa876174c371759ac1046c980bbf8096273bb03261429bdce1",
            onnx_sha256=None,
            license="other",
            extra_files=(
                PinnedFile(
                    "config.json",
                    f"{_MIT_B1}/config.json",
                    "8fd62155be0484e51dbdbc7d240c407d8d355e72a739bde0339a89a3416e6eb1",
                ),
            ),
        ),
        "yolov8n": PinnedWeights(
            name="yolov8n",
            family="openingAndFurnitureDetection",
            source_url=f"{_YOLO_TAG}/yolov8n.pt",
            source_sha256="f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36",
            onnx_sha256="1e252b7363e1936a0f06a40c221f144f65e86ae8ef01c96e71f7fb33cc3a334d",
            license="AGPL-3.0",
        ),
        "yolov8s": PinnedWeights(
            name="yolov8s",
            family="openingAndFurnitureDetection",
            source_url=f"{_YOLO_TAG}/yolov8s.pt",
            source_sha256="1f47a78bf100391c2a140b7ac73a1caae18c32779be7d310658112f7ac9aa78a",
            onnx_sha256="c1a1267211199d1e44a9176d81b202ffe46f396bbfc1cba63e993fc5bd8d72ea",
            license="AGPL-3.0",
        ),
        "rapidocrRec": PinnedWeights(
            name="rapidocrRec",
            family="dimensionReading",
            source_url="",
            source_sha256="48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b",
            onnx_sha256="48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b",
            license="Apache-2.0",
        ),
    }
)

BASELINE: Final[Mapping[ModelFamily, str]] = MappingProxyType(
    {"openingAndFurnitureDetection": "yolov8n", "dimensionReading": "rapidocrRec"}
)
"""Bản gốc B6-01 seed theo họ; `wallSegmentation` không có (đường lùi cổ điển, BE-00 §9)."""


class FetchError(Exception):
    """Tải bản ghim hỏng; `exit_code` là mã thoát CLI (2 lệch hay chưa ghim, 3 mạng/IO)."""

    def __init__(self, exit_code: int, reason: str) -> None:
        super().__init__(reason)
        self.exit_code: Final = exit_code


class Readable(Protocol):
    """Phần của phản hồi HTTP mà `fetch` dùng: đọc theo khúc."""

    def read(self, size: int, /) -> bytes: ...


type Opener = Callable[[str], AbstractContextManager[Readable]]


def open_https(url: str) -> AbstractContextManager[Readable]:
    """Mở URL ghim với trần thời gian tường minh (R-24); chỉ nhận `https://`."""
    if not url.startswith("https://"):
        raise ValueError(f"bản ghim chỉ tải qua https: {url!r}")
    response: AbstractContextManager[Readable] = urllib.request.urlopen(  # noqa: S310 — URL https cố định trong PINNED
        url, timeout=FETCH_TIMEOUT_S
    )
    return response


def file_sha256(path: Path) -> str:
    """SHA-256 của tệp, đọc theo khúc (R-22)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, part: Path, opener: Opener) -> str:
    """Luồng vào `part`, băm khi đọc; vượt `FETCH_MAX_BYTES` → trả `""` (coi như lệch)."""
    digest = hashlib.sha256()
    size = 0
    with opener(url) as response, part.open("wb") as out:
        while chunk := response.read(_CHUNK_BYTES):
            size += len(chunk)
            if size > FETCH_MAX_BYTES:
                return ""
            digest.update(chunk)
            out.write(chunk)
    return digest.hexdigest()


def _fetch_file(target: Path, pin: PinnedFile, opener: Opener) -> None:
    """Một tệp: có sẵn đúng SHA thì không mở mạng; lệch → xoá, thoát 2; mạng/IO → thoát 3."""
    if target.is_file() and file_sha256(target) == pin.sha256:
        return
    part = target.with_name(target.name + _PART_SUFFIX)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = _download(pin.url, part, opener)
    except (OSError, http.client.HTTPException) as exc:
        part.unlink(missing_ok=True)
        raise FetchError(EXIT_IO, f"không tải được {pin.url}: {type(exc).__name__}") from exc
    if digest != pin.sha256:
        part.unlink()
        raise FetchError(EXIT_MISMATCH, f"SHA-256 lệch bản ghim: {pin.url}")
    os.replace(part, target)


def fetch(dest: Path, *, opener: Opener = open_https, pinned: Mapping[str, PinnedWeights] = PINNED) -> None:
    """Tải mọi tệp ghim vào `dest/<name>/`; bản nào còn `UNPINNED` thì dừng trước khi tải gì.

    Ném `FetchError`; tệp dở `.part` luôn bị xoá. Chạy lại an toàn: tệp đã đúng SHA
    không tải lại.
    """
    unpinned = sorted(weights.name for weights in pinned.values() if any(f.sha256 == UNPINNED for f in weights.files))
    if unpinned:
        raise FetchError(EXIT_MISMATCH, f"chưa ghim: {', '.join(unpinned)}")
    for weights in pinned.values():
        for pin in weights.files:
            _fetch_file(dest / weights.name / pin.filename, pin, opener)


def main(argv: Sequence[str] | None = None) -> int:
    """`python -m packages.ml_contracts.pinned fetch --dest DIR` → mã thoát 0/2/3."""
    parser = argparse.ArgumentParser(prog="python -m packages.ml_contracts.pinned")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fetch").add_argument("--dest", type=Path, required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        fetch(args.dest)
    except FetchError as exc:
        _log.error("pinned_fetch_failed: %s", exc)
        return exc.exit_code
    _log.info("pinned_fetch_done: %s", args.dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
