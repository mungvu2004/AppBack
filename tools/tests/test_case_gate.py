"""tools/case_gate.py — [8]: từng nhánh CASE §2.3 (đầu vào dựng tạm trong test)."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from tools import case_gate
from tools.case_gate import (
    CaseTraceEntry,
    EndpointOverride,
    Operation,
    TaskRequirement,
    TestResult,
    check_gpu_markers,
    check_skipped_xfail,
    evaluate,
    load_cases_toml,
    parse_case_trace,
    parse_junit,
    required_cases_for,
)
from tools.charter import BindRow


def _row(**kw: Any) -> BindRow:
    base: dict[str, Any] = dict(
        row_id="1",
        method="POST",
        path="/api/x",
        operation_id="x_create",
        case_type="G",
        outside=False,
        lock="thành viên",
        logged=True,
        owner="B9-99",
    )
    base.update(kw)
    return BindRow(**base)


def _op(**kw: Any) -> Operation:
    base: dict[str, Any] = dict(op="x_create", method="POST", path="/api/x", protected=True)
    base.update(kw)
    return Operation(**base)


# --- required_cases_for: các nhánh chính của §2.2 -----------------------------


def test_case_chung_chỉ_khi_protected() -> None:
    row = _row(case_type="C", lock="—")
    req_public = required_cases_for(row, _op(protected=False))
    req_protected = required_cases_for(_row(case_type="G"), _op(protected=True))
    assert not ({"C04", "C05", "C12", "C13", "C25"} & req_public)
    assert {"C04", "C05", "C12", "C13", "C25"} <= req_protected


def test_c10_c22_chỉ_khi_ghi_và_có_idempotency() -> None:
    row = _row(case_type="G")
    req = required_cases_for(row, _op(protected=True, idempotency="default", versioned=False))
    assert {"C10", "C22"} <= req
    req_get = required_cases_for(_row(case_type="Đ"), _op(method="GET", protected=True))
    assert not ({"C10", "C22"} & req_get)
    req_off = required_cases_for(row, _op(protected=True, idempotency="off"))
    assert not ({"C10", "C22"} & req_off)


def test_c07_miễn_khi_khoá_trống() -> None:
    req = required_cases_for(_row(case_type="G", lock="—"), _op(protected=True))
    assert "C07" not in req
    req2 = required_cases_for(_row(case_type="G", lock="layer.edit"), _op(protected=True))
    assert "C07" in req2


def test_c15_chỉ_khi_returns_list() -> None:
    row = _row(case_type="Đ")
    assert "C15" in required_cases_for(row, _op(method="GET", protected=True, returns_list=True))
    assert "C15" not in required_cases_for(row, _op(method="GET", protected=True, returns_list=False))


def test_c02_khi_has_body_hoặc_has_query() -> None:
    row = _row(case_type="G")
    assert "C02" in required_cases_for(row, _op(protected=True, has_body=True, has_query=False))
    assert "C02" in required_cases_for(row, _op(protected=True, has_body=False, has_query=True))
    assert "C02" not in required_cases_for(row, _op(protected=True, has_body=False, has_query=False))


def test_c21_cần_has_body_và_body_mirrors_path() -> None:
    row = _row(case_type="G")
    assert "C21" in required_cases_for(row, _op(protected=True, has_body=True, body_mirrors_path=True))
    assert "C21" not in required_cases_for(row, _op(protected=True, has_body=True, body_mirrors_path=False))


def test_c18_chỉ_khi_nhật_ký_có() -> None:
    assert "C18" in required_cases_for(_row(case_type="G", logged=True), _op(protected=True))
    assert "C18" not in required_cases_for(_row(case_type="G", logged=False), _op(protected=True))


def test_loại_a_c09_c14_khi_versioned() -> None:
    row = _row(case_type="A")
    assert {"C09", "C09b", "C14"} <= required_cases_for(row, _op(protected=True, versioned=True))
    assert not ({"C09", "C09b", "C14"} & required_cases_for(row, _op(protected=True, versioned=False)))


def test_g_sao_c08_c23_chỉ_khi_đường_có_ngoặc() -> None:
    row_id = _row(case_type="G*", path="/api/x/{id}")
    row_noid = _row(case_type="G*", path="/api/x")
    assert {"C08", "C23"} <= required_cases_for(row_id, _op(protected=True))
    assert not ({"C08", "C23"} & required_cases_for(row_noid, _op(protected=True)))


def test_c27_chỉ_login_và_n8_c26_chỉ_n9_n10() -> None:
    login = required_cases_for(_row(row_id="1", case_type="C", lock="—"), _op(protected=False))
    n8 = required_cases_for(_row(row_id="N8", case_type="C", lock="—"), _op(protected=False))
    n9 = required_cases_for(_row(row_id="N9", case_type="C", lock="—"), _op(protected=False))
    other = required_cases_for(_row(row_id="99", case_type="C", lock="—"), _op(protected=False))
    assert "C27" in login
    assert "C27" in n8
    assert "C27" not in n9
    assert "C26" in n9
    assert "C27" not in other
    assert "C26" not in other


def test_case_thêm_cố_định() -> None:
    row10 = _row(row_id="10", case_type="G")
    assert "C14" in required_cases_for(row10, _op(protected=True))
    row_n3 = _row(row_id="N3", case_type="G")
    req = required_cases_for(row_n3, _op(protected=True))
    assert {"C14", "C11"} <= req


def test_trường_thiếu_coi_là_áp_dụng() -> None:
    row = _row(case_type="Đ")
    # returns_list=None (chưa có B0-06) -> coi là True -> C15 vẫn bắt buộc
    req = required_cases_for(row, _op(method="GET", protected=True, returns_list=None))
    assert "C15" in req


# --- evaluate: found/missing, miễn, task ---------------------------------------


def test_miễn_chỉ_c16_được_phép() -> None:
    row = _row(row_id="1", case_type="G")
    op = _op(protected=True)
    overrides = {"x_create": EndpointOverride(waive={"C16": "thân không có chuỗi người nhập nào cả"})}
    result = evaluate([op], [row], overrides, [], [], [], [])
    r = result.op_results[0]
    assert "C16" not in r.missing
    assert "C16" in r.waived


def test_miễn_case_khác_c16_bị_cấm() -> None:
    row = _row(row_id="1", case_type="G")
    op = _op(protected=True)
    overrides = {"x_create": EndpointOverride(waive={"C06": "lý do dài đủ mười ký tự abc"})}
    result = evaluate([op], [row], overrides, [], [], [], [])
    assert any("miễn case khác" in f for f in result.findings)


def test_miễn_lý_do_ngắn_bị_cấm() -> None:
    row = _row(row_id="1", case_type="G")
    op = _op(protected=True)
    overrides = {"x_create": EndpointOverride(waive={"C16": "ngắn"})}
    result = evaluate([op], [row], overrides, [], [], [], [])
    assert any("quá ngắn" in f for f in result.findings)


def test_found_qua_junit_và_trace() -> None:
    row = _row(row_id="1", case_type="C", lock="—")
    op = _op(protected=False, has_body=False, has_query=False)
    tests = [TestResult(name="test_x_create__C01", outcome="passed")]
    trace = [CaseTraceEntry(test="test_x_create__C01", op="x_create", status=200)]
    result = evaluate([op], [row], {}, tests, trace, [], [])
    assert "C01" in result.op_results[0].found


def test_found_cần_status_khớp_mã_cố_định() -> None:
    row = _row(row_id="1", case_type="C", lock="—")
    op = _op(protected=False)
    tests = [TestResult(name="test_x_create__C06", outcome="passed")]
    trace_wrong = [CaseTraceEntry(test="test_x_create__C06", op="x_create", status=403)]  # cần 404
    result = evaluate([op], [row], {}, tests, trace_wrong, [], [])
    assert "C06" not in result.op_results[0].found


def test_op_mounted_không_có_be_bind_cảnh_báo() -> None:
    op = _op(op="lạ_không_có_trong_bind")
    result = evaluate([op], [], {}, [], [], [], [])
    assert "lạ_không_có_trong_bind" in result.unmounted_warnings
    assert not result.op_results


def test_task_thiếu_j01_j06_hỏng() -> None:
    result = evaluate([], [], {}, [], [], ["segment_walls"], [])
    assert any("segment_walls" in m for m in result.task_missing)


def test_task_đủ_j01_j06_đạt() -> None:
    tests = [
        TestResult(name="test_segment_walls__J01", outcome="passed"),
        TestResult(name="test_segment_walls__J06", outcome="passed"),
    ]
    result = evaluate([], [], {}, tests, [], ["segment_walls"], [])
    assert not result.task_missing


def test_task_lạ_trong_cases_toml_hỏng() -> None:
    result = evaluate([], [], {}, [], [], [], [TaskRequirement(fn="không_tồn_tại", require=set())])
    assert any("task lạ" in f for f in result.findings)


def test_hai_task_trùng_tên_hàm_hỏng() -> None:
    result = evaluate([], [], {}, [], [], ["segment_walls", "segment_walls"], [])
    assert any("trùng tên hàm" in f for f in result.findings)


def test_task_require_thêm_case() -> None:
    tests = [
        TestResult(name="test_train__J01", outcome="passed"),
        TestResult(name="test_train__J06", outcome="passed"),
    ]
    result = evaluate([], [], {}, tests, [], ["train"], [TaskRequirement(fn="train", require={"J03"})])
    assert any("train" in m and "J03" in m for m in result.task_missing)


# --- skipped / xfail -----------------------------------------------------------


def test_skipped_thường_hỏng() -> None:
    tests = [TestResult(name="test_x__C01", outcome="skipped", skip_reason="tạm tắt")]
    findings = check_skipped_xfail(tests)
    assert findings


def test_skipped_tham_số_rỗng_được_miễn() -> None:
    tests = [
        TestResult(
            name="test_x__C01",
            outcome="skipped",
            skip_reason="got empty parameter set for parametrize()",
        )
    ]
    assert check_skipped_xfail(tests) == []


def test_xfail_luôn_hỏng() -> None:
    tests = [TestResult(name="test_x__C01", outcome="passed", is_xfail=True)]
    assert check_skipped_xfail(tests)


# --- junit / case trace parsing -------------------------------------------------


def test_parse_junit_skipped_xfail(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text(
        """<?xml version="1.0"?>
