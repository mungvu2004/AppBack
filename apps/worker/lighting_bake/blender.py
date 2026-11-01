"""Dòng lệnh Blender cho `bake_glb.bpy` (hợp đồng LB-01: `-b --factory-startup --python-exit-code 1 -t 4`)."""

from pathlib import Path
from typing import Final

from apps.worker.lighting_bake.settings import BakeSettings

__all__ = ["BAKE_SCRIPT", "blender_argv"]

BAKE_SCRIPT: Final = Path(__file__).with_name("bake_glb.bpy")
BLENDER_THREADS: Final = 4


def blender_argv(settings: BakeSettings, script: Path, src: Path, out: Path) -> list[str]:
    """argv đầy đủ: Blender nền, không addon người dùng, lỗi Python → mã thoát 1, `out` là thư mục ra."""
    return [
        settings.blender_bin,
        "-b",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "-t",
        str(BLENDER_THREADS),
        "-P",
        str(script),
        "--",
        str(src),
        str(out),
        str(settings.bake_size),
        str(settings.bake_samples),
        str(settings.bake_cut_m),
    ]
