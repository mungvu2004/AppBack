"""12 phong cách chuẩn của AID-01: tên/mô tả tiếng Việt, nhóm tông, kiểu nền FE (`baseStyle`)."""

from dataclasses import dataclass
from typing import Final, Literal

Tone = Literal["sáng-ấm", "sáng-lạnh", "trầm-ấm", "tối-lạnh"]
BaseStyle = Literal["am-ap", "hien-dai-sang", "go-am", "toi-gian", "sang-trong-toi"]


@dataclass(frozen=True)
class Style:
    """Một phong cách: mã, tên + mô tả tiếng Việt, nhóm tông, kiểu nền FE."""

    id: str
    name_vi: str
    desc_vi: str
    tone: Tone
    base_style: BaseStyle


_ROWS: Final[tuple[Style, ...]] = (
    Style(
        "japandi", "Japandi", "gỗ sồi/tần bì sáng, vải lanh, tường kem/ghi ấm, tối giản, ấm áp", "sáng-ấm", "toi-gian"
    ),
    Style(
        "scandinavian",
        "Scandinavian",
        "trắng sáng, gỗ bạch dương nhạt, vải xám nhạt, nhiều ánh sáng, thân thiện",
        "sáng-lạnh",
        "hien-dai-sang",
    ),
    Style(
        "modern-min",
        "Hiện đại tối giản",
        "trắng/ghi lạnh, đen nhấn, bề mặt phẳng trơn, ít chi tiết",
        "sáng-lạnh",
        "toi-gian",
    ),
    Style(
        "modern-lux",
        "Hiện đại sang trọng",
        "đá vân sáng, gỗ óc chó, da, kim loại vàng đồng, tương phản đậm",
        "trầm-ấm",
        "sang-trong-toi",
    ),
    Style(
        "indochine",
        "Indochine",
        "gỗ tối, tông kem-vàng, gạch bông ở khu ướt, mây tre, cổ điển Á Đông",
        "trầm-ấm",
        "go-am",
    ),
    Style(
        "wabi-sabi",
        "Wabi-sabi",
        "vữa/xi măng thô màu đất, gỗ mộc, tông be-nâu trầm lặng, không bóng",
        "trầm-ấm",
        "am-ap",
    ),
    Style("industrial", "Industrial", "bê tông, xám than, da nâu, kim loại đen, gỗ thô", "tối-lạnh", "sang-trong-toi"),
    Style(
        "tropical", "Nhiệt đới hiện đại", "gỗ tếch, xanh lá, mây tre, trắng kem, cảm giác resort", "sáng-ấm", "am-ap"
    ),
    Style(
        "korean-min",
        "Hàn Quốc tối giản",
        "be-kem nhạt, gỗ sáng, vải nỉ mềm, nhẹ nhàng, gọn gàng",
        "sáng-ấm",
        "hien-dai-sang",
    ),
    Style(
        "neoclassic",
        "Tân cổ điển",
        "trắng-kem, gỗ sơn sáng, đá cẩm thạch, nét thanh lịch",
        "sáng-lạnh",
        "hien-dai-sang",
    ),
    Style(
        "midcentury", "Mid-century", "gỗ óc chó/teak, màu nhấn mù tạt/xanh rêu, chân đồ thanh mảnh", "trầm-ấm", "go-am"
    ),
    Style("rustic", "Rustic", "gỗ thô sẫm, gạch đất nung, vải thô, ấm cúng kiểu nhà quê", "trầm-ấm", "go-am"),
)

STYLES: Final[dict[str, Style]] = {s.id: s for s in _ROWS}
STYLE_IDS: Final[tuple[str, ...]] = tuple(STYLES)


def anchor_text(style_id: str) -> str:
    """Câu neo phong cách đưa vào prompt: "<tên>: <mô tả>"; mã lạ → `KeyError`."""
    s = STYLES[style_id]
    return f"{s.name_vi}: {s.desc_vi}"
