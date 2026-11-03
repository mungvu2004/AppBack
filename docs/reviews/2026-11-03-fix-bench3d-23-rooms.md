# Review merge fix/bench3d-23-rooms → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 2f7f9347610f (PR #50; merge-base 3bf5f3ecfdf5 = `origin/main` hiện tại; PR `MERGEABLE`)
- Cổng: Phạm vi kiểm: đầy đủ (CI GitHub Actions) — người dùng quyết định dùng CI của PR thay `run.sh verify` (PROMPT-dot3). Run 41618935029 (workflow CI, `pull_request`, head `2f7f9347610f344268fe62769c934d4fabcd6280` = đầu nhánh) `success`; run 41622660249 (Commits) và 41618934890 (CodeQL) cùng SHA `success`; `gh pr checks 50`: 24/24 pass (changes, commits, lint, typecheck, unit/integration/ml shards, build, contract, coverage, perf, CodeQL). Reviewer không chạy cổng, docker hay bench tại chỗ.
- Độ phủ (job `coverage` của run 41618935029, `tools.coverage_gate` đạt, `case_gate` đạt): tổng dòng 99,32% · nhánh 97,55% — gói bị chạm `apps/worker/pipeline_build` 98,52% / 94,40%, `packages/domain` 99,75% / 98,61%. ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước, nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch, HEAD = `origin/fix/bench3d-23-rooms`. `origin/main..HEAD` có 2 commit: `6d3b7561 fix(rooms): phòng ngủ suy lớn hẳn thành khách, cửa lùa cần lô gia > 800` (71 ký tự) và `2f7f9347 chore(changes): ghi chú BENCH3D-23`; dòng đầu đúng mẫu, đều có `Prompt: BENCH3D-23`; job `commits` xanh.
- `git diff --stat origin/main...HEAD`: 7 tệp, +120/−12; logic ~45 dòng (còn lại docstring/test) — dưới 400. Có `changes/BENCH3D-23.md`. Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa` trần, `type: ignore` mới, skip/xfail, không hạ ngưỡng. Một chú thích `# ponytail:` ghi giới hạn (xem finding #2).
- PR #51 (`fix/bench3d-24-silent-flags`, nhánh tích hợp r5) đã chứa 6d3b7561 và chạm cùng các tệp; `git merge-tree HEAD origin/fix/bench3d-24-silent-flags` không xung đột.

## Soát nội dung

