# Review merge feature/b3-06-rules-ai-post-rules → main

- Ngày: 2026-09-28 · Reviewer: phiên /merge-review (lượt 1, worktree riêng ở sha đi review, không sửa mã, không merge)
- Commit đầu nhánh: `6366dfa6b3ee` · một commit, cây sạch, diff chạm đúng `packages/domain/rules_ai/**` + `changes/B3-06.md` (16 file, +2.198 dòng)
- Cổng: phạm vi **đầy đủ** — lượt đầu của nhánh đi review (R-33b điều kiện 1; thêm gói `.py` mới).
  `bash tools/verify/run.sh verify` → **mã thoát 0** (log `F:/AppBack/backend/dieu-phoi/chay/B3-06/review-1-full.log`, dòng `EXIT=0`), reviewer tự chạy.
- Độ phủ (đo ở lượt này, không chép của tác giả): tổng dòng **99,56 %** · nhánh **98,54 %** · `packages/domain` 100,00/100,00 · tập file bị chạm 100,00/100,00 — mọi số ≥ 90/90.

## Bảng cổng (mã thoát thật của lượt reviewer)

|  # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | |
| 1 | `ruff format --check` | đạt | 923 file đã đúng định dạng |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | 5.655 qua, 9 bị loại theo marker, **0 hỏng**, 26 ph 14 s |
| 5b | `pytest -m perf` → `case_gate` | đạt | 2 test `perf`, 1,96 s; `case_gate`: 64 thao tác đã mount |
| 6 | `lint_migrations` → `migrate_check` | đạt | nhánh không thêm migration |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | AppFront @ `9cf0b0bfffbd` |
| 8 | `openapi` | đạt | 203.600 byte |

Không bước nào "không áp dụng", không bước nào "chưa chạy".

## Đã tự đối chiếu (không tin báo cáo tác giả)

