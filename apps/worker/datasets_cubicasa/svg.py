"""Đọc nhãn từ `model.svg` của CubiCasa5K mà không tin byte nào của nó (K13, B6-02b [6]).

Toạ độ trả về đã áp mọi `transform` (của phần tử và tổ tiên) và đã trừ gốc `viewBox`, tức là
pixel của `F1_scaled.png` 1:1. Luật này đo trên dữ liệu thật (2026-10-02, 120 mẫu, 3 subset):
đặt 1:1 cho `ink_ratio` cao hơn co giãn theo khổ `viewBox` ở 119/120 mẫu (trung vị 0,75 so với
0,19 ở `high_quality`) — phương án 1, người dùng đã duyệt; `viewBox` chỉ là khung bao nội dung.
"""

import math
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal
from xml.etree.ElementTree import Element

from packages.ml_contracts.artifacts import MAX_DETECTIONS, MAX_WALLS

Point = tuple[float, float]
Polygon = tuple[Point, ...]

SvgRejectReason = Literal["svg_rejected", "too_many_labels"]
"""Khoá bộ đếm bỏ mẫu khi SVG bị từ chối theo luật (khác `svg_invalid` = hỏng cú pháp)."""


class SvgRejectedError(ValueError):
    """SVG bị từ chối theo luật: quá trần byte, có NUL, có DTD/thực thể, hay quá nhiều nhãn.

    Lớp con của `ValueError` nên người gọi bắt nó **trước** `ValueError` chung (`svg_invalid`).
    """

    def __init__(self, reason: SvgRejectReason) -> None:
        """Thông điệp ngoại lệ chính là `reason` (khoá bộ đếm bỏ mẫu)."""
        super().__init__(reason)
        self.reason: Final = reason


@dataclass(frozen=True, slots=True)
class SvgLabels:
    """Nhãn của một mẫu theo pixel `F1_scaled.png`; `skipped` đếm phần tử bị bỏ theo lý do.

    `width`, `height` là khổ `viewBox` (vắng thì `width`/`height` của gốc): chỉ để báo cáo tỉ lệ
    khổ ảnh / khổ SVG, không dùng để co giãn toạ độ. `fixtures` giữ tên đồ (token thứ hai của
    `class`) và đa giác hộp bao 4 đỉnh của nhóm.
    """

    width: float
    height: float
    walls: tuple[Polygon, ...]
    doors: tuple[Polygon, ...]
    windows: tuple[Polygon, ...]
    fixtures: tuple[tuple[str, Polygon], ...]
    skipped: Mapping[str, int]


Matrix = tuple[float, float, float, float, float, float]
"""Ma trận affine 2x3 `(a, b, c, d, e, f)`: `x' = a*x + c*y + e`, `y' = b*x + d*y + f`."""

IDENTITY: Final[Matrix] = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

_NUM_BODY: Final = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
r"""Số SVG, **không mơ hồ**: phần thập phân chỉ tồn tại khi có dấu chấm.

Dạng cũ `\d+\.?\d*` chia được một chuỗi chữ số giữa `\d+` và `\d*` theo n cách, nên một
token `"1"*200000 + "x"` bắt bộ máy regex quay lui bậc hai (ReDoS, F-01 review lượt 1).
`(?:\.\d*)?` chỉ vào được sau một dấu chấm, nên mỗi chuỗi chỉ có một cách khớp."""

_MAX_NUM_CHARS: Final = 64
"""Trần độ dài một token số (phòng thủ tầng hai sau `_NUM_BODY`).

Không có số hợp lệ nào trong `model.svg` dài tới 64 ký tự (float64 in ra tối đa ~24), nên
token dài hơn chắc chắn là rác — chặn trước regex để bộ máy chỉ bao giờ chạy trên chuỗi
ngắn, kể cả nếu ai sửa `_NUM_BODY` thành dạng mơ hồ lần nữa."""

_NUM_RE: Final = re.compile(_NUM_BODY)
_LENGTH_RE: Final = re.compile(rf"\s*({_NUM_BODY})(?:px)?\s*")
_TRANSFORM_RE: Final = re.compile(r"([a-zA-Z]+)\s*\(([^()]*)\)")
_DOCTYPE_RE: Final = re.compile(rb"<!(?:DOCTYPE|ENTITY)", re.IGNORECASE)


