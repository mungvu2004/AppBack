"""`load_onnx` (M02, M03, K12): checksum, trần byte, định dạng, ONNX không tin, bản ghim, cache LRU."""

import json
import pickle
import struct
import zipfile
from collections.abc import Iterator, Mapping
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import onnx
import pytest
import torch
from onnx import TensorProto, helper, numpy_helper

from apps.ml.runtime import loader
from apps.ml.runtime.errors import MODEL_CHECKSUM_MISMATCH, MODEL_FORMAT_UNSUPPORTED, MODEL_NOT_FOUND, ORT_ERRORS
from apps.ml.runtime.export import export_onnx
from apps.ml.runtime.loader import clear_session_cache, has_external_data, load_onnx
from apps.ml.runtime.tests.helpers import (
    OPSETS,
    FailingReads,
    add_model,
    branch_graph,
    colliding_function_model,
    external_tensor,
    hidden_in_function_default,
    local_function_model,
    loop_graph,
    loop_model,
    model,
    nested_function_model,
    sha,
    some_id,
)
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE, NOT_FOUND
from packages.core.errors import AppError
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.payloads import ModelRef
from packages.ml_contracts.pinned import PINNED, PinnedWeights
from packages.storage.local import LocalDiskStorage
from packages.storage.port import ObjectStorage


@pytest.fixture(autouse=True)
def fresh_cache() -> Iterator[None]:
    clear_session_cache()
    yield
    clear_session_cache()


def storage_ref(data: bytes, *, checksum: str | None = None, name: str = "model.onnx") -> ModelRef:
    version = some_id("mdl")
    return ModelRef(
        version_id=version,
        family="wallSegmentation",
        weights_key=f"ml/models/{version}/{name}",
        pinned_name=None,
        checksum_sha256=checksum or sha(data),
    )


def pinned_ref(data: bytes, name: str = "yolov8n") -> ModelRef:
    return ModelRef(
        version_id=some_id("mdl"),
        family="openingAndFurnitureDetection",
        weights_key=None,
        pinned_name=name,
        checksum_sha256=sha(data),
    )


def pin_table(data: bytes, name: str = "yolov8n") -> dict[str, PinnedWeights]:
    weights = PinnedWeights(name, "openingAndFurnitureDetection", "", sha(data), sha(data), "AGPL-3.0")
    return {name: weights}


async def put(storage: LocalDiskStorage, ref: ModelRef, data: bytes) -> None:
    await storage.put(str(ref.weights_key), data, content_type="application/octet-stream", max_bytes=len(data) + 1)


async def expect(
    code: str,
    storage: ObjectStorage,
    ref: ModelRef,
    models_dir: Path,
    pinned: Mapping[str, PinnedWeights] = PINNED,
) -> None:
    with pytest.raises(PermanentError) as caught:
        await load_onnx(storage, ref, models_dir=models_dir, pinned=pinned)
    assert caught.value.code == code


def run(session: Any, value: float) -> float:
    """Chạy phiên một vào một ra (tên vào do bộ xuất đặt, không cố định là `x`)."""
    outputs = session.run(None, {session.get_inputs()[0].name: np.array([value], dtype=np.float32)})
    return float(outputs[0][0])


