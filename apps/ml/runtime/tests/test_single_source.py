"""Hằng khoá giữ chỗ và mã lệch họ model của `apps/ml/runtime` là một nguồn cho cả `apps/ml` (NO-285, NO-308, NO-314).

Quét AST theo đường tệp, không nhập các app khác: test của `runtime` không phụ thuộc gói
cao hơn nó.
"""

import ast
import subprocess
import sys
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


SOURCE_MODULES = ("gpu.py", "lease.py", "errors.py", "error_codes.py")
"""Module nguồn của `runtime`: khoá giữ chỗ (NO-308, NO-314) và mã lỗi `ml` (NO-285, C18b)."""


def test_runtime_constants__not_redeclared() -> None:
    """Hằng công khai của khoá giữ chỗ và mã lỗi `runtime` không có bản sao nào khác trong `apps/ml` (R-07)."""
    owners = [RUNTIME / name for name in SOURCE_MODULES if (RUNTIME / name).exists()]
    owned = Counter(name for path in owners for name in _module_constants(path) if not name.startswith("_"))
    assert [name for name, count in owned.items() if count > 1] == []
    copies = sorted(
        f"{path.relative_to(ML_ROOT).as_posix()}:{name}"
        for path in _sources(ML_ROOT)
        if path not in owners
        for name in _module_constants(path) & owned.keys()
    )
    assert copies == []


def test_error_codes__import_light() -> None:
    """`runtime.error_codes` và người nhập nó (trainer, hộp cát) không kéo `onnxruntime`/`torch` lúc nhập."""
    probe = (
        "import sys; import apps.ml.runtime.error_codes, apps.ml.ml_eval.sandbox, apps.ml.training_segformer.errors, "
        "apps.ml.training_runner.errors; "
        "assert not {'torch', 'onnxruntime'} & set(sys.modules), sorted({'torch', 'onnxruntime'} & set(sys.modules))"
    )
    completed = subprocess.run(  # noqa: S603 — argv cố định, không dữ liệu ngoài
        [sys.executable, "-c", probe], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr


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
