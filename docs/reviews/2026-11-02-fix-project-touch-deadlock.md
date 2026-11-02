# Review merge fix/project-touch-deadlock → main

- Ngày: 2026-11-02 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 77bd27b651fe (trên `origin/main` 46d19be3d47c, merge-base trùng)
- Cổng: phạm vi **đầy đủ** (lượt 1, R-33b điều kiện 1); `bash tools/verify/run.sh verify` — **CHỜ**: log `F:/App/qa-results/multi-floor/be-verify-2.log` lúc viết mới tới "uv sync xong" rồi "khoá cổng: chờ các lượt đang chạy xong", chưa có dòng `exit=N`. Reviewer không tự chạy cổng (phiên gọi chạy riêng).
- Độ phủ: **chưa có** (chờ cổng trên). Diff chỉ đổi một lời gọi trong `apps/api/projects/summaries.py` (dòng đã được test cũ phủ) và thêm test.

## Phạm vi

- Cây sạch, một commit `77bd27b6 fix(projects): lock projects FOR NO KEY UPDATE to stop deadlock`, dòng đầu đúng mẫu, có `Prompt: MULTI-FLOOR-02`. 3 tệp, +39/−4: `apps/api/projects/summaries.py`, `apps/api/projects/tests/test_summaries.py`, `changes/MULTI-FLOOR-02.md`.
- Không chạm `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`. Không pragma/`type: ignore`/`noqa`/skip/xfail mới.

## Soát gốc lỗi

- Chuỗi khoá thật của `pipeline.persist.run` (`apps/worker/pipeline_persist/service.py:202-232`): `create_version` chèn `versions` (FK `project_id` → `KEY SHARE` trên dòng `projects`) **trước** `write_layer` → `_commit` → `touch_project` (`apps/api/spatial_write/writer.py:642`). Hai tầng của cùng dự án (khác dòng `floors`, nên không nối đuôi ở `lock_run`) cùng giữ `KEY SHARE` rồi cùng xin `FOR UPDATE` → chu trình. Đúng như `changes/MULTI-FLOOR-02.md`.
- `FOR NO KEY UPDATE` không xung đột `FOR KEY SHARE` nhưng xung đột `NO KEY UPDATE`/`SHARE`/`UPDATE` → các lượt `touch_projects` vẫn tuần tự với nhau; lượt A giữ khoá dự án, chèn `versions`/`notifications` sau đó (KEY SHARE cùng giao dịch, tương thích), commit; lượt B chạy tiếp. Sửa ở hàm dùng chung nên mọi người gọi (`touch_project`/`touch_projects` ở 10 module) được hưởng (R-19).

## Câu hỏi của phiên gọi

