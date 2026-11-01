# Review merge perf/perf-11-gate-queue → main

- Ngày: 2026-11-01 · Reviewer: phiên /merge-review (agent độc lập, tác giả không tự chấm) · Commit đầu nhánh: 4034bfe70c5e
- Cổng: phạm vi lượt 1 **đầy đủ** — `bash tools/verify/run.sh verify` mã thoát 0, 8/8 bước đạt (log reviewer
  `.cache/review-verify.log`, log cổng `.cache/src-out/verify/20261101T092709Z-4034bfe70c5e.log`: SHA khớp HEAD; pytest
  9337 đạt trong 806 s; 5b không đơn vị perf bị chạm; bước 7 AppFront @ 7d5368d5 đạt). Lượt này tự xếp hàng sau cổng
  editor3d-dot2: chờ khoá 16:27 → 16:44 rồi vào, đúng thông báo "khoá cổng: chờ các lượt đang chạy xong"; một `hold` của
  phiên khác xếp sau nó
- Độ phủ: tổng dòng 99,41 % · nhánh 97,56 % | `tools` 98,76 % / 96,52 % | tập file bị chạm 100 % / 100 % (diff không có tệp `.py`;
  phần mới là shell, không đo độ phủ — xem finding 1)
- Phạm vi: 1 commit trên `main` 7e630484 (= `origin/main`); 92 dòng thêm / 16 bỏ, trong đó ~60 dòng shell logic (dưới 400).
  Cây sạch; commit đúng mẫu, có `Prompt: PERF-11`; có `changes/PERF-11.md`; không chạm `docs/charter/*`, `openapi.json`,
  `APPFRONT_SHA`, `uv.lock`; không `pragma`, `noqa` trần, `type: ignore`, skip/xfail mới, không hạ ngưỡng.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md`; trọng số chấm theo phán quyết trước
  (`2026-11-01-fix-r5-be-integ.md`).
- Reviewer tự thử `hold` (bản sao đúng khối `hold` của `run.sh`, volume nháp `review-perf11-scratch`, ảnh
  `appback-verify:local`): lệnh `exit 7` → `hold` trả 7; `kill -9` tiến trình `run.sh` đang giữ khoá → container giữ khoá
  tự thoát sau 2 s (`StdinOnce=true`, `AutoRemove=true`), lượt sau vào được; `kill -9` một lượt **đang chờ** → container của
  nó vẫn lấy khoá khi tới lượt rồi thoát ngay (stdin đã đóng), lượt thứ ba vào sau ~0 s, không còn container mồ côi.
  Cửa quay in đúng "có lượt đầy đủ xếp trước — chờ".

## Soát theo câu hỏi của người điều phối

- **`gate_lock.sh`**: mọi lượt lấy cửa quay (fd 6) rồi mới lấy khoá chính (fd 8), nhả cửa quay ngay sau khi có khoá chính;
  không ai giữ fd 8 mà chờ fd 6 → không có vòng chờ chéo. `verify` không `--fast` (cả `--steps`) → `x`; `verify --fast`,
  `shell` → `s`; `lock`/`openapi`/`merge-heads`/`gc` không khoá (như trước). Lượt `x` đang chờ giữ cửa quay nên lượt `s` mới
  không chen được (ưu tiên người ghi). Hệ quả có chủ đích: một `--fast` 1 phút có thể chờ sau hai cổng đầy đủ (~26 phút).
- **`hold`**: khoá nhả cả khi `run.sh` bị `kill -9` (đã thử, xem trên). Ctrl+C: SIGINT tới cả nhóm tiến trình, `run.sh`
  thoát → đóng stdin coproc → như trên. Fd coproc không rò sang lệnh con (bash đặt close-on-exec cho đầu cha), nên lệnh
  host để lại tiến trình nền cũng không giữ khoá.
- **`merge_base`**: `git merge-base HEAD main origin/main` = gốc chung của HEAD với bản gộp giả của hai nhánh, tức gốc mới
  hơn; đúng cả ba ca (main chậm, main vượt chưa đẩy, hai bên rẽ nhánh); không có `origin` → lùi về `main` như cũ.
- **Lượt dùng chung kéo dài**: không có trần thời gian. Một `shell` tương tác bỏ quên chặn cổng đầy đủ, và lượt `x` đang
  chờ đó giữ cửa quay nên chặn luôn mọi `--fast`/`shell` mới trên cả máy — xem finding 3. Phiên Claude chạy `shell < tệp`
  (không TTY) nên ca thực tế chủ yếu là terminal của người dùng.
- **Worktree cũ chưa có `gate_lock.sh`**: không vỡ. Cổng đầy đủ cũ vẫn `flock -x` cùng tệp `/work/gate-full.lock` nên
  loại trừ đúng với lượt `x`/`s` mới, nhưng bỏ qua cửa quay (có thể chen trước lượt `x` mới đang xếp hàng); `--fast`/`shell`
  cũ không khoá nên vẫn chạy cạnh cổng đầy đủ — xem finding 5.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | TEST-01 / R-19 | Hành vi mới không có test tự động: chọn chế độ khoá (`verify` → x, `--steps` → x, `--fast`/`shell` → s), cửa quay, `hold` (mã thoát lệnh, thiếu lệnh → 1, không giữ được khoá → 1), và `merge_base` ba nhánh. `tools/tests/test_run_sh.py` đã có harness docker giả cho từng việc của `run.sh` (`test_shell__build_xong_trước_khi_đọc_stdin`, `test_volume_work_được_tạo_…`), nhưng không thêm ca nào; `changes/PERF-11.md` chỉ ghi thử tay | `tools/verify/gate_lock.sh:12-33`, `tools/verify/run.sh:39-56`, `:76`, `tools/verify/in_container.sh:66-73` | Thêm vào `test_run_sh.py`: `hold -- sh -c 'exit 7'` với docker giả in `held` → mã 7; docker giả không in `held` → 1 + thông báo; `hold` không lệnh → 1. Một test `gate_lock` thật bằng `flock` trên thư mục tạm (ảnh verify có util-linux): `s`+`s` vào cùng lúc, `s` chờ khi `x` giữ, `s` mới chờ sau `x` đang chờ (thay `/work` bằng biến, mặc định `/work`). Một test repo git tạm cho `merge_base` khi `main` chậm hơn `origin/main` |
| 2 | P3 | MNT-04 / R-34 | Charter lệch mã: `ENV.md` §4 vẫn cho "`--steps 1,2,3,4` hay `run.sh shell` pytest đích: **2**, tính cả cổng đầy đủ đang chạy", còn PERF-11 làm `--steps` giữ một mình và `shell` không chạy cạnh cổng đầy đủ. Phần sửa ENV đã bị bỏ khỏi commit (cần `Charter-Approved`) nhưng `changes/PERF-11.md` không ghi nợ này | `docs/charter/ENV.md:70`; `changes/PERF-11.md` | Ghi vào `changes/PERF-11.md` (hoặc sổ nợ đang dùng) một dòng "ENV §4 chờ người dùng duyệt câu chữ", rồi người điều phối sửa ENV kèm `Charter-Approved` |
| 3 | P3 | RES-01 / OBS | Lượt dùng chung không có trần và không lộ danh tính: khi `x` chờ các lượt `s`, thông báo in `gate-full.owner` — chủ **lượt đầy đủ gần nhất**, không phải ai đang giữ khoá dùng chung. Một `shell` tương tác bỏ quên chặn cổng đầy đủ và (qua cửa quay) mọi lượt nhẹ mới, không ai biết container nào | `tools/verify/gate_lock.sh:20-22`, `:30-32` | Lượt `s` ghi `/work/gate-shared/<VERIFY_NAME>-<pid>` (xoá bằng `trap EXIT`, hoặc in danh sách kèm kiểm `docker ps --filter name=appback-verify-`), thông báo của `x` liệt kê các tệp đó; cân nhắc in cảnh báo khi `shell` có TTY |
| 4 | P3 | CON-04 | Gọi lồng tự khoá chết: `run.sh hold -- bash tools/verify/run.sh verify --fast` (hay một script dựng ảnh bên trong gọi `run.sh shell`) — lượt trong chờ `s`/`x` trong khi chính lượt ngoài giữ `x`, treo mãi. Không có chặn hay ghi chú | `tools/verify/run.sh:39-56` | Trong `hold` đặt `export VERIFY_GATE_HELD=1`; `run.sh verify`/`shell` thấy biến thì báo lỗi rõ ("đang trong hold — chạy ngoài hold") thay vì chờ; ghi một dòng trong README |
| 5 | P3 | MNT-04 | Worktree cũ (chưa có `gate_lock.sh`) chỉ được bảo vệ một phần: `--fast`/`shell` cũ không khoá và vẫn chạy cạnh cổng đầy đủ mới, cổng đầy đủ cũ bỏ qua cửa quay. Biện pháp "gộp `main` trước khi chạy cổng" mới nằm ở `F:/App/CLAUDE.md` (ngoài repo), không có trong `tools/verify/README.md`/`CLAUDE.md` của repo | `tools/verify/README.md:6-13` | Thêm một câu vào README: worktree tách trước PERF-11 phải gộp `main` để `--fast`/`shell` xếp hàng |
| 6 | Nit | RES-02 | `hold` không kiểm ảnh: thiếu `appback-verify:local` (máy sạch, sau `docker image prune -a`) thì `docker run` thử kéo từ registry, hỏng, và báo "không giữ được khoá cổng" — sai nguyên nhân | `tools/verify/run.sh:42-50` | `docker image inspect appback-verify:local >/dev/null` trước, thiếu thì báo "chạy `run.sh verify --fast` một lần để dựng ảnh" (hoặc gọi phần build của `run_container`) |
| 7 | Nit | OBS | `run.sh hold` để lại dòng "write /dev/stdout: The pipe is being closed." của docker client khi lượt chờ bị giết rồi lấy khoá (thấy khi thử); vô hại nhưng gây nhiễu log | `tools/verify/run.sh:44` | Có thể bỏ qua, hoặc `2>&1 | grep -v` không đáng; chỉ ghi lại |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 4 | 0,60 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 4 | 0,40 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 3 | 0,21 |
| OBS/OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,53 / 5

## PHÁN QUYẾT: APPROVE

Không P0/P1; cổng đầy đủ mã thoát 0 tại đúng HEAD, độ phủ ≥ 90/90; điểm 4,53 ≥ 4,0. Khoá đọc/ghi + cửa quay đúng thứ tự
lấy khoá, không vòng chờ chéo; `hold` nhả khoá cả khi bị `kill -9` (reviewer đã thử); `merge_base` đúng mọi ca; worktree
cũ không vỡ. Khuyến nghị mạnh làm finding 1 (P2, test cho `hold`/`gate_lock`/`merge_base` trong `test_run_sh.py`) ở nhánh kế
tiếp, và finding 2 (ghi nợ ENV §4 chờ duyệt charter). Các P3/Nit không chặn merge. Ngoài repo: script dựng web f14 trong
`chuoi.sh` vẫn còn vòng chờ RAM trống, cần chuyển sang `run.sh hold --` thì PERF-11 mới gỡ được ca treo đó.
