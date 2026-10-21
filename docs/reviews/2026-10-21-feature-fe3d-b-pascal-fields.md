# Review merge feature/fe3d-b-pascal-fields → main

- Ngày: 2026-10-21 · Reviewer: phiên /merge-review · Commit đầu nhánh: 3c7b1c8d69fa (base `main` 1ebe7573)
- Cổng: phạm vi **đầy đủ** — lượt review đầu của nhánh (R-33b (1)); diff còn chạm `packages/db/**`, `packages/domain/**`, migration, `tools/contract/APPFRONT_SHA`, `docs/contracts/**` (R-33b (2)) và đổi hình dạng dây (R-33b (5)).
  `bash tools/verify/run.sh verify` mã thoát **0** (log: `F:/worktrees/AppBack/fe3d-b/.cache/review-verify-full.log`; 8630 passed, bước 0–8 đạt, bước 7 H1 1989 mẫu @ AppFront c73be124).
  Thêm: `VERIFY_BRANCH=integration bash tools/verify/run.sh verify --steps 8` mã thoát **0** (log: `F:/worktrees/AppBack/fe3d-b/.cache/review-verify-step8-integration.log`): `docs/contracts/openapi.json` đã commit trùng bản xuất từ mã.
- Độ phủ: tổng dòng 99,47% · nhánh 98,01% · tập file bị chạm 99,73% / 97,98%. Gói bị chạm thấp nhất: `apps/worker/pipeline_persist` 98,51% / 90,62%; `packages/db` 97,43% / 95,90%. (Bước coverage có cảnh báo `Combined 1 file, skipped 1, 1 file errored` — một tệp dữ liệu tạm hỏng; cổng vẫn đạt, không phải finding.)

## Phạm vi và điều kiện dừng sớm

- Cây sạch (`git status --porcelain` rỗng). 6 commit, đều Conventional Commits ≤ 72 ký tự, trailer `Prompt: FE3D-B` đọc được bằng `%(trailers:key=Prompt)` (R-36b). Có `changes/FE3D-B.md` (+ B2…B5).
- 46 file, +1676/−49; ngoài test, `openapi.json`, `changes/`: 457 dòng thêm, trong đó **279 dòng mã** (còn lại docstring/comment/dòng trống) → dưới ngưỡng MNT-05.
- Không `pragma`, `type: ignore`, `noqa`, `skip`/`xfail` mới, không hạ ngưỡng. Không chạm `docs/charter/*`, `uv.lock`, `pyproject.toml`.
- File của người điều phối: `tools/contract/APPFRONT_SHA` (55af7d9c → 051add2e, bb255414 → c8b72f7c, 3c7b1c8d → c73be124) và `docs/contracts/openapi.json` (3c7b1c8d). **Chấp nhận** theo tiền lệ (`2026-10-13-refactor-f-15-pascal-flag.md`, `2026-10-15-fix-qa06-be.md`): `changes/FE3D-B.md:7` ghi hai tệp do người điều phối xuất/ghim, phiên gọi review xác nhận pin c73be124 là chủ ý; bằng chứng kỹ thuật: bước 8 so bản tham chiếu đạt, bước 7 @ c73be124 đạt. Git không phân biệt được tác giả (mọi commit cùng một tên), nên chỉ dựa vào hai nguồn trên.

## Hợp đồng FE — pin `APPFRONT_SHA`

