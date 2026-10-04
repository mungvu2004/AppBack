"""Hằng khoá giữ chỗ và mã lệch họ model của `apps/ml/runtime` là một nguồn cho cả `apps/ml` (NO-285, NO-308, NO-314).

Quét AST theo đường tệp, không nhập các app khác: test của `runtime` không phụ thuộc gói
cao hơn nó.
"""

import ast
from collections import Counter
from pathlib import Path

import pytest

from apps.ml.runtime import errors, gpu

ML_ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ML_ROOT / "runtime"


def _module_constants(path: Path) -> set[str]:
    """Tên VIẾT_HOA gán ở cấp module của `path` (`X = …`, `X: Final = …`)."""
    names: set[str] = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        names.update(t.id for t in targets if isinstance(t, ast.Name) and t.id.isupper())
    return names


def _sources(root: Path) -> list[Path]:
    """Tệp nguồn `.py` dưới `root`, bỏ thư mục `tests`."""
    return [p for p in root.rglob("*.py") if "tests" not in p.relative_to(ML_ROOT).parts]


LOCK_MODULES = ("gpu.py", "lease.py")
"""Module khoá giữ chỗ của `runtime`: hằng công khai của chúng là nguồn duy nhất (NO-308, NO-314)."""


def test_runtime_constants__not_redeclared() -> None:
    """Hằng khoá giữ chỗ của `runtime` và `MODEL_VERSION_FAMILY_MISMATCH` không có bản sao khác trong `apps/ml`."""
    lock_files = [RUNTIME / name for name in LOCK_MODULES]
    owned = Counter(name for path in lock_files for name in _module_constants(path) if not name.startswith("_"))
    assert [name for name, count in owned.items() if count > 1] == []
    watched = owned.keys() | {"MODEL_VERSION_FAMILY_MISMATCH"}
    copies = sorted(
        f"{path.relative_to(ML_ROOT).as_posix()}:{name}"
        for path in _sources(ML_ROOT)
        if path not in lock_files and path != RUNTIME / "errors.py"
        for name in _module_constants(path) & watched
    )
    assert copies == []


def test_model_version_family_mismatch__declared_in_runtime_errors() -> None:
    """Mã họ model lệch khai cạnh `MODEL_FORMAT_UNSUPPORTED`, giữ nguyên chuỗi đã lên trạng thái job (NO-285)."""
    assert errors.MODEL_VERSION_FAMILY_MISMATCH == "MODEL_VERSION_FAMILY_MISMATCH"


def test_gpu_slot__holds_through_shared_lease(messaging_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """`gpu_slot` giữ `gpu:0` qua lõi `held_lease` chung, không vòng lấy/gia hạn riêng (NO-308)."""
    from apps.ml.runtime import lease  # nhập trong thân: cây thiếu `lease` chỉ làm đỏ test này

    names: list[str] = []
    real = lease.held_lease

    def spy(ops: lease.LeaseOps[int], *, wait_s: float, ttl_ms: int, renew_every_ms: int) -> object:
        """Ghi tên khoá rồi chuyển nguyên cho lõi thật."""
        names.append(ops.name)
        return real(ops, wait_s=wait_s, ttl_ms=ttl_ms, renew_every_ms=renew_every_ms)

    monkeypatch.setattr(gpu, "held_lease", spy)
    with gpu.gpu_slot(wait_s=0, ttl_ms=600, renew_every_ms=200) as slot:
        slot.check()
    assert names == [gpu.GPU_LOCK_NAME]
