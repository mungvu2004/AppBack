"""Seed tự dò: mỗi module một file `packages/db/seeds/<module>.py`.

File seed khai:

- `async def seed(session: AsyncSession) -> None` — **idempotent**, chạy hai lần cho
  cùng kết quả (bước 4 của `migrate_check`);
- `ORDER: int` — thứ tự chạy;
- `ENVS: frozenset[str]` — môi trường được chạy (seed demo không có `production`).

Thiếu một trong ba → hỏng ngay lúc nạp, không âm thầm bỏ qua.
"""

import importlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from sqlalchemy.ext.asyncio import AsyncSession

SEEDS_DIR = Path(__file__).resolve().parent
_SKIP = {"__init__", "__main__"}


@dataclass(frozen=True, slots=True)
class Seed:
    name: str
    order: int
    envs: frozenset[str]
    run: Callable[[AsyncSession], Awaitable[None]]


def _seed_of(name: str, module: ModuleType) -> Seed:
    missing = [attr for attr in ("seed", "ORDER", "ENVS") if not hasattr(module, attr)]
    if missing:
        raise ValueError(f"seed {name} thiếu {', '.join(missing)}")
    envs = module.ENVS
    if not isinstance(envs, frozenset | set):
        raise ValueError(f"seed {name}: ENVS phải là frozenset[str]")
    return Seed(name=name, order=int(module.ORDER), envs=frozenset(envs), run=module.seed)


def load_seeds(env: str, directory: Path = SEEDS_DIR, package: str = __name__) -> tuple[Seed, ...]:
    """Seed chạy được ở `env`, đã sắp theo (ORDER, tên)."""
    seeds = []
    for path in sorted(directory.glob("*.py")):
        if path.stem in _SKIP:
            continue
        seed = _seed_of(path.stem, importlib.import_module(f"{package}.{path.stem}"))
        if env in seed.envs:
            seeds.append(seed)
    return tuple(sorted(seeds, key=lambda s: (s.order, s.name)))


async def apply_seeds(
    session: AsyncSession, env: str, directory: Path = SEEDS_DIR, package: str = __name__
) -> tuple[str, ...]:
    """Chạy seed của `env` trong session đang mở; trả tên các seed đã chạy."""
    names = []
    for seed in load_seeds(env, directory, package):
        await seed.run(session)
        names.append(seed.name)
    return tuple(names)
