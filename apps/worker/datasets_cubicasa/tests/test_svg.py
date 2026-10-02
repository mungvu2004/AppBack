"""Test `parse_model_svg` (B6-02b [8], việc B): không tin byte nào của `model.svg`, toạ độ pixel 1:1."""

import tracemalloc

import pytest

from apps.worker.datasets_cubicasa.svg import SvgRejectedError, parse_model_svg
from apps.worker.datasets_cubicasa.tests.fake_cubicasa import bounds, room, room_svg
from packages.ml_contracts.artifacts import MAX_DETECTIONS, MAX_WALLS

SVG_NS = 'xmlns="http://www.w3.org/2000/svg"'


def _svg(body: str, *, view_box: str = "0 0 100 100") -> bytes:
    """SVG tối giản cho test đơn vị của một luật riêng (không cần cấu trúc CubiCasa đầy đủ)."""
    return f'<svg {SVG_NS} viewBox="{view_box}">{body}</svg>'.encode()


def test_parse_model_svg_room_labels() -> None:
    """Phòng chuẩn: 4 tường, 1 cửa, 1 cửa sổ, 2 đồ; hộp khớp đáp án; `Space`/`Railing` không tạo nhãn."""
    spec = room()
    labels = parse_model_svg(room_svg(spec), max_bytes=1_000_000)
    assert len(labels.walls) == 4
    assert len(labels.doors) == 1
    assert len(labels.windows) == 1
    assert len(labels.fixtures) == 2
    for got, want in zip(labels.walls, spec.walls, strict=True):
        for (gx, gy), (wx, wy) in zip(got, want, strict=True):
            assert gx == pytest.approx(wx, abs=1e-6)
            assert gy == pytest.approx(wy, abs=1e-6)
    assert bounds(labels.doors[0]) == bounds(spec.doors[0])
    assert bounds(labels.windows[0]) == bounds(spec.windows[0])
    names = {name for name, _ in labels.fixtures}
    assert names == {"Toilet", "BaseCabinet"}
    for name, box in labels.fixtures:
        want_box = next(b for n, b in spec.fixtures if n == name)
        assert bounds(box) == bounds(want_box)
    assert labels.skipped == {}


def test_parse_model_svg_origin_shift_matches_zero_origin() -> None:
    """`room_svg(origin=(10, 20))` (viewBox dời cùng lượng) → toạ độ trùng bản gốc, sai số ≤ 0,5 px."""
    spec = room()
    base = parse_model_svg(room_svg(spec), max_bytes=1_000_000)
    shifted = parse_model_svg(room_svg(spec, origin=(10, 20)), max_bytes=1_000_000)
    for got, want in zip(shifted.walls, base.walls, strict=True):
        for (gx, gy), (wx, wy) in zip(got, want, strict=True):
            assert gx == pytest.approx(wx, abs=0.5)
            assert gy == pytest.approx(wy, abs=0.5)


def test_parse_model_svg_billion_laughs_rejected_with_low_memory() -> None:
    """Thực thể lồng kiểu billion laughs → `svg_rejected`, đỉnh bộ nhớ < 8 MiB (bỏ trước khi parse)."""
    payload = (
        b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
        + b"".join(f'<!ENTITY lol{i} "&lol{i - 1};&lol{i - 1};">'.encode() for i in range(1, 10))
        + b"]><svg><lolz>&lol9;</lolz></svg>"
    )
    tracemalloc.start()
    try:
        with pytest.raises(SvgRejectedError) as exc_info:
            parse_model_svg(payload, max_bytes=1_000_000)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert exc_info.value.reason == "svg_rejected"
    assert peak < 8 * 1024 * 1024


def test_parse_model_svg_doctype_system_rejected() -> None:
    """`<!DOCTYPE svg SYSTEM "file:///etc/passwd">` → `svg_rejected` (không mở tệp, không tải mạng)."""
    payload = b'<?xml version="1.0"?><!DOCTYPE svg SYSTEM "file:///etc/passwd"><svg></svg>'
    with pytest.raises(SvgRejectedError) as exc_info:
        parse_model_svg(payload, max_bytes=1_000_000)
    assert exc_info.value.reason == "svg_rejected"


