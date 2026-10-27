"""Test plugin `xdist_groups`: tệp ML chia đều ba nhóm theo LPT, tệp thường nhóm theo đường tệp."""

import pytest

from packages.testing.fixtures import xdist_groups


class _Item:
    """Thay cho `pytest.Item`: hook chỉ đọc `nodeid`, marker sẵn có và gắn marker."""

    def __init__(self, nodeid: str, group: str | None = None) -> None:
        self.nodeid = nodeid
        self.markers = [] if group is None else [pytest.mark.xdist_group(group).mark]

    def get_closest_marker(self, name: str) -> pytest.Mark | None:
        return next((mark for mark in self.markers if mark.name == name), None)

    def add_marker(self, marker: pytest.MarkDecorator) -> None:
        self.markers.append(marker.mark)


def test_ml_groups_lpt_can_bang() -> None:
    """Nặng trước, vào nhóm nhẹ nhất: 6,5,4,3,2,1 → {6,1}, {5,2}, {4,3} — mỗi nhóm 7 giây."""
    durations = {f"apps/ml/t{n}.py": float(n) for n in range(1, 7)}
    groups = xdist_groups.ml_groups(set(durations), durations)
    loads: dict[str, float] = {}
    for path, group in groups.items():
        loads[group] = loads.get(group, 0.0) + durations[path]
    assert loads == {"ml-0": 7.0, "ml-1": 7.0, "ml-2": 7.0}


def test_ml_groups_tep_la_khong_don_mot_nhom() -> None:
    """Tệp không có trong bảng tính `UNKNOWN_SECONDS` nên rải đều, không dồn hết vào `ml-0`."""
    groups = xdist_groups.ml_groups({"apps/ml/a.py", "apps/ml/b.py", "apps/ml/c.py"}, {})
    assert sorted(groups.values()) == ["ml-0", "ml-1", "ml-2"]


def test_hook_gan_nhom_theo_tep_va_giu_marker_san_co() -> None:
    """Tệp thường → nhóm = đường tệp; tệp ML → `ml-N`; test tự gắn `xdist_group` giữ nguyên."""
    items = [
        _Item("apps/api/tests/test_x.py::test_a"),
        _Item("apps/ml/runtime/tests/test_loader.py::test_b[1::2]"),
        _Item("apps/api/tests/test_y.py::test_c", group="rieng"),
    ]
    xdist_groups.pytest_collection_modifyitems(items)  # type: ignore[arg-type]
    names = [[mark.args[0] for mark in item.markers] for item in items]
    assert names[0] == ["apps/api/tests/test_x.py"]
    assert names[1][0].startswith("ml-")
    assert names[2] == ["rieng"]