<testsuites><testsuite>
<testcase classname="pkg.tests.test_a" name="test_a__C01"></testcase>
<testcase classname="pkg.tests.test_b" name="test_b__C02">
  <skipped message="got empty parameter set for parametrize()" />
</testcase>
<testcase classname="pkg.tests.test_c" name="test_c__C03">
  <skipped type="pytest.xfail" message="lý do" />
</testcase>
</testsuite></testsuites>""",
        encoding="utf-8",
    )
    results = parse_junit(junit)
    by_name = {r.name: r for r in results}
    assert by_name["test_a__C01"].outcome == "passed"
    assert by_name["test_b__C02"].outcome == "skipped"
    assert by_name["test_c__C03"].is_xfail is True


def test_parse_case_trace_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "trace.jsonl"
    p.write_text(
        '{"test": "t1", "op": "x_create", "status": 200, "code": null}\n'
        '{"test": "t2", "op": "x_create", "status": 422, "code": "VALIDATION"}\n',
        encoding="utf-8",
    )
    entries = parse_case_trace(p)
    assert len(entries) == 2
    assert entries[1].code == "VALIDATION"


def test_parse_case_trace_thiếu_file_trả_rỗng(tmp_path: Path) -> None:
    assert parse_case_trace(tmp_path / "không-có.jsonl") == []


def test_load_cases_toml(tmp_path: Path) -> None:
    p = tmp_path / "cases.toml"
    p.write_text(
        '[[endpoint]]\nop = "floors_create_floor"\nextra = ["C14"]\n'
        'waive = { C16 = "thân không có chuỗi người nhập" }\n\n'
        '[[task]]\nfn = "segment_walls"\nrequire = ["J03"]\n',
        encoding="utf-8",
    )
    overrides, tasks = load_cases_toml([p])
    assert overrides["floors_create_floor"].extra == {"C14"}
    assert overrides["floors_create_floor"].waive["C16"].startswith("thân")
    assert tasks == [TaskRequirement(fn="segment_walls", require={"J03"})]


# --- marker gpu ngoài apps/ml/** -------------------------------------------------


def _write_test(root: Path, rel: str, body: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def test_gpu_ngoài_apps_ml_hỏng(tmp_path: Path) -> None:
    _write_test(
        tmp_path,
        "packages/vision/tests/test_a.py",
        "import pytest\n\n@pytest.mark.gpu\ndef test_a() -> None:\n    pass\n",
    )
    assert check_gpu_markers(tmp_path) == ["marker gpu ngoài apps/ml/**: packages/vision/tests/test_a.py"]


def test_gpu_qua_pytestmark_ngoài_apps_ml_hỏng(tmp_path: Path) -> None:
    _write_test(tmp_path, "apps/api/x/tests/test_b.py", "import pytest\n\npytestmark = [pytest.mark.gpu]\n")
    assert len(check_gpu_markers(tmp_path)) == 1


def test_gpu_trong_apps_ml_đạt(tmp_path: Path) -> None:
    _write_test(
        tmp_path,
        "apps/ml/training/tests/test_c.py",
        "import pytest\n\n@pytest.mark.gpu\ndef test_c() -> None:\n    pass\n",
    )
    assert check_gpu_markers(tmp_path) == []


def test_marker_khác_không_bị_nhầm_là_gpu(tmp_path: Path) -> None:
    _write_test(
        tmp_path,
        "packages/vision/tests/test_d.py",
        "import pytest\n\n@pytest.mark.perf\ndef test_d() -> None:\n    pass\n",
    )
    assert check_gpu_markers(tmp_path) == []


# --- +ngoài (CASE §2.1) ------------------------------------------------------------


def _outside_setup() -> tuple[BindRow, Operation]:
    row = _row(row_id="44", case_type="A", outside=True, lock="user.manage")
    return row, _op(protected=True, idempotency="default", versioned=False)


def test_ngoài_không_được_thoả_bằng_test_common_c10() -> None:
    row, op = _outside_setup()
    tests = [TestResult(name="test_common__C10[x_create]", outcome="passed")]
    trace = [CaseTraceEntry(test="test_common__C10[x_create]", op="x_create", status=200)]
    result = evaluate([op], [row], {}, tests, trace, [], [])
    assert "C10" in result.op_results[0].missing


def test_ngoài_thoả_bằng_test_riêng_c10() -> None:
    row, op = _outside_setup()
    tests = [TestResult(name="test_x_create__C10_không_lặp_thư", outcome="passed")]
    trace = [CaseTraceEntry(test="test_x_create__C10_không_lặp_thư", op="x_create", status=200)]
    result = evaluate([op], [row], {}, tests, trace, [], [])
    assert "C10" in result.op_results[0].found


def test_ngoài_với_idempotency_off_hỏng() -> None:
    row, _ = _outside_setup()
    op = _op(protected=True, idempotency="off")
    result = evaluate([op], [row], {}, [], [], [], [])
    assert any("+ngoài" in f for f in result.findings)


def test_case_chung_thoả_bằng_test_common() -> None:
    row = _row(case_type="Đ", method="GET")
    op = _op(method="GET", protected=True)
    tests = [TestResult(name="test_common__C04[x_create]", outcome="passed")]
    trace = [CaseTraceEntry(test="test_common__C04[x_create]", op="x_create", status=401)]
    result = evaluate([op], [row], {}, tests, trace, [], [])
    assert "C04" in result.op_results[0].found


def test_id_tham_số_sau_mã_case_được_tính() -> None:
    row = _row(case_type="G")
    op = _op(protected=True)
    tests = [TestResult(name="test_x_create__C02[name]", outcome="passed")]
    trace = [CaseTraceEntry(test="test_x_create__C02[name]", op="x_create", status=422, code="VALIDATION")]
    result = evaluate([op], [row], {}, tests, trace, [], [])
    assert "C02" in result.op_results[0].found


def test_đường_be_bind_có_query_khớp_thao_tác() -> None:
    from tools.charter import load_bind_rows

    rows = load_bind_rows(case_gate.REPO_ROOT / "docs" / "charter" / "BE-BIND.md")
    op = Operation(op="versions_list_versions", method="GET", path="/api/projects/{project_id}/versions")
    result = evaluate([op], rows, {}, [], [], [], [])
    assert not result.unmounted_warnings
    assert result.op_results[0].row_id == "N17"


def test_task_có_j01_thiếu_j06_hỏng() -> None:
    tests = [TestResult(name="test_segment_walls__J01", outcome="passed")]
    result = evaluate([], [], {}, tests, [], ["segment_walls"], [])
    assert result.task_missing == ["segment_walls: thiếu ['J06']"]


def test_test_chỉ_có_trong_junit_perf_vẫn_được_tính(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text("<testsuites><testsuite></testsuite></testsuites>", encoding="utf-8")
    perf = tmp_path / "junit-perf.xml"
    perf.write_text(
        '<testsuite><testcase classname="a.tests.test_p" name="test_segment_walls__J01"/>'
        '<testcase classname="a.tests.test_p" name="test_segment_walls__J06"/></testsuite>',
        encoding="utf-8",
    )
    tests = parse_junit(junit, perf, tmp_path / "không-có.xml")
    result = evaluate([], [], {}, tests, [], ["segment_walls"], [])
    assert not result.task_missing


def test_parse_junit_failure_error(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text(
        "<testsuite>"
        '<testcase name="test_a"><failure message="x"/></testcase>'
        '<testcase name="test_b"><error message="y"/></testcase>'
        "</testsuite>",
        encoding="utf-8",
    )
    outcomes = {t.name: t.outcome for t in parse_junit(junit)}
    assert outcomes == {"test_a": "failed", "test_b": "error"}


def test_test_hỏng_không_được_tính() -> None:
    row = _row(case_type="C", lock="—")
    op = _op(protected=False)
    tests = [TestResult(name="test_x_create__C01", outcome="failed")]
    trace = [CaseTraceEntry(test="test_x_create__C01", op="x_create", status=200)]
    result = evaluate([op], [row], {}, tests, trace, [], [])
    assert "C01" not in result.op_results[0].found


# --- nối dữ liệu thật ------------------------------------------------------------------


def test_optional_attr_module_thiếu_trả_none() -> None:
    assert case_gate._optional_attr("apps.api.core.khong_ton_tai", "operations") is None
    assert case_gate._optional_attr("json", "dumps") is json.dumps


def test_real_operations_chép_đúng_trường_bỏ_trường_lạ(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_op = types.SimpleNamespace(op="x_create", method="POST", path="/api/x", protected=True, body_limit=1024)
    fake = types.SimpleNamespace(operations=lambda: [fake_op])
    monkeypatch.setitem(sys.modules, "apps.api.core.openapi", fake)
    ops = case_gate._real_operations()
    assert ops == [Operation(op="x_create", method="POST", path="/api/x", protected=True)]


def test_real_operations_khi_chủ_chưa_hợp_nhất_trả_rỗng(monkeypatch: pytest.MonkeyPatch) -> None:
    """Module có mà chưa có `operations` (prompt chủ chưa hợp nhất) → cổng chạy với 0 thao tác.

    Vắng mặt được dựng bằng `sys.modules`, không bằng trạng thái thật của repo: mọi
    prompt mount route đều làm sổ thao tác **khác rỗng** (CASE §2.3).
    """
    monkeypatch.setitem(sys.modules, "apps.api.core.openapi", types.SimpleNamespace())
    assert case_gate._real_operations() == []


def test_real_operations_đọc_được_sổ_thật() -> None:
    """Có `apps.api.core.openapi` thì cổng đọc được sổ thật và chép đúng kiểu gương."""
    assert all(isinstance(operation, Operation) for operation in case_gate._real_operations())


def test_real_task_names(monkeypatch: pytest.MonkeyPatch) -> None:
    import packages.messaging

    monkeypatch.setattr(packages.messaging, "registered_tasks", list, raising=False)
    assert case_gate._real_task_names() == []
    monkeypatch.setattr(packages.messaging, "registered_tasks", lambda: ["a", "b"], raising=False)
    assert case_gate._real_task_names() == ["a", "b"]


def test_main_đạt_khi_chưa_có_thao_tác(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Sổ thao tác và sổ task dựng tạm tại chỗ: cổng không được phụ thuộc repo đang có gì."""
    monkeypatch.setattr(case_gate, "JUNIT_PATHS", (tmp_path / "không-có.xml",))
    monkeypatch.setattr(case_gate, "_real_operations", list)
    monkeypatch.setattr(case_gate, "_real_task_names", list)
    assert case_gate.main() == 0


def test_main_hỏng_in_bảng(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<testsuite><testcase name="test_a"><skipped message="tạm tắt"/></testcase></testsuite>',
        encoding="utf-8",
    )
    trace = tmp_path / "trace.jsonl"
    trace.write_text("", encoding="utf-8")
    monkeypatch.setattr(case_gate, "JUNIT_PATHS", (junit,))
    monkeypatch.setenv("CASE_TRACE_FILE", str(trace))
    monkeypatch.setattr(
        case_gate,
        "_real_operations",
        lambda: [
            Operation(op="auth_login", method="POST", path="/api/auth/login", protected=False),
            Operation(op="lạ_không_bind", method="GET", path="/api/lạ"),
        ],
    )
    monkeypatch.setattr(case_gate, "_real_task_names", lambda: ["segment_walls"])
    assert case_gate.main() == 1
    out = capsys.readouterr().out
    assert "auth_login | bắt buộc" in out
    assert "CẢNH BÁO: lạ_không_bind" in out
    assert "HỎNG: test bị bỏ qua" in out
    assert "HỎNG task: segment_walls" in out
