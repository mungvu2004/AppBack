"""Đơn vị của bộ đọc: giải CTC, bảng ký tự, Otsu, cắt nắn, chia lát, chọn hướng.

Không gọi model thật ở đây (đo trên model thật nằm ở `test_reader_real.py`): mọi khẳng
định là mảng dựng tay hay ảnh vẽ tay, nên chúng chạy nhanh và chỉ đỏ khi chính luật
trong `reader.py` sai.
"""

import cv2
import numpy as np
import onnx
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
import pytest
from numpy.typing import NDArray

from apps.ml.text.reader import (
    DET_OVERLAP_PX,
    DET_TILE_PX,
    MAX_TEXT_ITEMS,
    REC_HEIGHT_PX,
    REC_MAX_WIDTH_PX,
    REC_MIN_WIDTH_PX,
    RapidOcrReader,
    _crop,
    _detect,
    _detector,
    _item,
    _merge,
    _otsu,
    _rec_input,
    _rec_widths,
    _starts,
    _tiles,
    ctc_decode,
    rec_characters,
)
from apps.ml.text.tests.helpers import CHARACTERS, rec_model
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.artifacts import MAX_TEXTS

PAGE = (400, 300)


def session_of(model: onnx.ModelProto) -> ort.InferenceSession:
    """Phiên ORT thật trên model tí hon (K23 cấm mock `onnxruntime`)."""
    return ort.InferenceSession(model.SerializeToString(), providers=["CPUExecutionProvider"])


def probs_of(sequence: list[int], classes: int = len(CHARACTERS), hit: float = 0.8) -> np.ndarray:
    """Mảng `(T, C)` có argmax đúng `sequence` ở từng bước."""
    probs = np.full((len(sequence), classes), (1.0 - hit) / (classes - 1), dtype=np.float32)
    probs[np.arange(len(sequence)), sequence] = hit
    return probs


def test_ctc_decode_collapses_repeats() -> None:
    """Chỉ số lặp liền nhau gộp làm một; `blank` bị bỏ khỏi chuỗi và khỏi trung bình."""
    text, confidence = ctc_decode(probs_of([4, 4, 0, 11, 11, 7]), CHARACTERS)
    assert text == "3.6"
    assert confidence == pytest.approx(0.8)


def test_ctc_decode_keeps_pair_split_by_blank() -> None:
    """Hai ký tự giống nhau tách bởi `blank` là hai ký tự, không phải một."""
    assert ctc_decode(probs_of([1, 0, 1]), CHARACTERS)[0] == "00"


def test_ctc_decode_all_blank_is_empty() -> None:
    """Toàn `blank` → chuỗi rỗng và tin cậy 0, không phải trung bình mảng rỗng."""
    assert ctc_decode(probs_of([0, 0, 0]), CHARACTERS) == ("", 0.0)


def test_rec_characters_wraps_metadata() -> None:
    """Bảng ký tự là `blank` + metadata + khoảng trắng, đúng quy ước PP-OCR."""
    assert rec_characters(session_of(rec_model())) == CHARACTERS


def test_rec_characters_without_metadata_is_unsupported() -> None:
    """Model rec không mang metadata `character` thì không đọc nổi chữ nào."""
    with pytest.raises(PermanentError, match="MODEL_FORMAT_UNSUPPORTED"):
        rec_characters(session_of(rec_model(characters=None)))


def test_rec_characters_rejects_multi_character_line() -> None:
    """Dòng hai ký tự là metadata sai hợp đồng, không phải ký tự lạ ([7])."""
    with pytest.raises(PermanentError, match="MODEL_FORMAT_UNSUPPORTED"):
        rec_characters(session_of(rec_model(characters=("ab", "c"))))


def test_from_session_rejects_class_count_mismatch() -> None:
    """`C` của model khác số ký tự → chỉ số giải ra sẽ trỏ ngoài bảng, từ chối ngay lúc dựng."""
    with pytest.raises(PermanentError, match="MODEL_FORMAT_UNSUPPORTED"):
        RapidOcrReader.from_session(session_of(rec_model(classes=len(CHARACTERS) - 1)))


def test_from_session_accepts_matching_model() -> None:
    """Model khớp bảng dựng được bộ đọc mang đúng bảng ký tự."""
    reader = RapidOcrReader.from_session(session_of(rec_model()), pinned_name="rapidocrRec")
    assert reader._characters == CHARACTERS


def test_otsu_inverts_dark_background() -> None:
    """Chữ trắng nền đen được đảo về chữ đen nền trắng, ảnh ra chỉ có 0 và 255."""
    crop = np.zeros((20, 60, 3), dtype=np.uint8)
    crop[6:14, 10:50] = 255
    out = _otsu(crop)
    assert set(np.unique(out).tolist()) == {0, 255}
    assert out[0, 0, 0] == 255
    assert out[10, 30, 0] == 0


