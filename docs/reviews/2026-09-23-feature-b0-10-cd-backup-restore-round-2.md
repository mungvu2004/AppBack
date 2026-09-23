# Review merge `feature/b0-10-cd-backup-restore` → main — **lượt 2**

- Ngày: 2026-09-23 · Reviewer: phiên `/merge-review` **độc lập** (worktree `b0-10-review2`, không phải tác giả, không phải người điều phối; không sửa mã, không merge) · Commit đầu nhánh: `872fce1488ee`
- Phán quyết lượt 1: `docs/reviews/2026-09-23-feature-b0-10-cd-backup-restore.md` (REQUEST CHANGES, 3,3/5 — 1 P1, 5 P2, 4 P3, 2 Nit)
- Phạm vi lượt này: `git diff d8956df..872fce1` — 14 tệp, +340/−34. Gồm `0457ce0` (sửa từ nghiệm thu), cặp `0fd7e13`+`aeaf2c5` (thêm rồi revert `DEBT.md`, **net rỗng** — đã kiểm `git diff main...HEAD -- DEBT.md` rỗng). Cộng soát hồi quy trên toàn `main...HEAD`.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**, tự chạy tại chỗ trên `872fce1`, container `appback-verify-b0-10-review2-verify-run-46a3469d0902`, lượt 1/1. Bước 5: **2555 passed, 10 skipped, 1 deselected** (341,7 s) — đúng con số tác giả báo, +9 test so với lượt 1.
- Độ phủ (số của lượt chạy này, không lấy từ báo cáo): tổng **dòng 99,06 % · nhánh 97,32 %**; tập file bị chạm **100,00 % · 100,00 %**. Cả hai ngưỡng 90 % đều đạt.

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị perf bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt |
| 7 | H1 H3 H4 H5 | đạt. H4/H5 `không áp dụng` **hợp lệ** — B3-05/B4-01 chưa hợp nhất (BE-00 §12) |
| 8 | openapi | đạt (8174 byte) |

Điều kiện dừng sớm (§2): **không có**. Cây sạch; `changes/B0-10.md` có; **11/11** dòng đầu commit đúng Conventional Commits, ≤ 72 ký tự (dài nhất 71) và **11/11** có trailer `Prompt: B0-10`; diff không chạm `docs/charter/*`, `openapi.json`, `uv.lock`, `tools/**`, `apps/**`, `packages/**`, `deploy/{docker,compose,nginx,tests}/**`, `.github/workflows/ci.yml`; không `pragma: no cover`, `# noqa` trần, `# type: ignore` trần, `skip`/`xfail` mới, không hạ ngưỡng.

## 1. Đối chiếu từng finding lượt 1 — **12/12 đã đóng**

Tự kiểm trong mã, không tin bảng của tác giả.