- **Gương FE, đọc thẳng `F:/AppFront`:** `gap_to_wall_face` khớp `gapToWallFace` (`fitout/index.ts:186-202`) từng dòng — 5 điểm dò đúng thứ tự, `distancePointToSegment` kẹp đầu mút, trừ nửa bề dày, `max(0, …)`. `outline_contains` khớp `outlineContains` (`area.ts:278-297`); `centroid` khớp `computeCentroid` (`:235-270`) kể cả ngưỡng suy biến `0,001` = `DEFAULT_EPSILON` (`units/compare.ts:23`). Bốn ca khoảng cách của `fitout.test.ts:348-382` được chép đúng số (5590→0; 5540→50; 5530→60; 5900 cỡ 200→0) ở `test_geometry.py:28-40`.
- **Chỉ mục = quét hết:** chứng minh được, không chỉ tin test. Tường nạp vào mọi ô chạm hộp bao nở `dày/2 + 300`; nếu `gap ≤ 300` thì tồn tại điểm dò `p` nằm **đồng thời** trong hộp nở của tường và trong hộp của đồ, nên ô của `p` vừa được nạp vừa được tra → ứng viên không bao giờ sót tường có thể thắng. Luật hoà giữ nhờ `sorted(found)` trên vị trí trong `walls` và so `<` chặt. Phòng cũng vậy: điểm ngoài hộp bao chắc chắn ngoài đường bao.
- **Hậu điều kiện luật 1:** dời `v = (f − p)·gap/d` đưa `|p′ − f|` về `dày/2`, tức khe 0; `js_round` chỉ thêm ≤ 0,71 mm sai số → `gap ≤ 50` luôn đúng, lượt hai không dời. Mẫu số `d > 50 + dày/2 > 0` nên không chia 0.
- **Bảy bước trộn** đối chiếu từng bước với [6]; `dropped_ai_ids` theo thứ tự `ai.entities()`, `id_map` chỉ tường/phòng (đúng chữ dòng 110 của [6]), `id_map` là `MappingProxyType` chỉ đọc, `changes == diff_layers(current, layer)` có test. `MergeResult` thoả **theo cấu trúc** `MergeOutcome` (`apps/api/spatial_write/writer.py:81`) — `test_merge.py:28-40,283` gán vào một Protocol chép lại và `mypy --strict` xanh, mà `rules_ai` không nhập B3-03 (kiểm bằng danh sách import).
- **Bản tham chiếu có thật:** `tests/reference.py` là bản quét hết / so mọi cặp riêng biệt, không gọi `post_rules.py` hay `merge.py` — `test_random.py` so 200 hạt giống, và `test_post_rules.py`/`test_merge.py` so **từng ca** qua `_apply_fixture`/`_merge`.
- **K18/K19/K21/K24:** không `round()` dựng sẵn cho toạ độ (chỉ một lần cho `confidence` của dữ liệu thử); không `float` mm trong mô hình ra (`js_round` → `int`); không `pragma: no cover`, không `skip`/`xfail`; bốn `# noqa`/`# type: ignore` đều có mã **và** lý do. Không nhập `sqlalchemy`, `fastapi`, `celery`, `numpy`, `torch`, `shapely`, `packages.db/storage/messaging/vision`, `apps.*`; `uv.lock` không đổi.
- **Ma trận [8]:** soát đủ từng dòng — 93 test (91 thường + 2 `perf`), không dòng nào của [8] thiếu test. Ngẫu nhiên 200 hạt giống, 25 % chung id (≥ 20 %), in hạt giống khi hỏng qua `add_note`. Hai test `perf` có marker, tự khẳng định trần trong test (`< 5 s`, `< 1 s`) và in số đo bằng `logging` đúng BE-00 §12 §479.
- **R-01/R-07/R-27:** mọi hàm và lớp trong diff đều có docstring; hàm dài nhất < 50 dòng; không hàm nào vượt cyclomatic 10; không chạm file của prompt khác, không chạm `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `tools/**`.
- **"Lệch khỏi prompt" của tác giả:** cả ba đều chấp nhận — (a) viết lại câu commit theo BE-00 §13.2 là **bắt buộc** của CLAUDE.md; (b) `id_map` chỉ tường/phòng là đúng chữ [6] dòng 110, không phải lệch; (c) các tên phụ trong `geometry.py` không xuất ở `__init__`, cần cho chỉ mục và luật hoà, không phá hợp đồng [2].

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG-03 (K21) | Luật 2 đánh dấu tường được nâng cấp bằng **id** (`promoted: set[str]`) rồi viết lại **mọi** tường mang id đó. Lớp có hai tường trùng id — bản đầu AI chưa duyệt, bản sau `source="human", reviewed=True` — thì bản của người cũng bị đổi `kind="envelope"` và hạ `confidence`, tức đụng thực thể được K21 bảo vệ. Đo trong container: `[('W-T000000001','envelope','ai',False), ('W-T000000001','envelope','human',True)]`. Giảm nhẹ: `check_integrity` đã báo `duplicateId` mức `critical` cho lớp ấy và pipeline sinh id W4 nên đầu vào này là dị dạng; luật 1 (`_snap_fixtures:114-120`) miễn nhiễm vì đánh dấu theo **vị trí**. | `packages/domain/rules_ai/post_rules.py:169,180,184` | Thêm chốt ở `:184`: `_envelope(w) if w.id in promoted and _editable(w) else w`; hoặc đánh dấu theo vị trí như `_snap_fixtures`. |
| 2 | P3 | PERF-02 | `_WallIndex` nạp mỗi tường vào **mọi ô của hộp bao** nở `thicknessMm/2 + 300`, không chỉ các ô đường tim đi qua, nên chi phí là O(dài²/cạnh²) với tường chéo thay vì O(dài/cạnh). Đo trong container: 2.000 tường ngang 4 m → 22.800 mục lưới / 0,008 s; 2.000 tường **chéo** 72 m → 5.170.800 mục / 0,601 s (227× số mục). Test hiệu năng `tests/test_perf.py:86-105` chỉ dựng tường **thẳng trục** 4 m, nên trần < 5 s của [8] chưa được kiểm đúng hình dạng mà chính docstring module cảnh báo (`post_rules.py:7-9`). | `packages/domain/rules_ai/post_rules.py:59-64`; `packages/domain/rules_ai/tests/test_perf.py:86-105` | Duyệt ô theo đường tim (DDA trên lưới) thay vì hộp bao, hoặc thêm một nhóm tường chéo dài vào lớp hiệu năng; ghi `DEBT.md` nếu để lại. |

### Nit (không chặn merge)

- **Nit 1 · TEST-07** — `reference.py` dùng lại `nearest_probe`, `centroid`, `outline_contains`, `wall_side` của `geometry.py` và chép **nguyên văn** phép dời của `_snap_fixture` (`reference.py:38-39` ↔ `post_rules.py:101-102`), nên bản tham chiếu chỉ thẩm định **chỉ mục**, không thẩm định hình học hay vector dời. Đó đúng là điều [8] đòi và các nguyên hàm có test đối chiếu số FE riêng (`test_geometry.py:28-40`), nhưng docstring "viết độc lập với mã" nói quá.
- **Nit 2 · MNT-02** — `merge.py:163-164` mang dấu `ponytail:`, quy ước ngoài repo này; hơn nữa phép so từng cặp phòng là **đúng chữ** [6] ("Không dựng lưới 50 mm theo hộp bao phòng"), không phải lối tắt cần ghi trần.
- **Nit 3 · LOG-08** — `post_rules.py:98` so `>` chặt với dung sai 50, FE so qua `compareNearly(..., 0.001)` (`fitout/index.ts:313`): khe 50,0005 mm FE coi là đạt, ở đây bị dời. Dưới micromet, không bản vẽ nào diễn đạt được — không cần sửa.
- **Nit 4 · MNT-02** — `geometry.py:127-128` bọc `//` trong `math.floor`; `//` đã làm tròn xuống sẵn nên lời gọi là thừa.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 | 0,60 |
| PERF – Hiệu năng | 10 % | 4 | 0,40 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 5 | 0,15 |
| **Tổng** | **100 %** | | **4,75 / 5** |

SEC 5: gói miền thuần, không I/O, không bí mật, không biên tin cậy ngoài tiền điều kiện `ValueError`. CON 5: hàm thuần, `MergeResult` frozen, `id_map` chỉ đọc, idempotent có test — đúng thứ B3-03 cần khi giữ khoá tài liệu tầng. LOG 4 và PERF 4 vì hai P3 ở trên. RES/DB/API 5: không phụ thuộc ngoài, không migration, không hợp đồng HTTP.

## PHÁN QUYẾT: APPROVE (4,75/5)

Không P0, không P1. Cổng đầy đủ do reviewer tự chạy thoát 0 cả tám bước; độ phủ mọi gói bị chạm 100 % dòng **và** 100 % nhánh. Phần khó nhất của prompt — chỉ mục lưới phải cho **cùng** kết quả với bản quét hết, và trộn phải không bao giờ đụng mục `reviewed=True` — không chỉ được test mà còn đứng vững khi soát bằng lập luận: điều kiện nạp ô của luật 1 thật sự bao hết mọi tường có thể thắng, và bản tham chiếu trong test là một cài đặt riêng chứ không phải chính mã soi gương. Gương FE được đối chiếu thẳng với `F:/AppFront` chứ không tin báo cáo.

Hai P3 không chặn merge: cả hai chỉ đụng đầu vào mà `check_integrity` đã gọi là `critical` (finding 1) hoặc một hình dạng mặt bằng nằm ngoài bộ đo hiện có (finding 2). **Điều kiện sau merge:** ghi hai dòng `NO-<nnn>` vào `DEBT.md` cho finding 1 và 2 (R-34) — chủ là B3-06; finding 1 sửa được bằng một chốt `and _editable(w)`, đáng gộp vào FIX kế tiếp chạm gói này.