def test_otsu_keeps_light_background() -> None:
    """Nền sáng giữ nguyên chiều: chữ vẫn tối sau khi nhị phân hoá."""
    crop = np.full((20, 60, 3), 255, dtype=np.uint8)
    crop[6:14, 10:50] = 0
    out = _otsu(crop)
    assert (out[0, 0, 0], out[10, 30, 0]) == (255, 0)


def test_crop_rotates_upright_quad() -> None:
    """Tứ giác cao gấp rưỡi bề rộng được xoay 90° nên ảnh ra rộng hơn cao."""
    image = np.full((200, 200, 3), 255, dtype=np.uint8)
    image[40:160, 90:110] = 0
    quad = np.array([[90, 40], [110, 40], [110, 160], [90, 160]], dtype=np.float32)
    out = _crop(image, quad)
    assert out.shape[0] < out.shape[1]
    assert (out.shape[1], out.shape[0]) == (120, 20)


def test_crop_keeps_wide_quad() -> None:
    """Tứ giác nằm ngang giữ nguyên hướng."""
    image = np.full((200, 200, 3), 255, dtype=np.uint8)
    quad = np.array([[10, 10], [130, 10], [130, 40], [10, 40]], dtype=np.float32)
    assert _crop(image, quad).shape[:2] == (30, 120)


def test_crop_degenerate_quad_is_empty() -> None:
    """Tứ giác suy biến không cắt được gì; người gọi bỏ vùng ấy."""
    quad = np.zeros((4, 2), dtype=np.float32)
    assert _crop(np.full((20, 20, 3), 255, dtype=np.uint8), quad).size == 0


class _FlipWins(RapidOcrReader):
    """Bộ đọc tiêm: lượt xoay 180° luôn tin cậy hơn, để kiểm luật chọn hướng."""

    def __init__(self) -> None:
        """Không cần phiên nào: chỉ `_run` bị thay."""

    def _run(self, crop: NDArray[np.uint8]) -> tuple[str, float]:
        """Ảnh đã xoay (điểm trên-trái tối) đọc chắc hơn ảnh gốc."""
        return ("flipped", 0.9) if int(crop[0, 0, 0]) == 0 else ("upright", 0.3)


class _TieKeepsFirst(_FlipWins):
    """Hai hướng tin cậy bằng nhau: luật nói lấy lượt không xoay."""

    def _run(self, crop: NDArray[np.uint8]) -> tuple[str, float]:
        """Cùng một mức tin cậy cho cả hai hướng."""
        return ("flipped", 0.7) if int(crop[0, 0, 0]) == 0 else ("upright", 0.7)


def _marked_crop() -> np.ndarray:
    """Ảnh có góc trên-trái sáng và góc dưới-phải tối: xoay 180° đổi hai góc cho nhau."""
    crop = np.full((10, 20, 3), 255, dtype=np.uint8)
    crop[-1, -1] = 0
    return crop


def test_best_takes_higher_confidence_orientation() -> None:
    """Lượt xoay 180° tin cậy cao hơn thì chuỗi của nó được chọn."""
    assert _FlipWins()._best(_marked_crop()) == ("flipped", 0.9)


def test_best_prefers_upright_on_tie() -> None:
    """Hoà tin cậy → giữ lượt đầu (không xoay), nên kết quả tất định."""
    assert _TieKeepsFirst()._best(_marked_crop()) == ("upright", 0.7)


def test_rec_widths_round_up_to_step() -> None:
    """`W` là bội 80 ≥ bề rộng đã co, không dưới sàn `REC_MIN_WIDTH_PX` (NO-254), không vượt trần."""
    assert _rec_widths(100, 48) == (100, REC_MIN_WIDTH_PX)
    assert _rec_widths(48, 48) == (48, REC_MIN_WIDTH_PX)
    assert _rec_widths(330, 48) == (330, 400)
    assert _rec_widths(10_000, 48) == (REC_MAX_WIDTH_PX, REC_MAX_WIDTH_PX)


def test_rec_input_pads_right_with_zeros() -> None:
    """Tensor đúng khổ, chuẩn hoá về `[-1, 1]`, phần thừa bên phải bằng 0."""
    crop = np.full((24, 60, 3), 255, dtype=np.uint8)
    tensor = _rec_input(crop)
    resized, padded = _rec_widths(60, 24)
    assert tensor.shape == (1, 3, REC_HEIGHT_PX, padded)
    assert tensor[0, :, :, :resized] == pytest.approx(1.0)
    assert tensor[0, :, :, resized:] == pytest.approx(0.0)


