# Review merge docs/setup-guide → main

- Ngày: 2026-10-07 · Reviewer: phiên /merge-review (R-37) · Commit đầu nhánh: d9815fd
- Cổng: phạm vi đích — nhánh chỉ thêm `docs/SETUP.md` (257 dòng, không mã; máy đang chạy cổng khác); không chạy `run.sh verify`, pnpm, docker compose, e2e (không áp dụng cho tài liệu thuần). Mã thoát: không đo.
- Độ phủ: không đo (phạm vi đích) — file đổi: `docs/SETUP.md` không phải mã.
- Cây làm việc sạch; 1 commit `docs(setup): ...`, trailer `Prompt: DEBT-04`; không chạm file cấm; `changes/DEBT-04.md` không bắt buộc cho tài liệu thuần (không kiểm lại ở phiên này).

## Cách kiểm
Đọc toàn bộ SETUP.md; đối chiếu ~55 trích dẫn `tệp:dòng` với mã (AppBack trong worktree; AppFront bằng `git show origin/master:<tệp>`; `chuoi.sh`, `build-images.sh`, `chung.md` trong `backend/` ngoài git). Đo lại: hooksPath AppFront `F:\AppFront\.githooks`, nhánh `e2e/integrate` chậm master 140 commit, `core.longpaths` chưa đặt, 5432/8080 đang LISTEN, phiên bản docker/node/pnpm/python/uv, Chrome có — đều khớp. Trích dẫn đúng gồm: BE-00 (209-212, 245-247, 464-474, 535-541), ENV.md (20-25, 29, 38, 51-53, 65-82), run.sh (33-60, 64-82, 71, 85, 93-122), steps.py (175-192, 301-324, 369-383), verify.yml (8, 17, 28-31, 54-58), dev.yml (74-108, 94-95, 183-198), env.example (1-3, 33-38, 92-101), web-context.sh (15-28), appfront_repo.sh (2-12), .gitignore (1-2, 26-28), job.sh (407, 418-419), chuoi.sh (6-9, 11-13, 17-31, 39-72), vite.config.ts (31-42), appClient.ts (47-65), run-playwright.mjs (9-36, 196), playwright.config.ts:20, ci.yml (44, 47), package.json, verify.mjs (19-65), AppFront CLAUDE.md (21-24, 109, 156-159, 190), e2e/fullstack/README.md (17-39, 102, 147), playwright.fullstack.config.ts (17-25), DEBT.md 423-432. Lệnh tài liệu nêu đều có thật (`run.sh` các việc, `web-context.sh <sha> <đích>`, `create-admin --password-stdin`, `pnpm e2e*`). Không có bí mật thật: chỉ nhắc `.secrets.env` (không giá trị), `$MAT_KHAU`; giá trị `change-me*` ở env.example không được chép vào tài liệu.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG | Ba trích dẫn tới dòng không tồn tại: `tools/verify/README.md` chỉ có 15 dòng nhưng SETUP trích `:27`, `:18-21`, `:22-24`. Nội dung đúng nằm ở `:15` (APPFRONT_REPO), `:6-9` (mypy nguội ~212 s), `:10-12` (shell trên bản chép). | `docs/SETUP.md:60`, `:150`, `:160` | Sửa số dòng thành `README.md:15`, `:10-12`, `:6-9`. |
| 2 | P3 | OPS | `chuoi.sh down` ghi chú `docker compose down -v` (xoá volume Postgres/MinIO của project `f14`) mà không cảnh báo mất dữ liệu; phạm vi chỉ `-p f14` nhưng người mới không biết. | `docs/SETUP.md:206` | Thêm "XOÁ dữ liệu project f14 (volume); chỉ dùng khi muốn dựng lại từ trắng". |
| 3 | P3 | OPS | Thiếu bước cài ban đầu cho máy mới: chỉ ghi phiên bản đã đo, không nói cài Docker Desktop (bật WSL2), Git for Windows, Node 20/24, pnpm 9 (corepack hay npm), cấp RAM cho VM Docker (≥ 11 GB theo ENV). Không nhắc `env.example` chỉ có giá trị `change-me*` — chỉ dùng dev, đặt `SECRET_KEY` riêng cho môi trường thật. | `docs/SETUP.md:37-53`, `:84-87` | Thêm 1 đoạn "cài" (liên kết/lệnh) và 1 dòng cảnh báo env.example. |
| 4 | P3 | LOG | `BE-00.md:41-60` được trích cho "Mailpit, nginx (`web`)" nhưng bảng đó không nêu hai thứ này (có Postgres 16, Redis ×2, MinIO, Celery, onnxruntime/torch). `build-images.sh:6` không nói tệp ở `backend/dieu-phoi/chay/F-14/` (ngoài git). | `docs/SETUP.md:12`, `:218` | Trích `dev.yml`/`base.yml` cho Mailpit/nginx; ghi đường đầy đủ của `build-images.sh`. |
| 5 | Nit | MNT | Số đo dễ lỗi thời: `C:` còn 15 GB → lúc review 18 GB (96%); mặc định `BE`/`FE` của chuoi.sh (`fix378-x`, `f14-w`) là worktree tạm có thể không còn. | `docs/SETUP.md:50`, `:211-212` | Ghi "đo ngày…" đã có; thêm lưu ý phải đặt `BE`/`FE` tường minh. |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 3 | 0,45 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS, OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,62 / 5

## PHÁN QUYẾT: APPROVE
Không P0/P1, điểm 4,62. Tài liệu chính xác ở hầu hết khẳng định (≈ 52/55 trích dẫn đúng), lệnh có thật, không lộ bí mật, không mã. Khuyến nghị (không chặn): sửa ba số dòng sai của finding 1 trước hoặc cùng lúc merge vì tài liệu tự xưng "nguồn sự thật là trích dẫn"; finding 2-5 có thể gộp vào cùng lần sửa. Merge thuộc phiên gọi review.
