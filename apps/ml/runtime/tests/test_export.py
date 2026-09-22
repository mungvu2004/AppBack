"""Xuất ONNX tất định, xuất YOLO (SHA trước khi nhập `ultralytics`), xuất bản ghim lúc build."""

import os
import subprocess
import sys
import textwrap
import types
from pathlib import Path
from typing import Any, ClassVar

import onnx
import pytest
import torch
from onnx import helper

from apps.ml.runtime import export_pinned
from apps.ml.runtime.errors import MODEL_CHECKSUM_MISMATCH
from apps.ml.runtime.export import export_onnx, normalize_onnx, write_atomic
from apps.ml.runtime.export_pinned import export_all, wheel_file
from apps.ml.runtime.export_yolo import export_yolo
from apps.ml.runtime.tests.helpers import add_model, external_tensor, model, sha
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.pinned import PINNED, UNPINNED, FetchError, PinnedWeights, file_sha256

REPO_ROOT = Path(__file__).resolve().parents[4]

EXPORT_SCRIPT = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    import torch
    from apps.ml.runtime.export import export_onnx

    torch.manual_seed(7)
    layers = (torch.nn.Conv2d(3, 4, 3), torch.nn.ReLU(), torch.nn.AdaptiveAvgPool2d(1), torch.nn.Flatten())
    net = torch.nn.Sequential(*layers)
    print(export_onnx(net, torch.zeros(1, 3, 16, 16), Path(sys.argv[1])))
    """
)


def test_export_onnx_deterministic(tmp_path: Path) -> None:
    """Hai tiến trình xuất cùng model → cùng SHA-256; tệp đúng là SHA trả về, không metadata giờ xuất."""
    digests = []
    for index in range(2):
        out = tmp_path / f"run{index}.onnx"
        result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
            [sys.executable, "-c", EXPORT_SCRIPT, str(out)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=300,
        )
        digests.append(result.stdout.strip().splitlines()[-1])
        assert digests[-1] == sha(out.read_bytes())
    assert digests[0] == digests[1]
    exported = onnx.load_model_from_string((tmp_path / "run0.onnx").read_bytes())
    assert exported.opset_import[0].version == 17
    assert list(exported.metadata_props) == []
    assert exported.producer_version == ""


def test_export_onnx_refuses_models_over_two_gib(tmp_path: Path) -> None:
    huge = torch.nn.Linear(32_768, 16_384, device="meta")
    with pytest.raises(ValueError, match="2 GiB"):
        export_onnx(huge, torch.zeros(1, 32_768), tmp_path / "huge.onnx")
    assert not (tmp_path / "huge.onnx").exists()


def test_normalize_onnx_strips_run_specific_fields() -> None:
    sample = add_model()
    sample.doc_string = "xuất lúc 10:00"
    sample.producer_version = "9.9"
    helper.set_model_props(sample, {"date": "2026-09-21T10:00:00"})
    sample.graph.doc_string = "/home/ai/train.py"
    sample.graph.node[0].doc_string = "File /home/ai/train.py, line 3"
    sample.graph.input[0].doc_string = "đầu vào"
    sample.graph.initializer[0].doc_string = "hằng"
    function = helper.make_function("local", "F", ["a"], ["b"], [helper.make_node("Identity", ["a"], ["b"])], [])
    function.doc_string = "hàm"
    sample.functions.append(function)
    cleaned = onnx.load_model_from_string(normalize_onnx(sample.SerializeToString()))
    assert (cleaned.doc_string, cleaned.producer_version, list(cleaned.metadata_props)) == ("", "", [])
    assert cleaned.graph.doc_string == cleaned.graph.node[0].doc_string == cleaned.functions[0].doc_string == ""
    assert cleaned.graph.input[0].doc_string == cleaned.graph.initializer[0].doc_string == ""
    assert normalize_onnx(cleaned.SerializeToString()) == cleaned.SerializeToString(deterministic=True)
    with_external = model([helper.make_node("Add", ["x", "c"], ["y"])], initializer=[external_tensor("c")])
    with pytest.raises(ValueError, match="dữ liệu ngoài"):
        normalize_onnx(with_external.SerializeToString())


def test_write_atomic(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "out.onnx"
    assert write_atomic(target, b"abc") == sha(b"abc")
    assert write_atomic(target, b"xyz") == sha(b"xyz")
    assert target.read_bytes() == b"xyz"
    assert sorted(path.name for path in target.parent.iterdir()) == ["out.onnx"]


def test_export_yolo_checks_sha_first(tmp_path: Path) -> None:
    """SHA `.pt` lệch → `MODEL_CHECKSUM_MISMATCH` mà `ultralytics` chưa hề được nhập (tiến trình mới)."""
    pt = tmp_path / "w.pt"
    pt.write_bytes(b"\x80\x04pickle gia")
    script = textwrap.dedent(
        f"""
        import sys
        from pathlib import Path
        from apps.ml.runtime.export_yolo import export_yolo
        from packages.messaging.tasks import PermanentError
        try:
            export_yolo(Path({str(pt)!r}), Path({str(tmp_path / "w.onnx")!r}), source_sha256="0" * 64)
        except PermanentError as exc:
            print(exc.code, "ultralytics" in sys.modules)
        """
    )
    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", script], cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=300
    )
    assert result.stdout.strip().splitlines()[-1] == f"{MODEL_CHECKSUM_MISMATCH} False"
    assert not (tmp_path / "w.onnx").exists()


class FakeYolo:
    """`ultralytics.YOLO` giả: ghi ONNX kèm metadata giờ xuất cạnh `.pt`, ghi lại tham số."""

    calls: ClassVar[list[tuple[str, dict[str, Any]]]] = []
    env: ClassVar[dict[str, str | None]] = {}

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def export(self, **kwargs: Any) -> str:
        FakeYolo.calls.append((self.path.name, kwargs))
        FakeYolo.env = {name: os.environ.get(name) for name in ("YOLO_OFFLINE", "YOLO_AUTOINSTALL", "YOLO_CONFIG_DIR")}
        exported = add_model()
        helper.set_model_props(exported, {"date": "bây giờ"})
        out = self.path.with_suffix(".onnx")
        out.write_bytes(exported.SerializeToString())
        return str(out)


def test_export_yolo_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Luồng xuất: cờ ngoại tuyến + thư mục cấu hình tạm, tham số tất định, chuẩn hoá, ghi nguyên tử."""
    fake = types.ModuleType("ultralytics")
    monkeypatch.setattr(fake, "YOLO", FakeYolo, raising=False)
    monkeypatch.setitem(sys.modules, "ultralytics", fake)
    monkeypatch.setenv("YOLO_OFFLINE", "0")
    monkeypatch.delenv("YOLO_CONFIG_DIR", raising=False)
    pt = tmp_path / "yolov8n.pt"
    pt.write_bytes(b"trong so")
    digest = export_yolo(pt, tmp_path / "out" / "yolov8n.onnx", source_sha256=sha(b"trong so"), imgsz=320)
    assert digest == sha((tmp_path / "out" / "yolov8n.onnx").read_bytes())
    assert FakeYolo.calls[-1] == (
        "yolov8n.pt",
        {"format": "onnx", "opset": 17, "imgsz": 320, "simplify": False, "dynamic": False, "device": "cpu"},
    )
    assert FakeYolo.env["YOLO_OFFLINE"] == "1"
    assert FakeYolo.env["YOLO_AUTOINSTALL"] == "false"
    assert FakeYolo.env["YOLO_CONFIG_DIR"] is not None
    assert list(onnx.load(str(tmp_path / "out" / "yolov8n.onnx")).metadata_props) == []
    assert os.environ["YOLO_OFFLINE"] == "0"
    assert "YOLO_CONFIG_DIR" not in os.environ
    with pytest.raises(PermanentError):
        export_yolo(pt, tmp_path / "x.onnx", source_sha256="1" * 64)


