"""Test `convert.py`: chọn ảnh, mặt nạ tường, hộp cửa/đồ, tỉ lệ mực (B6-02b [8], việc C)."""

import numpy as np
import pytest

from apps.worker.datasets_cubicasa.convert import (
    FIXTURE_LABELS,
    ImageChoice,
    boxes_from_labels,
    choose_image,
    ink_ratio,
    wall_mask_from_polygons,
)
from apps.worker.datasets_cubicasa.svg import SvgLabels
from apps.worker.datasets_cubicasa.tests.fake_cubicasa import Room, rect, room, room_pixels


def _labels_from_room(room_spec: Room) -> SvgLabels:
    """Dựng `SvgLabels` thẳng từ `Room` chuẩn (không qua `parse_model_svg`, như spec việc C đòi)."""
    return SvgLabels(
        width=room_spec.width,
        height=room_spec.height,
        walls=room_spec.walls,
        doors=room_spec.doors,
        windows=room_spec.windows,
        fixtures=room_spec.fixtures,
        skipped={},
    )


def test_choose_image_picks_f1_scaled() -> None:
    """Có `F1_scaled.png` → chọn nó, `sx == sy == 1`, nhánh `identity`, `fit` đúng tỉ lệ."""
    choice = choose_image((320, 240), {"F1_scaled.png": (336, 252), "F1_original.png": (160, 120)})
    assert choice is not None
    assert choice.filename == "F1_scaled.png"
    assert choice.sx == 1.0
    assert choice.sy == 1.0
    assert choice.branch == "identity"
    assert choice.fit_x == pytest.approx(1.05)
    assert choice.fit_y == pytest.approx(1.05)


def test_choose_image_missing_scaled_returns_none() -> None:
    """Thiếu `F1_scaled.png` (chỉ có `F1_original.png`) → `None`, importer bỏ mẫu `no_image`."""
    assert choose_image((320, 240), {"F1_original.png": (160, 120)}) is None


def test_choose_image_no_sizes_returns_none() -> None:
    """Không có ảnh nào → `None`."""
    assert choose_image((320, 240), {}) is None


def test_wall_mask_from_polygons_standard_room_pixel_count() -> None:
    """Phòng chuẩn 320x240: mặt nạ có đúng 8163 pixel True (đo lại trong container sau khi tô từng đa giác —
    số 7967 của bản tô một lệnh/chẵn-lẻ toàn cục đã sai, xem `test...wall_corners_are_filled`)."""
    room_spec = room()
    labels = _labels_from_room(room_spec)
    choice = ImageChoice("F1_scaled.png", 1.0, 1.0, "identity", 1.0, 1.0)
    mask = wall_mask_from_polygons(labels, choice, width_px=room_spec.width, height_px=room_spec.height)
    assert mask.dtype == np.bool_
    assert mask.shape == (room_spec.height, room_spec.width)
    assert int(mask.sum()) == 8163


def test_wall_mask_from_polygons_wall_corners_are_filled() -> None:
    """Góc nơi hai tường chạm/chồng nhau phải True ở cả bốn góc (tô từng đa giác, không chẵn-lẻ toàn cục).

    `fillPoly` nhiều đường viền trong một lệnh tô theo luật chẵn-lẻ toàn cục nên góc chồng của hai
    hình chữ nhật từng bị huỷ thành lỗ (đo trong container: `(24, 19)` = 0 khi tô một lệnh, = 1 khi
    tô từng đa giác); tường CubiCasa thật chồng ở góc/chữ T nên lỗi này ăn thẳng vào mẫu thật.
    """
    room_spec = room()
    labels = _labels_from_room(room_spec)
    choice = ImageChoice("F1_scaled.png", 1.0, 1.0, "identity", 1.0, 1.0)
    mask = wall_mask_from_polygons(labels, choice, width_px=room_spec.width, height_px=room_spec.height)
    assert mask[19, 24]  # góc trên-trái (tường trên chạm tường trái)
    assert mask[221, 24]  # góc dưới-trái
    assert mask[19, 291]  # góc trên-phải
    assert mask[221, 291]  # góc dưới-phải