def test_parse_model_svg_lowercase_doctype_rejected() -> None:
    """`<!doctype` chữ thường vẫn bị chặn (regex không phân biệt hoa thường)."""
    payload = b'<?xml version="1.0"?><!doctype svg><svg></svg>'
    with pytest.raises(SvgRejectedError) as exc_info:
        parse_model_svg(payload, max_bytes=1_000_000)
    assert exc_info.value.reason == "svg_rejected"


@pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be"])
def test_parse_model_svg_utf16_with_bom_rejected(codec: str) -> None:
    """UTF-16 (LE/BE, BOM) chứa thực thể → `svg_rejected` (byte NUL chặn trước khi xem nội dung)."""
    bom = b"\xff\xfe" if codec == "utf-16-le" else b"\xfe\xff"
    text = '<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x "y">]><svg></svg>'
    payload = bom + text.encode(codec)
    with pytest.raises(SvgRejectedError) as exc_info:
        parse_model_svg(payload, max_bytes=1_000_000)
    assert exc_info.value.reason == "svg_rejected"


def test_parse_model_svg_too_many_bytes_rejected() -> None:
    """17 MiB với `max_bytes=16 MiB` → `svg_rejected` trước khi parse."""
    payload = b"<svg>" + b" " * (17 * 1024 * 1024) + b"</svg>"
    with pytest.raises(SvgRejectedError) as exc_info:
        parse_model_svg(payload, max_bytes=16 * 1024 * 1024)
    assert exc_info.value.reason == "svg_rejected"


def test_parse_model_svg_malformed_xml_raises_value_error_not_rejected() -> None:
    """XML hỏng cú pháp → `ValueError` thường, không phải `SvgRejectedError`."""
    with pytest.raises(ValueError, match="invalid svg xml") as exc_info:
        parse_model_svg(b"<svg><unclosed></svg>", max_bytes=1_000_000)
    assert not isinstance(exc_info.value, SvgRejectedError)


def test_parse_model_svg_non_svg_root_raises_value_error() -> None:
    """Gốc không phải `svg` → `ValueError`."""
    with pytest.raises(ValueError, match="root element is not svg"):
        parse_model_svg(b'<?xml version="1.0"?><root/>', max_bytes=1_000_000)


def test_parse_model_svg_missing_size_raises_value_error() -> None:
    """Thiếu cả `viewBox` lẫn `width`/`height` → `ValueError`."""
    with pytest.raises(ValueError, match="missing or invalid svg size"):
        parse_model_svg(f"<svg {SVG_NS}></svg>".encode(), max_bytes=1_000_000)


