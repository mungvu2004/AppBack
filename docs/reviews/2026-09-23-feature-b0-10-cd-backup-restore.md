# Review merge feature/b0-10-cd-backup-restore → main

- Ngày: 2026-09-23 · Reviewer: phiên `/merge-review` **độc lập** (không phải tác giả, không phải người điều phối); phiên này không sửa mã, không merge. Mọi khẳng định trong `backend/dieu-phoi/chay/B0-10/bao-cao-lop1.md` và trong thân commit đều được tự kiểm lại · Commit đầu nhánh: `d8956dff8f7f` · 7 commit, 33 tệp, +3298/−0.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**, tự chạy tại chỗ trên `d8956df` từ worktree `b0-10-review`, container `appback-verify-b0-10-review-verify-run-41aa84e10ac8`. Log host: `.cache/src-out/verify/20260923T014107Z-d8956dff8f7f.log`. Bước 5: **2546 passed, 10 skipped, 1 deselected** (324,7 s) — khớp đúng con số tác giả báo. 10 `skipped` là của mã sẵn có trên `main`, nhánh này **không** thêm `skip`/`xfail` nào (đã `git diff` kiểm riêng).
- Hai lượt chạy đầu hỏng vì **môi trường, không phải mã**: lượt 1 container bị giết giữa lúc tải gói (`unexpected EOF`, máy đang chạy nghiệm thu drill song song), lượt 2 hỏng vì lượt 1 để lại wheel cụt trong cache (`import_linter-2.15 … Metadata field Name not found`). Xoá volume `appback-verify-b0-10-review_appback-work` rồi chạy lại sạch → mã thoát 0. Bảng dưới lấy từ lượt 3.
- Độ phủ: tổng dòng **99,07 %** · nhánh **97,37 %**; tập file bị chạm **100,00 %** · **100,00 %**. Cả hai ngưỡng 90 % đều đạt, khớp báo cáo tác giả.

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
| 7 | H1 H3 H4 H5 | đạt. H4/H5 `không áp dụng` **hợp lệ** vì B3-05/B4-01 chưa hợp nhất (BE-00 §12) |
| 8 | openapi | đạt |

## Phạm vi

`git diff main...HEAD` = 7 commit, 33 file, +3298/−0 (hai `.gitkeep` bị xoá — dọn đúng
chỗ khi file thật đã có). Toàn bộ diff nằm trong `so_huu` của B0-10; **không** chạm
`docs/charter/*`, `openapi.json`, `uv.lock`, `tools/**`, `apps/**`, `packages/**`,
`deploy/{docker,compose,nginx,tests}/**`, `.github/workflows/ci.yml`.