- `git -C F:/App/AppFront diff c73be124 feat/pascal-ui-polish -- src/api` **rỗng**. Các đường khác mà `tools/contract` đọc (`src/lib/auth/*`, `src/domain/rules/*`) cũng không đổi. `src/domain/**` (danh sách `FURNITURE_VARIANTS`, `RoomFinish`) và `src/lib/pascal/sceneStyles.ts` không đổi.
- Thay đổi dây thật sự duy nhất phía FE sau c73be124: `toSpatial.ts` ghi mọi `library:<id>` của vendor (`libraryMaterialIds.ts`); đã đối chiếu mọi id với `MaterialRef` `^(library|scene):[a-z0-9_-]{1,64}$` của BE: đều khớp. `model.src`, `slots`, `heightMm`/`liftMm` vẫn cùng luật như ở c73be124.
- Kết luận: **BE không phải đổi schema**; về hợp đồng, c73be124 và `feat/pascal-ui-polish` (3f6a34df) tương đương. Pin vẫn nên trỏ commit FE thật sự lên master, vì CI/deploy dựng ảnh `web` từ đúng SHA ghim (finding 3).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG-02 / R-13 | `merge_preferences` để lọt `null` khi khoá cha chưa có (hoặc không phải object): `elif isinstance(value, dict) and isinstance(old, dict)` sai thì rơi vào `merged[key] = value`, chép nguyên dict có `None`. Tái hiện trong container (`run.sh shell`): `UpdateMeBody{"preferences":{"notifications":{"aiCompleted":null}}}` trên người có `{}` → lưu `{'notifications': {'aiCompleted': None}}` → `UserPreferences.model_validate` ném `ValidationError` → PATCH N12 trả **500** cho một thân mà OpenAPI và FE `PreferencesPatchSchema` (`NotificationPatchSchema.nullable()`) đều cho phép. `AppRoute` rollback khi có ngoại lệ (`routing.py:262-280`) nên không lưu gì hỏng, vì vậy mức là P2. Cùng gốc: `{"appearance":{"density":null}}` trên `{}` lưu `{"appearance":{"density":null}}` (rác `null` trong JSONB, đọc vẫn qua). FE gửi `null` khi hoàn tác một ô (`accountSettingsGateway.ts` `preferencesPatchOf`), nên gặp lỗi khi bản FE đang cầm đã cũ hơn máy chủ (hai tab, hay sau `preferences: null`). | `apps/api/me/router.py:129-132` | Đệ quy cả khi giá trị cũ không phải object: `elif isinstance(value, dict): merged[key] = merge_preferences(old if isinstance(old, dict) else {}, value)`. Thêm case vào `test_preferences.py`: người `{}` PATCH `{"notifications":{"aiCompleted":null}}` → 200, `preferences` không còn `null` nào; cùng thể cho `appearance`. |
| 2 | P2 | TEST-04 / CON-01 | Commit 3947af09 và `changes/FE3D-B4.md` khẳng định "Đọc-gộp-ghi dưới `SELECT … FOR UPDATE` (hai PATCH song song không mất bản vá)", nhưng không có test đồng thời nào (`test_preferences.py` chỉ có 5 test tuần tự). Mã có khoá đúng (`with_for_update()`), nhưng khẳng định về khoá cần một test chạy trên dịch vụ thật (K23 / R-29). | `apps/api/me/router.py:150-155`; `apps/api/me/tests/test_preferences.py` | Thêm test hai session `db_sessionmaker`: PATCH A `{"appearance":{"showGrid":true}}` và PATCH B `{"seen":{"welcome":true}}` chạy chồng nhau (giữ khoá ở A bằng event/hook như `test_notify__row_trimmed…`), rồi khẳng định cả hai khoá đều còn. |
| 3 | P2 | OPS-03 / API-03 | Pin `tools/contract/APPFRONT_SHA` = c73be124 tương đương về hợp đồng với HEAD FE sẽ lên master (`src/api` không đổi), **nhưng** `tools/ci/job.sh:445-447` và `.github/workflows/deploy.yml:51,83-89` dựng ảnh `web` từ đúng SHA ghim. Giữ c73be124 thì bản deploy **thiếu FE3D-FIX-004 và 28 commit chỉnh giao diện** (c73be124..3f6a34df). Ngoài ra c73be124 hiện chỉ nằm trên `fix/pascal-parity`, `feat/pascal-ui-polish`, `fix/pascal-realism`, chưa có trên master AppFront: nếu FE được squash thì master không còn chứa SHA đã ghim. | `tools/contract/APPFRONT_SHA:1` | Việc của người điều phối, **không** làm trên nhánh này: sau khi FE lên master, ghim `APPFRONT_SHA` = SHA master sau gộp (3f6a34df nếu fast-forward, hoặc commit merge `--no-ff`, không squash, để c73be124 vẫn đọc được), chạy `bash tools/verify/run.sh verify --steps 7,8` (dự kiến đạt vì `src/api` không đổi), commit `chore(contract): pin AppFront <sha>`. |
| 4 | P3 | R-02 / MNT-04 | Ghi chú thay đổi cũ hơn nội dung sẽ vào `main`: `changes/FE3D-B.md:7` ghi `APPFRONT_SHA` = 051add2e (thực tế c73be124); `changes/FE3D-B2.md:7` và `changes/FE3D-B3.md:8` còn ghi "FE phải đọc khoan dung trước khi ghim … bước 7 chưa chạy", trong khi pin c73be124 đã đọc các khoá này và bước 7 đạt. | `changes/FE3D-B.md:7`, `changes/FE3D-B2.md:7`, `changes/FE3D-B3.md:8` | Sửa thành: pin c73be124 (FE3D-FIX-003 W4c), bước 7/8 đạt @ c73be124. |
| 5 | P3 | R-34 | Giới hạn tác giả tự nêu không có dòng nợ: "Kênh email chưa có ở BE (chỉ lưu lựa chọn)". Màn tài khoản FE vẫn cho bật/tắt email. `DEBT.md` đã bị gỡ khỏi repo (TIDY-ROOT 6b2e4d52, bản lưu ở `F:/backup/app-cleanup-2026-10-18/AppBack/DEBT.md`), nên không có chỗ ghi theo R-34. | `changes/FE3D-B4.md:7` | Ghi một dòng nợ ở sổ nợ hiện hành mà người dùng chọn (hoặc mục "Nợ" trong `changes/FE3D-B4.md`): "kênh email của `preferences.notifications` chỉ lưu, chưa gửi". |
| 6 | Nit | MNT | Việc ghim `APPFRONT_SHA` nằm lẫn trong hai commit `feat` (55af7d9c, bb255414) thay vì nằm riêng ở commit `chore(contract)`. Squash một prompt thì không còn ảnh hưởng. | 55af7d9c, bb255414 | Lần sau tách commit pin riêng. |
| 7 | Nit | LOG-06 | Bật/tắt `hiddenIn3d` (tuỳ chọn hiển thị) ghi nhật ký `FLOOR_EDIT` và `touch_project` như một lần sửa tầng, nên nhật ký hoạt động và "cập nhật lúc" của dự án thay đổi chỉ vì ẩn/hiện 3D. | `apps/api/floors/service.py:310-323` | Tuỳ sản phẩm: bỏ qua ghi nhật ký khi `changes` chỉ có `hidden_in_3d`. |