def test_parse_model_svg_width_height_fallback_without_viewbox() -> None:
    """Vắng `viewBox` → dùng `width`/`height` của gốc, CTM đơn vị (không dời gốc)."""
    body = '<g class="Wall"><polygon points="0,0 10,0 10,10 0,10"/></g>'
    data = f'<svg {SVG_NS} width="50px" height="40">{body}</svg>'.encode()
    labels = parse_model_svg(data, max_bytes=1_000_000)
    assert (labels.width, labels.height) == (50.0, 40.0)
    assert labels.walls == (((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),)


def test_parse_model_svg_nested_translate_scale_matrix() -> None:
    """`translate` + `scale` + `matrix` lồng ba tầng → toạ độ đúng (tính tay)."""
    body = (
        '<g transform="translate(10,20)"><g transform="scale(2,3)">'
        '<g transform="matrix(1,0,0,1,5,5)"><g class="Wall">'
        '<polygon points="0,0 1,0 1,1 0,1"/></g></g></g></g>'
    )
    labels = parse_model_svg(_svg(body, view_box="0 0 100 100"), max_bytes=1_000_000)
    assert labels.walls == (((20.0, 35.0), (22.0, 35.0), (22.0, 38.0), (20.0, 38.0)),)


def test_parse_model_svg_combined_transform_functions_in_one_attribute() -> None:
    """Nhiều phép trong một thuộc tính `transform` → ghép đúng như hai tầng riêng."""
    body = '<g transform="translate(10,20) scale(2,3)"><g class="Wall"><polygon points="0,0 1,0 1,1 0,1"/></g></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.walls == (((10.0, 20.0), (12.0, 20.0), (12.0, 23.0), (10.0, 23.0)),)


def test_parse_model_svg_rotate_around_point() -> None:
    """`rotate(90 cx cy)` quanh một điểm → toạ độ đúng ±0,5 px (tính tay)."""
    body = '<g class="Wall" transform="rotate(90 10 5)"><polygon points="11,5 12,5 12,6 11,6"/></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    want = ((10.0, 6.0), (10.0, 7.0), (9.0, 7.0), (9.0, 6.0))
    for (gx, gy), (wx, wy) in zip(labels.walls[0], want, strict=True):
        assert gx == pytest.approx(wx, abs=1e-9)
        assert gy == pytest.approx(wy, abs=1e-9)


def test_parse_model_svg_rotate_single_argument_around_origin() -> None:
    """`rotate(a)` (một đối số, không tâm) → quay quanh gốc toạ độ."""
    body = '<g class="Wall" transform="rotate(90)"><polygon points="1,0 2,0 2,1 1,1"/></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    want = ((0.0, 1.0), (0.0, 2.0), (-1.0, 2.0), (-1.0, 1.0))
    for (gx, gy), (wx, wy) in zip(labels.walls[0], want, strict=True):
        assert gx == pytest.approx(wx, abs=1e-9)
        assert gy == pytest.approx(wy, abs=1e-9)


@pytest.mark.parametrize(
    "transform",
    [
        "skewX(10)",
        "skewY(5)",
        "translate(1,2,3)",
        "scale(1,2,3)",
        "matrix(1,2,3)",
        "rotate(1,2)",
        "foo",
        "scale(,)",
    ],
)
def test_parse_model_svg_unsupported_transform_drops_subtree(transform: str) -> None:
    """Tên lạ hay sai số đối số → bỏ phần tử và cả cây con, đếm `transform_unsupported`."""
    body = f'<g transform="{transform}"><g class="Wall"><polygon points="0,0 1,0 1,1 0,1"/></g></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.walls == ()
    assert labels.skipped == {"transform_unsupported": 1}


def test_parse_model_svg_polygon_own_transform_applied_in_wall() -> None:
    """`transform` đặt trên chính `polygon` (không phải nhóm `Wall`) vẫn được áp dụng."""
    body = '<g class="Wall"><polygon transform="translate(10,0)" points="0,0 1,0 1,1 0,1"/></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.walls == (((10.0, 0.0), (11.0, 0.0), (11.0, 1.0), (10.0, 1.0)),)


def test_parse_model_svg_polygon_own_transform_applied_in_door() -> None:
    """`transform` đặt trên chính `polygon` của `Door` vẫn được áp dụng."""
    body = '<g class="Door Swing"><polygon transform="translate(0,5)" points="0,0 1,0 1,1 0,1"/></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.doors == (((0.0, 5.0), (1.0, 5.0), (1.0, 6.0), (0.0, 6.0)),)


def test_parse_model_svg_rect_own_transform_applied_in_fixture() -> None:
    """`transform` đặt trên chính `rect` của `FixedFurniture` vẫn được áp dụng."""
    body = '<g class="FixedFurniture Chair"><rect transform="translate(2,3)" x="0" y="0" width="4" height="5"/></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.fixtures == (("Chair", ((2.0, 3.0), (6.0, 3.0), (6.0, 8.0), (2.0, 8.0))),)


def test_parse_model_svg_polygon_own_unsupported_transform_dropped() -> None:
    """`skewX` trên chính `polygon` (không phải tổ tiên) → bỏ phần tử, đếm `transform_unsupported`."""
    body = '<g class="Wall"><polygon transform="skewX(10)" points="0,0 1,0 1,1 0,1"/></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.walls == ()
    assert labels.skipped == {"transform_unsupported": 1}


def test_parse_model_svg_door_polygon_own_unsupported_transform_dropped() -> None:
    """`skewX` trên chính `polygon` của `Door` → bỏ, đếm `transform_unsupported` (không `polygon_invalid`)."""
    body = '<g class="Door Swing"><polygon transform="skewX(5)" points="0,0 1,0 1,1 0,1"/></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.doors == ()
    assert labels.skipped == {"transform_unsupported": 1}


def test_parse_model_svg_door_invalid_polygon_counted() -> None:
    """Đa giác `< 3 điểm` trong `Door` → bỏ, đếm `polygon_invalid`."""
    body = '<g class="Door Swing"><polygon points="0,0 1,0"/></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.doors == ()
    assert labels.skipped == {"polygon_invalid": 1}


def test_parse_model_svg_wall_group_child_then_polygon_sibling() -> None:
    """`Wall` có nhóm con đứng trước `polygon`: nhóm con duyệt tiếp, vẫn tới `polygon` tường kế đó."""
    body = (
        '<g class="Wall"><g class="Other"><polygon points="9,9 9,10 10,10 10,9"/></g>'
        '<polygon points="0,0 10,0 10,10 0,10"/></g>'
    )
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert len(labels.walls) == 1


def test_parse_model_svg_door_group_child_then_polygon_sibling() -> None:
    """`Door` có nhóm con (`PanelArea`) đứng trước `polygon`: nhóm con duyệt tiếp, vẫn tới `polygon` cửa kế đó."""
    body = (
        '<g class="Door Swing"><g class="PanelArea"><polygon points="0,0 1,0 1,1 0,1"/></g>'
        '<polygon points="2,0 3,0 3,1 2,1"/></g>'
    )
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert len(labels.doors) == 1


def test_parse_model_svg_viewbox_wrong_count_raises_value_error() -> None:
    """`viewBox` không đủ 4 số → `ValueError`."""
    with pytest.raises(ValueError, match="invalid viewBox"):
        parse_model_svg(f'<svg {SVG_NS} viewBox="0 0 100"></svg>'.encode(), max_bytes=1_000_000)


def test_parse_model_svg_viewbox_non_positive_size_raises_value_error() -> None:
    """`viewBox` có khổ không dương → `ValueError`."""
    with pytest.raises(ValueError, match="invalid viewBox size"):
        parse_model_svg(f'<svg {SVG_NS} viewBox="0 0 0 100"></svg>'.encode(), max_bytes=1_000_000)


def test_parse_model_svg_fixture_fallback_skips_line_path_and_bad_transform() -> None:
    """Quét gộp `FixedFurniture` không `BoundaryPolygon`: `path` bị bỏ, `line` bị bỏ, nhóm con lẫn `polygon` có
    `transform` không hỗ trợ bị bỏ (đếm `transform_unsupported`), chỉ `rect` hợp lệ góp hộp bao."""
    body = (
        '<g class="FixedFurniture Desk">'
        '<path d="M0 0 L1 1"/>'
        '<line x1="0" y1="0" x2="1" y2="1"/>'
        '<g transform="skewX(5)"><polygon points="0,0 1,0 1,1 0,1"/></g>'
        '<polygon transform="skewX(3)" points="9,9 9,10 10,10 10,9"/>'
        '<rect x="0" y="0" width="2" height="2"/>'
        "</g>"
    )
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.fixtures == (("Desk", ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0))),)
    assert labels.skipped == {"path_skipped": 1, "transform_unsupported": 2}