Điều kiện dừng sớm (§2): **không có**. Cây sạch; `changes/B0-10.md` có; cả 7 dòng đầu
commit đúng Conventional Commits và đều có trailer `Prompt: B0-10`; không `pragma: no
cover`, không `# noqa` trần (mọi `noqa` đều có mã + lý do), không `skip`/`xfail` mới,
không hạ ngưỡng.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | LOG-01 / R-19 | `cleanup()` chạy `rm -rf "$BACKUP_TARGET"` ở **mọi** lối thoát, kể cả lối thoát vì sai đối số — xảy ra **trước** khi `main()` gán `BACKUP_TARGET="$(mktemp -d)"` (dòng 206). `SCRATCH`/`AGE_DIR` được khởi tạo `""` ở dòng 37–38, `BACKUP_TARGET` thì không, nên `${BACKUP_TARGET:-}` đọc **giá trị thừa kế từ môi trường**. Đã tái hiện: `BACKUP_TARGET=<thư mục> bash deploy/scripts/drill.sh --bogus-arg` → thoát 2 và **xoá sạch `<thư mục>`**. README §9 bảo người vận hành đặt `BACKUP_TARGET` trong `appback.env`, §11 bảo chạy `drill.sh` ở mỗi mốc M1–M4 ⇒ một lần gõ nhầm đối số trên VPS mất toàn bộ bản sao lưu. | `deploy/scripts/drill.sh:47` (thiếu khởi tạo ở `:37-38`, gán ở `:206`, lối thoát ở `:271,:280`) | Thêm `BACKUP_TARGET=""` cạnh `SCRATCH=""`/`AGE_DIR=""` (`main()` vẫn ghi đè ở `:206`). Thêm test hồi quy: gọi sai đối số với `BACKUP_TARGET` thừa kế → thư mục còn nguyên. |
| 2 | P2 | SEC-01 | `TAG_NAME` (`github.ref_name`, tag `v*` do người đẩy lên) **không qua kiểm regex** rồi ghép thẳng vào chuỗi lệnh ssh `"/opt/appback/scripts/deploy.sh ${TAG_NAME}"`. sshd phía xa đưa chuỗi đó qua shell, nên tag tên `v1.0.0;<lệnh>` chạy `<lệnh>` trên máy production bằng user `deploy` (nhóm `docker` ⇒ tương đương root). Đã kiểm: `git check-ref-format 'refs/tags/v1.0.0;reboot'` **hợp lệ** và khớp trigger `v*`. (Không có nội suy lệnh phía runner — `${TAG_NAME}` không bị quét lại — nên dòng `imagetools` `:147` tự nó không khai thác được; sink là shell phía xa.) Đường `rollback` đã kiểm đúng regex cần thiết ở `:209`; đường production thì không. Cần quyền đẩy tag **và** người duyệt Environment `production`, nên không phải P0/P1. | `.github/workflows/deploy.yml:184` (và `:147`) | Áp đúng `^(v[0-9]+\.[0-9]+\.[0-9]+\|sha-[0-9a-f]{12})$` cho `TAG_NAME` trong `promote`/`production` trước khi dùng; mở rộng `test_workflows_deploy.py` để khẳng định **mọi** job có `ssh` đều kiểm tag. |
| 3 | P2 | SEC-02 / LOG-02 | `storage` đọc từ `manifest.json` (`:73`) chỉ được kiểm hợp lệ trong `case` ở bước 6 — tức **sau khi** đã dừng dịch vụ (`:107`), `DROP DATABASE` (`:112`) và `pg_restore` (`:119`). Manifest có `storage` lạ ⇒ hệ thống nằm im với CSDL đã khôi phục, kho object chưa đụng, rồi `exit 1`. `backup.sh:27-33` kiểm đúng giá trị này ngay đầu — biên ở đây lệch chuẩn của chính nhánh. | `deploy/backup/restore.sh:123-136` | Chuyển kiểm `s3\|local` lên ngay sau `:73`, trước mọi lệnh dừng. |
| 4 | P2 | CON-01 | `concurrency.group` = `deploy-${{ …head_branch \|\| github.ref_name \|\| inputs.target }}`. Với `workflow_dispatch`, `github.ref_name` **luôn** có giá trị (nhánh chạy dispatch), nên `inputs.target` không bao giờ tới lượt: rollback production rơi vào nhóm `deploy-main`, còn deploy production theo tag ở nhóm `deploy-v1.2.3`. Hai lượt `deploy.sh` có thể chạy **đồng thời trên cùng máy production**. Prompt [6] đòi `concurrency` **theo môi trường**. Test hiện chỉ khẳng định `cancel-in-progress is False`, không khẳng định cách nhóm. | `.github/workflows/deploy.yml:28-30` | Khoá nhóm theo môi trường, vd `deploy-${{ inputs.target \|\| (startsWith(github.ref,'refs/tags/v') && 'production' \|\| 'staging') }}`; thêm test cho cách nhóm. |
| 5 | P2 | R-34 | Bốn nợ worker nêu trong `bao-cao-lop1.md` (drill seed lần hai; Pha A cần `cli.py`; README §11 giả định thư mục systemd; `wait_healthy` trùng lặp) **không có dòng nào trong `DEBT.md`**; nhánh cũng không chạm `DEBT.md`. Tự kiểm: ba trong bốn nợ **đã thực sự được xử lý** (`apps/api/auth/cli.py` tồn tại; `wait_container_healthy` đã gom chung ở `lib.sh:52` và `restore.sh` `source` lại; hai thư mục systemd có thật), nợ còn lại (seed hai lần) là lựa chọn thiết kế theo [6] bước 1. | `DEBT.md` (thiếu), `bao-cao-lop1.md` | Ghi một dòng `NO-<nnn>` cho mục "seed hai lần" với lý do **chấp nhận** đứng được, và ghi rõ ba mục kia đã đóng — không để sổ nợ im lặng. |
| 6 | P2 | MNT-05 | ~1 300 dòng logic không phải test (tổng +3298) — vượt ngưỡng 400 dòng của §1. Ghi nhận theo đúng luật, nhưng **không đáng tách**: đây đúng bằng tập `so_huu` của một prompt, vốn đã do bốn worker song song làm rồi gộp lại. | toàn nhánh | Giữ nguyên; ghi nhận để không lặp quy mô này khi không cần. |
| 7 | P3 | SEC-03 | `backup_dir` dùng nguyên văn làm nguồn bind `-v` của Docker (`:126`, `:130`). Đường tương đối không phải đường tuyệt đối với Docker, và lỗi chỉ nổ **sau khi** CSDL đã bị drop. | `deploy/backup/restore.sh:25` | `backup_dir="$(cd "$backup_dir" && pwd)"` ngay sau kiểm `-d`. |
| 8 | P3 | RES-01 | `new_id` lấy id **cuối** không thuộc `old_ids`; nếu `--no-recreate` không tạo container nào thì `new_id` rỗng, `wait_container_healthy ""` quay đủ `APPBACK_HEALTH_TIMEOUT_S` (mặc định 180 s) rồi mới hỏng. | `deploy/scripts/lib.sh:92-97` | Chặn `new_id` rỗng, hỏng ngay kèm thông điệp. |
| 9 | P3 | RES-02 | Hạn 60 s được kiểm **trước** mỗi lần gọi, nhưng mỗi lần còn được `--max-time 10`, nên tổng có thể tới ~70 s; hợp đồng §2 ghi tổng ≤ 60 s. | `deploy/scripts/smoke.sh:15,21-27,33` | Truyền phần ngân sách còn lại vào `--max-time` thay vì cố định 10. |
| 10 | P3 | RES-03 | `health-failures` hỏng (nội dung không phải số) làm `$((failures + 1))` lỗi số học, script thoát khác 0 — trái hợp đồng §2 "0 luôn". | `deploy/scripts/healthcheck.sh:28` | Ép kiểu: nội dung không khớp `^[0-9]+$` thì coi là `0`. |
| 11 | Nit | SEC-04 | `${{ steps.sha12.outputs.sha12 }}` nội suy thẳng vào `run:`. Giá trị dẫn xuất từ `github.event.workflow_run.head_sha` (chỉ hex) nên **an toàn**, nhưng nó lách qua chính `test_deploy_yml_no_forbidden_interpolation_in_run_steps`. `HEAD_SHA` đã đi qua `env:` sẵn. | `.github/workflows/deploy.yml:68,71,75,84,122,148` | Đưa `SHA12` qua `env:` rồi dùng `$SHA12`, cho nhất quán với luật [9]. |
| 12 | Nit | OPS-01 | README §3 liệt kê secret `STAGING_USER`/`PRODUCTION_USER`, nhưng `deploy.yml` cứng `deploy@`. | `deploy/scripts/README.md` §3 | Bỏ hai dòng đó, hoặc dùng secret thật. |

