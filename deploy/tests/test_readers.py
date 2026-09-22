"""Test đơn vị cho bộ đọc Dockerfile/compose/nginx bằng chuỗi nhúng — phải xanh ngay
trên nhánh này, không phụ thuộc file thật của các worker khác.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deploy.tests.compose_reader import merge_service, resolve_service
from deploy.tests.dockerfile_reader import last_stage_instructions, parse_dockerfile
from deploy.tests.nginx_reader import find_directive, parse_nginx


def test_dockerfile_reader_tach_tang_va_gop_dong_noi(tmp_path: Path) -> None:
    """Multi-stage `FROM ... AS`, dòng nối `\\`, comment bị bỏ, `USER` ở tầng cuối."""
    dockerfile = tmp_path / "x.Dockerfile"
    dockerfile.write_text(
        "FROM python:3.12-slim-bookworm AS build\n"
        "# comment bị bỏ\n"
        "RUN apt-get update \\\n"
        "    && apt-get install -y curl\n"
        "FROM python:3.12-slim-bookworm\n"
        "COPY --from=build /opt/venv /opt/venv\n"
        "USER 10001\n",
        encoding="utf-8",
    )
    stages, instructions = parse_dockerfile(dockerfile)
    assert [s.base for s in stages] == ["python:3.12-slim-bookworm", "python:3.12-slim-bookworm"]
    assert stages[0].name == "build"
    assert stages[1].name is None
    run_instr = next(i for i in instructions if i.name == "RUN")
    assert run_instr.args == "apt-get update      && apt-get install -y curl"
    last = last_stage_instructions(instructions, stages)
    assert [i.name for i in last] == ["COPY", "USER"]
    assert last[-1].args == "10001"


def test_compose_reader_extends_hai_tang_gop_environment_thay_healthcheck(tmp_path: Path) -> None:
    """`extends` hai tầng (dev → base → base2); `environment` list+map gộp theo khoá;
    `command`/`healthcheck` của `dev` thay **nguyên** bản của base (không gộp khoá
    con của `healthcheck`, đo thật trên compose v5.3.0 — hợp đồng B0-08 §2 bản CHỐT 1)."""
    (tmp_path / "base2.yml").write_text(
        "services:\n"
        "  common:\n"
        "    environment:\n"
        "      - A=1\n"
        "      - B=2\n"
        "    healthcheck:\n"
        "      interval: 5s\n"
        '      test: ["CMD", "true"]\n',
        encoding="utf-8",
    )
    (tmp_path / "base.yml").write_text(
        "services:\n  api:\n    extends:\n      file: base2.yml\n      service: common\n    command: base-command\n",
        encoding="utf-8",
    )
    (tmp_path / "dev.yml").write_text(
        "services:\n"
        "  api:\n"
        "    extends:\n"
        "      file: base.yml\n"
        "      service: api\n"
        "    environment:\n"
        "      B: '20'\n"
        "      C: '3'\n"
        "    command: dev-command\n"
        "    healthcheck:\n"
        '      test: ["CMD", "dev-check"]\n',
        encoding="utf-8",
    )
    resolved = resolve_service(tmp_path / "dev.yml", "api")
    assert resolved["environment"] == {"A": "1", "B": "20", "C": "3"}
    assert resolved["command"] == "dev-command"
    assert resolved["healthcheck"] == {"test": ["CMD", "dev-check"]}


def test_compose_reader_merge_service_hop_list_bo_trung() -> None:
    """`ports`/`volumes`/`profiles` hợp theo thứ tự, phần tử đã có ở base không lặp lại."""
    base = {"ports": ["127.0.0.1:5432:5432"], "profiles": ["ml"]}
    override = {"ports": ["127.0.0.1:5432:5432", "127.0.0.1:5433:5433"], "profiles": ["gpu"]}
    merged = merge_service(base, override)
    assert merged["ports"] == ["127.0.0.1:5432:5432", "127.0.0.1:5433:5433"]
    assert merged["profiles"] == ["ml", "gpu"]


def test_compose_reader_thieu_dich_vu_nem_loi(tmp_path: Path) -> None:
    """Dịch vụ không tồn tại trong file `extends` phải báo lỗi rõ, không âm thầm rỗng."""
    (tmp_path / "base.yml").write_text("services:\n  other: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="thiếu dịch vụ"):
        resolve_service(tmp_path / "base.yml", "api")


def test_nginx_reader_regex_trong_nhay_va_bien_lien_trong_chuoi() -> None:
    """Regex có `{8,64}` phải nằm nguyên trong chuỗi nháy; `${VAR}` trong chuỗi vẫn là
    một chuỗi (không bị tách bởi dấu `{`/`}` bên trong regex)."""
    conf = (
        "map $http_x_request_id $appback_request_id {\n"
        '    "~^[A-Za-z0-9-]{8,64}$" $http_x_request_id;\n'
        "    default $request_id;\n"
        "}\n"
        "server {\n"
        "    add_header Content-Security-Policy \"img-src 'self' ${S3_PUBLIC_ENDPOINT}\" always;\n"
        "}\n"
    )
    nodes = parse_nginx(conf)
    map_node = find_directive(nodes, "map")[0]
    assert map_node.args == ["$http_x_request_id", "$appback_request_id"]
    regex_case = map_node.children[0]
    assert regex_case.directive == "~^[A-Za-z0-9-]{8,64}$"
    assert regex_case.args == ["$http_x_request_id"]
    server = find_directive(nodes, "server")[0]
    add_header = server.children[0]
    assert add_header.args[1] == "img-src 'self' ${S3_PUBLIC_ENDPOINT}"


def test_nginx_reader_location_long_va_include() -> None:
    """`location` lồng trong `server` được thấy bởi `find_directive`; `include` đọc
    được tên tệp gốc bất kể đường dẫn tuyệt đối."""
    conf = (
        "server {\n"
        "    location /api/ {\n"
        "        include /etc/nginx/appback/snippets/proxy_common.conf;\n"
        "        location = /api/admin/ml/model-versions {\n"
        "            client_max_body_size 512m;\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    nodes = parse_nginx(conf)
    locations = find_directive(nodes, "location")
    assert len(locations) == 2
    outer = locations[0]
    assert outer.args == ["/api/"]
    include_names = {Path(c.args[0]).name for c in outer.children if c.directive == "include"}
    assert include_names == {"proxy_common.conf"}