async def test_load_onnx_runs_a_storage_model(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    data = add_model(2.0).SerializeToString()
    ref = storage_ref(data)
    await put(local_storage, ref, data)
    session = await load_onnx(local_storage, ref, models_dir=tmp_path)
    assert run(session, 1.0) == 3.0
    with pytest.raises(ValueError, match="cổ điển"):
        await load_onnx(
            local_storage,
            ModelRef(
                version_id=None, family="wallSegmentation", weights_key=None, pinned_name=None, checksum_sha256=""
            ),
            models_dir=tmp_path,
        )


async def test_load_onnx_m02_checksum_mismatch(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    data = add_model().SerializeToString()
    ref = storage_ref(data, checksum="0" * 64)
    await put(local_storage, ref, data)
    await expect(MODEL_CHECKSUM_MISMATCH, local_storage, ref, tmp_path)
    (tmp_path / "yolov8n.onnx").write_bytes(data)
    await expect(MODEL_CHECKSUM_MISMATCH, local_storage, pinned_ref(data), tmp_path, pinned=pin_table(b"khac"))


async def test_load_onnx_m02_missing(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    data = add_model().SerializeToString()
    await expect(MODEL_NOT_FOUND, local_storage, storage_ref(data), tmp_path)
    await expect(MODEL_NOT_FOUND, local_storage, pinned_ref(data), tmp_path, pinned=pin_table(data))
    await expect(MODEL_NOT_FOUND, local_storage, pinned_ref(data), tmp_path, pinned={})


async def test_load_onnx_object_vanishes_or_storage_fails(tmp_path: Path) -> None:
    data = add_model().SerializeToString()
    await expect(
        MODEL_NOT_FOUND, FailingReads(tmp_path, NOT_FOUND.error(), pretend_size=1), storage_ref(data), tmp_path
    )
    broken = FailingReads(tmp_path, DEPENDENCY_UNAVAILABLE.error(retry_after=5), pretend_size=1)
    with pytest.raises(AppError) as caught:
        await load_onnx(broken, storage_ref(data), models_dir=tmp_path)
    assert caught.value.code is DEPENDENCY_UNAVAILABLE


async def test_load_onnx_m02_size_cap(
    local_storage: LocalDiskStorage, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = add_model().SerializeToString()
    monkeypatch.setattr(loader, "MODEL_MAX_BYTES", len(data) - 1)
    ref = storage_ref(data)
    await put(local_storage, ref, data)
    await expect(MODEL_FORMAT_UNSUPPORTED, local_storage, ref, tmp_path)
    # Kho khai cỡ nhỏ hơn thật: vẫn dừng khi luồng đọc vượt trần.
    meta = tmp_path / "objects" / f"{ref.weights_key}.meta.json"
    fields = json.loads(meta.read_text(encoding="utf-8"))
    meta.write_text(json.dumps(fields | {"size": 1}), encoding="utf-8")
    await expect(MODEL_FORMAT_UNSUPPORTED, local_storage, ref, tmp_path)
    (tmp_path / "yolov8n.onnx").write_bytes(data)
    await expect(MODEL_FORMAT_UNSUPPORTED, local_storage, pinned_ref(data), tmp_path, pinned=pin_table(data))


def _zip_bytes() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("archive/data.pkl", pickle.dumps({"w": 1}))
    return buffer.getvalue()


def _safetensors_bytes() -> bytes:
    header = json.dumps({"w": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}).encode()
    return struct.pack("<Q", len(header)) + header + struct.pack("<f", 1.0)


async def test_load_onnx_m03_user_pickle(
    local_storage: LocalDiskStorage, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pickle, zip `.pt`, safetensors với checksum **khớp** vẫn bị chặn; không bộ giải pickle nào được gọi."""

    def forbidden(*_: object, **__: object) -> None:
        raise AssertionError("bộ giải pickle không được chạm tới")

    for target, name in ((pickle, "loads"), (pickle, "load"), (torch, "load")):
        monkeypatch.setattr(target, name, forbidden)
    samples = (
        pickle.dumps({"w": 1}, protocol=4),
        _zip_bytes(),
        _safetensors_bytes(),
        b"",
        b"\x08\xff\xff\xff\xff",
    )
    for data in samples:
        ref = storage_ref(data)
        await put(local_storage, ref, data)
        await expect(MODEL_FORMAT_UNSUPPORTED, local_storage, ref, tmp_path)


def _function(name: str, nodes: list[onnx.NodeProto]) -> onnx.FunctionProto:
    return helper.make_function("local", name, ["a"], ["b"], nodes, [helper.make_opsetid("", 17)])


LOCAL_OPSETS = [helper.make_opsetid("", 17), helper.make_opsetid("local", 1)]


def _external_function_model() -> onnx.ModelProto:
    """`Constant` trong `FunctionProto` trỏ `../x` — dữ liệu ngoài giấu trong thân hàm."""
    constant = helper.make_node("Constant", [], ["k"], value=external_tensor("k"))
    function = _function("F", [constant, helper.make_node("Add", ["a", "k"], ["b"])])
    return model([helper.make_node("F", ["x"], ["y"], domain="local")], functions=[function], opsets=LOCAL_OPSETS)


async def test_load_onnx_m03_external_data(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    samples = (
        _external_function_model(),
        model([helper.make_node("Add", ["x", "c"], ["y"])], initializer=[external_tensor("c")]),
    )
    for sample in samples:
        data = sample.SerializeToString()
        ref = storage_ref(data)
        await put(local_storage, ref, data)
        await expect(MODEL_FORMAT_UNSUPPORTED, local_storage, ref, tmp_path)
    pinned_data = samples[1].SerializeToString()
    (tmp_path / "yolov8n.onnx").write_bytes(pinned_data)
    await expect(
        MODEL_FORMAT_UNSUPPORTED, local_storage, pinned_ref(pinned_data), tmp_path, pinned=pin_table(pinned_data)
    )


def test_has_external_data_walks_every_tensor() -> None:
    """Mọi chỗ chứa tensor: initializer, sparse, thuộc tính `t`/`tensors`/`sparse_*`, đồ thị con, hàm."""
    plain = helper.make_tensor("p", TensorProto.FLOAT, [1], [1.0])
    sparse = helper.make_sparse_tensor(plain, helper.make_tensor("i", TensorProto.INT64, [1], [0]), [1])
    external_sparse = helper.make_sparse_tensor(
        external_tensor("v"), helper.make_tensor("i", TensorProto.INT64, [1], [0]), [1]
    )
    clean = model(
        [
            helper.make_node("Constant", [], ["s"], sparse_value=sparse),
            helper.make_node("Custom", ["x"], ["y"], domain="x", many=[plain], sparse_many=[sparse]),
        ],
        initializer=[plain],
    )
    clean.graph.sparse_initializer.append(sparse)
    assert not has_external_data(clean)
    cases = [
        model([helper.make_node("Constant", [], ["s"], sparse_value=external_sparse)]),
        model([helper.make_node("Custom", ["x"], ["y"], domain="x", many=[external_tensor("m")])]),
        model([helper.make_node("Custom", ["x"], ["y"], domain="x", sparse_many=[external_sparse])]),
        model(
            [
                helper.make_node(
                    "If", ["c"], ["y"], then_branch=_graph_with(external_tensor("t")), else_branch=_graph_with(plain)
                )
            ]
        ),
        model([helper.make_node("Custom", ["x"], ["y"], domain="x", graphs=[_graph_with(external_tensor("g"))])]),
        _external_function_model(),
    ]
    sparse_initializer = model([])
    sparse_initializer.graph.sparse_initializer.append(external_sparse)
    cases.append(sparse_initializer)
    # Review 2026-09-21 #1: tensor ngoài giấu trong giá trị mặc định thuộc tính của hàm cục bộ.
    for default in (external_tensor("d"), external_sparse, _graph_with(external_tensor("g"))):
        hidden = local_function_model([helper.make_node("Identity", ["a"], ["b"])])
        hidden.functions[0].attribute_proto.append(helper.make_attribute("val", default))
        cases.append(hidden)
    assert all(has_external_data(case) for case in cases)


def _graph_with(tensor: TensorProto) -> onnx.GraphProto:
    return helper.make_graph(
        [helper.make_node("Identity", ["k"], ["out"])],
        "branch",
        [],
        [helper.make_tensor_value_info("out", TensorProto.FLOAT, [1])],
        initializer=[tensor],
    )


def _scan_model() -> onnx.ModelProto:
    return model([helper.make_node("Scan", ["x"], ["y"], num_scan_inputs=1)])


def _loop_in_if() -> onnx.ModelProto:
    loop = loop_model()
    branch = helper.make_graph(
        list(loop.graph.node), "then", [], [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])]
    )
    return model([helper.make_node("If", ["c"], ["y"], then_branch=branch, else_branch=branch)])


def _loop_in_function() -> onnx.ModelProto:
    function = _function(
        "F", [helper.make_node("Loop", ["", "", "a"], ["b"], body=loop_model().graph.node[0].attribute[0].g)]
    )
    return model([helper.make_node("F", ["x"], ["y"], domain="local")], functions=[function], opsets=LOCAL_OPSETS)


def _cyclic_functions() -> onnx.ModelProto:
    function = _function("F", [helper.make_node("F", ["a"], ["b"], domain="local")])
    return model([helper.make_node("F", ["x"], ["y"], domain="local")], functions=[function], opsets=LOCAL_OPSETS)


def _hidden_microsoft_op() -> onnx.ModelProto:
    """Op miền `com.microsoft` giấu trong mặc định thuộc tính hàm."""
    zero = numpy_helper.from_array(np.array([0.0], dtype=np.float32), "zero")
    hidden = branch_graph([helper.make_node("Gelu", ["zero"], ["out"], domain="com.microsoft")], [zero])
    return hidden_in_function_default(hidden, [*OPSETS, helper.make_opsetid("com.microsoft", 1)])


def _harmless_default() -> onnx.ModelProto:
    """Mặc định thuộc tính hàm chỉ có op chuẩn (ORT chạy ra `y = x`): vô hại, vẫn bị từ chối vì có hàm cục bộ."""
    zero = numpy_helper.from_array(np.array([0.0], dtype=np.float32), "zero")
    return hidden_in_function_default(branch_graph([helper.make_node("Identity", ["zero"], ["out"])], [zero]))


def _local_function_models() -> tuple[onnx.ModelProto, ...]:
    """Model có hàm cục bộ mà ORT nạp và chạy được — trước lượt sửa review 2026-09-22, cả sáu lọt dạng storage.

    Hàm vô hại, mặc định thuộc tính vô hại, hàm trùng id op contrib / `ai.onnx.ml` (ORT chạy
    kernel, không chạy thân), hàm lệch `overload` (bộ inline bỏ qua), lời gọi lồng 12 bậc (4 096 node).
    """
    one = numpy_helper.from_array(np.array([1.0], dtype=np.float32))
    plus_one = local_function_model(
        [helper.make_node("Constant", [], ["k"], value=one), helper.make_node("Add", ["a", "k"], ["b"])]
    )
    return (
        plus_one,
        _harmless_default(),
        colliding_function_model("com.microsoft", "Gelu"),
        colliding_function_model("ai.onnx.ml", "Binarizer"),
        colliding_function_model("com.microsoft", "Gelu", overload="khac"),
        nested_function_model(12),
    )


def test_structure_rules_reject_every_local_function() -> None:
    """Dạng storage: có hàm cục bộ là từ chối, kể cả hàm vô hại; model phẳng miền chuẩn thì nhận."""
    assert loader._structure_allowed(add_model())
    assert not loader._structure_allowed(hidden_in_function_default(loop_graph(5)))
    assert not loader._structure_allowed(_hidden_microsoft_op())
    assert not any(loader._structure_allowed(sample) for sample in _local_function_models())


async def test_load_onnx_m03_local_functions_rejected(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    """Review 2026-09-22 #9, #10: luật không thấy thứ ORT chạy khi có hàm cục bộ → dạng storage từ chối hết.

    Bản ghim miễn luật cấu trúc nên cùng model đó vẫn nạp được ở dạng ghim.
    """
    for sample in _local_function_models():
        data = sample.SerializeToString()
        ref = storage_ref(data)
        await put(local_storage, ref, data)
        await expect(MODEL_FORMAT_UNSUPPORTED, local_storage, ref, tmp_path)
    data = _local_function_models()[0].SerializeToString()
    (tmp_path / "yolov8n.onnx").write_bytes(data)
    session = await load_onnx(local_storage, pinned_ref(data), models_dir=tmp_path, pinned=pin_table(data))
    assert run(session, 2.0) == 3.0


async def test_load_onnx_m03_control_flow(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    """Dạng storage: `Loop`/`Scan` ở mọi độ sâu (đồ thị chính, `If`, thân hàm, **mặc định thuộc tính hàm**),
    miền lạ, hàm vòng → từ chối; op lạ miền chuẩn → ORT từ chối.

    Ca mặc định thuộc tính là model 578 byte với `Loop` 2^63 - 1 vòng mà review 2026-09-21 (#1)
    dựng được: ORT nạp nó bình thường, nên trước bản sửa `load_onnx` trả phiên thay vì từ chối.
    """
    samples = (
        hidden_in_function_default(loop_graph(2**63 - 1)),
        _hidden_microsoft_op(),
        loop_model(),
        _scan_model(),
        _loop_in_if(),
        _loop_in_function(),
        _cyclic_functions(),
        model([helper.make_node("Attention", ["x"], ["y"], domain="com.microsoft")]),
        model([helper.make_node("FooBar", ["x"], ["y"])]),
    )
    for sample in samples:
        data = sample.SerializeToString()
        ref = storage_ref(data)
        await put(local_storage, ref, data)
        await expect(MODEL_FORMAT_UNSUPPORTED, local_storage, ref, tmp_path)


def test_ort_errors_are_every_real_onnxruntime_error() -> None:
    """`ORT_ERRORS` là **đúng** mọi lớp lỗi của onnxruntime đã khoá; nâng bản mà có lớp mới thì test đỏ."""
    from onnxruntime.capi import onnxruntime_pybind11_state as state  # type: ignore[import-untyped]  # module C++

    real = {value for value in vars(state).values() if isinstance(value, type) and issubclass(value, Exception)}
    assert set(ORT_ERRORS) == real


async def test_load_onnx_m03_pinned_loads(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    """Bản ghim miễn luật cấu trúc (`Loop` nạp được); lượt sau trúng cache, không đọc lại tệp."""
    data = loop_model().SerializeToString()
    (tmp_path / "yolov8n.onnx").write_bytes(data)
    ref = pinned_ref(data)
    session = await load_onnx(local_storage, ref, models_dir=tmp_path, pinned=pin_table(data))
    assert run(session, 0.0) == 3.0
    (tmp_path / "yolov8n.onnx").unlink()
    assert await load_onnx(local_storage, ref, models_dir=tmp_path, pinned=pin_table(data)) is session


async def test_session_cache_keeps_three(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    refs = []
    for value in range(4):
        data = add_model(float(value)).SerializeToString()
        ref = storage_ref(data)
        await put(local_storage, ref, data)
        await load_onnx(local_storage, ref, models_dir=tmp_path)
        refs.append(ref)
    await local_storage.delete(str(refs[0].weights_key))
    await local_storage.delete(str(refs[3].weights_key))
    assert run(await load_onnx(local_storage, refs[3], models_dir=tmp_path), 0.0) == 3.0
    await expect(MODEL_NOT_FOUND, local_storage, refs[0], tmp_path)


async def test_load_onnx_m03_exported_storage(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    """Model torch tí hon → `export_onnx` → storage → `load_onnx` chạy ra cùng số với torch."""
    torch.manual_seed(0)
    net = torch.nn.Sequential(torch.nn.Linear(1, 4), torch.nn.ReLU(), torch.nn.Linear(4, 1))
    path = tmp_path / "net.onnx"
    digest = export_onnx(net, torch.zeros(1), path)
    data = path.read_bytes()
    assert digest == sha(data)
    ref = storage_ref(data)
    await put(local_storage, ref, data)
    session = await load_onnx(local_storage, ref, models_dir=tmp_path)
    expected = float(net(torch.tensor([0.5]))[0])
    assert abs(run(session, 0.5) - expected) < 1e-5