def test_parse_model_svg_boundary_polygon_subtree_has_path_and_nested_group() -> None:
    """Cây `BoundaryPolygon`: `path` hậu duệ bị bỏ (đếm `path_skipped`), `polygon` qua nhóm con có transform vẫn
    tính."""
    body = (
        '<g class="FixedFurniture Vanity"><g class="BoundaryPolygon">'
        '<path d="M0 0 L1 1"/><g transform="translate(5,5)"><polygon points="0,0 2,0 2,2 0,2"/></g>'
        "</g></g>"
    )
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.fixtures == (("Vanity", ((5.0, 5.0), (7.0, 5.0), (7.0, 7.0), (5.0, 7.0))),)
    assert labels.skipped == {"path_skipped": 1}


def test_parse_model_svg_path_direct_child_of_wall_skipped() -> None:
    """`path` con trực tiếp của `Wall` bị bỏ, đếm `path_skipped`; `polygon` cạnh nó vẫn thành tường."""
    body = '<g class="Wall"><polygon points="0,0 10,0 10,10 0,10"/><path d="M0 0 L1 1"/></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert len(labels.walls) == 1
    assert labels.skipped == {"path_skipped": 1}


def test_parse_model_svg_path_direct_child_of_door_skipped() -> None:
    """`path` con trực tiếp của `Door` bị bỏ, đếm `path_skipped`."""
    body = '<g class="Door Swing"><polygon points="0,0 10,0 10,10 0,10"/><path d="M0 0 L1 1"/></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert len(labels.doors) == 1
    assert labels.skipped == {"path_skipped": 1}


