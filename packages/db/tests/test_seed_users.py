"""Seed admin cố định `packages/db/seeds/users.py` trên Postgres thật (NO-107)."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.ids import is_id
from packages.db.models.auth import User
from packages.db.seeds import apply_seeds, load_seeds
from packages.db.seeds.users import ENVS, SEED_ADMIN_ID, seed


def test_seed_admin_id_is_a_valid_usr_id() -> None:
    """Id admin seed đúng mẫu `usr_<ULID>` mà `FakeTokenVerifier` nhận."""
    assert is_id("usr", SEED_ADMIN_ID)


def test_load_seeds__users_not_in_production() -> None:
    """Seed admin chạy ở dev/test/ci, không chạy ở staging/production."""
    assert sorted(ENVS) == ["ci", "dev", "test"]
    for env in ("dev", "test", "ci"):
        assert "users" in [s.name for s in load_seeds(env)]
    for env in ("staging", "production"):
        assert "users" not in [s.name for s in load_seeds(env)]


async def test_seed__twice_keeps_one_admin(db_session: AsyncSession) -> None:
    """Seed hai lần → đúng một dòng admin active, không nhân bản."""
    await seed(db_session)
    await seed(db_session)
    count = (await db_session.execute(select(func.count()).select_from(User).where(User.id == SEED_ADMIN_ID))).scalar_one()
    assert count == 1
    row = await db_session.get(User, SEED_ADMIN_ID)
    assert row is not None
    assert (row.role, row.status, row.password_hash) == ("admin", "active", None)


async def test_seed__keeps_edited_row(db_session: AsyncSession) -> None:
    """Seed chạy lại không ghi đè dòng admin đã bị sửa tay."""
    await seed(db_session)
    row = await db_session.get(User, SEED_ADMIN_ID)
    assert row is not None
    row.name = "Đổi tên"
    await db_session.flush()
    await apply_seeds(db_session, "test")
    await db_session.refresh(row)
    assert row.name == "Đổi tên"
