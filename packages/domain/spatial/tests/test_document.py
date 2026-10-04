"""`document_to_json`, `entity_ids`, `layer_counts` trên toà mẫu A14 (NO-220)."""

from packages.domain.spatial import sample_layer
from packages.domain.spatial.document import LayerCounts, document_to_json, entity_ids, layer_counts


def test_document_to_json_writes_layer_and_dimensions_but_no_axes() -> None:
    """Khoá ngoài là `layer`/`axes`/`dimensions`; `axes` luôn `[]` ở v1."""
    layer = sample_layer(0)
    document = document_to_json(layer, (), ())
    assert set(document) == {"layer", "axes", "dimensions"}
    assert document["axes"] == [] and document["dimensions"] == []
    assert document["layer"] == layer.model_dump(mode="json", by_alias=True, exclude_none=True)


def test_entity_ids_is_the_set_of_entity_ids() -> None:
    """Tầng 1 của A14: tập id bằng id của `layer.entities()`, không trùng nhau."""
    layer = sample_layer(0)
    assert entity_ids(layer) == frozenset(entity.id for entity in layer.entities())
    assert len(entity_ids(layer)) == len(tuple(layer.entities()))


def test_layer_counts_has_no_area_without_rooms() -> None:
    """Lớp rỗng: 0 tường, 0 đã duyệt, diện tích `None` (khác 0 m²)."""
    empty = sample_layer(0).model_copy(update={"walls": (), "rooms": ()})
    assert layer_counts(empty) == LayerCounts(walls_total=0, walls_reviewed=0, area_m2=None)
