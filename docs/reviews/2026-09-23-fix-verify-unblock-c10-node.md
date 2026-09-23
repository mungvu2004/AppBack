# Review merge `fix/verify-unblock-c10-node` → main

- Ngày: 2026-09-23 · Reviewer: phiên `/merge-review` (worktree `review-fix-verify-unblock`, tách rời, không sửa mã)
- Commit đầu nhánh: `165d9fc84a9f` · 5 commit (FIX-073..077), `git diff --stat main...HEAD`: 5 file, +79 −29
- Cổng: `bash tools/verify/run.sh verify` chạy tại chỗ, **mã thoát 1** — log
  `.cache/src-out/verify/20260923T101103Z-165d9fc84a9f.log`
- Độ phủ: tổng dòng 99,13% · nhánh 97,53% — **tập file bị chạm: dòng 96,84% · nhánh 83,33% (đỏ)**
- Test: 2790 passed, 7 skipped, 4 deselected, 0 failed (430 s)

## Bảng cổng (mã thoát thật)

|  # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `coverage run -m pytest` → `coverage_gate` | **hỏng** | mọi test xanh; `coverage_gate`: `[độ phủ nhánh tập file bị chạm < 90%] 83.33%` |
| 5b | `pytest -m perf` → `case_gate` | chưa chạy | |
| 6 | `lint_migrations` → `migrate_check` | chưa chạy | |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | chưa chạy | |
| 8 | `openapi` | chưa chạy | |

Ghi chú vận hành (không tính vào phán quyết): hai lượt trước đó hỏng vì hạ tầng, không vì nhánh —
lượt 1 mã thoát 125 (`error waiting for container: unexpected EOF`, container AutoRemove bị reap),
lượt 2 mã thoát 2 (`uv` cache trong volume `appback-verify-review-fix-verify-unblock_appback-work`
hỏng sau lượt 1: `The wheel is invalid: Metadata field Name not found`). Xoá `uv-cache` + `venv-*`
trong volume rồi chạy lại mới ra kết quả trên. Ảnh verify dựng lại theo Dockerfile mới của FIX-074
và **chạy được** — `libatomic1` đã gỡ đúng NO-126 (bước 0 và toàn bộ test `tools/contract/*` xanh).

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | TEST-01 / K24 (BE-00 §12) | Cổng đỏ ở bước 5. `omit = ["*/tests/*"]` (`pyproject.toml`) loại 4/5 file đổi khỏi coverage, nên **tập file bị chạm chỉ còn `tools/charter.py`**: 95 câu lệnh / 3 thiếu, 30 nhánh / 5 thiếu → nhánh 83,33% < 90%. Thiếu độ phủ là **có sẵn** trong `charter.py`, nhưng FIX-075 sửa một dòng ở đó nên kéo cả file vào `VERIFY_CHANGED` (`tools/verify/run.sh:47-51`) và làm cổng đỏ. Hệ quả: nhánh này **không** xanh 8/8, và bước 5b chưa chạy nên chưa có bằng chứng `case_gate` đã hết báo thiếu C05 (NO-129). | `tools/charter.py:115` (dòng sửa); thiếu: dòng `40`, `57`, `66` + nhánh `46->48`, `48->50` | Thêm 5 test vào `tools/tests/test_charter.py` (B0-01 sở hữu cả hai file, đã sửa file này trong nhánh). `_write_table` có sẵn ở `tools/tests/test_charter.py:19` làm sẵn khuôn: (a) dòng không mở bằng `\|` → `_is_separator_line` trả `False`; (b) bảng thiếu cột → `_find_col` ném `ValueError`; (c) method lạ → `_parse_method_path` ném `ValueError`; (d) ô không mở bằng `\|`; (e) ô không đóng bằng `\|`. Chạy lại `run.sh verify` cho đủ 8/8. |
| 2 | P3 | TEST-05 | `test_khoá_bỏ_backtick` đọc `BE-BIND.md` thật và ghim hàng 25. Nếu hiến chương bỏ backtick ở ô đó, test vẫn xanh nhưng **không còn canh** hồi quy NO-128. Cũng là test mới duy nhất trong nhánh không dùng `_write_table` đã có sẵn. | `tools/tests/test_charter.py:49-53` | Dựng bảng bằng `_write_table` với một ô Khoá có backtick rồi khẳng định `lock` không còn backtick; gộp luôn với finding 1. |
| 3 | P3 | TEST-05 | `_seed` suy ra `completed = state == STATE_COMPLETED`; truyền `state` lạ sẽ âm thầm mồi một dòng thiếu `status_code`/`response_body`, và C10 hỏng bằng assert khó đọc thay vì nêu tên `state` sai. | `apps/api/core/tests/test_common.py:236-240` | `state: Literal["in_progress", "completed"]`, hoặc `assert state in {STATE_IN_PROGRESS, STATE_COMPLETED}, state`. |
| 4 | Nit | MNT-02 | Thân commit FIX-075 nói cột Khoá "giữ backtick (`project.create`)", nhưng thực tế **25 hàng** có backtick (`floor.upload` ×5, `layer.edit` ×8, `user.manage` ×9, `project.settings.edit` ×2, `project.create` ×1). Sửa đúng gốc, chỉ là thân commit nói hẹp hơn tầm ảnh hưởng. | `77acfb8` | Khi squash, nêu đủ 25 hàng. |