def _numbers(value: str) -> tuple[float, ...] | None:
    """Tách danh sách số cách bởi khoảng trắng/dấu phẩy; token lạ (`nan`, `inf`, `1_0`, rác) → `None`.

    Mỗi token phải khớp trọn `_NUM_RE` (không gọi `float()` thẳng lên cả chuỗi: nó nhận những
    dạng JSON/SVG không cho phép) và dài không quá `_MAX_NUM_CHARS` — trần độ dài kiểm **trước**
    regex, nên một token rác dài 200 000 ký tự bị loại mà bộ máy regex không chạy lên nó.
    """
    tokens = [t for t in re.split(r"[\s,]+", value.strip()) if t]
    if not tokens:
        return None
    if any(len(t) > _MAX_NUM_CHARS or _NUM_RE.fullmatch(t) is None for t in tokens):
        return None
    return tuple(float(t) for t in tokens)


def _length(value: str | None) -> float | None:
    """Một số kiểu CSS (hậu tố `px` tuỳ chọn); `None` nếu vắng, quá dài, hay không khớp trọn chuỗi.

    Trần `_MAX_NUM_CHARS` (cộng chỗ cho `px` và khoảng trắng) chặn trước regex vì cùng lý do như
    `_numbers`: thuộc tính `width`/`height` cũng là byte của kẻ xấu.
    """
    if value is None or len(value) > _MAX_NUM_CHARS + 8:
        return None
    match = _LENGTH_RE.fullmatch(value)
    return float(match.group(1)) if match else None


def _mat_mult(outer: Matrix, inner: Matrix) -> Matrix:
    """Ghép CTM: áp `inner` trước rồi `outer` (`CTM_con = CTM_cha x T`, B6-02b [6])."""
    a1, b1, c1, d1, e1, f1 = outer
    a2, b2, c2, d2, e2, f2 = inner
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _apply(matrix: Matrix, point: Point) -> Point:
    """Ánh xạ một điểm qua ma trận affine."""
    a, b, c, d, e, f = matrix
    x, y = point
    return a * x + c * y + e, b * x + d * y + f


def _transform_matrix(name: str, args: tuple[float, ...]) -> Matrix | None:
    """Một phép `matrix/translate/scale/rotate`; tên khác hay sai số đối số → `None` (K không hỗ trợ)."""
    if name == "matrix" and len(args) == 6:
        return args[0], args[1], args[2], args[3], args[4], args[5]
    if name == "translate" and len(args) in (1, 2):
        tx = args[0]
        ty = args[1] if len(args) == 2 else 0.0
        return 1.0, 0.0, 0.0, 1.0, tx, ty
    if name == "scale" and len(args) in (1, 2):
        sx = args[0]
        sy = args[1] if len(args) == 2 else sx
        return sx, 0.0, 0.0, sy, 0.0, 0.0
    if name == "rotate" and len(args) in (1, 3):
        angle = math.radians(args[0])
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        rotation: Matrix = (cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0)
        if len(args) == 1:
            return rotation
        cx, cy = args[1], args[2]
        return _mat_mult(_mat_mult((1.0, 0.0, 0.0, 1.0, cx, cy), rotation), (1.0, 0.0, 0.0, 1.0, -cx, -cy))
    return None


def _parse_transform(value: str) -> Matrix | None:
    """Ghép mọi phép trong `transform` theo thứ tự viết; tên lạ, sai đối số, rác thừa → `None`."""
    text = value.strip()
    pos = 0
    result = IDENTITY
    while pos < len(text):
        match = _TRANSFORM_RE.match(text, pos)
        if match is None:
            return None
        name, raw_args = match.group(1), match.group(2)
        args = _numbers(raw_args) if raw_args.strip() else ()
        if args is None:
            return None
        matrix = _transform_matrix(name, args)
        if matrix is None:
            return None
        result = _mat_mult(result, matrix)
        pos = match.end()
        while pos < len(text) and text[pos] in " ,\t\n\r":
            pos += 1
    return result