@pytest.mark.parametrize(
    "points",
    ["0,0 1,0 1,1 0", "0,0 1,0", "0,0 1,0 nan,1"],
    ids=["odd_count", "two_points", "nan_value"],
)
def test_parse_model_svg_invalid_polygon_counted(points: str) -> None:
    """Lẻ số, < 3 điểm, hay `nan` → bỏ phần tử, đếm `polygon_invalid`."""
    body = f'<g class="Wall"><polygon points="{points}"/></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.walls == ()
    assert labels.skipped == {"polygon_invalid": 1}


def test_parse_model_svg_too_many_walls_rejected() -> None:
    """Hơn `MAX_WALLS` tường → `too_many_labels`, chặn ngay lúc duyệt."""
    groups = '<g class="Wall"><polygon points="0,0 1,0 1,1 0,1"/></g>' * (MAX_WALLS + 1)
    with pytest.raises(SvgRejectedError) as exc_info:
        parse_model_svg(_svg(groups), max_bytes=200_000_000)
    assert exc_info.value.reason == "too_many_labels"


def test_parse_model_svg_too_many_detections_rejected() -> None:
    """Hơn `MAX_DETECTIONS` cửa + cửa sổ + đồ → `too_many_labels`."""
    groups = '<g class="Door Swing"><polygon points="0,0 1,0 1,1 0,1"/></g>' * (MAX_DETECTIONS + 1)
    with pytest.raises(SvgRejectedError) as exc_info:
        parse_model_svg(_svg(groups), max_bytes=50_000_000)
    assert exc_info.value.reason == "too_many_labels"


def test_parse_model_svg_too_many_fixtures_rejected() -> None:
    """Hơn `MAX_DETECTIONS` đồ đạc (`FixedFurniture`) → `too_many_labels` ngay khi thêm cái vượt trần."""
    groups = "".join(
        '<g class="FixedFurniture Chair"><rect x="0" y="0" width="1" height="1"/></g>'
        for _ in range(MAX_DETECTIONS + 1)
    )
    with pytest.raises(SvgRejectedError) as exc_info:
        parse_model_svg(_svg(groups), max_bytes=50_000_000)
    assert exc_info.value.reason == "too_many_labels"


def test_parse_model_svg_fixture_without_name_is_empty_string() -> None:
    """`FixedFurniture` không có tên (token thứ hai) → tên `""`."""
    body = '<g class="FixedFurniture"><rect x="0" y="0" width="4" height="5"/></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.fixtures == (("", ((0.0, 0.0), (4.0, 0.0), (4.0, 5.0), (0.0, 5.0))),)


def test_parse_model_svg_fixture_rect_default_origin() -> None:
    """`rect` không có `x`/`y` → mặc định `0` (nhánh mặc định của `_rect_points`)."""
    body = '<g class="FixedFurniture Stool"><rect width="4" height="6"/></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.fixtures == (("Stool", ((0.0, 0.0), (4.0, 0.0), (4.0, 6.0), (0.0, 6.0))),)


def test_parse_model_svg_fixture_invalid_rect_is_dropped() -> None:
    """`rect` thiếu `width`/`height` trong `FixedFurniture` → không có hộp, không có đồ nào được thêm."""
    body = '<g class="FixedFurniture Bad"><rect x="0" y="0"/></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.fixtures == ()


