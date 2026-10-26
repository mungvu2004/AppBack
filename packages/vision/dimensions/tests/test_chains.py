"""Đo đoạn kích thước trên ảnh dựng tay: đường nhạt, vạch đứng/xiên, chữ dọc, vạch giả, cụm tỉ số."""

import numpy as np
import pytest
from numpy.typing import NDArray

from packages.domain.scale import ScaleSample
from packages.ml_contracts.artifacts import BoxPx
from packages.vision.dimensions.chains import densest_cluster, dimension_spans, ink_mask

LINE_Y = 100
LIGHT = 225
"""Đường và vạch nhạt hơn nền 30 mức, như CAD xuất ảnh."""


def page(background: int = 255) -> NDArray[np.uint8]:
    """Trang 400 x 220 một màu."""
    return np.full((220, 400), background, dtype=np.uint8)


def chain(
    gray: NDArray[np.uint8], ticks: tuple[int, ...], *, ink: int = LIGHT, down: bool = True, slash: bool = False
) -> NDArray[np.uint8]:
    """Vẽ đường ngang ở `LINE_Y` từ vạch đầu tới vạch cuối, vạch đứng dài 15 px xuống (hay lên), hay vạch xiên 45°."""
    gray[LINE_Y, ticks[0] : ticks[-1] + 1] = ink
    for x in ticks:
        if slash:
            for d in range(-7, 8):
                gray[LINE_Y - d, x + d] = ink
        elif down:
            gray[LINE_Y : LINE_Y + 16, x] = ink
        else:
            gray[LINE_Y - 15 : LINE_Y + 1, x] = ink
    return gray


def label(cx: float, *, width: float = 30.0, height: float = 14.0, gap: float = 2.0) -> BoxPx:
    """Hộp chữ ngang tâm `cx`, đáy cách đường `gap` px."""
    return BoxPx(x_min=cx - width / 2, y_min=LINE_Y - gap - height, x_max=cx + width / 2, y_max=LINE_Y - gap)


def test_dimension_spans__light_chain_with_vertical_ticks() -> None:
    """Hai chữ trên chuỗi 50-150-350: mỗi chữ ra đúng đoạn của nó."""
    gray = chain(page(), (50, 150, 350))
    assert dimension_spans(gray, [label(100), label(250)]) == (100.0, 200.0)


def test_dimension_spans__ticks_drawn_towards_text_side() -> None:
    """Vạch kéo lên (về phía chữ, chuỗi nằm dưới căn) vẫn đo được."""
    gray = chain(page(), (50, 150, 350), down=False)
    assert dimension_spans(gray, [label(100), label(250)]) == (100.0, 200.0)


def test_dimension_spans__slash_ticks() -> None:
    """Vạch xiên 45° cắt qua đường (ký hiệu CAD) là đầu đoạn."""
    gray = chain(page(), (50, 150, 350), slash=True)
    assert dimension_spans(gray, [label(100)]) == (100.0,)


def test_dimension_spans__vertical_text_on_vertical_chain() -> None:
    """Chuỗi đứng: đo trên ảnh chuyển vị, hộp chữ cao hơn rộng."""
    gray = np.ascontiguousarray(chain(page(), (50, 150, 350)).T)
    horizontal = label(100)
    box = BoxPx(x_min=horizontal.y_min, y_min=horizontal.x_min, x_max=horizontal.y_max, y_max=horizontal.x_max)
    assert dimension_spans(gray, [box]) == (100.0,)


def test_dimension_spans__grey_background_and_dark_ink() -> None:
    """Nền xám 190 (bản vẽ màu) với đường đậm: mặt nạ theo màu nền phổ biến nhất, không theo trắng."""
    gray = chain(page(190), (50, 150, 350), ink=120)
    assert dimension_spans(gray, [label(250)]) == (200.0,)


def test_dimension_spans__no_line_near_text() -> None:
    """Chữ đứng một mình (nhãn phòng): `None`; danh sách hộp rỗng: rỗng."""
    gray = page()
    assert dimension_spans(gray, [label(100)]) == (None,)
    assert dimension_spans(gray, []) == ()


def test_dimension_spans__line_without_ticks() -> None:
    """Có đường mà không có vạch hai bên chữ (đường kẻ trang trí): `None`."""
    gray = page()
    gray[LINE_Y, 20:380] = LIGHT
    assert dimension_spans(gray, [label(200)]) == (None,)


