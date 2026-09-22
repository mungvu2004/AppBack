"""Test plugin `--ci-split` (`packages/testing/fixtures/ci_split.py`) bằng `pytester`.

`pytester` là plugin lõi của pytest, tắt mặc định — bật bằng `pytest_plugins = ["pytester"]`
ngay trong file này (không sửa `conftest.py` gốc, không `conftest.py` lồng, B0-09 [4]). Mọi
dự án con dựng bằng `pytester.makepyfile`/`pytester.path` là **thư mục tạm cô lập**, không
đụng `conftest.py` hay fixture dịch vụ thật của repo — fixture tên `postgres_url`/`appfront_dir`
khai lại trong đó chỉ để kiểm bộ phân loại theo *tên*, không phải mock dịch vụ đang bị kiểm
(K23 áp cho test dịch vụ, không áp cho test đơn vị của chính bộ phân loại).
"""

import pytest

pytest_plugins = ["pytester"]

PLUGIN_ARG = "-p"
PLUGIN_NAME = "packages.testing.fixtures.ci_split"

_UNIT_INTEGRATION_ML = """
import pytest


@pytest.fixture
def postgres_url():
    return "postgres://fake"


@pytest.fixture
def uses_pg(postgres_url):
    return postgres_url


def test_via_indirect_fixture(uses_pg):
    assert uses_pg


@pytest.fixture
def appfront_dir():
    return "fake-appfront"


def test_via_appfront_dir(appfront_dir):
    assert appfront_dir


def test_plain_unit():
    assert True
"""

_ML_TEST = """
def test_under_apps_ml():
    assert True
"""

_OVERRIDE_TEST = """
import pytest


@pytest.fixture
def postgres_url():
    return "postgres://fake"


@pytest.mark.ci_unit
def test_explicit_marker_overrides_fixture_guess(postgres_url):
    assert postgres_url
"""

_TWO_MARKERS_TEST = """
import pytest


@pytest.mark.ci_unit
@pytest.mark.ci_ml
def test_marked_with_two_group_markers():
    assert True
"""


def _write_project(pytester: pytest.Pytester) -> None:
    """Dựng dự án tạm: 1 unit, 1 integration (gián tiếp), 1 appfront (integration), 1 ml."""
    pytester.makepyfile(test_group=_UNIT_INTEGRATION_ML)
    ml_dir = pytester.path / "apps" / "ml"
    ml_dir.mkdir(parents=True)
    (ml_dir / "test_ml_case.py").write_text(_ML_TEST, encoding="utf-8")


def test_no_option_runs_every_test(pytester: pytest.Pytester) -> None:
    """Case thường: không truyền `--ci-split` → không lọc gì, mọi test chạy (B0-09 [6])."""
    _write_project(pytester)
    result = pytester.runpytest_inprocess(PLUGIN_ARG, PLUGIN_NAME)
    result.assert_outcomes(passed=4)


def test_split_classifies_ml_by_path(pytester: pytest.Pytester) -> None:
    """Case thường: test dưới `apps/ml/` → nhóm `ml`, các test khác bị bỏ chọn."""
    _write_project(pytester)
    result = pytester.runpytest_inprocess(PLUGIN_ARG, PLUGIN_NAME, "--ci-split=ml")
    result.assert_outcomes(passed=1, deselected=3)
    result.stdout.fnmatch_lines(["*apps/ml/test_ml_case.py*"])


def test_split_classifies_indirect_service_fixture_as_integration(pytester: pytest.Pytester) -> None:
    """Case thường: dùng `postgres_url` chỉ qua bao đóng gián tiếp (`uses_pg`) vẫn tính `integration`."""
    _write_project(pytester)
    result = pytester.runpytest_inprocess(PLUGIN_ARG, PLUGIN_NAME, "--ci-split=integration")
    result.assert_outcomes(passed=2, deselected=2)


def test_split_classifies_appfront_dir_as_integration(pytester: pytest.Pytester) -> None:
    """Case thường: `appfront_dir` trực tiếp → `integration`, cùng nhóm với `postgres_url` gián tiếp."""
    _write_project(pytester)
    result = pytester.runpytest_inprocess(PLUGIN_ARG, PLUGIN_NAME, "--ci-split=integration", "-k", "appfront")
    result.assert_outcomes(passed=1, deselected=3)


def test_split_plain_test_is_unit(pytester: pytest.Pytester) -> None:
    """Case thường: test không đụng fixture dịch vụ và không ở `apps/ml/` → `unit`."""
    _write_project(pytester)
    result = pytester.runpytest_inprocess(PLUGIN_ARG, PLUGIN_NAME, "--ci-split=unit")
    result.assert_outcomes(passed=1, deselected=3)


