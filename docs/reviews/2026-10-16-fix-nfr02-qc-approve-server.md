# Review merge fix/nfr02-qc-approve-server → main (phán quyết cuối)

- Ngày: 2026-10-16 · Reviewer: phiên /merge-review · Commit đầu nhánh: 6f65c07730cf (merge-base = `main` bae4b668, base không đổi)
- Cổng: phạm vi **đầy đủ** — lượt 1 của nhánh (R-33b đk 1); vòng sửa thêm thư mục test dưới `packages/testing` nên vẫn đầy đủ.
  `bash tools/verify/run.sh verify` **mã thoát 0** (log: `F:/worktrees/AppBack/nfr02-qc-approve/.cache/src-out/verify/20261016T081406Z-6f65c07730cf.log`,
  tên log mang đúng sha đầu nhánh; `gate.out` kết thúc `exit=0`). Bước 0–8 đều `đạt`: 0 làm ấm node_modules, 1 ruff format, 2 ruff check,
  3 mypy --strict, 4 lint-imports, 5 pytest (cov) → coverage_gate, 5b perf → case_gate ("0 đơn vị bị chạm"), 6 lint_migrations → migrate_check,
  7 H1 H3 H4 H5, 8 openapi (log dòng 554–565). Junit (`…6f65c07730cf.junit.xml`): `tests="8505" failures="0" errors="0" skipped="0"`.
  Reviewer **đọc log và junit**, không chạy lại (một việc Docker nặng mỗi lúc, CLAUDE.md).
- Độ phủ: tổng dòng 99,46% · nhánh 97,99% — `apps/api/spatial_write` 99,54% · 98,11% — `apps/api/versions` 100,00% · 100,00% —
  `packages/testing` 99,55% · 98,46% — tập file bị chạm 99,58% · 98,41% (log dòng 383–387).

## Phạm vi

5 commit trên `main` (c894bc0c bản sửa; c338a719, 0ab93ed0, e21e1a7f, 6f65c077 vòng sửa review), 7 file: `writer.py` (kiểm `qc.approve`
dưới khoá tầng, khoá `(loại, id)`), `spatial_write/router.py`, `versions/service.py` (truyền `can(role, "qc.approve")`), hai tệp test route,
`packages/testing/fixtures/permissions.py` (fixture + `assert_forbidden`), `packages/testing/tests/test_permissions.py`, `changes/SEC-01.md`.
Điều kiện dừng sớm (§2): không có. Cây sạch; mọi commit đúng Conventional Commits, trailer `Prompt: SEC-01` liền khối `Co-Authored-By`;
không chạm tệp cấm; không `pragma`, `noqa`, `type: ignore`, `skip`/`xfail` mới.

Chi tiết soát tính đúng: `review-round-1.md` (phủ mọi đường cấp `reviewed=True`: chỉ #35 và N19; đóng mặc định; K08; `model.export`/`share.create`
không có route máy chủ) và `review-round-2.md` (vòng sửa P3/Nit).

Vòng cuối `e21e1a7f..6f65c077`: `assert_forbidden` đòi header `X-Request-Id` có mặt (`request_id is None` → `AssertionError`), thêm ca
"thiếu header + thân `requestId: null`" vào `test_assert_forbidden__rejects_other_responses` → đóng Nit #1 lượt 2.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | MNT | Helper khẳng định `assert_forbidden` nằm trong module fixture mà `conftest.py` gốc nạp như plugin — chạy được, trộn helper với fixture (Nit #2 lượt 2, tác giả giữ nguyên) | `packages/testing/fixtures/permissions.py:16-21` | Không chặn; khi có thêm helper khẳng định W7, gom ra module helper test riêng |
| 2 | Nit | TEST | Bằng chứng đỏ-trước chỉ có tên 4 test hỏng, không có dòng `E assert` (Nit #5 lượt 1, chấp nhận) | `nfr02-qc-approve-out/red-before-fix.log` | Lần sau giữ lý do hỏng trong log đỏ |

Các finding đã đóng: lượt 1 P3 #1 (khoá `(loại, id)`), P3 #2 (test bỏ duyệt), P3 #3 (rollback bản "trước"), Nit #4, #6, #7; lượt 2 Nit #1.
Không có P0/P1/P2/P3.

## Kiểm sổ nợ

Tác giả không nêu nợ; không P3 nào còn mở → không cần dòng `DEBT.md`. Hai Nit không bắt buộc ghi nợ.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4,5 | 0,135 |

Tổng: 4,99 / 5

## PHÁN QUYẾT: APPROVE

`qc.approve` nay được kiểm ở máy chủ tại hàm chung `write_layer`, dưới khoá tầng, so với tài liệu thật, mặc định đóng; phủ cả hai đường
cấp dấu duyệt (#35, N19), worker không đổi, K08 giữ nguyên. Test phủ định đỏ trước sửa, xanh sau; cổng đầy đủ ở đúng sha đầu nhánh
`6f65c077` mã thoát 0 (8505 test, độ phủ 99,46/97,99, tập file bị chạm 99,58/98,41). Hai Nit còn lại không chặn. Gộp **squash** với khối
trailer `Prompt: SEC-01`. Cây sau gộp trùng cây đã qua cổng (base `bae4b668` không đổi) → không cần verify lại, trừ khi `main` đổi trước lúc gộp.
