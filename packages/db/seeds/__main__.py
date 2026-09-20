"""`python -m packages.db.seeds` — chạy seed theo `APP_ENV`."""

import asyncio
import os
import sys

from packages.db.engine import create_engine, create_sessionmaker, session_scope
from packages.db.models import load_all_models
from packages.db.seeds import apply_seeds
from packages.db.settings import get_database_settings


def _say(text: str) -> None:
    print(text)  # noqa: T201 — CLI in kết quả ra stdout cho người điều phối


async def _run(env: str) -> tuple[str, ...]:
    load_all_models()
    engine = create_engine(get_database_settings())
    try:
        async with session_scope(create_sessionmaker(engine)) as session:
            return await apply_seeds(session, env)
    finally:
        await engine.dispose()


def main() -> int:
    env = os.environ.get("APP_ENV")
    if not env:
        _say("thiếu APP_ENV")
        return 2
    names = asyncio.run(_run(env))
    _say(f"seed {env}: {', '.join(names) if names else 'không có seed nào'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
