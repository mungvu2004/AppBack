"""Mái Pascal (roof-contract.md): tương thích ngược, khứ hồi `nodes`, toàn vẹn, diff một mục `roof`."""

import json

import pytest
from pydantic import ValidationError

from packages.core.errors import MISSING
from packages.domain.spatial import (
    FieldChange,
    IntegrityIssue,
    Roof,
    SpatialGraph,
    SpatialLayer,
    check_integrity,
    diff_layers,
    document_to_json,
    has_critical,
    sample_building,
    sample_layer,
    sample_roof,
)
from packages.domain.spatial.model import ROOF_JSON_MAX_BYTES, ROOF_NODES_MAX

LAYER = sample_layer(0)
ROOF = sample_roof(0)
WITH_ROOF = LAYER.model_copy(update={"roofs": (ROOF,)})


def wire(model: SpatialLayer | SpatialGraph | Roof) -> dict[str, object]:
    """Dạng dây chung của mọi thực thể (camelCase, vắng khoá thay `null`)."""
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


def roof_raw(**changes: object) -> dict[str, object]:
    """Dạng dây của mái mẫu, đè các khoá truyền vào."""
    return {**wire(ROOF), **changes}


# 1. Tương thích ngược


def test_layer_without_roofs_dumps_without_the_key() -> None:
    """Lớp cũ (không `roofs`) đọc được, `roofs == ()`, và dump ra không có khoá `roofs`."""
    raw = wire(LAYER)
    assert "roofs" not in raw
    assert SpatialLayer.model_validate(raw).roofs == ()
    assert SpatialLayer.model_validate({**raw, "roofs": []}) == LAYER
    assert document_to_json(LAYER, (), ())["layer"] == raw


def test_graph_without_roofs_dumps_without_the_key() -> None:
    """Đồ thị A14 không có mái: khoá `roofs` vắng, khứ hồi y nguyên."""
    raw = wire(sample_building())
    assert "roofs" not in raw
    assert SpatialGraph.model_validate(raw) == sample_building()


def test_layers_without_roofs_diff_as_before() -> None:
    """Hai lớp không mái: diff rỗng; thêm một tầng có mái rỗng (`[]`) cũng không đổi gì."""
    assert diff_layers(LAYER, SpatialLayer.model_validate({**wire(LAYER), "roofs": []})) == []


# 2. Khứ hồi giữ nguyên `nodes`


def test_roof_round_trip_keeps_nodes_byte_for_byte() -> None:
    """Đọc rồi ghi lại (cả đường `dict` lẫn đường chuỗi JSON) ra đúng từng byte JSON của `nodes`."""
    raw = wire(WITH_ROOF)
    sent = json.dumps(raw["roofs"][0]["nodes"], ensure_ascii=False)  # type: ignore[index]
    from_dict = SpatialLayer.model_validate(raw)
    from_json = SpatialLayer.model_validate_json(json.dumps(raw))
    for layer in (from_dict, from_json):
        assert json.dumps(wire(layer)["roofs"][0]["nodes"], ensure_ascii=False) == sent  # type: ignore[index]
    assert document_to_json(from_json, (), ())["layer"] == raw


def test_graph_carries_roofs() -> None:
    """`SpatialGraph.roofs` nhận và trả mái như lớp."""
    raw = {**wire(sample_building()), "roofs": [wire(ROOF)]}
    assert wire(SpatialGraph.model_validate(raw))["roofs"] == [wire(ROOF)]


# 3. Kiểm tra mái


@pytest.mark.parametrize("bad_id", ["R-ROOF0000000", "W-ROOF0000000", "RF-roof0000000", "RF-SHORT", "roof_1"])
def test_roof_id_must_have_rf_prefix(bad_id: str) -> None:
    """Id sai tiền tố `RF-` (kể cả `R-` của phòng) hay sai thân W4 → hỏng."""
    with pytest.raises(ValidationError):
        Roof.model_validate(roof_raw(id=bad_id))


def test_duplicate_roof_id_is_critical() -> None:
    """Hai mái cùng id, hay mái trùng id với tường → `duplicateId` mức chặn."""
    twice = LAYER.model_copy(update={"roofs": (ROOF, ROOF)})
    clash = LAYER.model_copy(update={"roofs": (ROOF,), "walls": (LAYER.walls[0].model_copy(update={"id": ROOF.id}),)})
    for layer in (twice, clash):
        issues = check_integrity(layer)
        assert IntegrityIssue("duplicateId", "critical", ROOF.id) in issues
        assert has_critical(issues)


