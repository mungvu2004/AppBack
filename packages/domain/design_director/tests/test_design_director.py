"""AID-01 gói thuần: phong cách, dữ liệu vật liệu thật, hồ sơ, vai trò, xếp hạng, prompt, đổi đáp án."""

import json

import pytest

from packages.domain.design_director.answer import to_result
from packages.domain.design_director.materials import Material, MaterialSets, material_sets, sheet_jpeg
from packages.domain.design_director.profiles import Profile, parse_profile, parse_profiles
from packages.domain.design_director.prompts import (
    PROMPT_VERSION,
    concept_prompt,
    concept_schema,
    fill_prompt,
    fill_schema,
    pick_style_prompt,
    pick_style_schema,
)
from packages.domain.design_director.ranking import fits_size, rank_candidates
from packages.domain.design_director.roles import ROLE_TYPE, TYPICAL_SIZE_MM, roles_for_usages
from packages.domain.design_director.styles import STYLE_IDS, STYLES, anchor_text


def _prof(pid: str, **kw: object) -> Profile:
    """Hồ sơ tổng hợp: giường đôi hợp cỡ, có license, qc ok, trừ khi ghi đè."""
    base: dict[str, object] = {
        "w": 1800.0,
        "d": 2100.0,
        "h": 900.0,
        "type": "bed",
        "license": "CC0",
        "qc_ok": True,
        "lightness": 70.0,
        "warmth": 12.0,
    }
    base.update(kw)
    return Profile(id=pid, **base)  # type: ignore[arg-type]


def _mat(mid: str, lightness: float) -> Material:
    """Vật liệu tổng hợp với độ sáng cho trước."""
    return Material(mid, f"library:{mid}", "colors", ("wall",), (lightness, 0.0, 0.0), lightness, 0.0, 0.0, 0.0)


SETS = MaterialSets(paint=(_mat("p1", 90), _mat("p2", 60)), dry=(_mat("d1", 55), _mat("d2", 88)), wet=(_mat("w1", 70),))


def test_styles_12_ids_and_anchor() -> None:
    """12 mã đúng hợp đồng, baseStyle đúng bảng, câu neo có tên + mô tả."""
    assert STYLE_IDS == (
        "japandi",
        "scandinavian",
        "modern-min",
        "modern-lux",
        "indochine",
        "wabi-sabi",
        "industrial",
        "tropical",
        "korean-min",
        "neoclassic",
        "midcentury",
        "rustic",
    )
    assert STYLES["industrial"].base_style == "sang-trong-toi"
    assert STYLES["rustic"].base_style == "go-am"
    assert anchor_text("japandi").startswith("Japandi: gỗ sồi")
    with pytest.raises(KeyError):
        anchor_text("free:abc")


def test_real_material_data() -> None:
    """Dữ liệu commit: ba tập đúng luật, ô khớp materials.json, ảnh JPEG < 400 KB."""
    sets = material_sets()
    assert sets.paint
    assert sets.dry
    assert sets.wet
    assert all(m.category == "colors" for m in sets.paint)
    assert all("floor" in m.surfaces for m in sets.dry)
    assert all(m.pattern <= 10 for m in sets.dry)
    assert all(m.category in ("tile", "stone") for m in sets.wet)
    assert all(m.ref == f"library:{m.id}" for m in sets.paint)
    for name in ("paint", "dry", "wet"):
        jpg = sheet_jpeg(name)
        assert jpg[:2] == b"\xff\xd8"
        assert len(jpg) < 400_000