def _own_ctm(element: Element, ctm: Matrix, skipped: dict[str, int]) -> Matrix | None:
    """CTM của `element` dưới CTM `ctm` của tổ tiên; `None` nếu `transform` không hỗ trợ (bỏ cả cây con)."""
    transform_attr = element.get("transform")
    if not transform_attr:
        return ctm
    own = _parse_transform(transform_attr)
    if own is None:
        skipped["transform_unsupported"] = skipped.get("transform_unsupported", 0) + 1
        return None
    return _mat_mult(ctm, own)


def _push_child_group(
    stack: list[tuple[Element, Matrix]], element: Element, ctm: Matrix, skipped: dict[str, int]
) -> None:
    """Đẩy nhóm `element` lên ngăn xếp duyệt với CTM của nó; bỏ nếu `transform` không hỗ trợ."""
    next_ctm = _own_ctm(element, ctm, skipped)
    if next_ctm is not None:
        stack.append((element, next_ctm))


def _local_tag(element: Element) -> str:
    """Tên thẻ không kèm namespace (SVG thật có `{http://www.w3.org/2000/svg}` trên mọi thẻ)."""
    return element.tag.rpartition("}")[2]


def _leaf_points(element: Element, ctm: Matrix, local: str, skipped: dict[str, int]) -> tuple[Point, ...] | None:
    """Điểm `polygon`/`rect` sau CTM riêng của chính lá (transform trên lá cũng được áp dụng, B6-02b [6]).

    `transform` không hỗ trợ trên lá → `None` (đã đếm `transform_unsupported` trong `_own_ctm`,
    không đếm `polygon_invalid` chồng lên).
    """
    leaf_ctm = _own_ctm(element, ctm, skipped)
    if leaf_ctm is None:
        return None
    return _polygon_points(element, leaf_ctm) if local == "polygon" else _rect_points(element, leaf_ctm)


def _polygon_points(element: Element, ctm: Matrix) -> tuple[Point, ...] | None:
    """Đa giác `polygon` qua CTM; lẻ số, < 3 điểm, hay toạ độ không hữu hạn sau transform → `None`."""
    raw = element.get("points")
    numbers = _numbers(raw) if raw is not None else None
    if numbers is None or len(numbers) < 6 or len(numbers) % 2 != 0:
        return None
    points = tuple(_apply(ctm, (numbers[i], numbers[i + 1])) for i in range(0, len(numbers), 2))
    return points if all(math.isfinite(v) for p in points for v in p) else None


def _rect_points(element: Element, ctm: Matrix) -> tuple[Point, ...] | None:
    """4 góc `rect` qua CTM; `width`/`height` thiếu hay không dương → `None`."""
    x, y = _length(element.get("x", "0")), _length(element.get("y", "0"))
    width, height = _length(element.get("width")), _length(element.get("height"))
    if x is None or y is None or width is None or height is None or width <= 0 or height <= 0:
        return None
    corners = ((x, y), (x + width, y), (x + width, y + height), (x, y + height))
    points = tuple(_apply(ctm, p) for p in corners)
    return points if all(math.isfinite(v) for p in points for v in p) else None


def _root_geometry(root: Element) -> tuple[float, float, Matrix]:
    """Khổ báo cáo + CTM gốc: `viewBox` thắng (CTM = dời ngược gốc); vắng thì `width`/`height`, đơn vị."""
    view_box = root.get("viewBox")
    if view_box is not None:
        numbers = _numbers(view_box)
        if numbers is None or len(numbers) != 4:
            raise ValueError("invalid viewBox")
        vb_x, vb_y, width, height = numbers
        if not (math.isfinite(width) and math.isfinite(height) and width > 0 and height > 0):
            raise ValueError("invalid viewBox size")
        return width, height, (1.0, 0.0, 0.0, 1.0, -vb_x, -vb_y)
    fallback_width, fallback_height = _length(root.get("width")), _length(root.get("height"))
    if fallback_width is None or fallback_height is None or fallback_width <= 0 or fallback_height <= 0:
        raise ValueError("missing or invalid svg size")
    return fallback_width, fallback_height, IDENTITY