| # lượt 1 | Mức | Trạng thái | Bằng chứng tự kiểm |
|---|---|---|---|
| 1 | **P1** LOG-01 | **đóng** | `drill.sh:44-45` khởi tạo `BACKUP_TARGET=""` **và** thêm cờ `DRILL_OWNS_BACKUP_TARGET=0`; `cleanup():54` chỉ `rm -rf` khi cờ = 1, cờ chỉ lên 1 ở `:215` ngay sau `mktemp -d`. Mạnh hơn đề xuất của lượt 1 (biến rỗng đơn thuần): giá trị thừa kế **khác rỗng** cũng không thể bị xoá. Hai test mới `test_drill.py` phủ cả nhánh đối số lạ lẫn nhánh `--compare` thiếu đối số. |
| 2 | P2 SEC-01 | **đóng** | Bước `kiem tag truoc khi dung` là **bước đầu tiên** của `promote` (`deploy.yml:153-158`, trước cả `docker login` và `imagetools`) và đứng trước bước ssh của `production` (`:190-195`), cùng regex `^(v[0-9]+\.[0-9]+\.[0-9]+\|sha-[0-9a-f]{12})$` với `rollback:243`. Test `test_deploy_yml_every_ssh_job_checks_tag_with_same_regex` **trích regex từ chính YAML của `rollback`** rồi đối chiếu — không chép tay, không trôi được. |
| 3 | P2 SEC-02/LOG-02 | **đóng** | `restore.sh:83-89` kiểm `s3\|local` ngay sau khi đọc manifest (`:77`), **trước** giải mã `age` (`:110`), trước `docker compose stop` (`:122`) và trước `DROP DATABASE` (`:127`). Test khẳng định đúng điều quan trọng: `"stop" not in log` và `"DROP DATABASE" not in log`. |
| 4 | P2 CON-01 | **đóng** | `concurrency` mức workflow đã bỏ; mỗi job có nhóm theo **môi trường thật**: `images`+`staging` → `deploy-staging` (`:35,:95`), `promote`+`production` → `deploy-production` (`:142,:177`), `rollback` → `deploy-${{ inputs.target }}` (`:225`). `cancel-in-progress: false` cả 5. `production` và `rollback(target=production)` nay **cùng** nhóm ⇒ loại trừ lẫn nhau, đúng ý finding. Test viết lại khẳng định cả `"concurrency" not in doc` lẫn từng nhóm. |
| 5 | P2 R-34 | **đóng** | Người điều phối đã ghi `NO-114`…`NO-119` trên `main` (`DEBT.md:134-139`), gồm dòng `NO-119` "seed hai lần" mức **Chấp nhận** có lý do đứng được (seed idempotent, drill đếm sau khi seed). Nhánh **revert** commit `DEBT.md` của chính nó — đúng R-27, vì `DEBT.md` nằm ngoài `so_huu` của B0-10. Xử lý đúng chuẩn. |
| 6 | P2 MNT-05 | **ghi nhận** | Không cần sửa (lượt 1 đã kết luận "giữ nguyên"). |
| 7 | P3 SEC-03 | **đóng** | `restore.sh:30` `backup_dir="$(cd "$backup_dir" && pwd)"` ngay sau kiểm `-d`, trước mọi `-v` của Docker. Test dùng `monkeypatch.chdir` + đường tương đối. |
| 8 | P3 RES-01 | **đóng** | `lib.sh:100-106` chặn `new_id` rỗng, `return 1` trước khi gọi `wait_container_healthy`. Test **đo thời gian** (`elapsed < 10` với `APPBACK_HEALTH_TIMEOUT_S=120`) — hỏng lại nếu ai bỏ guard. |
| 9 | P3 RES-02 | **đóng** | `smoke.sh` thêm `SMOKE_DEADLINE_S` (mặc định 60) và `_max_time()` = min(10, ngân sách còn lại), dùng ở cả 3 chỗ `curl`. Test route treo 5 s với `SMOKE_DEADLINE_S=2`. |
| 10 | P3 RES-03 | **đóng** | `healthcheck.sh:29` `[[ "$failures" =~ ^[0-9]+$ ]] \|\| failures=0`. Test ghi nội dung hỏng, khẳng định thoát 0 và bộ đếm về `1`. |
| 11 | Nit SEC-04 | **đóng, vượt yêu cầu** | 6 chỗ `${{ steps.sha12.outputs.sha12 }}` đã qua `env: SHA12`; test siết từ "cấm `inputs.`/`github.event.`" thành **cấm mọi `${{` trong `run:`** — luật giờ không còn kẽ hở theo loại biểu thức. Đã tự kiểm `deploy.yml` và `notify.yml` không còn `${{` nào trong `run:`. |
| 12 | Nit OPS-01 | **đóng** | Hai dòng `STAGING_USER`/`PRODUCTION_USER` đã bỏ khỏi README §3. |

Bất biến **[9] soát lại trên bản sau sửa, không hồi quy**: migrate (`deploy.sh:40`) vẫn trước `swap_api` (`:45`); `lib.sh:107-123` vẫn chờ `new_id` healthy **rồi** mới `stop`/`rm` container cũ (thêm `sleep` chỉ **kéo dài** khoảng an toàn, không rút ngắn); hết giờ thì xoá container **mới**, giữ cũ (`:108`); `rollback.sh` không có lệnh `alembic` nào, `restore.sh:140` chỉ `upgrade head`; **không** `${{ inputs.* }}`/`${{ github.event.* }}` (và nay không `${{` nào) trong `run:`; 3 action đều ghim SHA 40 ký tự; không `continue-on-error`, không `pull_request_target`; `packages: write` chỉ ở `images` và `promote`; `notify.yml` **không đổi** ở lượt này — vẫn `permissions: {}`, không `uses:` nào (không checkout), mọi giá trị `workflow_run` qua `env:` ⇒ an toàn với PR fork; không `set -x`, secret chỉ giãn **trong** container, khoá ssh vào `$RUNNER_TEMP` + `chmod 600` + `trap rm -f`; `shellcheck -x` quét bằng glob nên tự phủ các dòng mới của `drill.sh`/`lib.sh` (0 cảnh báo, trong bước 5).

