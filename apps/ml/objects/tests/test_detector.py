"""Test `apps.ml.objects.detector`: dựng, tiền xử lý, toạ độ, lỗi chạy, tất định (khối [8])."""

import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
import pytest
from numpy.typing import NDArray
from onnx import TensorProto, helper, numpy_helper

from apps.ml.objects.detector import YoloOnnxDetector, _preprocess_tile
from apps.ml.objects.tests.onnx_models import make_const_yolo, make_runtime_broken_yolo, yolo_output
from apps.ml.objects.tiles import Window
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.labels import OBJECT_LABELS
from packages.ml_contracts.ports import ObjectDetector


def _session(data: bytes) -> ort.InferenceSession:
    """Phiên ONNX CPU thật từ bytes model (K23: không mock `onnxruntime`)."""
    return ort.InferenceSession(data, providers=["CPUExecutionProvider"])


def _two_input_yolo(output: NDArray[np.float32]) -> bytes:
    """Model hợp lệ (ra đúng hợp đồng) nhưng khai hai đầu vào — `__init__` phải từ chối."""
    const_y = numpy_helper.from_array(output.astype(np.float32), "const_y")
    zero = numpy_helper.from_array(np.array(0.0, dtype=np.float32), "zero")
    nodes = [
        helper.make_node("Constant", [], ["const_y_val"], value=const_y),
        helper.make_node("ReduceSum", ["x"], ["x_sum"], keepdims=0),
        helper.make_node("Mul", ["x_sum", "zero"], ["zero_sum"]),
        helper.make_node("Add", ["const_y_val", "zero_sum"], ["y"]),
    ]
    graph = helper.make_graph(
        nodes,
        "two_in",
        [
            helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 3, 640, 640]),
            helper.make_tensor_value_info("x2", TensorProto.FLOAT, [1, 3, 640, 640]),
        ],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, list(output.shape))],
        initializer=[zero],
    )
    model = helper.make_model(graph, ir_version=10, opset_imports=[helper.make_opsetid("", 17)])
    return bytes(model.SerializeToString())


def _two_output_yolo(output: NDArray[np.float32]) -> bytes:
    """Model hợp lệ ở đầu ra `y` nhưng khai thêm đầu ra `y2` — `__init__` phải từ chối."""
    const_y = numpy_helper.from_array(output.astype(np.float32), "const_y")
    zero = numpy_helper.from_array(np.array(0.0, dtype=np.float32), "zero")
    nodes = [
        helper.make_node("Constant", [], ["const_y_val"], value=const_y),
        helper.make_node("ReduceSum", ["x"], ["x_sum"], keepdims=0),
        helper.make_node("Mul", ["x_sum", "zero"], ["zero_sum"]),
        helper.make_node("Add", ["const_y_val", "zero_sum"], ["y"]),
        helper.make_node("Identity", ["y"], ["y2"]),
    ]
    graph = helper.make_graph(
        nodes,
        "two_out",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 3, 640, 640])],
        [
            helper.make_tensor_value_info("y", TensorProto.FLOAT, list(output.shape)),
            helper.make_tensor_value_info("y2", TensorProto.FLOAT, list(output.shape)),
        ],
        initializer=[zero],
    )
    model = helper.make_model(graph, ir_version=10, opset_imports=[helper.make_opsetid("", 17)])
    return bytes(model.SerializeToString())


def test_init__rejects_dynamic_input_size() -> None:
    """Chiều `S` động (chuỗi, không phải `int` tĩnh) → `MODEL_FORMAT_UNSUPPORTED`."""
    data = make_const_yolo(yolo_output([], nc=1), input_shape=(1, 3, "S", "S"))
    with pytest.raises(PermanentError) as excinfo:
        YoloOnnxDetector(_session(data), ("door",))
    assert excinfo.value.code == "MODEL_FORMAT_UNSUPPORTED"


def test_init__rejects_non_square_input() -> None:
    """`S` khác nhau ở hai trục (640 và 480) → `MODEL_FORMAT_UNSUPPORTED`."""
    data = make_const_yolo(yolo_output([], nc=1), input_shape=(1, 3, 640, 480))
    with pytest.raises(PermanentError) as excinfo:
        YoloOnnxDetector(_session(data), ("door",))
    assert excinfo.value.code == "MODEL_FORMAT_UNSUPPORTED"


def test_init__rejects_size_not_divisible_by_32() -> None:
    """`S = 100` không chia hết 32 → `MODEL_FORMAT_UNSUPPORTED`."""
    data = make_const_yolo(yolo_output([], nc=1), input_shape=(1, 3, 100, 100))
    with pytest.raises(PermanentError) as excinfo:
        YoloOnnxDetector(_session(data), ("door",))
    assert excinfo.value.code == "MODEL_FORMAT_UNSUPPORTED"


def test_init__rejects_wrong_channel_count() -> None:
    """Kênh vào khác 3 → `MODEL_FORMAT_UNSUPPORTED`."""
    data = make_const_yolo(yolo_output([], nc=1), input_shape=(1, 4, 640, 640))
    with pytest.raises(PermanentError) as excinfo:
        YoloOnnxDetector(_session(data), ("door",))
    assert excinfo.value.code == "MODEL_FORMAT_UNSUPPORTED"


def test_init__rejects_size_below_32() -> None:
    """`S = 16` dưới trần tối thiểu → `MODEL_FORMAT_UNSUPPORTED`."""
    data = make_const_yolo(yolo_output([], nc=1), input_shape=(1, 3, 16, 16))
    with pytest.raises(PermanentError) as excinfo:
        YoloOnnxDetector(_session(data), ("door",))
    assert excinfo.value.code == "MODEL_FORMAT_UNSUPPORTED"