def test_split_union_of_two_groups(pytester: pytest.Pytester) -> None:
    """Case thường: `--ci-split=unit,integration` lấy hợp — tổng chạy = unit + integration."""
    _write_project(pytester)
    result = pytester.runpytest_inprocess(PLUGIN_ARG, PLUGIN_NAME, "--ci-split=unit,integration")
    result.assert_outcomes(passed=3, deselected=1)


def test_split_all_groups_deselects_nothing(pytester: pytest.Pytester) -> None:
    """Case biên: hợp cả 3 nhóm chọn hết mọi test — không có gì để bỏ chọn."""
    _write_project(pytester)
    result = pytester.runpytest_inprocess(PLUGIN_ARG, PLUGIN_NAME, "--ci-split=unit,integration,ml")
    result.assert_outcomes(passed=4)


def test_split_union_whitespace_tolerant(pytester: pytest.Pytester) -> None:
    """Case biên: khoảng trắng quanh dấu phẩy vẫn được `_parse_groups` chấp nhận."""
    _write_project(pytester)
    result = pytester.runpytest_inprocess(PLUGIN_ARG, PLUGIN_NAME, "--ci-split= unit , ml ")
    result.assert_outcomes(passed=2, deselected=2)


def test_split_unknown_group_is_usage_error(pytester: pytest.Pytester) -> None:
    """Case lỗi: nhóm lạ → thoát mã dùng sai (`UsageError`), không chạy test nào."""
    _write_project(pytester)
    result = pytester.runpytest_inprocess(PLUGIN_ARG, PLUGIN_NAME, "--ci-split=bogus")
    assert result.ret == 4  # ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*--ci-split*bogus*"])


def test_split_empty_value_is_usage_error(pytester: pytest.Pytester) -> None:
    """Case biên: `--ci-split=` rỗng → cũng là nhóm lạ, fail-closed (R-17)."""
    _write_project(pytester)
    result = pytester.runpytest_inprocess(PLUGIN_ARG, PLUGIN_NAME, "--ci-split=")
    assert result.ret == 4


def test_all_check_prints_counts_and_deselects_everything(pytester: pytest.Pytester) -> None:
    """Case thường: `all-check` không chạy test nào, in đúng số lượng mỗi nhóm, thoát **0**.

    `pytest_sessionfinish` của plugin nới đúng mã `NO_TESTS_COLLECTED` (5, pytest tự trả vì mọi
    item bị bỏ chọn) về 0 khi tổng đã khớp — hợp đồng B0-09 §2 "thoát khác 0 **khi hỏng**".
    """
    _write_project(pytester)
    result = pytester.runpytest_inprocess(PLUGIN_ARG, PLUGIN_NAME, "--ci-split=all-check")
    assert result.ret == 0
    result.assert_outcomes(deselected=4)
    result.stdout.fnmatch_lines(
        [
            "*ci_split all-check: nhóm integration = 2*",
            "*ci_split all-check: nhóm ml = 1*",
            "*ci_split all-check: nhóm unit = 1*",
            "*ci_split all-check: tổng thu được = 4*",
        ]
    )


def test_explicit_marker_overrides_fixture_based_guess(pytester: pytest.Pytester) -> None:
    """Case thường: marker `ci_unit` tường minh thắng suy luận từ `postgres_url` — không rơi hai nhóm.

    Cùng luật cho phép `tools/ci/tests/test_h2.py::test_main_real_app_passes` tự khai
    `ci_integration` dù không dùng fixture dịch vụ nào (Testcontainers dựng trực tiếp).
    """
    pytester.makepyfile(test_override=_OVERRIDE_TEST)
    result = pytester.runpytest_inprocess(PLUGIN_ARG, PLUGIN_NAME, "--ci-split=all-check")
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*ci_split all-check: nhóm unit = 1*", "*ci_split all-check: tổng thu được = 1*"])


def test_all_check_fails_when_test_carries_two_group_markers(pytester: pytest.Pytester) -> None:
    """Case lỗi: test tự mang **hai** marker `ci_*` cùng lúc → rơi hai nhóm thật, tổng lệch → hỏng."""
    pytester.makepyfile(test_two_markers=_TWO_MARKERS_TEST)
    result = pytester.runpytest_inprocess(PLUGIN_ARG, PLUGIN_NAME, "--ci-split=all-check")
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*tổng nhóm*test rơi hai nhóm*test_marked_with_two_group_markers*"])