## Những chỗ đã tự kiểm và **đạt**

Bất biến [9] — kiểm từng cái trong mã, không tin báo cáo:

- **Không migrate sau khi đổi container:** `deploy.sh:40` (migrate) đứng trước `:45` (`swap_api`). ✔
- **Không dừng `api` cũ trước khi `api` mới healthy:** `lib.sh:98` chờ healthy → `:102-105` mới `stop`/`rm`; hết giờ thì xoá container **mới** và giữ cũ (`:99-100`). ✔
- **Không `alembic downgrade` trong rollback:** `rollback.sh` không có lệnh migrate nào; `restore.sh:140` chỉ `upgrade head`. ✔
- **Không nội suy `${{ inputs.* }}` / `${{ github.event.* }}` vào `run:`:** đúng ở cả `deploy.yml` và `notify.yml` (xem Nit 11 về `steps.*`). ✔
- **Ghim action theo SHA:** cả 4 action đều là SHA 40 ký tự và đều đã có trong `ci.yml`. ✔
- **Không `continue-on-error`, không `pull_request_target`.** ✔
- **`packages: write` chỉ ở `images` và `promote`.** ✔
- **`notify.yml` an toàn với `workflow_run` từ PR fork:** `permissions: {}`, không `actions/checkout`, không chạy mã của lượt được báo, mọi giá trị sự kiện đi qua `env:`. ✔
- **Secret không lọt log/bản sao lưu:** không `set -x`; `$MINIO_ROOT_PASSWORD`/`$POSTGRES_*` chỉ giãn **trong** container (chuỗi lệnh ở host chỉ chứa tên biến); khoá ssh ghi ra `$RUNNER_TEMP` kèm `chmod 600` và `trap … rm -f`; bản sao lưu không chứa `appback.env`. ✔
- **Thứ tự `restore.sh`:** SHA-256 (`:47-71`) và kiểm thiếu `BACKUP_AGE_IDENTITY` (`:90-93`) đều đứng trước `stop` đầu tiên (`:107`); `DROP … WITH (FORCE)` trước `pg_restore`. ✔
- **`mc mirror` lúc sao lưu không `--remove`** (`backup.sh:114`); lúc khôi phục **có** `--remove` đúng ý đồ (`restore.sh:127`). ✔
- **Thân tin cảnh báo:** dựng bằng `python3 json.dumps`, `text` == `content`, `curl --fail --max-time 10`, gửi hỏng chỉ `::warning::`/stderr, không làm đỏ lượt chạy. ✔
- **`shellcheck -x`** quét bằng glob lúc chạy trên mọi `.sh` của `deploy/{scripts,backup}` — 0 cảnh báo (trong bước 5 của cổng). ✔