def _collect_wall(
    element: Element, ctm: Matrix, walls: list[Polygon], skipped: dict[str, int], stack: list[tuple[Element, Matrix]]
) -> None:
    """`polygon` con trực tiếp của `Wall` là một tường; `path` con trực tiếp bị bỏ; `g` con duyệt tiếp."""
    for child in element:
        local = _local_tag(child)
        if local == "polygon":
            leaf_ctm = _own_ctm(child, ctm, skipped)
            if leaf_ctm is None:
                continue
            polygon = _polygon_points(child, leaf_ctm)
            if polygon is None:
                skipped["polygon_invalid"] = skipped.get("polygon_invalid", 0) + 1
                continue
            walls.append(polygon)
            if len(walls) > MAX_WALLS:
                raise SvgRejectedError("too_many_labels")
        elif local == "path":
            skipped["path_skipped"] = skipped.get("path_skipped", 0) + 1
        elif local == "g":
            stack.append((child, ctm))


def _collect_opening(
    element: Element,
    ctm: Matrix,
    kind: str,
    doors: list[Polygon],
    windows: list[Polygon],
    fixtures: list[tuple[str, Polygon]],
    skipped: dict[str, int],
    stack: list[tuple[Element, Matrix]],
) -> None:
    """`polygon` con trực tiếp của `Door`/`Window` là ô mở; nhóm con (`PanelArea`,…) duyệt tiếp, không lấy đa giác."""
    target = doors if kind == "Door" else windows
    for child in element:
        local = _local_tag(child)
        if local == "polygon":
            leaf_ctm = _own_ctm(child, ctm, skipped)
            if leaf_ctm is None:
                continue
            polygon = _polygon_points(child, leaf_ctm)
            if polygon is None:
                skipped["polygon_invalid"] = skipped.get("polygon_invalid", 0) + 1
                continue
            target.append(polygon)
            if len(doors) + len(windows) + len(fixtures) > MAX_DETECTIONS:
                raise SvgRejectedError("too_many_labels")
        elif local == "path":
            skipped["path_skipped"] = skipped.get("path_skipped", 0) + 1
        elif local == "g":
            stack.append((child, ctm))


def _boundary_points(element: Element, ctm: Matrix, skipped: dict[str, int]) -> tuple[Point, ...]:
    """Gom mọi điểm `polygon`/`rect` trong cây `BoundaryPolygon` (không tìm `BoundaryPolygon` lồng tiếp)."""
    points: list[Point] = []
    stack: list[tuple[Element, Matrix]] = [(element, ctm)]
    while stack:
        node, node_ctm = stack.pop()
        for child in node:
            local = _local_tag(child)
            if local == "path":
                skipped["path_skipped"] = skipped.get("path_skipped", 0) + 1
            elif local in ("polygon", "rect"):
                points.extend(_leaf_points(child, node_ctm, local, skipped) or ())
            elif local == "g":
                _push_child_group(stack, child, node_ctm, skipped)
    return tuple(points)


def _fixture_points(element: Element, ctm: Matrix, skipped: dict[str, int]) -> tuple[Point, ...]:
    """Điểm `polygon`/`rect` hậu duệ của `FixedFurniture`; gặp `BoundaryPolygon` đầu tiên → chỉ dùng cây đó."""
    fallback: list[Point] = []
    stack: list[tuple[Element, Matrix]] = [(child, ctm) for child in reversed(list(element))]
    while stack:
        child, child_ctm = stack.pop()
        local = _local_tag(child)
        if local == "path":
            skipped["path_skipped"] = skipped.get("path_skipped", 0) + 1
            continue
        if local in ("polygon", "rect"):
            fallback.extend(_leaf_points(child, child_ctm, local, skipped) or ())
            continue
        if local != "g":
            continue
        next_ctm = _own_ctm(child, child_ctm, skipped)
        if next_ctm is None:
            continue
        classes = (child.get("class") or "").split()
        if classes and classes[0] == "BoundaryPolygon":
            return _boundary_points(child, next_ctm, skipped)
        stack.extend((grandchild, next_ctm) for grandchild in reversed(list(child)))
    return tuple(fallback)


