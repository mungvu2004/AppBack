"""Plugin gắn `xdist_group` cho mọi test: tệp thường một nhóm riêng, tệp ML dồn vào `ml-0..2` (PERF-03).

Đo PERF-03: collect cả bộ chỉ tốn ~0,66 GiB mỗi worker; RSS ~2 GiB đến từ lúc **chạy** test ML
(torch, phiên ONNX, OCR giữ lại trong tiến trình). Khi bước 5 chuyển sang `--dist loadgroup`,
gom mọi tệp dưới `apps/ml/` vào ba nhóm thì chỉ ba worker phình RAM, các worker còn lại ở mức
collect — đủ chỗ tăng `-n`. Nhóm mặc định là đường tệp nên `loadgroup` xử như `loadfile` cho phần
còn lại; với `--dist loadfile` marker vô hại.

Chia ba nhóm ML theo LPT trên `test_durations.json` (cùng bảng với `ordering.py`): tệp nặng trước,
mỗi tệp vào nhóm đang nhẹ nhất. Tất định vì mọi worker thu thập cùng tập tệp. Tệp chưa có trong
bảng tính `UNKNOWN_SECONDS` để không dồn hết vào một nhóm.
"""

import pytest

from packages.testing.fixtures.ordering import _DURATIONS

ML_PREFIX = "apps/ml/"
ML_GROUPS = 3
UNKNOWN_SECONDS = 1.0


def pytest_configure(config: pytest.Config) -> None:
    """Đăng ký `xdist_group` cả khi `-p no:xdist` (`strict_markers=true`); xdist đăng ký trùng thì vô hại."""
    config.addinivalue_line("markers", "xdist_group(name): nhóm việc của `--dist loadgroup` (PERF-03)")


def ml_groups(paths: set[str], durations: dict[str, float] = _DURATIONS) -> dict[str, str]:
    """Gán mỗi tệp ML trong `paths` vào `ml-0..ml-{ML_GROUPS-1}` theo LPT (nặng trước, nhóm nhẹ nhất)."""
    loads = [0.0] * ML_GROUPS
    result: dict[str, str] = {}
    for path in sorted(paths, key=lambda p: (-durations.get(p, UNKNOWN_SECONDS), p)):
        index = loads.index(min(loads))
        loads[index] += durations.get(path, UNKNOWN_SECONDS)
        result[path] = f"ml-{index}"
    return result


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Gắn `xdist_group` (trừ test đã tự gắn); chạy trước hook `trylast` của xdist đọc marker này."""
    files = {item.nodeid.split("::", 1)[0] for item in items}
    ml = ml_groups({path for path in files if path.startswith(ML_PREFIX)})
    for item in items:
        if item.get_closest_marker("xdist_group") is None:
            path = item.nodeid.split("::", 1)[0]
            item.add_marker(pytest.mark.xdist_group(ml.get(path, path)))