Đã soát, không có finding: SEC (mọi trường mới đều validate strict ở biên: `StrictBool`, `Literal`, regex `MaterialRef`/`SlotName`/`model.src` chặn URL ngoài, trần 8 slot / 64 tour / 120 ký tự id; `/me` chỉ ghi chính người gọi; `notify` dùng containment JSONB có tham số); DB (3 migration expand thuần, NOT NULL có `server_default`, CHECK khớp model, `migrate_check` lên/xuống/lên trên DB có dữ liệu đạt); CON (project_settings giữ ghi nguyên tử theo `revision`, `sceneStyle` vắng không đổi băm C09b; floors PATCH dưới khoá tầng); PERF (`notify` thêm đúng 1 truy vấn theo PK, không nằm trong vòng lặp; `with_floor_height` O(n) tường); worker B5 (`rescale_unreviewed` giữ `height_mm`; lan can và tường của người không bị đổi; có test Postgres thật).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 3 | 0,45 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 3 | 0,21 |
| OBS, OPS | 5% | 3 | 0,15 |
| MNT | 3% | 4 | 0,12 |

Tổng: **4,43 / 5** · P0: 0 · P1: 0 · P2: 3 · P3: 2 · Nit: 2

## PHÁN QUYẾT: APPROVE

Không có P0/P1, cổng đầy đủ thoát 0, độ phủ ≥ 90/90 ở mọi gói bị chạm, OpenAPI đã commit trùng mã, hợp đồng FE @ c73be124 xanh và tương đương HEAD `feat/pascal-ui-polish` (`src/api` không đổi). Điểm 4,43 ≥ 4,0 nên theo ma trận là APPROVE. Theo `RULE.md` §1, mỗi P2 phải được sửa trước merge hoặc có ticket/dòng nợ (R-38), nên điều kiện merge là:
1. Finding 1 và 2: sửa trên nhánh rồi chạy kiểm **đích** (`verify --steps 1,2,3,4` + pytest/coverage `apps/api/me`), **hoặc** ghi dòng nợ P2 có chủ (`apps/api/me`) trước khi gộp.
2. Finding 3: gộp FE vào master bằng fast-forward/`--no-ff` (không squash), rồi người điều phối ghim lại `APPFRONT_SHA` = SHA master FE và chạy `verify --steps 7,8` trước lần dựng ảnh/deploy tiếp theo.
3. Gộp BE: squash (một prompt FE3D-B, R-36), giữ trailer `Prompt: FE3D-B`. Cây sau gộp khác cây đã kiểm thì chạy verify tích hợp trên `main`.