def test_parse_model_svg_fixture_fallback_collects_nested_group_polygon() -> None:
    """Không có `BoundaryPolygon` → hộp bao gom mọi `polygon`/`rect` hậu duệ (kể cả qua nhóm con có transform)."""
    body = '<g class="FixedFurniture Shelf"><g transform="translate(1,1)"><polygon points="0,0 2,0 2,2 0,2"/></g></g>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.fixtures == (("Shelf", ((1.0, 1.0), (3.0, 1.0), (3.0, 3.0), (1.0, 3.0))),)


def test_parse_model_svg_fixture_boundary_polygon_ignores_sibling_inner_polygon() -> None:
    """Có `BoundaryPolygon` → chỉ dùng cây đó, bỏ `InnerPolygon` anh em (chép cấu trúc `fake_cubicasa`)."""
    body = (
        '<g class="FixedFurniture Sink" transform="matrix(1,0,0,1,100,200)">'
        '<g class="BoundaryPolygon"><polygon points="0,0 10,0 10,10 0,10"/></g>'
        '<g class="InnerPolygon"><polygon points="900,900 901,900 901,901 900,901"/></g>'
        "</g>"
    )
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.fixtures == (("Sink", ((100.0, 200.0), (110.0, 200.0), (110.0, 210.0), (100.0, 210.0))),)


def test_parse_model_svg_space_and_railing_create_no_labels() -> None:
    """`Space`/`Railing` không tạo nhãn nhưng vẫn duyệt con (không ảnh hưởng nhãn khác)."""
    body = (
        '<g class="Space Kitchen"><polygon points="0,0 100,0 100,100 0,100"/></g>'
        '<g class="Railing"><polygon points="0,0 4,0 4,4 0,4"/></g>'
        '<g class="Wall"><polygon points="0,0 10,0 10,10 0,10"/></g>'
    )
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert len(labels.walls) == 1
    assert labels.doors == ()
    assert labels.windows == ()
    assert labels.fixtures == ()


def test_parse_model_svg_defs_subtree_ignored() -> None:
    """`defs` không được duyệt dù chứa cấu trúc `Wall` hợp lệ."""
    body = '<defs><g class="Wall"><polygon points="0,0 10,0 10,10 0,10"/></g></defs>'
    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)
    assert labels.walls == ()


def test_parse_model_svg_deeply_nested_groups_no_recursion_error() -> None:
    """10.000 nhóm `g` lồng nhau → không `RecursionError` (duyệt bằng ngăn xếp tường minh)."""
    wall = '<g class="Wall"><polygon points="0,0 10,0 10,10 0,10"/></g>'
    body = "<g>" * 10_000 + wall + "</g>" * 10_000
    labels = parse_model_svg(_svg(body), max_bytes=50_000_000)
    assert len(labels.walls) == 1


def test_parse_model_svg_very_long_number_token_in_wall_is_rejected() -> None:
    """Token 200 001 ký tự trong `points` của `Wall` → `polygon_invalid`, không quay lui bậc hai.

    Trần `_MAX_NUM_CHARS` kiểm **trước** regex nên bộ máy regex không bao giờ chạy lên chuỗi này;
    test không đo đồng hồ, vì dạng `_NUM_BODY` không mơ hồ vẫn giữ tuyến tính nếu trần biến mất
    (hai tầng phòng thủ, F-01 review lượt 1).
    """
    token = "1" * 200_000 + "x"

    labels = parse_model_svg(_svg(f'<g class="Wall"><polygon points="{token}"/></g>'), max_bytes=1_000_000)

    assert labels.walls == ()
    assert labels.skipped.get("polygon_invalid") == 1


def test_parse_model_svg_very_long_number_token_in_fixture_rect_is_dropped() -> None:
    """Token rác dài trong `width` của `rect` đồ → bỏ hộp (trần độ dài chặn trước regex)."""
    token = "1" * 200_000 + "x"
    body = f'<g class="FixedFurniture Toilet"><rect x="1" y="1" width="{token}" height="10"/></g>'

    labels = parse_model_svg(_svg(body), max_bytes=1_000_000)

    assert labels.fixtures == ()
