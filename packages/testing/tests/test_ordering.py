"""Test plugin `ordering`: tệp nặng trước, tệp lạ sau, thứ tự trong tệp giữ nguyên."""

from packages.testing.fixtures import ordering


class _Item:
    """Thay cho `pytest.Item`: hook chỉ đọc `nodeid`, không cần phiên pytest thật."""

    def __init__(self, nodeid: str) -> None:
        self.nodeid = nodeid


_NANG = max(ordering._DURATIONS, key=lambda p: ordering._DURATIONS[p])
_NHE = min(ordering._DURATIONS, key=lambda p: ordering._DURATIONS[p])


def _order(nodeids: list[str]) -> list[str]:
    """Chạy hook trên danh sách `nodeid` và trả lại thứ tự sau khi xếp."""
    items = [_Item(nodeid) for nodeid in nodeids]
    ordering.pytest_collection_modifyitems(items)  # type: ignore[arg-type]
    return [item.nodeid for item in items]


def test_bang_thoi_gian_co_du_tep_va_giay_duong() -> None:
    """Bảng commit trong repo phải không rỗng và mọi giá trị là giây dương."""
    assert len(ordering._DURATIONS) > 100
    assert all(path.endswith(".py") and seconds > 0 for path, seconds in ordering._DURATIONS.items())


def test_tep_nang_dung_truoc_tep_nhe() -> None:
    """Hai tệp đều có trong bảng: tệp cộng dồn lớn hơn đứng trước, dù thu thập sau."""
    assert _order([f"{_NHE}::test_b", f"{_NANG}::test_a"]) == [f"{_NANG}::test_a", f"{_NHE}::test_b"]


def test_tep_la_dung_sau_moi_tep_da_biet() -> None:
    """Tệp không có trong bảng đứng sau cả tệp nhẹ nhất đã biết."""
    assert _order(["x/tests/test_moi.py::test_a", f"{_NHE}::test_b"]) == [
        f"{_NHE}::test_b",
        "x/tests/test_moi.py::test_a",
    ]


def test_thu_tu_trong_mot_tep_giu_nguyen() -> None:
    """Nhiều test cùng tệp giữ đúng thứ tự thu thập (loadfile dựa vào thứ tự trong tệp)."""
    assert _order([f"{_NHE}::test_z", f"{_NHE}::test_a"]) == [f"{_NHE}::test_z", f"{_NHE}::test_a"]


def test_cac_tep_la_giu_nguyen_thu_tu_thu_thap() -> None:
    """Giữa các tệp lạ với nhau, thứ tự thu thập không bị đảo (xếp ổn định)."""
    assert _order(["z/tests/test_z.py::test_a", "a/tests/test_a.py::test_a"]) == [
        "z/tests/test_z.py::test_a",
        "a/tests/test_a.py::test_a",
    ]


def test_khoa_xep_lay_duong_truoc_dau_hai_cham() -> None:
    """`file_sort_key` tách tệp ở `::` nên tham số trong tên test không ảnh hưởng."""
    assert ordering.file_sort_key(f"{_NANG}::test_a[1::2]") == (0, -ordering._DURATIONS[_NANG])
    assert ordering.file_sort_key("khong/co/test_x.py::test_a") == (1, 0.0)
