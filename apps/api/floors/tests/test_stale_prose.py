"""Quét văn bản: docstring của `apps/api/floors` không còn nói route "chưa hợp nhất" (NO-172)."""

from pathlib import Path

FLOORS_DIR = Path(__file__).resolve().parents[1]
STALE_PHRASE = "chưa hợp nhất"


def test_floors_sources__no_stale_unmerged_claim() -> None:
    """Route tầng đã nằm trong nhánh; câu "chưa hợp nhất trên nhánh này" là mô tả cũ, không được sót."""
    stale = [
        f"{path.relative_to(FLOORS_DIR)}:{number}"
        for path in sorted(FLOORS_DIR.rglob("*.py"))
        if path != Path(__file__).resolve()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if STALE_PHRASE in line
    ]
    assert stale == []
