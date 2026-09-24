"""Test tĩnh cho `deploy/nginx/**` (hợp đồng §3, prompt [6]/[8]).

`alias`/`root` cục bộ (K15): kiểm tra bằng cách cấm hẳn chỉ thị `alias` — cách duy
nhất một `location` ánh xạ 1-1 sang thư mục đĩa tuỳ ý; `root` chỉ dùng cho thư mục
dist SPA tĩnh (không phải nơi lưu file người dùng tải lên), nên không cần cấm riêng.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from deploy.tests.nginx_reader import Node, direct_includes, find_directive, parse_nginx, resolve_includes, walk
from deploy.tests.support import REPO_ROOT, require_path

NGINX_ROOT = REPO_ROOT / "deploy" / "nginx"
_MINIO_VHOST_SUFFIX = "templates/prod/minio.conf.template"
_BARE_NGINX_VAR_RE = re.compile(r"^\$[A-Za-z_][A-Za-z0-9_]*$")


def _all_nginx_files() -> dict[Path, list[Node]]:
    """Đọc mọi `.conf`/`.conf.template` dưới `deploy/nginx/`; `fail` nếu không có file nào.

    Cây vật lý từng file, giữ nguyên `include` — dùng cho luật kiểm include trực
    tiếp (một `location` có include đúng snippet của nó)."""
    require_path("deploy/nginx")
    files = sorted({*NGINX_ROOT.glob("**/*.conf"), *NGINX_ROOT.glob("**/*.conf.template")})
    if not files:
        pytest.fail("thiếu file cấu hình nginx dưới deploy/nginx/")
    return {path: parse_nginx(path.read_text(encoding="utf-8")) for path in files}


def _entry_files_assembled() -> dict[Path, list[Node]]:
    """Các file nginx là **điểm vào thật** (`templates/{dev,prod}/*.conf.template` —
    nạp trực tiếp qua `NGINX_ENVSUBST_TEMPLATE_DIR`), với mọi `include` đã lắp ráp
    (snippet không tự đứng làm cấu hình nên không có ngữ cảnh — `resolver`, `set`
    khai ở template cha chỉ thấy được qua cây đã lắp ráp)."""
    require_path("deploy/nginx")
    files = sorted(NGINX_ROOT.glob("templates/*/*.conf.template"))
    if not files:
        pytest.fail("thiếu file template nginx dưới deploy/nginx/templates/")
    return {path: resolve_includes(parse_nginx(path.read_text(encoding="utf-8")), NGINX_ROOT) for path in files}


def _is_minio_vhost(path: Path) -> bool:
    """`True` nếu `path` là vhost MinIO (không chịu luật của server ứng dụng)."""
    return path.as_posix().endswith(_MINIO_VHOST_SUFFIX)


def _require_snippet(relative: str) -> list[Node]:
    """Nạp một snippet cụ thể dưới `deploy/nginx/`; `fail` rõ nếu chưa có."""
    path = require_path(f"deploy/nginx/{relative}")
    return parse_nginx(path.read_text(encoding="utf-8"))


def _walk_with_ancestors(
    nodes: list[Node], ancestors: tuple[Node, ...] = ()
) -> Iterator[tuple[Node, tuple[Node, ...]]]:
    """Duyệt cây kèm danh sách khối cha (từ ngoài vào trong) — cần để kiểm `resolver`
    "cùng khối/khối cha" với `proxy_pass`."""
    for node in nodes:
        yield node, ancestors
        yield from _walk_with_ancestors(node.children, (*ancestors, node))


def _proxy_headers(nodes: list[Node]) -> dict[str, str]:
    """`{tên header: giá trị}` của mọi `proxy_set_header` ở cấp trực tiếp `nodes`."""
    return {n.args[0]: " ".join(n.args[1:]) for n in nodes if n.directive == "proxy_set_header" and n.args}


def _locations_matching(files: dict[Path, list[Node]], predicate: Callable[[Node], bool]) -> list[tuple[Path, Node]]:
    """Mọi `(file, location)` mà `predicate(location)` đúng, quét toàn bộ cây (kể cả lồng)."""
    return [(path, loc) for path, nodes in files.items() for loc in find_directive(nodes, "location") if predicate(loc)]


def test_nginx_every_proxy_location_includes_proxy_common() -> None:
    """Mọi `location` có `proxy_pass` phải `include proxy_common.conf` (một
    `proxy_set_header` khai trực tiếp trong `location` xoá hết header thừa kế) — kể
    cả vhost MinIO: `proxy_common.conf` đặt `Host $appback_proxy_host` (biến, không
    hằng `$host`), mỗi server tự `set $appback_proxy_host` theo giá trị của mình
    (`$host` cho app, `$http_host` cho MinIO) nên không còn xung đột header `Host`
    (hợp đồng B0-08 §3 bản CHỐT 1, sự cố đo thật ở bản W `f23bfc4`)."""
    for path, nodes in _all_nginx_files().items():
        for loc in find_directive(nodes, "location"):
            if any(c.directive == "proxy_pass" for c in loc.children):
                assert "proxy_common.conf" in direct_includes(loc), (
                    f"{path}: location {loc.args} có proxy_pass nhưng thiếu include proxy_common.conf"
                )


_ERROR_BODY_SNIPPETS = {"error_413_body.conf", "error_503_body.conf"}


def test_nginx_every_spa_location_includes_security_headers() -> None:
    """Mọi `location` phục vụ SPA (không `proxy_pass`, không `internal`, không
    `return`) trong server ứng dụng (không phải vhost MinIO) phải `include
    security_headers.conf`.

    Bốn location lỗi `/__errors/…` mang `internal`/`return` trong snippet thân dùng
    chung (`error_{413,503}_body.conf`, R-07) chứ không ở cây vật lý của chính nó,
    nên nhận ra chúng bằng tên snippet — không phải là location SPA."""
    for path, nodes in _all_nginx_files().items():
        if _is_minio_vhost(path):
            continue
        for loc in find_directive(nodes, "location"):
            child_names = {c.directive for c in loc.children}
            if child_names & {"proxy_pass", "internal", "return"}:
                continue
            if direct_includes(loc) & _ERROR_BODY_SNIPPETS:
                continue
            assert "security_headers.conf" in direct_includes(loc), (
                f"{path}: location {loc.args} phục vụ SPA nhưng thiếu include security_headers.conf"
            )


def test_nginx_no_proxy_intercept_errors_on() -> None:
    """Cấm `proxy_intercept_errors on` — thân 503 `IDEMPOTENCY_IN_PROGRESS` của app phải
    tới FE nguyên vẹn."""
    for path, nodes in _all_nginx_files().items():
        for node in find_directive(nodes, "proxy_intercept_errors"):
            assert node.args != ["on"], f"{path}: cấm proxy_intercept_errors on"


def test_nginx_proxy_pass_uses_variable_and_has_resolver() -> None:
    """Mọi `proxy_pass` là một biến (`$…`), không kèm URI; có `resolver` ở cùng khối
    hoặc khối cha (nginx lên được khi upstream chưa lên, theo kịp container mới) — xét
    trên cây đã lắp ráp include vì `resolver` thường khai ở template, không ở snippet
    chứa `proxy_pass`."""
    for path, nodes in _entry_files_assembled().items():
        for node, ancestors in _walk_with_ancestors(nodes):
            if node.directive != "proxy_pass":
                continue
            assert len(node.args) == 1, f"{path}: proxy_pass {node.args} phải là một biến duy nhất"
            assert _BARE_NGINX_VAR_RE.match(node.args[0]), (
                f"{path}: proxy_pass {node.args[0]!r} không phải biến trần, có thể kèm URI phía sau"
            )
            scopes = [nodes, *(block.children for block in ancestors)]
            has_resolver = any(any(c.directive == "resolver" for c in scope) for scope in scopes)
            assert has_resolver, f"{path}: proxy_pass {node.args[0]} thiếu resolver cùng khối/khối cha"


def test_nginx_proxy_common_has_required_headers() -> None:
    """`proxy_common.conf`: `Host $appback_proxy_host` (biến — mỗi server tự `set` giá
    trị riêng, tránh hai header `Host` khi vhost MinIO cũng include snippet này),
    `X-Forwarded-For $remote_addr` (không nối), `X-Forwarded-Proto`, `X-Request-Id`.

    Các tham số chịu lỗi khi đổi phiên bản (`proxy_connect_timeout`,
    `proxy_next_upstream…`) do `test_nginx_proxy_common_survives_api_container_swap`
    giữ — không chốt cùng một hằng số ở hai test (R-07)."""
    nodes = _require_snippet("snippets/proxy_common.conf")
    headers = _proxy_headers(nodes)
    assert headers.get("Host") == "$appback_proxy_host", (
        "proxy_common.conf: Host phải là biến $appback_proxy_host, không $host trực tiếp"
    )
    assert headers.get("X-Forwarded-For") == "$remote_addr", "X-Forwarded-For phải là $remote_addr"
    assert "X-Forwarded-Proto" in headers, "proxy_common.conf thiếu X-Forwarded-Proto"
    assert "X-Request-Id" in headers, "proxy_common.conf thiếu X-Request-Id"


def test_nginx_proxy_locations_set_appback_proxy_host() -> None:
    """Mọi `location`/`server` có `proxy_pass` tự `set $appback_proxy_host …;` trước
    khi include `proxy_common.conf` — app đặt `$host`, vhost MinIO đặt `$http_host`
    (chữ ký MinIO tính trên host, hợp đồng B0-08 §3 bản CHỐT 1) — xét trên cây đã lắp
    ráp include, cùng lý do với luật `resolver`."""
    for path, nodes in _entry_files_assembled().items():
        for node, ancestors in _walk_with_ancestors(nodes):
            if node.directive != "proxy_pass":
                continue
            scopes = [nodes, *(block.children for block in ancestors)]
            has_set = any(
                any(c.directive == "set" and c.args[:1] == ["$appback_proxy_host"] for c in scope) for scope in scopes
            )
            assert has_set, f"{path}: proxy_pass thiếu set $appback_proxy_host … cùng khối/khối cha"


def test_nginx_ssl_server_blocks_have_http2_on() -> None:
    """Mọi khối `server` có `listen … ssl` phải có `http2 on` (SSE bị trần 6 kết nối/
    origin trên HTTP/1.1)."""
    for path, nodes in _all_nginx_files().items():
        for server in find_directive(nodes, "server"):
            listens = [n for n in server.children if n.directive == "listen"]
            if not any("ssl" in listen.args for listen in listens):
                continue
            http2 = [n for n in server.children if n.directive == "http2"]
            assert http2, f"{path}: server có listen ssl thiếu http2 on"
            assert http2[0].args == ["on"], f"{path}: server có listen ssl thiếu http2 on"


def test_nginx_app_server_client_max_body_size_8m() -> None:
    """Mọi khối `server` ứng dụng thật sự phục vụ nội dung (có `location`, không phải
    server chỉ redirect 80→443) khai `client_max_body_size 8m` ở cấp server (location
    riêng như N26 được đè lên sau)."""
    for path, nodes in _all_nginx_files().items():
        if _is_minio_vhost(path):
            continue
        for server in find_directive(nodes, "server"):
            if not any(c.directive == "location" for c in server.children):
                continue
            direct = [n for n in server.children if n.directive == "client_max_body_size"]
            assert direct, f"{path}: server thiếu client_max_body_size 8m"
            assert direct[0].args == ["8m"], f"{path}: server thiếu client_max_body_size 8m"


def test_nginx_ml_model_versions_location_body_size() -> None:
    """`location = /api/admin/ml/model-versions`: `client_max_body_size 512m` và
    `proxy_request_buffering off` (tải trọng lượng ONNX lớn)."""
    files = _all_nginx_files()
    matches = _locations_matching(files, lambda loc: loc.args == ["=", "/api/admin/ml/model-versions"])
    assert matches, "không tìm thấy location = /api/admin/ml/model-versions"
    for path, loc in matches:
        sizes = [n.args for n in loc.children if n.directive == "client_max_body_size"]
        assert sizes == [["512m"]], f"{path}: model-versions thiếu client_max_body_size 512m"
        buffering = [n.args for n in loc.children if n.directive == "proxy_request_buffering"]
        assert buffering == [["off"]], f"{path}: model-versions thiếu proxy_request_buffering off"


def test_nginx_streams_location_sse_tuning() -> None:
    """`/api/streams/`: tắt buffer/cache, ép HTTP/1.1, bỏ `Connection`, đọc 1h (SSE)."""
    files = _all_nginx_files()
    matches = _locations_matching(files, lambda loc: bool(loc.args) and loc.args[-1] == "/api/streams/")
    assert matches, "không tìm thấy location /api/streams/"
    for path, loc in matches:
        pairs = {(n.directive, tuple(n.args)) for n in loc.children}
        assert ("proxy_buffering", ("off",)) in pairs, f"{path}: streams thiếu proxy_buffering off"
        assert ("proxy_cache", ("off",)) in pairs, f"{path}: streams thiếu proxy_cache off"
        assert ("proxy_http_version", ("1.1",)) in pairs, f"{path}: streams thiếu proxy_http_version 1.1"
        assert ("proxy_set_header", ("Connection", "")) in pairs, f"{path}: streams thiếu Connection rỗng"
        assert ("proxy_read_timeout", ("1h",)) in pairs, f"{path}: streams thiếu proxy_read_timeout 1h"


def test_nginx_files_location_disables_access_log() -> None:
    """`/api/files/`: `access_log off` NGAY TRONG location, và cả hai `error_page`
    của nó trỏ sang location lỗi riêng cũng `access_log off`.

    Bản cũ tắt log bằng `map $request_uri $appback_access_log` ở mức server vì
    `access_log off` trong location gốc mất tác dụng khi `error_page` chuyển hướng
    nội bộ (nginx ghi log theo location ĐÍCH). Nhưng `$request_uri` là URI THÔ nên
    map phải đoán mọi dạng méo bằng regex và vẫn bỏ lọt `/api/./files/…`,
    `/api/x/../files/…`, `/%61pi/files/…` (NO-095 — vá triệu chứng, R-19). Nay
    quyết định ở mức location, trên `$uri` đã chuẩn hoá, còn chuyển hướng nội bộ
    được xử bằng đích riêng `/__errors/{413,503}-files`. Map phải biến mất hẳn —
    còn nó là còn một nguồn quyết định thứ hai."""
    files = _all_nginx_files()
    matches = _locations_matching(files, lambda loc: bool(loc.args) and loc.args[-1] == "/api/files/")
    assert matches, "không tìm thấy location /api/files/"

    leftover_maps = [
        m for nodes in files.values() for m in find_directive(nodes, "map") if m.args[:1] == ["$request_uri"]
    ]
    assert not leftover_maps, "vẫn còn map $request_uri (quyết định log phải nằm ở mức location)"
    leftover_if = [
        n
        for nodes in files.values()
        for n in find_directive(nodes, "access_log")
        if any("$appback_access_log" in a for a in n.args)
    ]
    assert not leftover_if, "vẫn còn access_log … if=$appback_access_log"

    for path, loc in matches:
        assert any(n.directive == "access_log" and n.args == ["off"] for n in loc.children), (
            f"{path}: /api/files/ thiếu access_log off"
        )
        targets = {n.args[-1] for n in loc.children if n.directive == "error_page" and n.args}
        assert targets == {"/__errors/413-files", "/__errors/503-files"}, (
            f"{path}: /api/files/ phải trỏ error_page sang đích riêng tắt log, đang là {targets}"
        )


def test_nginx_files_location_elevates_error_log_level() -> None:
    """`/api/files/`: `error_log … crit` (hoặc `alert`/`emerg`) trực tiếp trong
    location — mỗi lần `api` không tới được, nginx ghi nguyên dòng `request: "GET
    /api/files/<token> …"` vào error log mặc định (`warn`); `access_log off`/map
    chỉ chữa log truy cập, không chữa error log (BE-00 §8, review 2026-09-22 #2,
    probe Q2)."""
    files = _all_nginx_files()
    matches = _locations_matching(files, lambda loc: bool(loc.args) and loc.args[-1] == "/api/files/")
    assert matches, "không tìm thấy location /api/files/"
    for path, loc in matches:
        error_logs = [n.args for n in loc.children if n.directive == "error_log"]
        assert error_logs, f"{path}: /api/files/ thiếu error_log … crit"
        levels = {args[-1] for args in error_logs if args}
        assert levels & {"crit", "alert", "emerg"}, f"{path}: /api/files/ error_log phải mức crit/alert/emerg"


def test_nginx_error_pages_declared() -> None:
    """`error_page 413 /__errors/413;` và `error_page 502 503 504 =503 /__errors/503;`
    xuất hiện ở đâu đó trong cấu hình."""
    files = _all_nginx_files()
    all_error_pages = [n.args for nodes in files.values() for n in find_directive(nodes, "error_page")]
    assert ["413", "/__errors/413"] in all_error_pages, "thiếu error_page 413 /__errors/413"
    assert ["502", "503", "504", "=503", "/__errors/503"] in all_error_pages, (
        "thiếu error_page 502 503 504 =503 /__errors/503"
    )


def test_nginx_error_locations_are_internal_json_with_request_id() -> None:
    """Bốn `location` lỗi: `internal`, `default_type application/json`, thân chứa mã
    lỗi + `$appback_request_id`; 503 có `Retry-After 5 always`; riêng hai bản
    `-files` (đích `error_page` của `/api/files/`) có thêm `access_log off`.

    Đọc cây ĐÃ LẮP RÁP `include`: thân 413/503 nằm ở `snippets/error_{413,503}_body.conf`
    dùng chung cho bản thường và bản `-files` (R-07), nên trên cây vật lý mỗi
    location chỉ thấy một dòng `include`."""
    files = _entry_files_assembled()
    names = ("/__errors/413", "/__errors/503", "/__errors/413-files", "/__errors/503-files")
    by_name = {name: _locations_matching(files, lambda loc, n=name: loc.args[-1:] == [n]) for name in names}
    for name, found in by_name.items():
        assert found, f"thiếu location {name}"
    for name, found in by_name.items():
        expected_code = "PAYLOAD_TOO_LARGE" if name.startswith("/__errors/413") else "DEPENDENCY_UNAVAILABLE"
        for path, loc in found:
            child_names = {n.directive for n in loc.children}
            assert "internal" in child_names, f"{path}: {name} thiếu internal"
            default_type = [n.args for n in loc.children if n.directive == "default_type"]
            assert default_type == [["application/json"]], f"{path}: {name} thiếu default_type application/json"
            body = " ".join(" ".join(n.args) for n in loc.children)
            assert expected_code in body, f"{path}: thân {name} thiếu {expected_code}"
            assert "$appback_request_id" in body, f"{path}: thân {name} thiếu $appback_request_id"
            if expected_code == "DEPENDENCY_UNAVAILABLE":
                retry_headers = [n.args for n in loc.children if n.directive == "add_header"]
                assert ["Retry-After", "5", "always"] in retry_headers, (
                    f"{path}: {name} thiếu add_header Retry-After 5 always"
                )
            has_off = any(n.directive == "access_log" and n.args == ["off"] for n in loc.children)
            if name.endswith("-files"):
                assert has_off, f"{path}: {name} phải access_log off (token của /api/files/ nằm trong $request_uri)"
            else:
                assert not has_off, f"{path}: {name} không được tắt log — 502/503 của đường khác cần thấy trong log"


def test_nginx_map_request_id_regex() -> None:
    """`map $http_x_request_id $appback_request_id` có case regex `^[A-Za-z0-9-]{8,64}$`."""
    files = _all_nginx_files()
    maps = [
        n
        for nodes in files.values()
        for n in find_directive(nodes, "map")
        if n.args == ["$http_x_request_id", "$appback_request_id"]
    ]
    assert maps, "thiếu map $http_x_request_id $appback_request_id"
    assert any(c.directive == "~^[A-Za-z0-9-]{8,64}$" for m in maps for c in m.children), (
        "map thiếu case regex ^[A-Za-z0-9-]{8,64}$"
    )


def test_nginx_draco_and_assets_return_404_when_missing() -> None:
    """`/draco/` và `/assets/`: `try_files … =404` (thiếu `.wasm`/asset không trả HTML 200)."""
    files = _all_nginx_files()
    for suffix in ("/draco/", "/assets/"):
        matches = _locations_matching(files, lambda loc, s=suffix: bool(loc.args) and loc.args[-1] == s)
        assert matches, f"không tìm thấy location {suffix}"
        for path, loc in matches:
            try_files = [n.args for n in loc.children if n.directive == "try_files"]
            assert try_files, f"{path}: {suffix} thiếu try_files … =404"
            assert try_files[0][-1] == "=404", f"{path}: {suffix} thiếu try_files … =404"


def test_nginx_security_headers_csp_required_sources() -> None:
    """CSP trong `security_headers.conf` chứa `'wasm-unsafe-eval'`, `worker-src 'self'
    blob:`, `form-action 'self'`, `frame-ancestors 'none'`, `object-src 'none'`."""
    nodes = _require_snippet("snippets/security_headers.conf")
    csp_values = [
        " ".join(n.args[1:])
        for n in nodes
        if n.directive == "add_header" and n.args and n.args[0] == "Content-Security-Policy"
    ]
    assert csp_values, "security_headers.conf thiếu add_header Content-Security-Policy"
    csp = " ".join(csp_values)
    for required in (
        "'wasm-unsafe-eval'",
        "worker-src 'self' blob:",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "object-src 'none'",
    ):
        assert required in csp, f"CSP thiếu {required!r}"


def test_nginx_minio_vhost_hardening() -> None:
    """Vhost MinIO: `limit_except GET HEAD { deny all; }`, `X-Content-Type-Options
    nosniff always`, `Content-Security-Policy "sandbox" always`, và `set
    $appback_proxy_host $http_host;` (chữ ký MinIO tính trên host — không còn
    `proxy_set_header Host` riêng lẻ vì vhost giờ include `proxy_common.conf`, sự cố
    đo thật ở bản W `f23bfc4`, hợp đồng B0-08 §3 bản CHỐT 1)."""
    nodes = _require_snippet(_MINIO_VHOST_SUFFIX)
    limit_blocks = find_directive(nodes, "limit_except")
    assert any(
        lb.args == ["GET", "HEAD"] and any(c.directive == "deny" and c.args == ["all"] for c in lb.children)
        for lb in limit_blocks
    ), "vhost MinIO thiếu limit_except GET HEAD { deny all; }"
    add_headers = {(n.args[0], tuple(n.args[1:])) for n in find_directive(nodes, "add_header") if n.args}
    assert ("X-Content-Type-Options", ("nosniff", "always")) in add_headers, (
        "thiếu X-Content-Type-Options nosniff always"
    )
    assert ("Content-Security-Policy", ("sandbox", "always")) in add_headers, (
        'thiếu Content-Security-Policy "sandbox" always'
    )
    set_directives = [n.args for n in find_directive(nodes, "set")]
    assert ["$appback_proxy_host", "$http_host"] in set_directives, (
        "vhost MinIO thiếu set $appback_proxy_host $http_host;"
    )


def test_nginx_minio_vhost_disables_access_log_and_elevates_error_log() -> None:
    """`location /` của vhost MinIO: `access_log off` + `error_log … crit`/`alert`/
    `emerg` — mỗi GET tới đây mang `X-Amz-Signature`/`X-Amz-Credential` (URL ký 2
    giờ) trong `$request`; không chữa thì access log và error log (khi `minio`
    gián đoạn) đều ghi nguyên chữ ký (review 2026-09-22 #14 P1, probe R5)."""
    nodes = _require_snippet(_MINIO_VHOST_SUFFIX)
    locations = find_directive(nodes, "location")
    assert locations, "vhost MinIO thiếu location /"
    for loc in locations:
        access_logs = [n.args for n in loc.children if n.directive == "access_log"]
        assert ["off"] in access_logs, "vhost MinIO: location / thiếu access_log off"
        error_logs = [n.args for n in loc.children if n.directive == "error_log"]
        assert error_logs, "vhost MinIO: location / thiếu error_log … crit"
        levels = {args[-1] for args in error_logs if args}
        assert levels & {"crit", "alert", "emerg"}, "vhost MinIO: error_log phải mức crit/alert/emerg"


_MALFORMED_FILES_URIS = (
    "//api/files/SECRET",
    "/api//files/SECRET",
    "/api/%66iles/SECRET",
    "/api/./files/SECRET",
    "/api/x/../files/SECRET",
    "/%61pi/files/SECRET",
    "/api%2Ffiles/SECRET",
)


def test_nginx_files_log_decision_is_location_scoped_not_request_uri() -> None:
    """Không còn chỗ nào quyết định tắt log dựa trên `$request_uri` (URI THÔ).

    Bảy dạng méo trong `_MALFORMED_FILES_URIS` đều được `location /api/files/`
    phục vụ vì nginx chuẩn hoá path (bỏ `.`/`..`, gộp `/`, giải `%XX`) TRƯỚC khi
    chọn location; regex trên `$request_uri` thì phải đoán từng dạng và bản cũ bỏ
    lọt ba dạng cuối (NO-095). Test tĩnh chỉ chốt được hình dạng cấu hình — chứng
    minh hành vi là probe thật 7 URI + `grep -c` token = 0, ghi trong báo cáo."""
    for path, nodes in _all_nginx_files().items():
        for node in walk(nodes):
            if node.directive in {"access_log", "map"} and any("$request_uri" in a for a in node.args):
                pytest.fail(f"{path}: {node.directive} {node.args} còn quyết định log theo $request_uri thô")
    assert len(set(_MALFORMED_FILES_URIS)) == 7, "probe phải có đúng 7 dạng URI méo khác nhau"


def test_nginx_prod_redirect_server_disables_access_log() -> None:
    """Server `listen 8080` của prod chỉ `return 301` nhưng dùng access log mặc định
    của ảnh nền: `http://…/api/files/<token>` (hoặc URL ký S3 gọi bằng http) để lại
    token trong `docker logs web` trước khi client kịp sang https (NO-094). Nó không
    include `app_locations.conf` nên không thừa hưởng luật log của `/api/files/` —
    phải tự `access_log off`."""
    path = NGINX_ROOT / "templates" / "prod" / "app.conf.template"
    nodes = parse_nginx(path.read_text(encoding="utf-8"))
    redirects = [
        server
        for server in find_directive(nodes, "server")
        if any(c.directive == "return" and c.args[:1] == ["301"] for c in server.children)
    ]
    assert redirects, "prod: không tìm thấy server 301"
    for server in redirects:
        assert any(c.directive == "access_log" and c.args == ["off"] for c in server.children), (
            "prod: server 301 (listen 8080) thiếu access_log off"
        )


def test_nginx_proxy_common_survives_api_container_swap() -> None:
    """`proxy_common.conf` phải cho nginx thử địa chỉ khác khi container `api` cũ bị
    dừng giữa lúc `deploy.sh` đổi phiên bản (NO-117): `proxy_next_upstream error
    timeout` + trần số lần/thời gian, và `proxy_connect_timeout` ngắn (≤ 2s) để một
    địa chỉ đã chết không giữ client chờ hết 5s rồi mới được thử lại.

    Không có `upstream {}`: nginx mã nguồn mở giải tên trong khối đó đúng một lần
    lúc nạp cấu hình và không giải lại (`resolve` chỉ có ở NGINX Plus), nên nó sẽ
    khoá chết vào IP của container đã bị thay."""
    nodes = _require_snippet("snippets/proxy_common.conf")
    directives = {n.directive: n.args for n in nodes}
    assert directives.get("proxy_next_upstream") == ["error", "timeout"], (
        f"proxy_common.conf: proxy_next_upstream phải `error timeout`, đang {directives.get('proxy_next_upstream')}"
    )
    assert "proxy_next_upstream_tries" in directives, "proxy_common.conf: thiếu proxy_next_upstream_tries"
    assert "proxy_next_upstream_timeout" in directives, "proxy_common.conf: thiếu proxy_next_upstream_timeout"
    connect_timeout = directives.get("proxy_connect_timeout")
    assert connect_timeout, "proxy_common.conf: thiếu proxy_connect_timeout"
    assert int(connect_timeout[0].removesuffix("s")) <= 2, (
        f"proxy_connect_timeout {connect_timeout[0]} quá dài cho một bridge Docker nội bộ"
    )
    for path, nodes_of_file in _all_nginx_files().items():
        assert not find_directive(nodes_of_file, "upstream"), (
            f"{path}: cấm khối upstream {{}} — nginx OSS không giải lại tên trong đó"
        )


def test_nginx_no_autoindex_anywhere() -> None:
    """K15: cấm `autoindex` ở bất kỳ file nào."""
    for path, nodes in _all_nginx_files().items():
        assert not find_directive(nodes, "autoindex"), f"{path}: cấm autoindex"


def test_nginx_no_alias_directive() -> None:
    """K15: cấm `alias` — cách duy nhất một `location` ánh xạ 1-1 sang thư mục đĩa,
    rủi ro lộ thư mục lưu trữ cục bộ nếu trỏ nhầm."""
    for path, nodes in _all_nginx_files().items():
        assert not find_directive(nodes, "alias"), f"{path}: cấm dùng alias (K15)"


def test_nginx_no_cors_header_on_app_server() -> None:
    """W19: cấm `add_header Access-Control-Allow-Origin` ở server ứng dụng (không CORS cho `/api`)."""
    for path, nodes in _all_nginx_files().items():
        if _is_minio_vhost(path):
            continue
        for node in find_directive(nodes, "add_header"):
            assert node.args[:1] != ["Access-Control-Allow-Origin"], f"{path}: cấm bật CORS cho /api (W19)"