def test_starts_places_last_tile_against_the_edge() -> None:
    """Lát cuối dịch sát mép thay vì đệm ảnh, nên không lát nào ra ngoài trang."""
    assert _starts(3400, DET_TILE_PX, DET_OVERLAP_PX) == [0, 1400, 1800]
    assert _starts(1200, DET_TILE_PX, DET_OVERLAP_PX) == [0]


def test_tiles_cover_the_page() -> None:
    """Lưới lát phủ hết trang 3.400 x 1.700 và không lát nào vượt biên."""
    tiles = _tiles(3400, 1700)
    assert len(tiles) == 6
    assert max(x1 for _, _, x1, _ in tiles) == 3400
    assert max(y1 for _, _, _, y1 in tiles) == 1700


def _quad(x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
    """Tứ giác chữ nhật theo thứ tự trên-trái, trên-phải, dưới-phải, dưới-trái."""
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32)


def test_merge_keeps_the_higher_score() -> None:
    """Hai tứ giác chồng nhau nhiều thì chỉ tứ giác điểm dò cao hơn sống sót."""
    kept = _merge([_quad(0, 0, 100, 20), _quad(2, 1, 102, 21)], [0.4, 0.9])
    assert len(kept) == 1
    assert kept[0][0].tolist() == [2.0, 1.0]


def test_merge_keeps_distinct_boxes() -> None:
    """Hai vùng rời nhau không bị gộp."""
    assert len(_merge([_quad(0, 0, 100, 20), _quad(0, 200, 100, 220)], [0.9, 0.9])) == 2


def test_merge_of_nothing_is_empty() -> None:
    """Trang không có vùng nào thì gộp ra danh sách rỗng."""
    assert _merge([], []) == []


def test_item_clips_box_and_rounds() -> None:
    """Hộp kẹp trong trang và làm tròn 2 chữ số; chuỗi chuẩn hoá NFC rồi `strip`."""
    item = _item(" 3.600 ", 0.9, _quad(-5.0, 10.126, 60.0, 30.0), PAGE)
    assert item is not None
    assert (item.text, item.box.x_min, item.box.y_min) == ("3.600", 0.0, 10.13)


def test_item_drops_low_confidence() -> None:
    """Dưới `TEXT_CONFIDENCE_MIN` là rác của bộ đọc, không vào artifact."""
    assert _item("3.600", 0.49, _quad(0, 0, 60, 20), PAGE) is None


def test_item_drops_empty_and_overlong() -> None:
    """Chuỗi rỗng sau `strip` và chuỗi quá 64 ký tự đều bị bỏ (trần của `TextPx`)."""
    assert _item("   ", 0.9, _quad(0, 0, 60, 20), PAGE) is None
    assert _item("9" * 65, 0.9, _quad(0, 0, 60, 20), PAGE) is None


def test_item_drops_box_outside_the_page() -> None:
    """Hộp nằm trọn ngoài trang kẹp lại thành suy biến → bỏ, không ném."""
    assert _item("3.600", 0.9, _quad(500.0, 400.0, 600.0, 420.0), PAGE) is None


def test_item_caps_confidence_at_one() -> None:
    """Tin cậy > 1 của model lạ bị kẹp về 1 thay vì làm hỏng `TextPx`."""
    item = _item("3.600", 1.4, _quad(0, 0, 60, 20), PAGE)
    assert item is not None
    assert item.confidence == 1.0


def test_max_text_items_matches_artifact_cap() -> None:
    """Trần mục của bộ đọc đúng bằng trần `TextResult` của B5-01."""
    assert MAX_TEXT_ITEMS == MAX_TEXTS


def _page_with_text(width: int, height: int, spots: list[tuple[int, int]]) -> np.ndarray:
    """Trang trắng có vài chuỗi số đen vẽ bằng OpenCV (K28: không vòng lặp theo điểm ảnh)."""
    page = np.full((height, width, 3), 255, dtype=np.uint8)
    for x, y in spots:
        cv2.putText(page, "3.600", (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 0), 4, cv2.LINE_AA)
    return page


def test_detect_merges_text_seen_by_two_tiles() -> None:
    """Chữ nằm trong dải chồng của hai lát chỉ còn **một** tứ giác sau khi gộp."""
    page = _page_with_text(3400, 1700, [(1450, 900)])
    quads = _detect(_detector(), page)
    near = [q for q in quads if 1380 < q[:, 0].mean() < 1750 and 820 < q[:, 1].mean() < 950]
    assert len(near) == 1


def test_detect_keeps_text_crossing_the_inner_edge() -> None:
    """Chữ vắt qua mép trong của lát đầu vẫn ra đúng một mục, do lát sau bắt trọn."""
    page = _page_with_text(3400, 1700, [(1560, 400)])
    quads = _detect(_detector(), page)
    near = [q for q in quads if 1500 < q[:, 0].mean() < 1900 and 330 < q[:, 1].mean() < 450]
    assert len(near) == 1
