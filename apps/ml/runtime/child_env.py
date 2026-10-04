"""Môi trường tối thiểu cho tiến trình con của `ml` (huấn luyện, hộp cát đánh giá): một nguồn lọc (R-07)."""

import os
from collections.abc import Collection


def allowlisted_env(keep: Collection[str], prefixes: tuple[str, ...]) -> dict[str, str]:
    """Biến của tiến trình hiện tại có tên trong `keep` hoặc mang tiền tố trong `prefixes`; `PYTHONPATH` mặc định `cwd`.

    Mỗi nơi gọi tự khai danh sách của mình: con nào cần biến gì là hiểu biết của nơi đó, còn việc "không thừa hưởng
    bí mật khác của `ml`" (`S3_SECRET_KEY`, URL Redis, khoá cloud…) nằm ở một chỗ.
    """
    env = {name: value for name, value in os.environ.items() if name in keep or name.startswith(prefixes)}
    env.setdefault("PYTHONPATH", os.getcwd())
    return env
