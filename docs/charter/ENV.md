# ENV — Môi trường chạy đã đo

> **Bản 4 · 2026-09-18** (phân xử phần 7) · số đo gốc: `docs/backend/03-moi-truong.md`. Thay đổi so với bản 3:
> - §4: lượt verify tích hợp của người điều phối cũng tính vào giới hạn (N-3);
> - §5: chỉ giao spec qua Git Bash (PowerShell 5.1 hỏng khứ hồi, đo ở phần 6); prompt lưu LF thuần (Q-10);
> - kết quả chạy khô Orca (Q-7) ghi vào §5 khi chạy (`00-SO-TRA.md` §6.1 mục 3b).
>
> **Bản 3 · 2026-09-17** (tranh luận phần 3 chặng 3):
> - máy **không có `just`**: lệnh thật là `bash tools/verify/run.sh <việc>`;
> - `git archive` phải tắt `core.autocrlf` (đã đo: bật thì SHA-256 lệch);
> - ảnh verify có `curl`, `shellcheck`, `gitleaks`; container chạy root;
> - biến `CONTRACT_SAMPLES_DIR`, `APPFRONT_DIR`, `CONTRACT_NODE_DIR`; mạng `bridge`; cache mypy trong volume; `run.sh gc`.
>
> **Bản 2:** thêm Node 20, AppFront xuất bằng `git archive`, `VERIFY_TOUCHED`, volume; N phải đo lại ở M1. Người điều phối cập nhật lại sau M1.

## 1. Máy thực thi

- Windows 11, 12 luồng CPU, 23,7 GB RAM, GPU RTX 4050 Laptop 6 GB.
- Docker Desktop 29.6.1 trên WSL2: VM 12 CPU, 11,5 GB RAM. **GPU vào được container** (`--gpus all`).
- Worktree Orca nằm ở `C:\Users\mxuan\orca\workspaces\…`, ổ `C:` còn 127 GB.
- Kho pnpm ở `F:\.pnpm-store`, khác ổ với worktree → mỗi worktree FE chép `node_modules` (~434 MB).
- **Không có `just`, không có uv dùng được** (uv máy 0.4.18 quá cũ). Git cấu hình hệ thống `core.autocrlf=true`.
- `F:\AppBack` do người điều phối `git init -b main` (một commit rỗng trên `main`) trước W00. Máy đặt `init.defaultBranch=master`: thiếu `-b main` thì ra `master` (kiểm áp phần 7, K7-7).

## 2. Chạy `just verify` (AppBack)

**Lệnh thật trên máy Windows:** `bash tools/verify/run.sh verify` (Git Bash). `justfile` chỉ là bí danh cho Linux/CI.

**Trên máy chủ, trước khi gọi container:**
1. `VERIFY_BRANCH=integration|worker` (nhánh `main` là `integration`).
2. `VERIFY_CHANGED` = file đổi so với `git merge-base HEAD main`, cộng file chưa commit. Git chạy trên máy chủ, vì file `.git` của worktree Orca là **file** trỏ `gitdir: F:/AppBack/.git/worktrees/<tên>` (đường Windows), container không đọc được.
3. Xuất AppFront @ `tools/contract/APPFRONT_SHA` bằng `git -c core.autocrlf=false -c core.eol=lf -C F:/AppFront archive <sha> src package.json` vào `${APPBACK_CACHE:-$HOME/.cache/appback}/appfront/<sha>` (giải vào thư mục tạm rồi `mv`). Chưa có file SHA → mount một thư mục rỗng.
4. `VERIFY_NAME` chuẩn hoá về `[a-z0-9_-]` (tên project compose đòi chữ thường).

**Container:**
- **Ảnh:** `deploy/docker/verify.Dockerfile`, dựa trên `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`, chép Node 20 từ `node:20-bookworm-slim`, cài thêm `curl`, `shellcheck`, `gitleaks` (bản ghim). Ảnh gốc **không** có curl, git, docker CLI, shellcheck (đã đo). **Chạy bằng root.** Không dùng uv, Python hay Node của máy.
- **Mount:**

| Nguồn | Đích | Chế độ |
|---|---|---|
| worktree | `/src` | chỉ đọc |
| đệm AppFront @ SHA | `/appfront` | chỉ đọc |
| `contract-samples/` của worktree | `/src-out/contract-samples` | đọc-ghi (chỉ nhận bản chép cuối lượt) |
| `/var/run/docker.sock` | `/var/run/docker.sock` | đọc-ghi |
| volume `appback-work` | `/work` (`UV_CACHE_DIR=/work/uv-cache`, `UV_PROJECT_ENVIRONMENT=/work/venv-<VERIFY_NAME>`, `MYPY_CACHE_DIR=/work/mypy-<VERIFY_NAME>`, `CONTRACT_NODE_DIR=/work/contract-node`) | đọc-ghi |