- **T5 — `_open_space_labels`** (`rooms.py:859-903`): luật mới chỉ chạy khi các luật cũ (bếp/hành lang rộng, phòng không tên lớn nhất) không mở được phòng khách và tầng chưa có phòng khách. Điều kiện: ≥ 2 phòng ngủ, phòng lớn nhất không lấy từ nhãn chữ (`texted`), > 18 m² ở tỉ lệ ghi ra lớp, ≥ 1,3 lần phòng thứ hai (dung sai `_AREA_EPS_M2` cho ca đúng 1,3, góp ý Codex). `texted=()` mặc định giữ nguyên hành vi cho bộ gọi cũ (`test_rooms.py:972-974`). `area_factor = (final/build)²` đúng thứ nguyên: `Scaling.build/final` là mm/px (`geometry.py:118-126`), diện tích tỉ lệ bình phương. Sắp xếp theo `-area`; hai phòng ngang nhau thì tỉ lệ 1 < 1,3, không đổi. Nhãn đổi đi qua nhánh "tên đổi khác nhãn chữ là suy đoán" đã có (`rooms.py:1224-1225`), nên mang tin cậy suy đoán.
- **T6 — `_sliding_door`** (`post_rules.py:226-251`): thêm lượt dò thứ hai cách tim tường `max(800, t/2 + 150)`; lô gia phải còn ở đó, nếu không thì giữ cửa sổ. `deep[k]` là `None` (ra ngoài mọi phòng) cũng giữ cửa sổ. `_rooms_beside(reach=None)` giữ hành vi cũ cho bộ gọi cũ. Bản tham chiếu `tests/reference.py` sửa cùng logic (so định danh `d is r` đúng vì cả hai lấy từ cùng `layer.rooms`). Test 500/790/900 mm bao hai phía ngưỡng.
- **Hành vi đo thật**: replay cục bộ (`F:/runs/bench-3d/dot4/rooms/BAO-CAO.md`, `cmp.log`): tập F lỗi im lặng 16 → 13, f-02/f-08/f-11 P2 C→Đ, f-06 O1 T→Đ (O1b Đ→C), bench A/C/E 0 tiêu chí xấu đi. Chạy thật trên f14: `runs/r5` và `tap-f/runs/f3` có `stack.json` ghi md5 hot-patch `rooms.py` 17e64b72…, `post_rules.py` 7326fcd0…, `constants.py` 271c8c5a… — **trùng md5 của HEAD nhánh** (cộng mã các làn khác). f3 so f2: f-02 P2 C→Đ, P4 T→Đ; f-08 P2 C→Đ, kết luận ĐẠT; f-11 P2 C→Đ, hết im lặng; f-06 O1 T→Đ, O1b Đ→C, hết im lặng. r5: photo-tilted-ch05 P2 Đ, ch-01 (lô gia thật) O1/P2 Đ. cn-08 P2 C→T ở r5 **không do nhánh này**: lượt đó cn-08 có 0 đồ đạc (`F.items = 0`, tỉ lệ 23,5 thay 25,7, 6 phòng thay 7), trong khi T5 chỉ chạy trên phòng ngủ suy từ đồ.
- **PERF**: T5 là O(n log n) trên danh sách phòng; T6 thêm một lượt `_rooms_beside` chỉ cho cửa sổ ≥ 1400 mm đã cạnh lô gia chưa có cửa vào. Job `perf` xanh (41 passed, 114 s). cProfile làn: `_open_space_labels` 0,004 s.
- SEC/CON/RES: hàm thuần, không đầu vào người dùng mới, không trạng thái dùng chung, không I/O. DB/API: không migration, không đổi `layer.json`/hợp đồng; job `contract` xanh.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG | T5 đổi **phòng ngủ master thật** thành phòng khách khi tầng chưa nhận ra phòng khách, master > 18 m² và ≥ 1,3 lần phòng ngủ phụ (vd 19 m² và 14 m², tỉ lệ 1,36 — thường gặp ở căn hộ VN). Căn cứ "master thật lớn hơn phòng phụ ~1,1-1,25 lần" trong docstring không có số đo kèm theo; luật cũng không đòi đồ phòng khách (sofa/kệ TV) trong phòng bị đổi. Làn tự ghi rủi ro này ở "Chưa chắc" của báo cáo, nhưng `changes/BENCH3D-23.md` không ghi. Đổi tên mang tin cậy suy đoán và người dùng sửa được, nên không chặn. | `apps/worker/pipeline_build/rooms.py:153-158`, `:889-900`; `changes/BENCH3D-23.md:3` | Ghi giới hạn vào `changes/BENCH3D-23.md`. Lượt sau: thêm điều kiện phòng bị đổi có ít nhất một đồ loại khách/ăn trong `found_in`, hoặc đo tỉ lệ master/phụ trên đáp án bench (A/C/E/F) rồi mới chốt 1,3. |
| 2 | P3 | LOG | Ngưỡng `SLIDING_LOGGIA_MIN_DEPTH_MM` (800) đo ở tỉ lệ dựng vì `apply_post_rules` chạy trước `rescale_unreviewed`; khi `project_default` (`build ≠ final`) lô gia sâu 900 mm lúc dựng có thể chỉ còn ~630 mm khi ghi ra (Codex P2, chưa sửa). Lỗi cùng gốc với ngưỡng 1400 mm có sẵn, chỉ ở ca tỉ lệ chưa tin (màn Đặt tỷ lệ đã báo). Giới hạn chỉ ghi bằng chú thích `# ponytail:` trong mã, không có trong `changes/BENCH3D-23.md`. | `packages/domain/rules_ai/constants.py:27-35`; `packages/domain/rules_ai/post_rules.py:244-247` | Ghi vào `changes/BENCH3D-23.md`. Sửa gốc thuộc làn sở hữu `build.py`: truyền `final / build` vào `apply_post_rules` và nhân các ngưỡng mm. |
| 3 | P3 | TEST | Phần nối dây trong `build_rooms` (`texted=[text is not None …]`, `area_factor=(scaling.final / scaling.build) ** 2`) không có test nào khẳng định kết quả: test mới gọi thẳng `_open_space_labels`; các test `build_rooms` dùng `Scaling(1.0, 1.0)` hoặc không có hai phòng ngủ suy từ đồ. Đảo `final/build` hay đảo `texted` vẫn qua CI (độ phủ chỉ đo dòng đã chạy). | `apps/worker/pipeline_build/rooms.py:1216-1223` | Thêm một test `build_rooms` có hai phòng ngủ suy từ đồ, `Scaling(build=1.0, final=1.1)` (dưới 18 m² ở tỉ lệ dựng, trên 18 m² ở tỉ lệ ghi ra) và một biến thể có nhãn chữ "phòng ngủ" trong phòng lớn. |
| 4 | Nit | MNT | Trong cùng `_open_space_labels`, luật cũ so `_OPEN_SPACE_M2` ở tỉ lệ dựng (`wide`, `:879`) còn luật mới so ở tỉ lệ ghi ra (`:897`) — hai thước đo cho cùng một hằng số. | `apps/worker/pipeline_build/rooms.py:879`, `:897` | Khi sửa #2/#3, đổi `wide` cũng dùng `area_factor` (hay ghi rõ trong docstring vì sao luật cũ giữ tỉ lệ dựng). |
| 5 | Nit | MNT | Commit 2f7f9347: dòng `Prompt:` tách khỏi `Co-Authored-By:` bằng dòng trống nên `git interpret-trailers` không thấy nó (CI vẫn xanh vì đọc thân). | commit 2f7f9347 | Để `Prompt:` và `Co-Authored-By:` cùng khối trailer cuối. |

Không có P0/P1/P2. Hai P2 của Codex review cho làn: phát hiện "đúng 1,3 lần" đã sửa, có test; phát hiện tỉ lệ dựng còn lại là finding #2.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,72 / 5

## PHÁN QUYẾT: APPROVE

Không P0/P1/P2, điểm 4,72 ≥ 4,0. Hai luật nhỏ, đóng khung chặt (chỉ khi tầng chưa có phòng khách và phòng ngủ suy từ đồ; chỉ khi lô gia nông ngay trước ô kính), có test hai phía ngưỡng và bản tham chiếu sửa cùng logic. CI GitHub Actions trên đúng SHA đầu nhánh xanh 24/24, độ phủ gói và tổng ≥ 90/90. Hành vi đã đo thật trên f14 với đúng mã của nhánh (md5 trùng): f-02/f-08/f-11 P2 C→Đ, f-06 O1 T→Đ, lô gia thật ch-01 giữ cửa lùa. Các P3 (#1, #2) nên ghi vào `changes/BENCH3D-23.md` ở lượt sau; #3 là test nối dây nên thêm khi chạm lại `build_rooms`.