def test_parse_profiles_tolerant() -> None:
    """Trường lạ bị lờ, dòng hỏng bị bỏ kèm lý do, id trùng giữ dòng đầu, dòng trống im lặng."""
    good = {
        "id": "m1",
        "sizeMm": {"w": 1800, "d": 2100, "h": 900},
        "type": "bed",
        "extra": 1,
        "colors": [{"lab": [50, 1, 2], "share": 0.6, "hex": "#888"}, {"lab": [1, 2]}, "x"],
        "lightness": 60,
        "warmth": True,
        "styles": ["japandi", 3],
        "dupGroup": "g",
        "license": "CC0",
        "qc": {"ok": True, "issues": ["a"]},
        "descVi": "",
    }
    lines = [
        json.dumps(good),
        "",
        "{bad",
        json.dumps([1]),
        json.dumps({"id": "x", "type": "bed"}),
        json.dumps({"id": "", "type": "bed"}),
        json.dumps({"id": "y", "sizeMm": {"w": 1, "d": 1, "h": 0}}),
        json.dumps({"id": "z", "type": "bed", "sizeMm": {"w": 1, "d": 1, "h": -1}}),
        json.dumps({**good, "type": "sofa"}),
        json.dumps(
            {
                "id": "c",
                "type": "bed",
                "sizeMm": {"w": 1, "d": 1, "h": 1},
                "colors": [{"lab": [1, "a", 2], "share": 1}],
                "qc": "x",
            }
        ),
    ]
    res = parse_profiles(lines)
    assert [p.id for p in res.profiles] == ["m1", "c"]
    m1 = res.profiles[0]
    assert m1.w == 1800
    assert m1.warmth is None
    assert m1.styles == ("japandi",)
    assert m1.qc_ok
    assert m1.desc_vi is None
    assert len(m1.colors) == 1
    assert m1.colors[0].lab == (50.0, 1.0, 2.0)
    assert res.profiles[1].colors == ()
    assert not res.profiles[1].qc_ok
    assert len(res.skipped) == 7
    assert res.skipped[-1].endswith("id trùng m1")
    assert "dòng 3" in res.skipped[0]


def test_parse_profile_type_missing() -> None:
    """Thiếu type → ValueError."""
    with pytest.raises(ValueError, match="type"):
        parse_profile({"id": "a", "sizeMm": {"w": 1, "d": 1, "h": 1}})


def test_roles() -> None:
    """Vai trò theo công năng: không trùng, thứ tự chuẩn, công năng lạ bị lờ; mọi vai trò có cỡ điển hình."""
    assert roles_for_usages(["bedroom", "livingRoom", "bedroom", "corridor"]) == (
        "doubleBed",
        "closet",
        "armchair",
        "sofa",
        "nightstand",
        "coffeeTable",
        "plant",
    )
    assert roles_for_usages(["loggia", "utility"]) == ("washer", "plant")
    assert set(TYPICAL_SIZE_MM) == set(ROLE_TYPE)
    assert ROLE_TYPE["counter"] == "kitchenCabinet"


def test_fits_size_rotation() -> None:
    """Cỡ ±30 % và cho phép xoay 90°."""
    assert fits_size(_prof("a", w=2100.0, d=1800.0), (1800, 2100))
    assert not fits_size(_prof("a", w=3000.0), (1800, 2100))


def test_rank_filters_scores_dedupes() -> None:
    """Lọc cứng, phong cách trước màu, bỏ trùng dupGroup, hoà điểm theo id, giới hạn 12/4."""
    ps = [
        _prof("z-style", styles=("japandi",)),
        _prof("a-style2", styles=("scandinavian", "japandi"), dup_group="g1"),
        _prof("b-style2", styles=("scandinavian", "japandi"), dup_group="g1", lightness=20.0),
        _prof("c-plain"),
        _prof("d-plain"),
        _prof("no-meas", lightness=None),
        _prof("no-lic", license=None, styles=("japandi",)),
        _prof("no-qc", qc_ok=False, styles=("japandi",)),
        _prof("sofa", type="sofa", styles=("japandi",)),
        _prof("big", w=5000.0, styles=("japandi",)),
    ]
    got = [p.id for p in rank_candidates(ps, "doubleBed", "japandi")]
    assert got == ["z-style", "a-style2", "c-plain", "d-plain", "no-meas"]
    assert [p.id for p in rank_candidates(ps, "doubleBed", "japandi", limit=2)] == ["z-style", "a-style2"]
    hint = rank_candidates([_prof("x", lightness=30.0), _prof("y")], "doubleBed", "japandi", palette_hint=(30, 0, 12))
    assert [p.id for p in hint] == ["x", "y"]
    plants = [_prof(f"p{i}", type="plant", w=450.0, d=450.0) for i in range(6)]
    assert len(rank_candidates(plants, "plant", "rustic")) == 4
    assert len(rank_candidates(plants, "plant", "rustic", size_mm=(900, 900))) == 0