- **Mạng:** `network_mode: bridge` (không tạo mạng riêng mỗi project; bể địa chỉ mặc định chỉ khoảng 30 mạng); `extra_hosts: host.docker.internal:host-gateway`.
- **Bước đầu của script:** `cp -r /src /tmp/w && find /tmp/w -type f -exec chmod 644 {} +`. Mount từ Windows làm mọi file mode 777, và ruff báo `EXE002` giả. Hiến chương cấm shebang trong `.py`, nên chmod 644 không sinh `EXE001`.
- **Biến môi trường:** `UV_LINK_MODE=hardlink`; `RUFF_CACHE_DIR`, `COVERAGE_FILE` trỏ vào `/tmp`; `TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal`; `APPFRONT_DIR=/appfront`; `CONTRACT_SAMPLES_DIR=/tmp/contract-samples` (mới mỗi lượt, cuối lượt chép ra `/src-out/contract-samples`).
- **Đồng bộ phụ thuộc:** `uv sync --locked --all-packages --group dev`; lock lệch pyproject thì hỏng. Mọi lệnh sau chạy bằng Python của venv.
- **Dọn:** `bash tools/verify/run.sh gc` xoá `venv-*`/`mypy-*` của worktree không còn tồn tại (mỗi venv ~1,3 GB).
- **Thời gian tham chiếu** (dự án mẫu chỉ có Postgres): 15–18 s một lượt; 3 lượt song song hết 21 s; 6 lượt song song hết 41 s.

## 3. ML

- Venv ML (torch CPU + onnxruntime + OpenCV headless + scikit-image + pypdfium2 + RapidOCR) nặng **1,3 GB**; cài từ kho ấm mất **2 s**.
- `rapidocr-onnxruntime` kéo `opencv-python` bản GUI, làm hỏng `import cv2` trong ảnh slim. Trong workspace dùng `override-dependencies` để loại nó (BE-00 §13.1); cài tay thì `--no-deps`.
- `ultralytics` kéo `torchvision`: khai trực tiếp `torchvision` từ chỉ mục `pytorch-cpu` để khớp torch CPU.
- **OCR mất dấu tiếng Việt** (`PHONG NGU 1`). Số đọc đúng, tin cậy 1,00. Mỗi ảnh ~0,9 s trên CPU.
- **Không cài PaddlePaddle.** paddle2onnx chuyển được mô hình Latin nhưng kết quả không tốt hơn.
- **GPU:** chỉ một tác vụ GPU mỗi lúc (khoá GPU). Test `@pytest.mark.gpu` không chạy trong `just verify`.

## 4. Giới hạn chạy song song cho người điều phối

| Loại lượt | Tối đa cùng lúc |
|---|---|
| `just verify` AppBack | **4** (tạm; đo lại ở M1 với đủ Postgres, 2 Redis, MinIO, Mailpit) |
| `pnpm verify` AppFront (~300 s một lượt, dùng hết CPU) | **2** |
| Tổng cả hai loại | **4** |
| Tác vụ GPU | **1** |

Đợt nào có nhiều prompt hơn giới hạn thì prompt còn lại **chờ trong hàng**. Không mở thêm worker vượt giới hạn.

Lượt verify **tích hợp** của người điều phối (sau mỗi lần hợp nhất) cũng tính vào giới hạn trên (phân xử phần 7, N-3).

## 5. Giao spec cho Orca

- `orca` là file `.exe` của Windows, gọi từ **Git Bash**: `MSYS_NO_PATHCONV=1 orca orchestration worker-start --spec "$(cat <file prompt>)" …`.
- **Luôn đặt `MSYS_NO_PATHCONV=1`**, cho cả `orca` lẫn mọi `docker run` có tham số đường. Không có nó, MSYS đổi tham số bắt đầu bằng `/` hoặc `KHOÁ=/…` thành `C:/Program Files/Git/…`. Đã đo: hỏng ở 2/3 mẫu; có biến này thì đạt 3/3.
- `$(cat …)` bỏ các dòng trống ở cuối file. `kiem_bo_prompt.py` so khứ hồi theo đúng cách gọi này.
- **Chỉ giao spec qua Git Bash.** PowerShell 5.1 giữ nguyên spec ở các mẫu đo đầu, nhưng hỏng khứ hồi với prompt có dấu nháy kép thẳng (lint báo NHẮC "khứ hồi PowerShell", phần 6).
- Prompt phải lưu **LF thuần**: `$(cat …)` giữ nguyên byte CR; `kiem_bo_prompt.py` báo LỖI khi có CR (phần 7).

## 6. Tiền đề trước khi chạy Orca

| Trước | Việc | Ai |
|---|---|---|
| W00 | commit `docs/backend/` vào `master` của AppFront (B0-01 chép hiến chương từ đó) | người điều phối, sau khi người dùng đồng ý |
| W00 | `git init -b main F:/AppBack` + commit rỗng trên `main`; khai repo với Orca (`00-SO-TRA.md` §6.1 mục 2) | người điều phối |
| W05 | AppFront public trên GitHub có SHA ghim (job `contract` của CI checkout nó) | người điều phối kiểm |
| lần CI đầu | đẩy AppBack lên GitHub | **hỏi người dùng** (việc ra bên ngoài) |