def test_pinned_rapidocr_matches_wheel() -> None:
    """ONNX nhận dạng trong wheel đã khoá chính là bản ghim, và còn bảng ký tự cho B5-04."""
    path = wheel_file("rapidocrRec")
    pin = PINNED["rapidocrRec"]
    assert file_sha256(path) == pin.onnx_sha256 == pin.source_sha256
    keys = [prop.key for prop in onnx.load(str(path), load_external_data=False).metadata_props]
    assert "character" in keys


def pin(name: str, *, source_url: str = "https://x.test/v1/w.pt", onnx_sha256: str | None = None) -> PinnedWeights:
    fields: dict[str, Any] = {
        "name": name,
        "family": "openingAndFurnitureDetection",
        "source_url": source_url,
        "source_sha256": sha(b"nguon"),
        "onnx_sha256": onnx_sha256,
        "license": "AGPL-3.0",
    }
    return PinnedWeights(**fields)


def test_export_all_rules(tmp_path: Path) -> None:
    """Chỉ bản có ONNX; YOLO qua bộ xuất; bản trong wheel chép nguyên; lệch → xoá và thoát 2."""
    rec = wheel_file("rapidocrRec")
    calls: list[Path] = []

    def exporter(source: Path, out: Path, *, source_sha256: str) -> str:
        calls.append(source)
        return write_atomic(out, b"onnx-" + source.name.encode())

    table = {
        "seg": pin("seg"),
        "det": pin("det", onnx_sha256=sha(b"onnx-w.pt")),
        "rapidocrRec": PINNED["rapidocrRec"],
    }
    assert export_all(tmp_path, pinned=table, exporter=exporter) == {
        "det": sha(b"onnx-w.pt"),
        "rapidocrRec": file_sha256(rec),
    }
    assert calls == [tmp_path / "det" / "w.pt"]
    assert (tmp_path / "rapidocrRec.onnx").read_bytes() == rec.read_bytes()
    with pytest.raises(FetchError, match="lệch") as caught:
        export_all(tmp_path, pinned={"det": pin("det", onnx_sha256="e" * 64)}, exporter=exporter)
    assert caught.value.exit_code == 2
    assert not (tmp_path / "det.onnx").exists()


