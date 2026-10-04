"""Test `model.load_pretrained`: checksum trước, định dạng, và quét AST cấm pickle (K12)."""

import ast
import logging
import subprocess
import sys
import time
from pathlib import Path

import pytest
from transformers import SegformerForSemanticSegmentation

from apps.ml.runtime.errors import MODEL_CHECKSUM_MISMATCH as RUNTIME_MODEL_CHECKSUM_MISMATCH
from apps.ml.runtime.errors import MODEL_FORMAT_UNSUPPORTED as RUNTIME_MODEL_FORMAT_UNSUPPORTED
from apps.ml.training_runner.errors import DATASET_SPLIT_EMPTY as RUNNER_DATASET_SPLIT_EMPTY
from apps.ml.training_segformer import model as segformer_model
from apps.ml.training_segformer.errors import (
    DATASET_SPLIT_EMPTY,
    MODEL_CHECKSUM_MISMATCH,
    MODEL_FORMAT_UNSUPPORTED,
)
from apps.ml.training_segformer.tests.support import pinned_for, write_pinned_tiny_model, write_tiny_model
from packages.messaging.tasks import PermanentError

_FORBIDDEN_NAMES: frozenset[str] = frozenset({"load", "Unpickler"})
_FORBIDDEN_IMPORTS: frozenset[str] = frozenset({"pickle", "joblib"})


def test_train_m02_pinned_checksum(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SHA tệp lệch bản ghim → `MODEL_CHECKSUM_MISMATCH`, không gọi `from_pretrained`."""
    sha = write_tiny_model(tmp_path, "mitB0")
    pinned = pinned_for("0" * 64, "mitB0")
    assert sha != pinned["mitB0"].source_sha256

    def _must_not_run(*_args: object, **_kwargs: object) -> None:
        """Không được gọi: checksum lệch phải chặn trước khi chạm `from_pretrained`."""
        raise AssertionError("from_pretrained không được gọi khi checksum lệch")

    monkeypatch.setattr(SegformerForSemanticSegmentation, "from_pretrained", staticmethod(_must_not_run))
    start = time.monotonic()
    with pytest.raises(PermanentError) as excinfo:
        segformer_model.load_pretrained(tmp_path, "mitB0", pinned)
    logging.getLogger(__name__).info("test_train_m02 %.3fs", time.monotonic() - start)
    assert excinfo.value.code == MODEL_CHECKSUM_MISMATCH


def test_train_m03_no_pickle(tmp_path: Path) -> None:
    """Thư mục chỉ có `pytorch_model.bin` (không `model.safetensors`) → `MODEL_FORMAT_UNSUPPORTED`."""
    target = tmp_path / "mitB0"
    target.mkdir()
    (target / "pytorch_model.bin").write_bytes(b"not-really-a-checkpoint")
    pinned = pinned_for("0" * 64, "mitB0")
    with pytest.raises(PermanentError) as excinfo:
        segformer_model.load_pretrained(tmp_path, "mitB0", pinned)
    assert excinfo.value.code == MODEL_FORMAT_UNSUPPORTED


def _violations(source: str) -> list[str]:
    """Lỗi K12 trong một đoạn mã: `torch.load`/`load`/`Unpickler` (mọi cách nhập), pickle/joblib, cờ không an toàn."""
    found: list[str] = []
    torch_aliases: set[str] = {"torch"}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _FORBIDDEN_IMPORTS:
                    found.append(f"nhập {alias.name}")
                if alias.name == "torch" and alias.asname:
                    torch_aliases.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            if node.module in _FORBIDDEN_IMPORTS:
                found.append(f"nhập từ {node.module}")
            if node.module == "torch" and any(alias.name in _FORBIDDEN_NAMES for alias in node.names):
                found.append("nhập tên cấm từ torch")
        elif isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_NAMES:
            if isinstance(node.value, ast.Name) and node.value.id in torch_aliases:
                found.append(f"gọi torch.{node.attr}")
        elif isinstance(node, ast.keyword):
            if node.arg == "weights_only" and isinstance(node.value, ast.Constant) and node.value.value is False:
                found.append("weights_only=False")
            if node.arg == "trust_remote_code":
                found.append("trust_remote_code dùng")
    return found


def test_train_m03_ast_no_pickle_load() -> None:
    """Quét AST mọi `.py` của gói: không `torch.load`, `pickle`/`joblib`, `weights_only=False`, `trust_remote_code`."""
    package_root = Path(__file__).resolve().parents[1]
    for path in package_root.rglob("*.py"):
        assert _violations(path.read_text(encoding="utf-8")) == [], str(path)


@pytest.mark.parametrize(
    "source",
    [
        "from torch import load",
        "import torch as t\nt.load('x')",
        "import torch\ntorch.load('x')",
        "import torch\ntorch.Unpickler",
        "import pickle",
        "from joblib import load",
        "f(weights_only=False)",
        "f(trust_remote_code=True)",
    ],
)
def test_ast_scan__flags_every_unsafe_form(source: str) -> None:
    """Máy quét K12 bắt cả `from torch import load` và bí danh `import torch as t` (NO-318 P3-8)."""
    assert _violations(source) != []


def test_load_base_model__hf_offline_env_forced() -> None:
    """Nhập gói đặt `HF_HUB_OFFLINE=1` + `TRANSFORMERS_OFFLINE=1` **trước** `transformers` (BE-00 §9, NO-333)."""
    probe = "; ".join(
        [
            "import os",
            "os.environ['HF_HUB_OFFLINE'] = '0'",
            "os.environ.pop('TRANSFORMERS_OFFLINE', None)",
            "import apps.ml.training_segformer.model",
            "import huggingface_hub.constants as c",
            "assert os.environ['HF_HUB_OFFLINE'] == '1' and os.environ['TRANSFORMERS_OFFLINE'] == '1'",
            "assert c.HF_HUB_OFFLINE is True",
        ]
    )
    completed = subprocess.run(  # noqa: S603 — argv cố định, không dữ liệu ngoài
        [sys.executable, "-c", probe], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr


def test_train_loads_pinned_model_with_contract_labels(tmp_path: Path) -> None:
    """SHA khớp bản ghim → model nạp được, `num_labels == 2`, `id2label` đúng khối [6]."""
    model = segformer_model.load_pretrained(tmp_path, "mitB0", write_pinned_tiny_model(tmp_path))
    assert model.config.num_labels == 2
    id2label = model.config.id2label
    assert id2label is not None
    assert {int(key): value for key, value in id2label.items()} == {0: "background", 1: "wall"}


def test_train_from_pretrained_error_is_format_unsupported(tmp_path: Path) -> None:
    """`config.json` hỏng (JSON sai) → `from_pretrained` ném lỗi của nó → `MODEL_FORMAT_UNSUPPORTED`."""
    pinned = write_pinned_tiny_model(tmp_path)
    (tmp_path / "mitB0" / "config.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(PermanentError) as excinfo:
        segformer_model.load_pretrained(tmp_path, "mitB0", pinned)
    assert excinfo.value.code == MODEL_FORMAT_UNSUPPORTED


def test_errors_match_runtime_and_runner_strings() -> None:
    """`errors.py` không nhập lại `apps.ml.runtime.errors`/`training_runner.errors` nhưng chuỗi phải khớp."""
    assert MODEL_CHECKSUM_MISMATCH == RUNTIME_MODEL_CHECKSUM_MISMATCH
    assert MODEL_FORMAT_UNSUPPORTED == RUNTIME_MODEL_FORMAT_UNSUPPORTED
    assert DATASET_SPLIT_EMPTY == RUNNER_DATASET_SPLIT_EMPTY
