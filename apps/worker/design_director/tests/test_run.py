"""`run_concept` với `FakeGenAI` và dữ liệu vật liệu thật: chọn kiểu, thử lại, mã lỗi, bổ sung đồ."""

import io
from typing import Any, Final

import pytest
from PIL import Image

from apps.api.design_director.state import DESIGN_DIRECTOR_FAILED, DESIGN_DIRECTOR_OUTPUT_INVALID
from apps.worker.design_director.run import DesignDirectorError, DesignInputs, LevelInput, run_concept, to_jpeg
from apps.worker.design_director.tests.test_fill import pt
from packages.domain.design_director.materials import material_sets
from packages.domain.design_director.profiles import Profile
from packages.domain.spatial.model import Room, SpatialLayer
from packages.genai import GENAI_UNAVAILABLE, GenAIError, GenAIResult, TextPart
from packages.testing.fixtures.genai import FakeGenAI

TOILET: Final = Profile("itm-t1", 400, 700, 800, "toilet", lightness=70, warmth=5, license="CC0", qc_ok=True)
BASIN_BIG: Final = Profile("itm-b2", 600, 450, 850, "basin", license="CC0", qc_ok=True)
BASIN_SMALL: Final = Profile("itm-b1", 500, 400, 850, "basin", license="CC0", qc_ok=True)


def concept_answer(**models: int) -> dict[str, Any]:
    """Đáp án concept hợp lệ trên dữ liệu thật: sơn ô 1, sàn khô lệch sáng ≥ 8, sàn ướt ô 1."""
    sets = material_sets()
    wall = sets.paint[0]
    dry = next(i for i, m in enumerate(sets.dry, 1) if abs(m.lightness - wall.lightness) >= 8)
    return {"nameVi": "Căn gỗ", "summaryVi": "Ấm.", "wallPaint": 1, "dryFloor": dry, "wetFloor": 1, "models": models}


def png() -> bytes:
    """Ảnh trang nhỏ."""
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buf, "PNG")
    return buf.getvalue()


def inputs(style: str | None = "japandi", *, rooms: bool = True) -> DesignInputs:
    """Một tầng một phòng tắm 3x2 m, ảnh trang nhỏ; tầng thứ hai rỗng không ảnh."""
    kw: dict[str, Any] = {"id": "r1", "level_id": "L1", "usage": "bathroom", "area_m2": 6, "wall_ids": ()}
    bath = Room.model_construct(outline=(pt(0, 0), pt(3000, 0), pt(3000, 2000), pt(0, 2000)), **kw)
    layer = SpatialLayer.model_construct(walls=(), openings=(), rooms=(bath,) if rooms else (), furniture=())
    empty = SpatialLayer.model_construct(walls=(), openings=(), rooms=(), furniture=())
    levels = (LevelInput("L1", "Tầng 1", layer, png()), LevelInput("L2", "Tầng 2", empty))
    return DesignInputs("prj", style, levels, (TOILET, BASIN_BIG, BASIN_SMALL))


def texts(parts: tuple[Any, ...]) -> list[str]:
    """Các đoạn chữ của một lời gọi."""
    return [p.text for p in parts if isinstance(p, TextPart)]


FILL: Final = {
    "additions": [
        {"type": "toilet", "roomRef": "R1", "edgeRef": "R1:E1", "pos": 0.5},
        {"type": "basin", "roomRef": "R1", "edgeRef": "R1:E3", "pos": 0.5},
        "x",
    ]
}


def test_happy_path_with_pick_and_fill() -> None:
    """Chọn kiểu → concept hợp lệ ngay → bổ sung đồ: mẫu AI chọn, không thì mẫu gọn nhất cùng loại."""
    genai = FakeGenAI().queue(
        GenAIResult({"styleId": "indochine"}, 10, 5, 0.5),
        GenAIResult(concept_answer(toilet=1), 10, 5, 0.5),
        GenAIResult(FILL, 10, 5, 0.5),
    )
    out = run_concept(inputs(None), genai)
    assert out.style_id == "indochine"
    assert out.usage == {"inputTokens": 30, "outputTokens": 15, "calls": 3, "seconds": 1.5}
    assert out.result["models"] == {"toilet": "itm-t1"}
    assert out.result["wall"]["interior"].startswith("library:")
    placed = {(a["kind"], a["variant"]): (a["modelId"], a["widthMm"]) for a in out.result["additions"]}
    assert placed == {("sanitaryFixture", "wc"): ("itm-t1", 400), ("sanitaryFixture", "basin"): ("itm-b1", 500)}
    concept = texts(genai.calls[1].parts)
    assert 'Bảng "paint":' in concept
    assert 'Bảng "toilet":' in concept
    assert "Ảnh mặt bằng Tầng 1:" in concept
    assert "Ảnh mặt bằng Tầng 2:" not in concept
    assert "Tầng 1, sơ đồ đánh số:" in texts(genai.calls[2].parts)


def test_retry_gives_errors_back() -> None:
    """Lần đầu sai → gọi lại kèm lỗi → hợp lệ; không phòng → không gọi lượt bổ sung."""
    genai = FakeGenAI().queue({**concept_answer(), "wallPaint": 999}, concept_answer())
    out = run_concept(inputs(rooms=False), genai)
    assert out.result["additions"] == []
    assert out.usage["calls"] == 2
    feedback = texts(genai.calls[1].parts)[-1]
    assert feedback.startswith("Câu trả lời trước không hợp lệ: wallPaint=999")


def test_invalid_twice_and_bad_pick() -> None:
    """Sai hai lần → OUTPUT_INVALID; kiểu lạ ở lượt chọn → OUTPUT_INVALID."""
    bad = {**concept_answer(), "wetFloor": 0}
    with pytest.raises(DesignDirectorError) as err:
        run_concept(inputs(), FakeGenAI().queue(bad, bad))
    assert err.value.code == DESIGN_DIRECTOR_OUTPUT_INVALID
    with pytest.raises(DesignDirectorError) as err:
        run_concept(inputs(None), FakeGenAI().queue({"styleId": "free:x"}))
    assert err.value.code == DESIGN_DIRECTOR_OUTPUT_INVALID


def test_ai_errors() -> None:
    """`GenAIError` ở concept → FAILED; lượt bổ sung hỏng chỉ bỏ additions."""
    with pytest.raises(DesignDirectorError) as err:
        run_concept(inputs(), FakeGenAI().queue(GenAIError(GENAI_UNAVAILABLE)))
    assert err.value.code == DESIGN_DIRECTOR_FAILED
    genai = FakeGenAI().queue(concept_answer(), GenAIError(GENAI_UNAVAILABLE))
    assert run_concept(inputs(), genai).result["additions"] == []


def test_to_jpeg() -> None:
    """Ảnh hỏng → None; ảnh lớn thu về cạnh 1600."""
    assert to_jpeg(b"junk") is None
    buf = io.BytesIO()
    Image.new("RGB", (3200, 800)).save(buf, "PNG")
    jpeg = to_jpeg(buf.getvalue())
    assert jpeg is not None
    assert Image.open(io.BytesIO(jpeg)).size == (1600, 400)