1. **Đường khác khoá `projects … FOR UPDATE`?** `grep with_for_update` toàn `apps/`, `packages/`: không chỗ nào khoá dòng `Project` ngoài `touch_projects`. Các khoá có join tới dự án đều giới hạn bằng `of=` (`apps/api/versions/service.py:105` `of=VersionRecord`, `apps/api/projects/memberships.py:104`/`apps/api/project_members/service.py:114` `of=ProjectMembership`). Không có SQL thô `FOR UPDATE` trên `projects` ngoài test. Lệnh duy nhất tự xin khoá `FOR UPDATE` trên dòng dự án là `DELETE` của lịch dọn (`apps/api/projects/jobs.py:78`): giao dịch riêng, chỉ dự án đã xoá mềm > 30 ngày, có `lock_timeout`, không gọi `touch_project` — không đổi bởi nhánh này, không tạo chu trình mới.
2. **NO KEY UPDATE có làm yếu bảo đảm nào?** Không thấy. Bảng `projects` chỉ có khoá chính `id` làm "key" (không unique index nào khác — `r20260923_b2_01_projects.py`). Không đoạn mã nào đổi `projects.id`; xoá cứng chỉ ở lịch dọn (trên); xoá mềm `delete_project`/`cancel_create_project` là `UPDATE deleted_at` (cột không phải key, tự xin `NO KEY UPDATE`) và không gọi `touch_project`. Các trần/kiểm trùng (`templates`, `measurements`) dựa trên `lock_project_scope` (khoá tư vấn) chứ không dựa trên khoá của `touch_project`. Không người gọi nào cần chặn lượt chèn dòng con song song bằng khoá dự án.
3. **NO-142/NO-193 còn ý nghĩa?** Có. Test hình dạng SQL (`test_summaries.py:284-306`) giờ khẳng định `FOR NO KEY UPDATE` + `ORDER BY`. Test hai session NO-193 (`test_summaries.py:330-370`): `holder` giữ `low` bằng `FOR UPDATE`, xung đột với `NO KEY UPDATE` của `toucher` → `toucher` vẫn chờ ở `low`; `holder` lấy `high` bằng `FOR UPDATE NOWAIT` chỉ được khi `toucher` chưa giữ `high` → vẫn chứng minh thứ tự id. Hai `NO KEY UPDATE` loại trừ nhau nên khoá chéo vẫn có thể xảy ra nếu bỏ `ORDER BY`; test vẫn cần thiết.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | TEST | Test mới chỉ dựng một phía của chu trình (một phiên giữ `FOR KEY SHARE`, `touch_project` phải xong trong 5 s). Đủ làm điều kiện cần — đột biến về `FOR UPDATE` chắc chắn làm `toucher` chờ → `TimeoutError` (theo bảng xung đột khoá của Postgres; reviewer không tự chạy đột biến) — nhưng không tái hiện đúng hai lượt persist. Thử thật 3/3 tầng trên f14 chỉ có trong báo cáo tác giả. | `apps/api/projects/tests/test_summaries.py:309-327` | Chấp nhận như hiện tại; nếu muốn chặt hơn, khi chạm lại thêm test hai session: mỗi phiên chèn một dòng con (vd `versions`/`notifications`) rồi `touch_project`, cả hai xong trong trần. |
| 2 | Nit | TEST | Test mới không khẳng định `updated_at` đã đổi sau khi `toucher` commit (các test khác đã phủ). | `apps/api/projects/tests/test_summaries.py:325-326` | Thêm một `assert` đọc lại `updated_at` khi chạm lại. |
| 3 | Nit | DOC | BE-00 §7 coi `touch_project` là "lời khoá mới cuối cùng" nhưng không nói tới `KEY SHARE` ngầm của FK chèn trước đó trên `projects`; bản sửa này là lý do điều đó an toàn. | `docs/charter/BE-00.md:339` (không thuộc nhánh) | Điều phối cân nhắc thêm một câu vào §7 qua quy trình duyệt charter; không chặn merge. |
| 4 | Nit | OPS | Tên nhánh không mang mã prompt (`<loại>/<mã>-<mô tả>`). | tên nhánh | Không cần đổi. |

Không có nợ mới tác giả nêu; không cần dòng nợ.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 5 | 0,15 |
Tổng: 4,91 / 5

## PHÁN QUYẾT: APPROVE (có điều kiện cổng)

Sửa đúng gốc, một dòng, ở hàm dùng chung; không đường nào khác khoá dòng `projects` theo cách có thể khoá chéo với `KEY SHARE` của FK; `NO KEY UPDATE` không làm yếu bảo đảm nào người gọi dựa vào (không đổi `id`, không xoá cứng trong cùng giao dịch, `projects` không có key ngoài PK); test NO-142/NO-193 vẫn có nghĩa. Không P0/P1/P2. **Điều kiện merge:** `F:/App/qa-results/multi-floor/be-verify-2.log` kết thúc `exit=0` với độ phủ ≥ 90/90 cho `apps/api/projects` và tổng. Nếu `exit≠0` → coi là REQUEST CHANGES, sửa bước hỏng rồi review lại phần sửa.