@pytest.mark.parametrize(
    ("table", "code"),
    [
        ({"x": PinnedWeights("x", "dimensionReading", "", UNPINNED, UNPINNED, "MIT")}, 2),
        ({"rapidocrRec": pin("rapidocrRec", source_url="", onnx_sha256="e" * 64)}, 2),
        ({"det": pin("det", onnx_sha256="e" * 64)}, 2),
    ],
)
def test_export_all_failures(tmp_path: Path, table: dict[str, PinnedWeights], code: int) -> None:
    def mismatch(source: Path, out: Path, *, source_sha256: str) -> str:
        raise PermanentError(MODEL_CHECKSUM_MISMATCH)

    with pytest.raises(FetchError) as caught:
        export_all(tmp_path, pinned=table, exporter=mismatch)
    assert caught.value.exit_code == code


def test_export_all_missing_source_exits_3(tmp_path: Path) -> None:
    with pytest.raises(FetchError, match="thiếu tệp") as caught:
        export_all(tmp_path, pinned={"yolov8n": PINNED["yolov8n"]})
    assert caught.value.exit_code == 3


def test_wheel_file_requires_the_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(export_pinned.WHEEL_FILES, "ghost", ("khong_co_goi_nay", "x.onnx"))
    with pytest.raises(FileNotFoundError, match="khong_co_goi_nay"):
        wheel_file("ghost")


def test_export_pinned_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Điểm vào `python -m`: thiếu `.pt` đã tải → thoát 3 (không mạng, không nhập ultralytics)."""
    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-m", "apps.ml.runtime.export_pinned", "--dest", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert result.returncode == 3, result.stderr
    monkeypatch.setattr(export_pinned, "export_all", lambda dest: {"yolov8n": "a" * 64})
    assert export_pinned.main(["--dest", str(tmp_path)]) == 0
