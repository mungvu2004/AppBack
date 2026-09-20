"""Model của mọi module, mỗi module một file `packages/db/models/<module>.py`.

`load_all_models()` nhập hết theo thứ tự tên; Alembic và `migrate_check` gọi nó trước
khi đọc `Base.metadata`. Prompt khác **không** sửa file này, chỉ thêm file của mình.
"""

import importlib
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent


def model_modules(directory: Path = MODELS_DIR) -> list[str]:
    return sorted(path.stem for path in directory.glob("*.py") if path.stem != "__init__")


def load_all_models(directory: Path = MODELS_DIR, package: str = __name__) -> None:
    for name in model_modules(directory):
        importlib.import_module(f"{package}.{name}")