## 2. Finding mới lượt 2

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| N1 | **P2** | RES-04 / OPS-02 | Điều [8] "đổi container **không gián đoạn**" vẫn **chưa đạt**: đo lại bằng client trong container trên mạng compose (loại bỏ giả thuyết `curl.exe`/Windows của `NO-117`) cho **5/569 phản hồi không 2xx**. Gốc đã được tác giả chứng minh bằng log nginx: Docker gắn bí danh DNS `api` cho container mới **ngay lúc tạo**, trước khi `uvicorn` lắng nghe; mẫu `set $api …; proxy_pass $api;` không có cơ chế thử lại sang container còn sống. `APPBACK_API_SWAP_SETTLE_S` chỉ chắn chiều ngược lại (xoá container cũ quá sớm). **Phiên này tự đánh giá phương án trong phạm vi B0-10 và đồng ý là không có**: gate bí danh mạng trong `swap_api` (`docker network disconnect` ngay sau khi tạo, `connect --alias` sau khi healthy) **không khả thi** vì healthcheck của `api` cần tới postgres/redis qua chính mạng đó — container bị ngắt mạng sẽ không bao giờ healthy; và bản thân lệnh `disconnect` vẫn đua với lượt re-resolve đầu tiên của nginx. Sửa đúng nằm ở `deploy/nginx/templates/{dev,prod}/app.conf.template` (khối `upstream` + `proxy_next_upstream`, hoặc `error_page 502 503 504 = @retry`) hoặc gate readiness ở `deploy/compose/**` — **cả hai thuộc `so_huu` B0-08 và nằm trong khối [12] "KHÔNG ĐƯỢC SỬA"**. Tác giả báo lại thay vì vòng qua hay im lặng — **xử lý đúng**. Tác động thực tế: ~0,9 % request trong cửa sổ ~1,4 s **mỗi lượt deploy**, HTTP 502/refused, **không mất dữ liệu, không hỏng trạng thái**, deploy production còn cần người duyệt. | `deploy/nginx/templates/prod/app.conf.template:29` (gốc), `deploy/scripts/lib.sh:111-119` (chỗ đã chắn được một nửa) | Giao **FIX cho B0-08** (không phải B0-10): thêm khối `upstream` + `proxy_next_upstream error timeout http_502 http_503` cho `api`, kèm test đo lại vòng poll trong container. Trước M1 vận hành `production` có giám sát và retry ở tầng gọi API. |
| N2 | P3 | TEST-02 / K23 | `test_drill.py` gọi `run_script(...)` **không** truyền `bin_dir`, nên `drill.sh` chạy với `docker` **thật** trên `PATH`. Lối thoát sớm kích hoạt `trap cleanup EXIT`, và `cleanup():51` chạy `docker compose down -v --remove-orphans` với `COMPOSE_PROJECT_NAME=appback-drill` + `COMPOSE_FILE=deploy/compose/ci.yml` (đặt ở `:24-26`, **trước** khi parse đối số). Trong container verify không có `docker` nên `\|\| true` nuốt lỗi và cổng vẫn xanh — nhưng chạy `pytest` trên máy dev có Docker sẽ **xoá volume** của một lượt `drill.sh` đang chạy song song. Mọi test khác của nhánh đều đã stub `docker` bằng `fake_bin` — chỗ này lệch chuẩn của chính nhánh. | `deploy/scripts/tests/test_drill.py:22,36` | Truyền `bin_dir=fake_bin(tmp_path / "bin", {"docker": "…exit 0…"})` như `test_deploy.py`. |
| N3 | P3 | R-05 | Mặc định `APPBACK_API_SWAP_SETTLE_S=11` ràng buộc với `resolver 127.0.0.11 valid=10s` của **file thuộc prompt khác** (`deploy/nginx/templates/{dev,prod}/app.conf.template:29`). Ràng buộc được ghi trong comment `lib.sh:115-118` và bảng README — nhưng **không test nào chốt nó**: B0-08 nâng `valid=` lên 30 s thì deploy âm thầm quay lại gây 502 thật, cổng vẫn xanh. `test_deploy_respects_api_swap_settle_s` chỉ chốt "có `sleep`", không chốt "đủ dài". | `deploy/scripts/lib.sh:119` | Test trong `deploy/scripts/tests/` (chỉ **đọc** file B0-08, không sửa): trích `valid=(\d+)s` từ cả hai template, khẳng định mặc định của `lib.sh` ≥ giá trị lớn nhất + 1. |
| N4 | P3 | R-34 | `DEBT.md:137` (`NO-117`, trên `main`) vẫn ghi nguyên nhân **đã bị chính tác giả bác bỏ** ("`curl.exe` tranh cổng ephemeral… hiện tượng phía máy kiểm Windows") và hướng đóng "đo lại trên Linux mà hết thì đóng, không sửa mã". Sau phép đo trong container, nguyên nhân thật là đua DNS phía nginx và **phải sửa mã**. Ai đọc sổ nợ sau này sẽ đóng nhầm `NO-117`. Ngoài diff nhánh (`DEBT.md` thuộc người điều phối), nhưng là điều kiện merge. | `DEBT.md:137` | Viết lại `NO-117` theo bằng chứng ở `REPORT.md` (log nginx `connect() failed (111)` + mốc tạo `api-2`), đổi chủ sang **B0-08**, giữ mức P2. |
| N5 | Nit | CON-02 | `images` và `staging` cùng nhóm `deploy-staging`, `promote` và `production` cùng nhóm `deploy-production`. GitHub chỉ giữ **một** job `pending` mỗi nhóm; job pending cũ bị huỷ khi có job mới vào. Với 3 lượt trở lên chồng nhau (nhiều tag đẩy liên tiếp, hoặc CI `main` xanh dồn dập), một `staging`/`production` đang xếp hàng có thể bị huỷ **trước khi chạy**. Không gây deploy dở dang (job bị huỷ khi chưa khởi động), chỉ làm rơi một lượt deploy. | `.github/workflows/deploy.yml:35,95,142,177` | Chấp nhận được; nếu muốn chắc thì thêm `::notice::` hoặc job `notify` khi lượt bị huỷ. |
| N6 | Nit | MNT-06 | `--dry-run` của `deploy.sh` không in bước chờ mới: `swap_api:83-88` chỉ `plan` "chờ healthy" rồi "xoá cũ", thiếu `sleep` settle ở `:119`. Kế hoạch in ra đã lệch khỏi thứ tự thật mà `test_deploy_dry_run_prints_order_without_docker` đang chốt. | `deploy/scripts/lib.sh:83-88` | Thêm `plan "chờ nginx dịch lại DNS …s"` giữa hai dòng `plan` hiện có. |
| N7 | Nit | R-07 | Nhánh `*)` của `case "$storage"` ở bước 6 nay **không thể tới được** (đã chặn ở `:83-89`). Giữ lại là phòng thủ hợp lý, nhưng trùng thông điệp lỗi từng chữ. | `deploy/backup/restore.sh:148-151` | Giữ, đổi chú thích thành "không thể tới — đã kiểm ở :83" để người sau không tưởng còn đường vào. |
| N8 | Nit | TEST-03 / R-01 | Hai test mới khẳng định theo **đồng hồ thật** (`elapsed >= 2`, `elapsed < 8`, `elapsed < 10`). Biên khá rộng nên rủi ro flake thấp, nhưng máy nạp nặng (đúng lúc chạy 2 container verify song song) có thể chạm. Ngoài ra `test_restore.py:255` `monkeypatch` thiếu annotation — lọt vì `pyproject.toml` `[tool.mypy] files = ["packages","apps","tools"]` **không gồm `deploy/`**, nên bước 3 không hề soi thư mục này (vấn đề tiền tồn tại của B0-01, không phải nhánh này gây ra). | `test_deploy.py:280-284`, `test_smoke.py:66-70`, `test_restore.py:255` | Nới biên trên hoặc dùng ngưỡng "≥" rộng hơn; annotate `monkeypatch: pytest.MonkeyPatch`. |

