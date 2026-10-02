"""Nạp model SegFormer nhà cung cấp đã ghim, kiểm checksum trước khi giải (K12, BE-00 §9).

`trainer.py` gọi qua thuộc tính module (`segformer_model.load_pretrained`) để test vá được
(khối [6]). Module này nhập `torch`/`transformers` ở mức module — không đi qua `trainer`
lúc `discover_trainers()`.
"""

import hashlib
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from transformers import SegformerForSemanticSegmentation

from apps.ml.training_segformer.errors import MODEL_CHECKSUM_MISMATCH, MODEL_FORMAT_UNSUPPORTED
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.pinned import PinnedWeights

__all__ = ["load_pretrained"]

_log: Final = logging.getLogger(__name__)

_WEIGHTS_FILE: Final = "model.safetensors"
_ID2LABEL: Final = {0: "background", 1: "wall"}
_LABEL2ID: Final = {"background": 0, "wall": 1}


def _unsupported() -> PermanentError:
    """Lỗi chung cho mọi thư mục model không nạp được (không tiết lộ chi tiết)."""
    return PermanentError(MODEL_FORMAT_UNSUPPORTED)


def load_pretrained(
    models_dir: Path, base_model: str, pinned: Mapping[str, PinnedWeights]
) -> SegformerForSemanticSegmentation:
    """Model `base_model` dưới `models_dir/base_model`, checksum khớp `pinned` trước khi giải.

    Thiếu `model.safetensors` (kể cả khi có `.bin`/`.pt`) → `MODEL_FORMAT_UNSUPPORTED`; SHA-256
    lệch `pinned[base_model].source_sha256` → `MODEL_CHECKSUM_MISMATCH`, **trước** khi gọi
    `from_pretrained` (hàm dựng model không được chạm vào tệp đã lệch checksum). Lỗi của chính
    `from_pretrained` (dạng không nạp được, config hỏng — luôn `OSError`, đọc trong venv
    `transformers 5.17` `modeling_utils.py` quanh `use_safetensors`/`local_files_only`) →
    `MODEL_FORMAT_UNSUPPORTED`.
    """
    target = models_dir / base_model
    weights_path = target / _WEIGHTS_FILE
    if not weights_path.is_file():
        _log.warning("thiếu %s cho %s", _WEIGHTS_FILE, base_model)
        raise _unsupported()
    with weights_path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    expected = pinned[base_model].source_sha256
    if digest != expected:
        raise PermanentError(MODEL_CHECKSUM_MISMATCH)
    try:
        model = SegformerForSemanticSegmentation.from_pretrained(
            target,
            num_labels=2,
            id2label=_ID2LABEL,
            label2id=_LABEL2ID,
            use_safetensors=True,
            local_files_only=True,
        )
    except OSError as exc:
        _log.warning("nạp %s lỗi: %s", base_model, type(exc).__name__)
        raise _unsupported() from exc
    return model
