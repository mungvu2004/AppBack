"""Plugin `--ci-split`: chia test của `coverage run -m pytest` thành 3 nhóm CI (B0-09).

Mỗi test được xếp vào **đúng một** trong `unit`/`integration`/`ml` (ưu tiên đường dẫn dưới
`apps/ml/`, sau đó tới việc dùng — trực tiếp hay gián tiếp qua bao đóng `item.fixturenames`
— một fixture dịch vụ thật). `--ci-split=<nhóm>[,<nhóm>]` giữ hợp các nhóm, bỏ chọn phần còn
lại; `--ci-split=all-check` không chạy test nào, chỉ in số lượng mỗi nhóm và hỏng nếu tổng số
lần một test được tính lệch khỏi số test thu được (vd một test đã tự mang marker `ci_*` khác
nhóm tính ra — rơi vào hai nhóm cùng lúc, R-17 fail-closed). Giá trị lạ/rỗng → `UsageError`.

Tiền tố `ephemeral_` (không phải tên cố định) vì các fixture bọc factory `ephemeral_*` của
`services.py` (không phải fixture pytest, test tự gọi rồi `.stop()`) có thể được chủ mỗi
module đặt tên riêng khi bọc thành fixture cục bộ; không liệt kê hết được nên bắt theo mẫu.
"""

from pathlib import Path
from typing import cast

import pytest
from _pytest.terminal import TerminalReporter

OPTION_NAME = "--ci-split"
ALL_CHECK = "all-check"

SERVICE_FIXTURE_NAMES = frozenset(
    {"postgres_url", "redis_broker_url", "redis_cache_url", "minio_endpoint", "mailpit", "appfront_dir"}
)
EPHEMERAL_PREFIX = "ephemeral_"

GROUP_MARKERS: dict[str, str] = {
    "unit": "ci_unit",
    "integration": "ci_integration",
    "ml": "ci_ml",
}
VALID_GROUPS = frozenset(GROUP_MARKERS)

_ALL_CHECK_OK_ATTR = "_ci_split_all_check_ok"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Khai `--ci-split=<nhóm>[,<nhóm>]|all-check`; không truyền thì không lọc gì (B0-09 [6])."""
    parser.addoption(
        OPTION_NAME,
        action="store",
        default=None,
        metavar="NHOM",
        help="Lọc test theo nhóm CI: unit,integration,ml (hợp) hoặc 'all-check' (chỉ đếm).",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Đăng ký marker `ci_unit`/`ci_integration`/`ci_ml` (bắt buộc vì `strict_markers=true`)."""
    for group, marker in GROUP_MARKERS.items():
        config.addinivalue_line("markers", f"{marker}: test thuộc nhóm CI '{group}' (B0-09 --ci-split)")


def _group_of(item: pytest.Item, rootpath: Path) -> str:
    """Nhóm suy ra từ đường dẫn (ưu tiên `apps/ml/`) rồi tới bao đóng fixture của `item`.

    `item.path` luôn nằm dưới `rootpath` (pytest chỉ thu thập trong `testpaths`), nên không
    bọc `try/except`: lệch giả định này là lỗi thật, không nuốt (R-16).
    """
    parts = item.path.relative_to(rootpath).parts
    if parts[:2] == ("apps", "ml"):
        return "ml"
    if _uses_service_fixture(item):
        return "integration"
    return "unit"


def _uses_service_fixture(item: pytest.Item) -> bool:
    """`True` khi bao đóng fixture (`item.fixturenames`, đã gồm phụ thuộc gián tiếp) đụng dịch vụ thật."""
    names = getattr(item, "fixturenames", ())
    return any(name in SERVICE_FIXTURE_NAMES or name.startswith(EPHEMERAL_PREFIX) for name in names)


def _parse_groups(raw: str) -> set[str]:
    """Tách `raw` thành tập nhóm hợp lệ; nhóm lạ hoặc rỗng ném `UsageError` (fail-closed, R-17)."""
    groups = {piece.strip() for piece in raw.split(",")}
    if not groups <= VALID_GROUPS:
        raise pytest.UsageError(f"{OPTION_NAME}: nhóm lạ trong '{raw}', hợp lệ: {sorted(VALID_GROUPS)}")
    return groups


