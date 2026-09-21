"""`python -m packages.db.new_revision` — tên revision theo BE-00 §6.1."""

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory

from packages.db import new_revision
from packages.db.migrate_check import SCRIPT_LOCATION, alembic_config
from tools.lint_migrations import run as lint_migrations

TODAY = datetime.now(UTC).strftime("%Y%m%d")

SECOND_HEAD = '''\
"""thêm head thứ hai"""

from collections.abc import Sequence

revision: str = "r20260920_b9_99"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
'''


@pytest.fixture
def versions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Bản sao thư mục migration thật, để tạo revision mà không đụng repo."""
    migrations = tmp_path / "migrations"
    (migrations / "versions").mkdir(parents=True)
    for name in ("env.py", "script.py.mako"):
        shutil.copy(SCRIPT_LOCATION / name, migrations / name)
    for path in (SCRIPT_LOCATION / "versions").glob("*.py"):
        shutil.copy(path, migrations / "versions" / path.name)
    monkeypatch.setattr(new_revision, "alembic_config", lambda: alembic_config(migrations))
    return migrations / "versions"


def single_head(versions: Path) -> str:
    """Head duy nhất của bản sao cây revision.

    Không ghim chuỗi: mỗi prompt được thêm **một** revision (BE-00 §6.1), nên head
    đổi sau mỗi lần hợp nhất và một hằng ở đây sẽ đỏ với prompt kế tiếp.
    """
    heads = ScriptDirectory.from_config(alembic_config(versions.parent)).get_heads()
    assert len(heads) == 1, heads
    return str(heads[0])


def test_creates_revision_with_charter_name(versions: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Revision mới mang tên theo hiến chương và nối vào head hiện hành (BE-00 §6.1)."""
    head_before = single_head(versions)
    assert new_revision.main(["--code", "B2-01", "--slug", "add_projects"]) == 0
    created = list(versions.glob(f"r{TODAY}_b2_01_*.py"))
    assert [path.name for path in created] == [f"r{TODAY}_b2_01_add_projects.py"]
    body = created[0].read_text(encoding="utf-8")
    assert f'revision: str = "r{TODAY}_b2_01"' in body
    assert f'down_revision: str | None = "{head_before}"' in body
    assert f"r{TODAY}_b2_01" in capsys.readouterr().out
    assert lint_migrations(versions).violations == []


def test_second_revision_for_same_prompt_is_rejected(versions: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert new_revision.main(["--code", "B2-01", "--slug", "add_projects"]) == 0
    assert new_revision.main(["--code", "B2-01", "--slug", "add_more"]) == 2
    assert "đã có revision" in capsys.readouterr().out
    assert not list(versions.glob("*add_more*"))


def test_fix_revision_allowed_once(versions: Path) -> None:
    assert new_revision.main(["--code", "B2-01", "--slug", "add_projects"]) == 0
    assert new_revision.main(["--code", "B2-01", "--slug", "fix_index", "--fix", "001"]) == 0
    assert list(versions.glob(f"r{TODAY}_b2_01_fix001_fix_index.py"))
    assert new_revision.main(["--code", "B2-01", "--slug", "again", "--fix", "001"]) == 2
    assert lint_migrations(versions).violations == []


@pytest.mark.parametrize("slug", ["AddProjects", "add projects", "2_projects", "add-projects", ""])
def test_bad_slug_rejected(versions: Path, slug: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert new_revision.main(["--code", "B2-01", "--slug", slug]) == 2
    assert "snake_case" in capsys.readouterr().out


def test_bad_fix_number_rejected(versions: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert new_revision.main(["--code", "B2-01", "--slug", "x", "--fix", "1"]) == 2
    assert "ba chữ số" in capsys.readouterr().out


def test_too_long_revision_id_rejected(versions: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = "b2_01_" + "x" * 20  # r<8> + _ + 26 = 36 ký tự
    assert new_revision.main(["--code", code, "--slug", "x"]) == 2
    out = capsys.readouterr().out
    assert "32 ký tự" in out
    assert not list(versions.glob("*.py~"))


def test_two_heads_rejected(versions: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (versions / "r20260920_b9_99_second_head.py").write_text(SECOND_HEAD, encoding="utf-8")
    assert new_revision.main(["--code", "B2-01", "--slug", "add_projects"]) == 2
    assert "2 head" in capsys.readouterr().out


def test_bad_code_rejected(versions: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert new_revision.main(["--code", "2B*01", "--slug", "x"]) == 2
    assert "mã prompt sai mẫu" in capsys.readouterr().out


def test_baseline_revision_passes_lint() -> None:
    assert lint_migrations(SCRIPT_LOCATION / "versions").violations == []