## Kiểm đã làm, không thành finding

- **FIX-073 (C10) — đúng, và *mạnh hơn* bản cũ.** Mồi `completed` với
  `request_hash = request_digest(method, _url(op), "", b"{}")`; lượt lặp gửi đúng `json={}` nên hash
  khớp, dòng chưa `stale` (`expires_at = now+TTL`, `state != in_progress`) → `_claim_statement`
  không nhận việc → `_blocked` → `Replay(_replay_response(...))`
  (`apps/api/core/idempotency.py:264-266`). Test khẳng định 201 + `application/json` +
  `{"mau":"c10"}`, tức **chỉ đạt được khi route đã nối idempotency** — route chưa nối sẽ trả
  response thật của handler. Bản cũ so `first` với `replay` khi **cả hai đều là cùng một lỗi
  422/404**, nên đạt suông; đây là siết lại chứ không phải nới. Thân khác → hash lệch → 422
  `IDEMPOTENCY_KEY_REUSED` (`idempotency.py:263`). Hợp `CASE.md` §1/§2.1 và BE-00 §7. Vòng đời
  `complete()` → phát lại thật vẫn được chứng minh end-to-end trên app mẫu ở
  `apps/api/core/tests/test_idempotency.py:138 test_replay_returns_stored_response`, `:235`, `:333`,
  nên mồi sẵn không mất bằng chứng nào. `_seed` dùng chung công thức `request_hash` với C22 — C22
  xanh chính là bằng chứng digest khớp request thật.
- **FIX-074** — `libatomic1` thêm vào đúng lệnh `apt-get install` sẵn có, sửa chú thích "Node 20"
  sai. Tự dựng lại ảnh và chạy: không còn thoát 127.
- **FIX-075** — sửa ở **gốc** (`_parse_table`, một chỗ), không vá từng caller. Kiểm hết nơi đọc
  `BindRow.lock`: `tools/case_gate.py:163` (`!= "—"`), `:187` (`== "thành viên"`),
  `apps/api/core/tests/test_routes.py:80`, `apps/api/access/tests/test_deps.py:183`. Đã đối chiếu
  từng ô Khoá của BE-BIND: chỉ tên khoá thật mới có backtick; `—` (42 ô) và `thành viên` (9 ô)
  **không** có → `case_gate` không đổi hành vi, không có tác dụng phụ ngoài ý muốn.