def _explicit_group_marker(item: pytest.Item) -> str | None:
    """Nhóm test tự khai tường minh (`@pytest.mark.ci_integration`…), nếu có, trước khi plugin gắn gì.

    Ưu tiên hơn suy luận từ đường dẫn/fixture — lối thoát cho test dựng Testcontainers **trực
    tiếp** (không qua fixture dịch vụ, vd `test_main_real_app_passes` của H2) mà suy luận tự động
    xếp nhầm `unit`. Không tính là "rơi hai nhóm" ở `all-check` vì khi có marker tường minh, plugin
    **không** tự gắn thêm marker suy luận cho item đó (xem `pytest_collection_modifyitems`).
    """
    for group, marker in GROUP_MARKERS.items():
        if item.get_closest_marker(marker):
            return group
    return None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Gắn marker nhóm cho mọi test thu được, rồi lọc/đếm theo `--ci-split` nếu có truyền.

    Test đã tự mang marker `ci_*` (khai tường minh trong mã) giữ nguyên nhóm đó — plugin không
    ghi đè, không cộng thêm marker suy luận (tránh đếm hai lần ở `all-check`).
    """
    rootpath = config.rootpath
    for item in items:
        if _explicit_group_marker(item) is None:
            item.add_marker(GROUP_MARKERS[_group_of(item, rootpath)])

    raw = config.getoption(OPTION_NAME)
    if raw is None:
        return
    if raw == ALL_CHECK:
        _run_all_check(config, items)
        return

    requested = _parse_groups(raw)
    keep = [item for item in items if any(item.get_closest_marker(GROUP_MARKERS[g]) for g in requested)]
    deselected = [item for item in items if item not in keep]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = keep


def _run_all_check(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Đếm mỗi nhóm rồi thoát ngay (không chạy test nào, `all-check` chỉ để CI đếm/kiểm).

    Đếm dựa trên marker đã gắn ở trên **cộng** marker `ci_*` mà chính test đã tự mang (vd bản
    thân test dùng `@pytest.mark.ci_unit` dù bao đóng fixture của nó tính ra `integration`):
    một test như vậy mang hai marker nhóm, bị đếm hai lần, làm tổng lệch khỏi `len(items)` —
    đó chính là điều kiện hỏng chung cho cả hai case "rơi hai nhóm" và "tổng lệch" ở [8].
    Dùng `pytest.exit` (không phải `UsageError`, việc này không phải lỗi tham số dòng lệnh) để
    dừng phiên ngay tại bước thu thập, mã thoát khác 0 cho CI đọc được.

    **Số đếm ở đây đứng TRƯỚC bộ lọc `-m "not gpu and not perf"`** (`addopts` gốc,
    `pyproject.toml`): hook `pytest_collection_modifyitems` của plugin này chạy trước hook lọc
    `-m` tích hợp của pytest trong cùng phiên thu thập, nên `items` tại đây còn nguyên mọi test
    `gpu`/`perf`. Một lượt `--ci-split=<nhóm>` thật (không phải `all-check`) chạy tới lúc pytest
    tổng kết "N selected" thì bộ lọc `-m` đã loại xong — số "selected" cuối cùng có thể **ít
    hơn** đúng bằng số test `gpu`/`perf` trong nhóm đó so với số `all-check` in ra. Không phải
    lỗi phân loại: cả hai lượt đều nhất quán trong chính phiên của nó (đo thật, B0-09 m-fix).
    """
    counts = {group: 0 for group in GROUP_MARKERS}
    conflicted: list[str] = []
    total_membership = 0
    for item in items:
        item_groups = [group for group, marker in GROUP_MARKERS.items() if item.get_closest_marker(marker)]
        for group in item_groups:
            counts[group] += 1
        total_membership += len(item_groups)
        if len(item_groups) > 1:
            conflicted.append(item.nodeid)

    _print_all_check(config, counts, len(items))

    if total_membership != len(items):
        # total_membership > len(items) chỉ xảy ra khi ≥1 test rơi hai nhóm (mỗi test luôn
        # mang đúng một marker do chính plugin gắn); hai điều kiện hỏng ở [8] gộp về một
        # nhánh vì chúng luôn xảy ra cùng lúc — nhánh còn lại (bằng nhau) không tách được
        # test riêng cho "chỉ tổng lệch mà không có test rơi hai nhóm" (R-14).
        pytest.exit(
            f"ci_split all-check: tổng nhóm ({total_membership}) khác số test thu được "
            f"({len(items)}); test rơi hai nhóm: {', '.join(conflicted)}",
            returncode=1,
        )
    deselected = list(items)
    items[:] = []
    config.hook.pytest_deselected(items=deselected)
    setattr(config, _ALL_CHECK_OK_ATTR, True)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Ép mã thoát 0 khi `all-check` sạch — CLI job.sh coi "thoát khác 0" là hỏng.

    `pytest` tự trả `NO_TESTS_COLLECTED` (5) vì `_run_all_check` bỏ chọn toàn bộ item để không
    chạy test nào; đó không phải lỗi (hợp đồng B0-09 §2: "thoát khác 0 **khi hỏng**"), nên chỉ nới
    đúng mã 5 và đúng khi lượt `all-check` đã xác nhận tổng khớp (không nới cho lý do khác).
    """
    if getattr(session.config, _ALL_CHECK_OK_ATTR, False) and exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK


def _print_all_check(config: pytest.Config, counts: dict[str, int], total: int) -> None:
    """In số test mỗi nhóm qua terminal reporter (không `print`, ruff T20 cấm ngoài test).

    Không tự vệ `reporter is None`: plugin lõi `terminalreporter` luôn có mặt trừ khi ai đó
    chủ động tắt bằng `-p no:terminalreporter` — nhánh đó không test được nên không viết (R-14).
    """
    reporter = cast(TerminalReporter, config.pluginmanager.get_plugin("terminalreporter"))
    for group, count in sorted(counts.items()):
        reporter.write_line(f"ci_split all-check: nhóm {group} = {count}")
    reporter.write_line(f"ci_split all-check: tổng thu được = {total}")