def test_wall_mask_from_polygons_overlapping_doors_both_erased() -> None:
    """Hai khe cửa chồng lên nhau: cả hai đều bị xoá (vòng theo từng đa giác cửa, không chỉ đa giác đầu)."""
    labels = SvgLabels(
        width=100,
        height=100,
        walls=(rect(0, 0, 100, 100),),
        doors=(rect(10, 10, 30, 30), rect(20, 20, 40, 40)),
        windows=(),
        fixtures=(),
        skipped={},
    )
    choice = ImageChoice("F1_scaled.png", 1.0, 1.0, "identity", 1.0, 1.0)
    mask = wall_mask_from_polygons(labels, choice, width_px=100, height_px=100)
    assert not mask[15, 15]  # chỉ trong khe cửa thứ nhất
    assert not mask[35, 35]  # chỉ trong khe cửa thứ hai
    assert not mask[25, 25]  # vùng chồng của hai khe
    assert mask[5, 5]  # ngoài hai khe vẫn là tường


def test_wall_mask_from_polygons_wall_door_window_room_points() -> None:
    """Giữa mỗi tường True, giữa khe cửa False, giữa phòng False, giữa cửa sổ vẫn True (tường vẫn tô)."""
    room_spec = room()
    labels = _labels_from_room(room_spec)
    choice = ImageChoice("F1_scaled.png", 1.0, 1.0, "identity", 1.0, 1.0)
    mask = wall_mask_from_polygons(labels, choice, width_px=room_spec.width, height_px=room_spec.height)
    assert mask[19, 160]  # giữa tường trên, xa góc
    assert mask[221, 60]  # tường dưới, xa góc và xa khe cửa
    assert mask[120, 22]  # giữa tường trái theo chiều dọc
    assert mask[120, 296]  # giữa tường phải theo chiều dọc
    door = room_spec.doors[0]
    dx0, dy0, dx1, dy1 = door[0][0], door[0][1], door[2][0], door[2][1]
    assert not mask[int((dy0 + dy1) / 2), int((dx0 + dx1) / 2)]
    assert not mask[room_spec.height // 2, room_spec.width // 2]
    window = room_spec.windows[0]
    wx0, wy0, wx1, wy1 = window[0][0], window[0][1], window[2][0], window[2][1]
    assert mask[int((wy0 + wy1) / 2), int((wx0 + wx1) / 2)]


def test_wall_mask_from_polygons_rounds_half_pixel_corners() -> None:
    """Tường toạ độ `.4`/`.6`: biên mặt nạ làm tròn theo `np.round` (0,5 lên)."""
    labels = SvgLabels(
        width=100, height=60, walls=(rect(10.4, 20.6, 50.4, 28.6),), doors=(), windows=(), fixtures=(), skipped={}
    )
    choice = ImageChoice("F1_scaled.png", 1.0, 1.0, "identity", 1.0, 1.0)
    mask = wall_mask_from_polygons(labels, choice, width_px=100, height_px=60)
    assert mask[21, 10]
    assert not mask[21, 9]
    assert mask[21, 50]


def test_wall_mask_from_polygons_polygon_overflowing_canvas_is_clipped() -> None:
    """Đa giác tràn ngoài khổ ảnh: `cv2.fillPoly` tự cắt, không lỗi."""
    labels = SvgLabels(
        width=20, height=20, walls=(rect(-10, -10, 15, 15),), doors=(), windows=(), fixtures=(), skipped={}
    )
    choice = ImageChoice("F1_scaled.png", 1.0, 1.0, "identity", 1.0, 1.0)
    mask = wall_mask_from_polygons(labels, choice, width_px=20, height_px=20)
    assert mask.shape == (20, 20)
    assert mask[5, 5]


def test_wall_mask_from_polygons_no_walls_is_empty() -> None:
    """Không tường → mặt nạ rỗng toàn `False` (importer bỏ mẫu `no_labels`)."""
    labels = SvgLabels(width=10, height=10, walls=(), doors=(), windows=(), fixtures=(), skipped={})
    choice = ImageChoice("F1_scaled.png", 1.0, 1.0, "identity", 1.0, 1.0)
    mask = wall_mask_from_polygons(labels, choice, width_px=10, height_px=10)
    assert not mask.any()


def test_ink_ratio_standard_room() -> None:
    """Mặt nạ phòng chuẩn với ảnh phòng chuẩn → tỉ lệ mực (đo lại trong container, tô từng đa giác)."""
    room_spec = room()
    labels = _labels_from_room(room_spec)
    choice = ImageChoice("F1_scaled.png", 1.0, 1.0, "identity", 1.0, 1.0)
    mask = wall_mask_from_polygons(labels, choice, width_px=room_spec.width, height_px=room_spec.height)
    ratio = ink_ratio(mask, room_pixels(room_spec))
    assert ratio is not None
    assert ratio == pytest.approx(0.8889, abs=0.001)


def test_ink_ratio_empty_mask_is_none() -> None:
    """Mặt nạ rỗng → `None` (không chia 0)."""
    mask = np.zeros((10, 10), dtype=bool)
    pixels = np.full((10, 10, 3), 255, dtype=np.uint8)
    assert ink_ratio(mask, pixels) is None


def test_ink_ratio_all_white_image_is_zero() -> None:
    """Mặt nạ có tường nhưng ảnh toàn trắng → tỉ lệ mực 0 (không nhãn nào thấy mực)."""
    mask = np.zeros((10, 10), dtype=bool)
    mask[2:5, 2:5] = True
    pixels = np.full((10, 10, 3), 255, dtype=np.uint8)
    assert ink_ratio(mask, pixels) == 0.0


def test_ink_ratio_shape_mismatch_raises() -> None:
    """Khổ mặt nạ khác khổ ảnh → `ValueError`."""
    mask = np.zeros((10, 10), dtype=bool)
    mask[0, 0] = True
    pixels = np.full((20, 20, 3), 0, dtype=np.uint8)
    with pytest.raises(ValueError, match="khổ"):
        ink_ratio(mask, pixels)


def test_boxes_from_labels_standard_room_boxes() -> None:
    """Phòng chuẩn: hộp cửa/cửa sổ/đồ đúng đáp án, `BaseCabinet` đếm vào tên đồ lạ."""
    room_spec = room()
    labels = _labels_from_room(room_spec)
    choice = ImageChoice("F1_scaled.png", 1.0, 1.0, "identity", 1.0, 1.0)
    detections, unknown = boxes_from_labels(labels, choice, width_px=room_spec.width, height_px=room_spec.height)
    by_label = {d.label: d.box for d in detections}
    assert by_label["door"].x_min == pytest.approx(140, abs=1)
    assert by_label["door"].y_min == pytest.approx(217, abs=1)
    assert by_label["door"].x_max == pytest.approx(180, abs=1)
    assert by_label["door"].y_max == pytest.approx(225, abs=1)
    assert by_label["window"].x_min == pytest.approx(60, abs=1)
    assert by_label["window"].y_min == pytest.approx(15, abs=1)
    assert by_label["window"].x_max == pytest.approx(100, abs=1)
    assert by_label["window"].y_max == pytest.approx(23, abs=1)
    assert by_label["sanitary_fixture"].x_min == pytest.approx(44, abs=1)
    assert by_label["sanitary_fixture"].y_min == pytest.approx(39, abs=1)
    assert by_label["sanitary_fixture"].x_max == pytest.approx(76, abs=1)
    assert by_label["sanitary_fixture"].y_max == pytest.approx(79, abs=1)
    assert all(d.confidence == 1.0 for d in detections)
    assert unknown == {"BaseCabinet": 1}


def test_boxes_from_labels_order_follows_svg_order() -> None:
    """Thứ tự phát hiện: cửa, cửa sổ, rồi đồ đạc theo thứ tự SVG."""
    room_spec = room()
    labels = _labels_from_room(room_spec)
    choice = ImageChoice("F1_scaled.png", 1.0, 1.0, "identity", 1.0, 1.0)
    detections, _ = boxes_from_labels(labels, choice, width_px=room_spec.width, height_px=room_spec.height)
    assert [d.label for d in detections] == ["door", "window", "sanitary_fixture"]


def test_boxes_from_labels_overflowing_box_is_clamped() -> None:
    """Hộp tràn ngoài khổ ảnh: kẹp vào `[0, width] x [0, height]`."""
    labels = SvgLabels(
        width=20, height=20, walls=(), doors=(rect(-5, -5, 15, 15),), windows=(), fixtures=(), skipped={}
    )
    choice = ImageChoice("F1_scaled.png", 1.0, 1.0, "identity", 1.0, 1.0)
    detections, _ = boxes_from_labels(labels, choice, width_px=20, height_px=20)
    assert len(detections) == 1
    box = detections[0].box
    assert box.x_min == 0.0
    assert box.y_min == 0.0
    assert box.x_max == 15.0
    assert box.y_max == 15.0


def test_boxes_from_labels_box_entirely_outside_canvas_is_dropped() -> None:
    """Hộp nằm hẳn ngoài khổ ảnh: sau kẹp `x_max <= x_min` → bỏ, không tạo `DetectionPx`."""
    labels = SvgLabels(
        width=20, height=20, walls=(), doors=(rect(30, 30, 40, 40),), windows=(), fixtures=(), skipped={}
    )
    choice = ImageChoice("F1_scaled.png", 1.0, 1.0, "identity", 1.0, 1.0)
    detections, unknown = boxes_from_labels(labels, choice, width_px=20, height_px=20)
    assert detections == ()
    assert unknown == {}


def test_boxes_from_labels_closet_maps_to_wardrobe() -> None:
    """`Closet` (bảng `FIXTURE_LABELS`) → nhãn `wardrobe`."""
    labels = SvgLabels(
        width=20, height=20, walls=(), doors=(), windows=(), fixtures=(("Closet", rect(1, 1, 5, 5)),), skipped={}
    )
    choice = ImageChoice("F1_scaled.png", 1.0, 1.0, "identity", 1.0, 1.0)
    detections, unknown = boxes_from_labels(labels, choice, width_px=20, height_px=20)
    assert len(detections) == 1
    assert detections[0].label == "wardrobe"
    assert unknown == {}


def test_boxes_from_labels_empty_fixture_name_counts_as_unknown() -> None:
    """Tên đồ rỗng (`""`) không khớp bảng `FIXTURE_LABELS` → đếm vào tên đồ lạ, không tạo hộp."""
    labels = SvgLabels(
        width=20, height=20, walls=(), doors=(), windows=(), fixtures=(("", rect(1, 1, 5, 5)),), skipped={}
    )
    choice = ImageChoice("F1_scaled.png", 1.0, 1.0, "identity", 1.0, 1.0)
    detections, unknown = boxes_from_labels(labels, choice, width_px=20, height_px=20)
    assert detections == ()
    assert unknown == {"": 1}


def test_fixture_labels_exact_names_no_guessing() -> None:
    """`FIXTURE_LABELS` chỉ chứa đúng 5 tên bảng spec, không đoán thêm tên khác."""
    assert dict(FIXTURE_LABELS) == {
        "Toilet": "sanitary_fixture",
        "Sink": "sanitary_fixture",
        "Bathtub": "sanitary_fixture",
        "Shower": "sanitary_fixture",
        "Closet": "wardrobe",
    }