- **FIX-076** — `_TEST_COMMON_RE` (`tools/case_gate.py:294`) đòi đúng `test_common__C05[<op>]`; bỏ
  tham số hoá `token` trả id về đúng khuôn. Không mất độ mạnh: cả 4 `BAD_TOKENS` vẫn được thử và
  assert nêu `token={token!r}`. (Vòng lặp dừng ở token hỏng đầu tiên — chấp nhận được, thông điệp
  đã chỉ đúng token.) Chưa tự xác nhận được `case_gate` hết báo thiếu vì bước 5b chưa chạy
  (finding 1).
- **FIX-077** — `_existing` (`packages/db/new_revision.py:37-42`) duyệt bản sao thư mục `versions`
  thật, nên khi `r*_b2_01_*` có thật thì `--code B2-01` trả 2; đổi sang mã chưa ai dùng là sửa gốc.
  Xác nhận `packages/db/migrations/versions/` hiện chỉ có `b0_03`, `b0_06`, `b1_01`, `b1_02` —
  `b9_98` chưa ai dùng và khác `b9_99` của `SECOND_HEAD`. `_CODE_RE` chấp nhận `b9_98`; chú thích
  "r<8> + _ + 26 = 36 ký tự" ở `test_too_long_revision_id_rejected` vẫn đúng.
- **Điều kiện dừng sớm**: cây sạch; 5 dòng đầu commit đúng Conventional Commits, đủ trailer
  `Prompt:` + `Fix:`; không đụng `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`,
  `pyproject.toml`, `tools/verify/*`; không `pragma: no cover`, `type: ignore`, `noqa`,
  `skip`/`xfail` mới, không hạ ngưỡng nào.
- **Sổ nợ (R-34)**: NO-126, NO-127, NO-128, NO-129, NO-131 đều đã có dòng trên `main` với chủ và
  mức P1 — đủ. Nhánh này không sinh thêm nợ P0/P1 nào khác.
- **Sở hữu file (R-27)**: `tools/charter.py` + `tools/tests/test_charter.py` → `Prompt: B0-01` ✔;
  `deploy/docker/verify.Dockerfile` → B0-08 ✔; `apps/api/core/tests/test_common.py` → B0-06 ✔;
  `packages/db/tests/test_new_revision.py` → B0-03 ✔.
- **MNT-05**: 79 dòng thêm, không cần tách nhánh.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 1 | 0,07 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 4 | 0,12 |
| **Tổng** | **100%** | | **4,69 / 5** |

## PHÁN QUYẾT: REQUEST CHANGES

Năm bản sửa đều **đúng gốc**, đúng chủ, có lý do ghi rõ trong thân commit và trong `DEBT.md`;
FIX-073 còn làm C10 mạnh hơn bản cũ thay vì nới nó. Điểm 4,69/5. Nhưng ma trận `RULE.md` §5 đi theo
finding chứ không theo điểm: còn **một P1 chưa waiver** thì `REQUEST CHANGES` — và ở đây P1 chính
là cổng bắt buộc: `run.sh verify` mã thoát **1**, bước 5 đỏ, bước 5b–8 chưa chạy. Không merge nhánh
đỏ (BE-00 §12, R-37).

Để được `APPROVE`, chỉ cần một việc (finding 1, ~15 dòng test, cùng chủ B0-01 đã sửa file đó):

1. Thêm test cho 5 chỗ còn trống của `tools/charter.py` — dòng `40`, `57`, `66` và nhánh
   `46->48`, `48->50` — vào `tools/tests/test_charter.py`, dùng `_write_table` có sẵn. Phủ hết 5
   chỗ là `charter.py` lên 100% dòng / 100% nhánh và tập file bị chạm qua ngưỡng.
2. Gộp luôn finding 2 và 3 (P3, mỗi cái một dòng) trong cùng lượt.
3. Chạy lại `bash tools/verify/run.sh verify` **đủ 8/8 xanh** và dán log — riêng bước 5b phải xanh
   mới coi là đã chứng minh FIX-076 gỡ được NO-129, vì lượt này chưa chạy tới đó.

Không phải sửa gì ở FIX-073, FIX-074 và FIX-077.