Không có finding nào ở mức **P0** hay **P1**. Không phát hiện hồi quy nào so với lượt 1.

## 3. Test so với điều [8]

Mọi finding có sửa mã đều kèm test **đỏ trên mã cũ**, và test được viết theo cách khó gian lận: regex tag được **trích thẳng từ YAML của `rollback`** rồi so sánh với hai job kia (không chép hằng); ba finding thời gian (`new_id` rỗng, `_max_time`, `settle`) được chốt bằng **đo đồng hồ**, không chỉ bằng grep mã; test `storage` khẳng định **vắng mặt** `stop`/`DROP DATABASE` trong nhật ký docker giả thay vì chỉ khẳng định mã thoát. Việc siết `test_deploy_yml_no_forbidden_interpolation_in_run_steps` từ danh sách đen theo loại biểu thức sang **cấm toàn bộ `${{`** biến một Nit thành một luật không còn kẽ hở — đúng tinh thần R-19 (sửa gốc, không vá triệu chứng).

## 4. Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 4 | 0,60 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 4 | 0,40 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 4 | 0,28 |
| OBS, OPS – Vận hành | 5 % | 3 | 0,15 |
| MNT – Bảo trì | 3 % | 4 | 0,12 |
| **Tổng** | **100 %** | | **4,55 / 5** |