def test_roof_on_unknown_level_is_critical() -> None:
    """`levelId` không phải tầng đang ghi (tầng không tồn tại) → `levelMembership` mức chặn."""
    stray = Roof.model_validate(roof_raw(levelId="L-NOSUCHLEVEL"))
    issues = check_integrity(LAYER.model_copy(update={"roofs": (stray,)}), level_id=ROOF.level_id)
    assert issues == [IntegrityIssue("levelMembership", "critical", stray.id, "L-NOSUCHLEVEL")]
    with pytest.raises(ValidationError):
        Roof.model_validate(roof_raw(levelId="RF-ROOF0000000"))


def test_valid_roof_passes_integrity() -> None:
    """Mái hợp lệ cùng tầng không thêm lỗi nào."""
    assert check_integrity(WITH_ROOF, level_id=ROOF.level_id) == check_integrity(LAYER, level_id=ROOF.level_id)


@pytest.mark.parametrize("count", [0, ROOF_NODES_MAX + 1])
def test_nodes_count_out_of_range_is_rejected(count: int) -> None:
    """`nodes` rỗng hay hơn 33 phần tử → hỏng."""
    with pytest.raises(ValidationError):
        Roof.model_validate(roof_raw(nodes=[{"type": "roof-segment"}] * count))


def test_nodes_count_bounds_are_accepted() -> None:
    """1 và 33 node đều đạt."""
    for count in (1, ROOF_NODES_MAX):
        assert len(Roof.model_validate(roof_raw(nodes=[{"type": "roof-segment"}] * count)).nodes) == count


@pytest.mark.parametrize("node", [[1, 2], "roof", 3, None])
def test_node_must_be_a_json_object(node: object) -> None:
    """Phần tử `nodes` không phải object → hỏng."""
    with pytest.raises(ValidationError):
        Roof.model_validate(roof_raw(nodes=[{"type": "roof"}, node]))


def test_roof_json_over_64kb_is_rejected() -> None:
    """JSON của cả mái vượt 64 KB → hỏng; sát dưới trần thì đạt."""
    base = len(json.dumps(roof_raw(nodes=[{"pad": ""}]), ensure_ascii=False).encode())
    fits = ROOF_JSON_MAX_BYTES - base
    assert Roof.model_validate(roof_raw(nodes=[{"pad": "x" * fits}]))
    with pytest.raises(ValidationError):
        Roof.model_validate(roof_raw(nodes=[{"pad": "x" * (fits + 1)}]))


def test_non_finite_number_in_nodes_is_rejected() -> None:
    """`NaN`/`Infinity` không vào được jsonb → 422 ở mô hình, không 500 lúc ghi."""
    with pytest.raises(ValidationError):
        Roof.model_validate(roof_raw(nodes=[{"width": float("nan")}]))


# 4. Diff: mỗi lần thêm, sửa, xoá đúng một mục `roof`


def test_added_roof_is_one_change() -> None:
    """Thêm mái → một mục `nodes`."""
    assert diff_layers(LAYER, WITH_ROOF) == [FieldChange(ROOF.id, "roof", "nodes", wire(ROOF)["nodes"])]


def test_edited_roof_is_one_change() -> None:
    """Sửa sâu trong một segment → đúng một mục `nodes` mang toàn bộ `nodes` mới."""
    nodes = [dict(node) for node in ROOF.nodes]
    nodes[2] = {**nodes[2], "metadata": {"autoGutter": False}}
    edited = WITH_ROOF.model_copy(update={"roofs": (Roof.model_validate(roof_raw(nodes=nodes)),)})
    assert diff_layers(WITH_ROOF, edited) == [FieldChange(ROOF.id, "roof", "nodes", nodes)]


def test_deleted_roof_is_one_change() -> None:
    """Xoá mái → một mục `__deleted__` không giá trị."""
    assert diff_layers(WITH_ROOF, LAYER) == [FieldChange(ROOF.id, "roof", "__deleted__", MISSING)]