def test_dimension_spans__off_centre_pair_rejected() -> None:
    """Chữ lệch hẳn về một đầu đoạn (số nhỏ ghi ngoài đoạn): không có cặp vạch nào kẹp đúng tâm."""
    gray = chain(page(), (50, 350))
    assert dimension_spans(gray, [label(80)]) == (None,)


def test_dimension_spans__span_narrower_than_text_rejected() -> None:
    """Đoạn hẹp hơn bề rộng chữ (vạch giả sát chữ): `None`."""
    gray = chain(page(), (82, 118))
    assert dimension_spans(gray, [label(100, width=40)]) == (None,)


def test_dimension_spans__strokes_of_neighbour_text_do_not_merge_into_ticks() -> None:
    """Nét chữ của hộp bên cạnh đứng sát vạch không gộp vào vạch: thân mọi hộp bị xoá khi dò vạch."""
    gray = chain(page(), (50, 150, 350))
    neighbour = label(160, width=16)
    gray[int(neighbour.y_min) + 2 : int(neighbour.y_max) - 1, 154:170:3] = 0  # nét đứng của chữ "220"
    assert dimension_spans(gray, [label(250), neighbour])[0] == 200.0


def test_dimension_spans__thick_blobs_on_other_side_ignored() -> None:
    """Mảng dày (đồ đạc) phía trên không thắng các vạch mảnh phía dưới khi chọn phía vạch giới hạn."""
    gray = chain(page(), (50, 150, 350))
    gray[LINE_Y - 15 : LINE_Y, 200:212] = 0
    assert dimension_spans(gray, [label(100)]) == (100.0,)


def test_ink_mask__relative_to_most_common_tone() -> None:
    """Mực = tối hơn nền phổ biến >= 12 mức; nhạt hơn 10 mức không tính."""
    gray = page(200)
    gray[0, 0], gray[0, 1] = 188, 190
    mask = ink_mask(gray)
    assert mask[0, 0]
    assert not mask[0, 1]
    assert mask.sum() == 1


def sample(ratio: float, key: str) -> ScaleSample:
    """Mẫu 100 px với tỉ số `ratio` mm/px."""
    return ScaleSample(key, 100.0, ratio * 100)


def test_densest_cluster__keeps_tight_group_in_input_order() -> None:
    """Ba mẫu ~20 mm/px thắng hai mẫu rác; thứ tự đầu vào giữ nguyên."""
    samples = (sample(20.0, "a"), sample(35.0, "x"), sample(20.4, "b"), sample(5.0, "y"), sample(19.6, "c"))
    assert [s.id for s in densest_cluster(samples)] == ["a", "b", "c"]


@pytest.mark.parametrize(
    ("samples", "expected"),
    [
        ((), []),
        ((sample(10.0, "a"), sample(30.0, "b")), []),
        ((sample(10.0, "a"), sample(10.2, "b"), sample(10.45, "c"), sample(10.7, "d")), ["a", "b", "c"]),
    ],
)
def test_densest_cluster__empty_and_tie(samples: tuple[ScaleSample, ...], expected: list[str]) -> None:
    """Rỗng: rỗng; hai cụm đông nhất rời nhau: rỗng (K19, không đoán); cụm hoà chồng nhau: tâm nhỏ nhất.

    Ca chồng: tâm 10,2 ôm {a, b, c}, tâm 10,45 ôm {b, c, d}, cùng 3 mẫu, chung b, c → cùng một tỉ lệ.
    """
    assert [s.id for s in densest_cluster(samples)] == expected


def test_dimension_spans__nearest_line_beats_darker_wall_edge() -> None:
    """Đường kích thước nhạt có chỗ hở (phủ < 100 %) vẫn thắng mép tường đậm phủ kín ở xa chữ hơn."""
    gray = chain(page(), (50, 150, 350))
    gray[LINE_Y, 96:99] = 255  # chỗ hở dưới chữ
    gray[LINE_Y + 20, 0:400] = 0  # mép tường
    gray[LINE_Y + 21 : LINE_Y + 40, 0:400:6] = 0  # nét gạch tường: thành "vạch" nếu dò nhầm hàng
    assert dimension_spans(gray, [label(100)]) == (100.0,)