## PHÁN QUYẾT: APPROVE

Vòng sửa đóng **12/12** finding của lượt 1, và đóng chúng ở gốc chứ không vá triệu chứng. Riêng P1 được sửa **mạnh hơn** mức lượt 1 yêu cầu: thay vì chỉ khởi tạo `BACKUP_TARGET=""`, tác giả thêm cờ sở hữu nên `cleanup()` không thể xoá một giá trị thừa kế **khác rỗng** — kịch bản mất bản sao lưu trên VPS đã bị chặn triệt để, có hai test hồi quy. Không finding P0/P1 mới, không hồi quy. Cổng tự chạy tại chỗ mã thoát **0** ngay lượt đầu, 2555 test, độ phủ 99,06 % dòng / 97,32 % nhánh, tập file bị chạm 100 %/100 %. Mọi bất biến nguy hiểm của [9] vẫn đúng sau khi sửa.

Điểm đáng ghi nhận nhất về **cách làm việc**: khi phép đo lại (client trong container) bác bỏ chính giả thuyết `NO-117` trước đó, tác giả **không** sửa file cấm ở khối [12] để làm đẹp con số, cũng **không** im lặng bỏ qua — mà truy ra gốc bằng log nginx, chứng minh nó nằm ngoài `so_huu`, rồi trả lại cho người điều phối quyết định. Đó đúng là hành vi R-19 + R-27 mà luật mong đợi.

**Duyệt merge nhánh này.** Hai việc phải làm **trước hoặc ngay khi merge**, cả hai đều nằm ngoài nhánh (thuộc người điều phối), nên không chặn `APPROVE`:

1. **Viết lại `NO-117`** trong `DEBT.md` theo nguyên nhân thật (đua bí danh DNS của container `api` mới ở phía nginx), đổi chủ sang **B0-08**, giữ P2 (N4). Để nguyên bản cũ là để lại một dòng nợ sai sẽ bị đóng nhầm.
2. **Chốt với người dùng** rằng điều [8] "không gián đoạn" **chưa đạt** (5/569 ≈ 0,9 % trong ~1,4 s mỗi lượt deploy, không mất dữ liệu) và nó **không sửa được trong `so_huu` của B0-10** — cần một FIX cho B0-08 ở `deploy/nginx/**` (N1). Cho tới lúc đó, bật `production` lần đầu phải có giám sát và retry ở tầng gọi API.

Ba mục P3 (N2 test chạm Docker thật, N3 thiếu test chốt ràng buộc TTL, N4) nên gom vào một FIX nhỏ sau merge; N2 và N3 nằm gọn trong `so_huu` của B0-10 nên giao lại đúng chủ. Bốn Nit (N5–N8) tuỳ nghi, không cần theo dõi.