def test_init__rejects_channel_count_mismatch_with_labels() -> None:
    """Model khai `nc=80` nhưng truyền `OBJECT_LABELS` (10 lớp) → `MODEL_FORMAT_UNSUPPORTED`."""
    data = make_const_yolo(yolo_output([], nc=80))
    with pytest.raises(PermanentError) as excinfo:
        YoloOnnxDetector(_session(data), OBJECT_LABELS)
    assert excinfo.value.code == "MODEL_FORMAT_UNSUPPORTED"


def test_init__rejects_two_inputs() -> None:
    """Model khai hai đầu vào → `MODEL_FORMAT_UNSUPPORTED` (đúng 1 đầu vào theo khối [2])."""
    data = _two_input_yolo(yolo_output([], nc=1))
    with pytest.raises(PermanentError) as excinfo:
        YoloOnnxDetector(_session(data), ("door",))
    assert excinfo.value.code == "MODEL_FORMAT_UNSUPPORTED"


def test_init__rejects_two_outputs() -> None:
    """Model khai hai đầu ra → `MODEL_FORMAT_UNSUPPORTED` (đúng 1 đầu ra theo khối [2])."""
    data = _two_output_yolo(yolo_output([], nc=1))
    with pytest.raises(PermanentError) as excinfo:
        YoloOnnxDetector(_session(data), ("door",))
    assert excinfo.value.code == "MODEL_FORMAT_UNSUPPORTED"


def test_init__rejects_unknown_label() -> None:
    """Nhãn ngoài `ARTIFACT_LABELS` (và khác `None`) → `ValueError` qua `check_labels`."""
    data = make_const_yolo(yolo_output([], nc=1))
    # cố ý sai kiểu để test check_labels ở runtime
    bad_labels: tuple[str, ...] = ("not_a_real_label",)
    with pytest.raises(ValueError, match="nhãn ngoài"):
        YoloOnnxDetector(_session(data), bad_labels)  # type: ignore[arg-type]


def test_init__input_px_matches_declared_size() -> None:
    """`.input_px` đọc đúng `S` model khai (64), không hằng cứng 640."""
    data = make_const_yolo(yolo_output([], nc=1), input_shape=(1, 3, 64, 64))
    detector = YoloOnnxDetector(_session(data), ("door",))
    assert detector.input_px == 64


def test_preprocess_tile__pads_edge_without_scaling() -> None:
    """Lát sát mép: phần thật giữ nguyên giá trị, phần đệm là 114/255, không co giãn."""
    image = np.zeros((50, 40, 3), dtype=np.uint8)
    image[:, :, 0] = 200
    window = Window(0, 0, 40, 50)
    tensor = _preprocess_tile(image, window, input_px=64)
    assert tensor.shape == (1, 3, 64, 64)
    assert np.allclose(tensor[0, 0, :50, :40], 200 / 255.0)
    assert np.allclose(tensor[0, 0, 50:, :], 114 / 255.0)
    assert np.allclose(tensor[0, 0, :, 40:], 114 / 255.0)
    assert np.allclose(tensor[0, 1, :50, :40], 0.0)


def test_detect__page_coordinates_correct_at_every_tile() -> None:
    """Trang 1000x700 chia 4 lát chồng mép; model trả cùng hộp tương đối ở mọi lát."""
    output = yolo_output([(100, 120, 40, 30, 0, 0.9)], nc=1)
    detector = YoloOnnxDetector(_session(make_const_yolo(output)), ("door",))
    detections = detector.detect(np.zeros((700, 1000, 3), dtype=np.uint8))
    assert len(detections) == 4
    expected_origins = {(0, 0), (360, 0), (0, 60), (360, 60)}
    seen_origins = {(round(d.box.x_min - 80.0), round(d.box.y_min - 105.0)) for d in detections}
    assert seen_origins == expected_origins
    for d in detections:
        ox, oy = round(d.box.x_min - 80.0), round(d.box.y_min - 105.0)
        assert abs(d.box.x_min - (ox + 80.0)) <= 0.01
        assert abs(d.box.y_min - (oy + 105.0)) <= 0.01
        assert abs(d.box.x_max - (ox + 120.0)) <= 0.01
        assert abs(d.box.y_max - (oy + 135.0)) <= 0.01


def test_detect__runtime_error_maps_to_permanent_error() -> None:
    """`session.run` vỡ lúc chạy (hình khai đúng, dữ liệu sai) → `MODEL_FORMAT_UNSUPPORTED`."""
    detector = YoloOnnxDetector(_session(make_runtime_broken_yolo(size=64, nc=1)), ("door",))
    with pytest.raises(PermanentError) as excinfo:
        detector.detect(np.zeros((64, 64, 3), dtype=np.uint8))
    assert excinfo.value.code == "MODEL_FORMAT_UNSUPPORTED"


def test_detect__deterministic_across_runs() -> None:
    """Cùng ảnh, cùng phiên: hai lượt `detect` ra kết quả bằng nhau hệt (M01)."""
    output = yolo_output([(30, 30, 10, 10, 0, 0.9)], nc=1)
    detector = YoloOnnxDetector(_session(make_const_yolo(output, input_shape=(1, 3, 64, 64))), ("door",))
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    assert detector.detect(image) == detector.detect(image)


def test_detect__satisfies_object_detector_protocol() -> None:
    """`YoloOnnxDetector` gán được vào biến kiểu `ObjectDetector` (B5-01) và trả `tuple`."""
    output = yolo_output([], nc=1)
    detector: ObjectDetector = YoloOnnxDetector(
        _session(make_const_yolo(output, input_shape=(1, 3, 64, 64))), ("door",)
    )
    assert isinstance(detector.detect(np.zeros((64, 64, 3), dtype=np.uint8)), tuple)