def test_prompts_and_schemas() -> None:
    """Prompt có neo kiểu + dữ kiện không id; schema dùng enum số ô, 0 cho vai trò."""
    assert PROMPT_VERSION
    assert "Japandi" in pick_style_prompt([{"usage": "bedroom", "areaM2": 12}])
    assert pick_style_schema()["properties"]["styleId"]["enum"] == list(STYLE_IDS)
    text = concept_prompt("indochine", {"paint": 3, "dry": 2, "wet": 1}, {"sofa": [_prof("secret-id", type="sofa")]})
    assert "Indochine" in text
    assert "secret-id" not in text
    assert "1800x2100x900" in text
    sch = concept_schema(3, 2, 1, {"sofa": 2})
    assert sch["properties"]["wallPaint"]["enum"] == [1, 2, 3]
    assert sch["properties"]["models"]["properties"]["sofa"]["enum"] == [0, 1, 2]
    assert sch["properties"]["models"]["required"] == ["sofa"]
    assert "E1" in fill_prompt([{"edge": "E1", "room": "R0", "side": "trái", "len": 3000, "doors": []}])
    fs = fill_schema(["toilet", "basin"], ["R0"], ["E1", "E2"])["properties"]["additions"]["items"]["properties"]
    assert fs["type"]["enum"] == ["basin", "toilet"]
    assert fs["edgeRef"]["enum"] == ["E1", "E2"]
    assert fs["roomRef"]["enum"] == ["R0"]
    assert fs["pos"]["maximum"] == 1


def test_to_result_ok() -> None:
    """Đáp án hợp lệ → DesignResult: ref thư viện, sàn khô→wood, ướt→tile+mosaic, 0 = bỏ vai trò."""
    ans = {
        "nameVi": "  " + "x" * 50,
        "summaryVi": "Ấm.",
        "wallPaint": 1,
        "dryFloor": 1,
        "wetFloor": 1,
        "models": {"sofa": 2, "fridge": 0},
    }
    res, errs = to_result(ans, SETS, {"sofa": ["s1", "s2"], "fridge": ["f1"]}, "japandi")
    assert errs == ()
    assert res == {
        "nameVi": "x" * 40,
        "summaryVi": "Ấm.",
        "baseStyle": "toi-gian",
        "wall": {"interior": "library:p1"},
        "floor": {"wood": "library:d1", "tile": "library:w1", "mosaic": "library:w1"},
        "models": {"sofa": "s2"},
    }
    res2, _ = to_result({**ans, "nameVi": None, "summaryVi": 3, "models": {}}, SETS, {}, "rustic")
    assert res2 is not None
    assert res2["nameVi"] == "Rustic"
    assert res2["summaryVi"] == ""


def test_to_result_errors() -> None:
    """Số ngoài khoảng, bool, vai trò lạ, models sai kiểu, ΔL < 8 → None + lỗi."""
    bad = {"wallPaint": 0, "dryFloor": True, "wetFloor": 2, "models": {"sofa": 3, "bed": 1, "toilet": "1"}}
    res, errs = to_result(bad, SETS, {"sofa": ["s1"], "toilet": ["t1"]}, "japandi")
    assert res is None
    assert len(errs) == 6
    res, errs = to_result({"wallPaint": 1, "dryFloor": 2, "wetFloor": 1, "models": []}, SETS, {}, "japandi")
    assert res is None
    assert errs == ("models không phải object", "sàn và tường gần trùng độ sáng (ΔL=2 < 8)")
