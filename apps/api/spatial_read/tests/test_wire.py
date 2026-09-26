"""`apps.api.spatial_read.wire` — hình dạng dây của #33, N15, N16 (B3-02 [2], [8] C17).

Không đụng DB: đây là lớp biên giữa mô hình B3-01 và zod của FE, nên phép kiểm đúng là
"dump ra đúng khoá camelCase, đúng kiểu JSON, và trường tuỳ chọn **vắng** chứ không `null`".
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from apps.api.spatial_read.wire import (
    BuildingOut,
    DimensionOut,
    FloorLayerDocumentOut,
    FloorRevisionOut,
    LevelOut,
    SpatialGraphDocumentOut,
    SpatialGraphOut,
    dimensions_out,
    layer_out,
)
from packages.testing.factories.spatial import sample_floor_dimensions, sample_floor_layer

LEVEL_ID = "L-LEVEL000000"


def test_layer_out_keeps_every_entity_and_camel_keys() -> None:
    """Lớp toà mẫu đi qua nguyên vẹn; khoá trên dây là camelCase của `SpatialLayerSchema`."""
    layer = sample_floor_layer(0, level_id=LEVEL_ID)
    out = layer_out(layer)
    assert (len(out.walls), len(out.openings), len(out.rooms), len(out.furniture)) == (
        len(layer.walls),
        len(layer.openings),
        len(layer.rooms),
        len(layer.furniture),
    )
    wall = out.model_dump(by_alias=True)["walls"][0]
    assert set(wall) >= {"levelId", "openingIds", "thicknessMm", "centreline", "confidence", "source", "reviewed"}
    assert wall["levelId"] == LEVEL_ID


def test_layer_out_drops_absent_room_id() -> None:
    """Đồ đạc chưa gắn phòng **vắng khoá** `roomId`, không mang `null` (W2, K02, C17)."""
    layer = sample_floor_layer(0, level_id=LEVEL_ID)
    loose = layer.furniture[0].model_copy(update={"room_id": None})
    body = layer_out(layer.model_copy(update={"furniture": (loose,)})).model_dump(by_alias=True)
    assert "roomId" not in body["furniture"][0]


def test_room_area_is_json_number() -> None:
    """`areaM2` là **số** JSON, không phải chuỗi: `Decimal` in ra chuỗi thì zod của FE ném."""
    room = layer_out(sample_floor_layer(0, level_id=LEVEL_ID)).model_dump(mode="json", by_alias=True)["rooms"][0]
    assert isinstance(room["areaM2"], float | int)


def test_dimensions_out_maps_every_dimension() -> None:
    """Mọi kích thước của tầng mẫu qua được; `referenceIds` giữ nguyên thứ tự."""
    dimensions = sample_floor_dimensions(0, level_id=LEVEL_ID)
    out = dimensions_out(dimensions)
    assert [item.id for item in out] == [item.id for item in dimensions]
    assert [item.reference_ids for item in out] == [list(item.reference_ids) for item in dimensions]


def test_dimensions_out_of_empty_sequence() -> None:
    """Tầng chưa có kích thước → danh sách rỗng, không `None`."""
    assert dimensions_out(()) == []


def test_level_out_omits_optional_keys() -> None:
    """Tầng chưa đo diện tích, chưa hiệu chỉnh tỉ lệ → vắng cả `areaM2` lẫn tỉ lệ (C17)."""
    body = LevelOut(
        id=LEVEL_ID,
        name="Tầng 1",
        order=0,
        elevation_mm=0,
        height_mm=3000,
        confidence=1.0,
        source="human",
        reviewed=False,
    ).model_dump(by_alias=True)
    assert "areaM2" not in body
    assert "scaleMillimetresPerPixel" not in body


def test_building_out_omits_address_and_area() -> None:
    """Dự án không địa chỉ → vắng `address`; chưa có tầng → vẫn gửi `grossFloorAreaM2` 0 (C17)."""
    body = BuildingOut(
        name="Chung cư Hoàng Anh",
        datum_elevation_mm=0,
        gross_floor_area_m2=0.0,
        confidence=1.0,
        source="human",
        reviewed=False,
    ).model_dump(by_alias=True)
    assert "address" not in body
    assert body["grossFloorAreaM2"] == 0.0


def test_layer_document_omits_scale_status() -> None:
    """`scaleStatus=None` vắng hẳn khoá — zod chỉ nhận literal `'unresolved'` hoặc không có."""
    body = FloorLayerDocumentOut(
        revision=0,
        level=LevelOut(
            id=LEVEL_ID,
            name="Tầng 1",
            order=0,
            elevation_mm=0,
            height_mm=3000,
            confidence=1.0,
            source="human",
            reviewed=False,
        ),
        layer=layer_out(sample_floor_layer(0, level_id=LEVEL_ID)),
        axes=[],
        dimensions=[],
    ).model_dump(by_alias=True)
    assert "scaleStatus" not in body


def test_graph_document_is_strict() -> None:
    """Một khoá lạ ở mức ngoài → `ValidationError` ngay ở test của module này, không đợi FE (K01)."""
    with pytest.raises(ValidationError):
        SpatialGraphDocumentOut.model_validate({"graph": {}, "floorRevisions": [], "extra": 1})


def test_dimension_out_rejects_decimal_millimetres() -> None:
    """mm phải nguyên: `12.5` là dấu hiệu ai đó nhân tỉ lệ mà quên làm tròn (K20)."""
    with pytest.raises(ValidationError):
        DimensionOut(
            id="M-DIM0000001",
            level_id=LEVEL_ID,
            kind="linear",
            reference_ids=[],
            line={"start": {"x": 0, "y": 0}, "end": {"x": 10, "y": 0}},
            value_mm=Decimal("12.5"),
            confidence=0.5,
            source="ai",
            reviewed=False,
        )


def test_empty_graph_has_both_lists_empty() -> None:
    """Dự án chưa có tầng: `levels` và `floorRevisions` rỗng, `building.reviewed` sai ([6])."""
    graph = SpatialGraphOut(
        building=BuildingOut(
            name="Trống", datum_elevation_mm=0, gross_floor_area_m2=0.0, confidence=1.0, source="human", reviewed=False
        ),
        levels=[],
        walls=[],
        openings=[],
        furniture=[],
        rooms=[],
        axes=[],
        dimensions=[],
        notes=[],
    )
    document = SpatialGraphDocumentOut(graph=graph, floor_revisions=[])
    body = document.model_dump(by_alias=True)
    assert body["graph"]["levels"] == []
    assert body["floorRevisions"] == []
    assert body["graph"]["building"]["reviewed"] is False


def test_floor_revision_rejects_negative() -> None:
    """`revision` là số nguyên ≥ 0 (`FloorRevisionSchema`)."""
    with pytest.raises(ValidationError):
        FloorRevisionOut(floor_id=LEVEL_ID, revision=-1)
