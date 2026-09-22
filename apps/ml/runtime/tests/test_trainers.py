"""`discover_trainers`: dò một cấp theo tên, lỗi khai báo hỏng ngay, lỗi nhập nổi lên nguyên trạng."""

import importlib
import itertools
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from apps.ml.runtime.trainers import discover_trainers
from packages.ml_contracts.families import TRAINABLE_FAMILIES

TRAINER = """
class _Trainer:
    family = {family!r}

    def train(self, spec, data_dir, out_dir, reporter):
        raise NotImplementedError


TRAINER = _Trainer()
"""

_COUNTER = itertools.count()

type Builder = Callable[..., str]


@pytest.fixture
def make_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Builder]:
    """Dựng gói tạm `mlfake<n>` với các gói con cho trước; tên riêng mỗi lượt để không dính cache nhập."""
    created: list[str] = []

    def build(children: dict[str, str | None], modules: dict[str, str] | None = None) -> str:
        name = f"mlfake{next(_COUNTER)}"
        root = tmp_path / name
        root.mkdir()
        (root / "__init__.py").write_text("", encoding="utf-8")
        for child, source in children.items():
            (root / child).mkdir()
            (root / child / "__init__.py").write_text("", encoding="utf-8")
            if source is not None:
                (root / child / "trainer.py").write_text(source, encoding="utf-8")
        for module, source in (modules or {}).items():
            (root / f"{module}.py").write_text(source, encoding="utf-8")
        created.append(name)
        return name

    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    yield build
    for module in [key for key in sys.modules if key.split(".")[0] in created]:
        del sys.modules[module]


def test_discover_trainers_rules(make_package: Builder) -> None:
    package = make_package(
        {
            "training_yolo": TRAINER.format(family="openingAndFurnitureDetection"),
            "training_segformer": TRAINER.format(family="wallSegmentation"),
            "runtime": None,
        },
        {"loose": "RAISE = 1 / 0\n"},
    )
    found = discover_trainers(package=package)
    assert list(found) == ["wallSegmentation", "openingAndFurnitureDetection"]
    assert found["wallSegmentation"].family == "wallSegmentation"


@pytest.mark.parametrize(
    ("children", "match"),
    [
        ({"a": "TRAINER = None\n"}, "thiếu family hay train"),
        ({"a": "class T:\n    family = 'wallSegmentation'\nTRAINER = T()\n"}, "thiếu family hay train"),
        ({"a": "x = 1\n"}, "thiếu family hay train"),
        ({"a": TRAINER.format(family="dimensionReading")}, "họ lạ"),
        (
            {"a": TRAINER.format(family="wallSegmentation"), "b": TRAINER.format(family="wallSegmentation")},
            "hai trainer",
        ),
    ],
)
def test_discover_trainers_rejects(make_package: Builder, children: dict[str, str | None], match: str) -> None:
    package = make_package(children)
    with pytest.raises(RuntimeError, match=match):
        discover_trainers(package=package)


def test_discover_trainers_import_errors_surface(make_package: Builder) -> None:
    package = make_package({"a": "import khong_co_goi_nay\n"})
    with pytest.raises(ModuleNotFoundError, match="khong_co_goi_nay"):
        discover_trainers(package=package)


def test_real_ml_app_trainers_are_trainable_families() -> None:
    """Dò trên `apps.ml` thật không hỏng, dù B6-04a/b đã hợp nhất hay chưa (không chốt số lượng)."""
    assert set(discover_trainers()) <= set(TRAINABLE_FAMILIES)