def _fixture_box(element: Element, ctm: Matrix, skipped: dict[str, int]) -> Polygon | None:
    """Hộp bao 4 đỉnh của `FixedFurniture`; rỗng (không `polygon`/`rect` nào hợp lệ) → `None`."""
    points = _fixture_points(element, ctm, skipped)
    if not points:
        return None
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    return (x0, y0), (x1, y0), (x1, y1), (x0, y1)


def _add_fixture(
    fixtures: list[tuple[str, Polygon]], name: str, box: Polygon, doors: list[Polygon], windows: list[Polygon]
) -> None:
    """Thêm một đồ đạc; chặn ngay nếu tổng cửa + sổ + đồ vượt `MAX_DETECTIONS`."""
    fixtures.append((name, box))
    if len(doors) + len(windows) + len(fixtures) > MAX_DETECTIONS:
        raise SvgRejectedError("too_many_labels")


def _walk(
    root: Element, root_ctm: Matrix
) -> tuple[list[Polygon], list[Polygon], list[Polygon], list[tuple[str, Polygon]], dict[str, int]]:
    """Duyệt cây bằng ngăn xếp tường minh (không đệ quy, K); bỏ `defs` và phần tử không phải `g` ở tầng quét chung."""
    walls: list[Polygon] = []
    doors: list[Polygon] = []
    windows: list[Polygon] = []
    fixtures: list[tuple[str, Polygon]] = []
    skipped: dict[str, int] = {}
    stack: list[tuple[Element, Matrix]] = [(child, root_ctm) for child in reversed(list(root))]
    while stack:
        element, ctm = stack.pop()
        if _local_tag(element) != "g":
            continue
        child_ctm = _own_ctm(element, ctm, skipped)
        if child_ctm is None:
            continue
        classes = (element.get("class") or "").split()
        head = classes[0] if classes else ""
        if head == "Wall":
            _collect_wall(element, child_ctm, walls, skipped, stack)
        elif head in ("Door", "Window"):
            _collect_opening(element, child_ctm, head, doors, windows, fixtures, skipped, stack)
        elif head == "FixedFurniture":
            box = _fixture_box(element, child_ctm, skipped)
            if box is not None:
                _add_fixture(fixtures, classes[1] if len(classes) > 1 else "", box, doors, windows)
        else:
            stack.extend((child, child_ctm) for child in reversed(list(element)))
    return walls, doors, windows, fixtures, skipped


def _reject_unsafe(data: bytes, max_bytes: int) -> None:
    """Chặn trên byte thô trước khi parse: quá trần, UTF-16 (có NUL), hay có DTD/thực thể (K13)."""
    if len(data) > max_bytes or b"\x00" in data or _DOCTYPE_RE.search(data):
        raise SvgRejectedError("svg_rejected")


def parse_model_svg(data: bytes, *, max_bytes: int) -> SvgLabels:
    """Đọc nhãn từ `model.svg` không tin byte nào của nó; toạ độ trả về là pixel `F1_scaled.png` 1:1 (B6-02b [6]).

    `SvgRejectedError` khi SVG bị từ chối theo luật (quá trần, DTD/thực thể, quá nhiều nhãn);
    `ValueError` (không phải `SvgRejectedError`) khi XML hỏng, gốc không phải `svg`, hay thiếu khổ.
    """
    _reject_unsafe(data, max_bytes)
    try:
        root = ET.fromstring(data)  # noqa: S314 — NUL, DTD, thực thể đã chặn ở trên nên expat không mở rộng/tải gì
    except ET.ParseError as exc:
        raise ValueError(f"invalid svg xml: {exc}") from exc
    if _local_tag(root) != "svg":
        raise ValueError("root element is not svg")
    width, height, root_ctm = _root_geometry(root)
    walls, doors, windows, fixtures, skipped = _walk(root, root_ctm)
    return SvgLabels(
        width=width,
        height=height,
        walls=tuple(walls),
        doors=tuple(doors),
        windows=tuple(windows),
        fixtures=tuple(fixtures),
        skipped={key: value for key, value in skipped.items() if value > 0},
    )
