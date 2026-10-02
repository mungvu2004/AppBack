"""Trần của lệnh nhập CubiCasa5K (B6-02b [5]), đọc từ biến môi trường `CUBICASA_*`.

`cli.main()` dựng một `CubiCasaSettings()` rồi truyền cho `import_cubicasa`; test dựng thẳng
với trần nhỏ (`CubiCasaSettings(cubicasa_max_samples=2)`) thay vì đổi biến môi trường, nên
không có cache cấp tiến trình để rò giữa các test. `CUBICASA_WORK_DIR` mặc định là thư mục tạm
của hệ điều hành lúc dựng (ruff `S108` cấm chuỗi thư mục tạm cố định).
"""

import tempfile
from pathlib import Path
from typing import Annotated

from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.ml_contracts.artifacts import MASK_MAX_PIXELS


def _system_temp_dir() -> Path:
    """Thư mục tạm của hệ điều hành, đọc lúc dựng cấu hình (tôn trọng `TMPDIR`)."""
    return Path(tempfile.gettempdir())


class CubiCasaSettings(BaseSettings):
    """Trần số mẫu, giải nén (K13), SVG và điểm ảnh của một lượt nhập.

    `cubicasa_max_pixels` không vượt `MASK_MAX_PIXELS`: một ảnh lớn hơn thì `walls.png` của nó
    không giải lại được bằng `decode_mask`, và `SampleMeta` từ chối khổ đó.
    """

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    cubicasa_max_samples: PositiveInt = 6000
    cubicasa_max_files: PositiveInt = 60_000
    cubicasa_max_total_bytes: PositiveInt = 21_474_836_480
    cubicasa_max_file_bytes: PositiveInt = 268_435_456
    cubicasa_max_ratio: PositiveInt = 100
    cubicasa_svg_max_bytes: PositiveInt = 16_777_216
    cubicasa_max_pixels: Annotated[int, Field(gt=0, le=MASK_MAX_PIXELS)] = 40_000_000
    cubicasa_work_dir: Path = Field(default_factory=_system_temp_dir)
