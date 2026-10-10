"""Plugin xếp thứ tự thu thập: tệp test nặng trước, tệp lạ sau (PERF-01 BE-6).

Bước 5 chạy `pytest -n 6 --dist loadfile`: `LoadFileScheduling` của xdist gom test theo
tệp (`nodeid` trước `::`) vào các "work unit" theo **đúng thứ tự thu thập**, phát mỗi node
hai đơn vị đầu rồi phát tiếp mỗi khi một node rảnh. Đó là xếp lịch tham lam, nên thứ tự
thu thập quyết định đuôi lượt: tệp nặng thu thập cuối sẽ bắt đầu khi các node khác đã xong
và chạy một mình (đo nền: `deploy/tests/test_compose.py` nặng 188 s CPU, đuôi ≥ 270 s).
Xếp giảm dần theo thời gian cộng dồn của tệp là heuristic LPT (longest processing time):
đuôi ngắn nhất có thể cho bài toán phân việc tham lam.

Bảng thời gian là tĩnh, commit cùng repo (`test_durations.json`), sinh từ junit của một
lượt cổng nền. Tĩnh — không phải `--store-durations` động — vì mọi tiến trình xdist phải
thu thập **cùng một thứ tự**, và vì lượt cổng không được phụ thuộc tệp trạng thái sinh ra
ngoài repo. Tệp không có trong bảng (test mới, tệp vừa đổi tên) đứng sau mọi tệp có trong
bảng: chưa biết thì đừng đoán nặng, và tệp mới thường nhỏ.

Sinh lại bảng khi số đo nền lệch nhiều (chạy bằng Python nào cũng được, chỉ stdlib):

    import collections, json, sys, xml.etree.ElementTree as ET
    junit, out = sys.argv[1], sys.argv[2]
    tot = collections.Counter()
    for tc in ET.parse(junit).getroot().iter("testcase"):
        parts = (tc.get("classname") or "").split(".")
        while parts and not parts[-1].startswith("test_"):
            parts.pop()  # classname của test trong class là "<module>.<TenClass>"
        if parts:
            tot["/".join(parts) + ".py"] += float(tc.get("time") or 0.0)
    rows = sorted(tot.items(), key=lambda kv: (-kv[1], kv[0]))
    json.dump({f: round(s, 3) for f, s in rows}, open(out, "w", encoding="utf-8"), indent=0)

`trylast=True`: chạy **sau** hook cùng tên của `ci_split.py` và sau bộ lọc `-m` của pytest,
nên chỉ xếp lại đúng tập item còn được chọn (xếp trước rồi bị lọc là công thừa, và lọc
không bảo toàn thứ tự thì kết quả xếp vô nghĩa).
"""

import json
from pathlib import Path

import pytest

DURATIONS_FILE = Path(__file__).with_name("test_durations.json")
_DURATIONS: dict[str, float] = json.loads(DURATIONS_FILE.read_text(encoding="utf-8"))


def file_sort_key(nodeid: str) -> tuple[int, float]:
    """Khoá xếp của một `nodeid`: `(0, -giây)` nếu tệp có trong bảng, `(1, 0.0)` nếu không.

    Hạng 0/1 tách hẳn hai nhóm nên mọi tệp lạ đứng sau mọi tệp đã biết, bất kể giây. Tệp
    lấy từ phần `nodeid` trước `::` — **cùng một phép tách** mà `LoadFileScheduling` dùng,
    nên thứ tự ta xếp đúng là thứ tự xdist gom đơn vị việc.
    """
    path = nodeid.split("::", 1)[0]
    seconds = _DURATIONS.get(path)
    return (1, 0.0) if seconds is None else (0, -seconds)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Xếp `items` theo tệp, nặng trước; `list.sort` ổn định nên thứ tự trong một tệp giữ nguyên.

    Giữ nguyên thứ tự trong tệp là bắt buộc: `--dist loadfile` tồn tại để test phụ thuộc
    thứ tự trong cùng tệp không bị xé ra, xếp lại bên trong tệp sẽ phá chính giả định đó.
    """
    items.sort(key=lambda item: file_sort_key(item.nodeid))