**Test so với [8]:** phủ đủ **mọi** mục prompt đòi, và phủ theo cách khó gian lận — hai
đoạn `run:` của `notify.yml` và đoạn kiểm tag của `rollback` được **trích thẳng từ YAML
rồi chạy bằng `bash` thật** (không chép logic sang Python, không trôi giữa hai nơi);
`deploy.sh`/`restore.sh` chạy thật với `docker` giả và khẳng định **thứ tự** lệnh; regex
tag có case chống command injection. Đây là phần mạnh nhất của nhánh.

## Nghiệm thu chạy thật ([8]) — trạng thái bằng chứng

Prompt [11] bước 2 đòi dán kết quả `drill.sh`, số phản hồi không 2xx, thời gian và kích
thước bản sao lưu. Lúc review, **nghiệm thu đó đang chạy song song** trên worktree tác giả
và chưa có kết quả trong `bao-cao-lop1.md`. Theo K25 phiên này ghi **`chưa chạy`**, không
ghi đạt, và không tính nó vào điểm — nhưng nó vẫn là điều kiện của [11] mà người điều phối
phải chốt trước khi merge, cùng với vòng sửa các finding dưới đây.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 3 | 0,75 |
| CON – Concurrency & dữ liệu | 15 % | 3 | 0,45 |
| LOG – Tính đúng đắn | 15 % | 1 | 0,15 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 4 | 0,40 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 4 | 0,28 |
| OBS, OPS – Vận hành | 5 % | 4 | 0,20 |
| MNT – Bảo trì | 3 % | 3 | 0,09 |
| **Tổng** | **100 %** | | **3,3 / 5** |

## PHÁN QUYẾT: REQUEST CHANGES

Nhánh này làm tốt hơn mức trung bình rõ rệt: cổng xanh thật (tự chạy, mã thoát 0), độ phủ
99,07 % / 97,37 %, và **mọi bất biến nguy hiểm của [9] đều đúng** — migrate chạy trước khi
đổi container, container `api` cũ chỉ bị dừng sau khi bản mới healthy, rollback không hề
đụng `alembic`, `notify.yml` không checkout và không chạy mã của lượt được báo, secret chỉ
giãn bên trong container. Phần test là điểm sáng: các đoạn `run:` của workflow được trích
thẳng từ YAML rồi chạy bằng `bash` thật, nên test không thể trôi khỏi mã thật.

Chặn merge vì **một finding P1 gây mất dữ liệu**, không phải vì chất lượng tổng thể:
`drill.sh:47` xoá `rm -rf "$BACKUP_TARGET"` ở mọi lối thoát, kể cả lối thoát vì sai đối số
xảy ra **trước** khi biến đó được gán thư mục tạm — nên nó xoá giá trị **thừa kế từ môi
trường**. Đã tái hiện được: một lần gõ nhầm đối số trên VPS, với `BACKUP_TARGET` đặt trong
`appback.env` đúng như README §9 hướng dẫn, xoá sạch toàn bộ bản sao lưu. Đúng kịch bản mà
cả prompt B0-10 sinh ra để phòng.

**Phải sửa để được duyệt:**

1. **(P1, bắt buộc)** `deploy/scripts/drill.sh` — khởi tạo `BACKUP_TARGET=""` cạnh
   `SCRATCH=""`/`AGE_DIR=""` (dòng 37–38) để `cleanup()` không bao giờ chạm giá trị thừa kế;
   kèm một test hồi quy gọi `drill.sh` sai đối số với `BACKUP_TARGET` thừa kế và khẳng định
   thư mục còn nguyên.
2. **(P2)** `deploy.yml:184` / `:147` — kiểm `TAG_NAME` bằng đúng regex đang dùng ở `:209`
   trước khi ghép vào lệnh ssh; mở rộng test để khẳng định **mọi** job có `ssh` đều kiểm tag.
3. **(P2)** `restore.sh:123-136` — đưa kiểm `storage` lên ngay sau `:73`, trước mọi lệnh dừng.
4. **(P2)** `deploy.yml:28-30` — `concurrency.group` khoá theo môi trường, kèm test cho cách nhóm.
5. **(P2)** `DEBT.md` — ghi dòng `NO-<nnn>` cho nợ "drill seed hai lần" (chấp nhận, có lý do),
   ghi rõ ba nợ còn lại đã đóng.

Các P3 và Nit (7–12) nên gom vào cùng vòng sửa vì đều là sửa một hai dòng, nhưng không tự
mình chặn merge. Sau vòng sửa, nhánh cần **một lượt `/merge-review` mới** (R-37) cùng với
kết quả nghiệm thu chạy thật của [8].
