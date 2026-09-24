"""Test tĩnh cho `deploy/minio/init.sh` (hợp đồng §4, prompt [7]/[8]).

Kiểm chạy thật (hai lượt `minio-init` với hai `S3_ML_SECRET_KEY` khác nhau, và
chính sách sinh ra đọc/ghi đúng bucket thật) nằm ở mục "Kiểm chạy thật" của báo
cáo — file này chỉ kiểm cấu trúc script (đỏ trên bản trước sửa, xanh sau).
"""

from __future__ import annotations

from deploy.tests.support import require_path


def _script_text() -> str:
    """Nội dung thô của `deploy/minio/init.sh`."""
    return require_path("deploy/minio/init.sh").read_text(encoding="utf-8")


def _code_lines() -> list[str]:
    """Dòng của `init.sh` không tính comment (`#` đầu dòng sau khi bỏ khoảng trắng)."""
    return [line for line in _script_text().splitlines() if not line.strip().startswith("#")]


def test_minio_init_adds_app_and_ml_users_unconditionally() -> None:
    """`mc admin user add` chạy vô điều kiện cho **cả** khoá chung của app
    (`S3_ACCESS_KEY`/`S3_SECRET_KEY`, F3 — trước đây `init.sh` không cấp danh
    tính MinIO nào cho khoá này nên `/api/ready` 503 khi khoá khác
    `MINIO_ROOT_USER`, review 2026-09-22 #15) và khoá riêng của `ml` — không còn
    nhánh `mc admin user info` bỏ qua tạo lại khi user đã có (MinIO ghi đè
    secret của user đã có, nên nhánh đó làm xoay khoá không bao giờ có hiệu
    lực, review 2026-09-22 #8)."""
    code_lines = _code_lines()
    assert not any("user info" in line for line in code_lines), (
        "init.sh: vẫn còn lệnh mc admin user info (nhánh bỏ qua tạo lại)"
    )
    add_lines = [line for line in code_lines if "mc admin user add" in line]
    assert len(add_lines) == 2, f"init.sh: phải có đúng hai lệnh mc admin user add (app, ml), có {add_lines}"
    assert any('"${S3_ACCESS_KEY}" "${S3_SECRET_KEY}"' in line for line in add_lines), (
        "init.sh: thiếu mc admin user add cho khoá chung của app"
    )
    assert any('"${S3_ML_ACCESS_KEY}" "${S3_ML_SECRET_KEY}"' in line for line in add_lines), (
        "init.sh: thiếu mc admin user add cho khoá riêng của ml"
    )


def test_minio_init_generates_real_policies_from_templates_into_tmp() -> None:
    """Chính sách thật (app **và** ml) được sinh vào `/tmp` (không sửa
    `{app,ml}-policy.json` tại chỗ — hai file đó là **mẫu**, giữ chỗ bucket)
    bằng một hàm dùng chung `render_policy` (không chép tay mã thay thế
    `${var//…}` hai lần, F3), rồi `mc admin policy create` đọc từ bản đã sinh,
    không trực tiếp từ `/deploy/minio/*.json` (review 2026-09-22 #9)."""
    text = _script_text()
    assert "render_policy" in text, "init.sh: thiếu hàm render_policy dùng chung cho app/ml"
    substitution = "//__BUCKET__/${S3_BUCKET}}"
    assert text.count(substitution) == 1, (
        f"init.sh: thay thế __BUCKET__ phải nằm ở đúng MỘT chỗ (hàm dùng chung), có {text.count(substitution)}"
    )
    assert "/tmp/app-policy.json" in text, "init.sh: chính sách app thật phải sinh vào /tmp"  # noqa: S108
    assert "/tmp/ml-policy.json" in text, "init.sh: chính sách ml thật phải sinh vào /tmp"  # noqa: S108
    policy_create_lines = [line for line in text.splitlines() if "mc admin policy create" in line]
    assert len(policy_create_lines) == 2, (
        f"init.sh: phải có đúng hai lệnh mc admin policy create, có {policy_create_lines}"
    )
    assert all("/deploy/minio/" not in line for line in policy_create_lines), (
        "init.sh: mc admin policy create phải đọc bản đã sinh ở /tmp, không phải mẫu tại /deploy/minio/"
    )


def test_minio_init_attaches_app_and_ml_policies_to_their_users() -> None:
    """Chính sách `app-policy` gắn vào `S3_ACCESS_KEY`, `ml-policy` gắn vào
    `S3_ML_ACCESS_KEY` — mỗi khoá chỉ nhận chính sách của mình (least privilege
    giữa hai danh tính, F3)."""
    text = _script_text()
    assert 'attach_policy_if_missing app-policy "${S3_ACCESS_KEY}"' in text, (
        "init.sh: thiếu gắn app-policy vào khoá chung của app"
    )
    assert 'attach_policy_if_missing ml-policy "${S3_ML_ACCESS_KEY}"' in text, (
        "init.sh: thiếu gắn ml-policy vào khoá riêng của ml"
    )


def test_minio_init_revokes_identities_left_over_from_key_rotation() -> None:
    """Xoay khoá phải THU HỒI danh tính cũ, không chỉ tạo danh tính mới (NO-096).

    `mc admin user add` cho khoá mới không đụng gì tới user của khoá cũ: user đó
    vẫn giữ `app-policy`/`ml-policy` và secret cũ vẫn đọc/ghi được bucket, nên đổi
    `S3_ACCESS_KEY`/`S3_ML_ACCESS_KEY` trước đây không thu hồi được quyền nào. Mỗi
    chính sách phải được quét đúng một lần, với khoá hiện tại của nó làm ngoại lệ.
    """
    text = _script_text()
    assert "revoke_stale_users()" in text, "init.sh: thiếu hàm revoke_stale_users"
    assert "mc admin user remove" in text, "init.sh: không có lệnh gỡ user nào"
    code_lines = _code_lines()
    calls = [line.strip() for line in code_lines if line.startswith("revoke_stale_users ")]
    assert calls == [
        'revoke_stale_users app-policy "${S3_ACCESS_KEY}"',
        'revoke_stale_users ml-policy "${S3_ML_ACCESS_KEY}"',
    ], f"init.sh: phải gỡ danh tính cũ của CẢ HAI chính sách, đang có {calls}"
