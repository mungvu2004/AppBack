"""Blender giả cho test: chỉ thay ranh giới tiến trình con, mọi thứ khác của task chạy thật.

    python -m apps.worker.lighting_bake.tests.fake_blender --mode ok -- <in.glb> <out_dir> size samples cut_m

Môi trường của con bị lọc (không mang biến của test), nên chế độ đi qua argv `--mode`:
`ok` ghi ba tệp hợp lệ, `fail` thoát 1, `sleep` ngủ lâu (test trần thời gian), `missing` bỏ
`lightmap.png`, `killed` tự `SIGKILL` (giả OOM). `manifest.json` ghi lại `CUDA_VISIBLE_DEVICES`.
Chỉ dùng thư viện chuẩn.
"""

import json
import os
import signal
import struct
import sys
import time
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Final

MODES: Final = ("ok", "fail", "sleep", "missing", "killed")


def tiny_glb() -> bytes:
    """GLB v2 nhỏ nhất `sniff` nhận là `glb`: header 12 byte + một khúc JSON `{}` đệm khoảng trắng."""
    chunk = b"{}  "
    body = struct.pack("<I4s", len(chunk), b"JSON") + chunk
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body


def tiny_png() -> bytes:
    """PNG 1x1 xám hợp lệ."""

    def block(kind: bytes, data: bytes) -> bytes:
        """Một khúc PNG: độ dài, loại, dữ liệu, CRC."""
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n" + block(b"IHDR", ihdr) + block(b"IDAT", zlib.compress(b"\x00\x80")) + block(b"IEND", b"")
    )


def argv_for(mode: str) -> Callable[[Path, Path], list[str]]:
    """`ArgvFor` cho task: chạy bộ giả này bằng trình Python hiện tại với chế độ `mode`."""

    def build(src: Path, out: Path) -> list[str]:
        """argv như của Blender thật sau dấu `--`."""
        return [
            sys.executable,
            "-m",
            "apps.worker.lighting_bake.tests.fake_blender",
            "--mode",
            mode,
            "--",
            str(src),
            str(out),
            "2048",
            "128",
            "1.0",
        ]

    return build


def main(argv: list[str]) -> int:
    """Đọc `--mode` và hai đối số đầu sau `--`, làm đúng việc của chế độ."""
    mode = argv[argv.index("--mode") + 1]
    src, out = (Path(value) for value in argv[argv.index("--") + 1 :][:2])
    print(f"fake blender mode={mode} in={src}", flush=True)
    if mode == "fail":
        print("Traceback: giả lỗi Python trong bake_glb", file=sys.stderr)
        return 1
    if mode == "sleep":
        time.sleep(60)
    if mode == "killed":
        os.kill(os.getpid(), signal.SIGKILL)
    if not src.read_bytes().startswith(b"glTF"):
        return 1
    (out / "baked.glb").write_bytes(tiny_glb())
    if mode != "missing":
        (out / "lightmap.png").write_bytes(tiny_png())
    manifest: dict[str, object] = {"lightmap": "lightmap.png", "intensity": 1.0, "channel": 1}
    manifest["cuda"] = os.environ.get("CUDA_VISIBLE_DEVICES")
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
