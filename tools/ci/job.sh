#!/usr/bin/env bash
# tools/ci/job.sh <job> [--no-scan] — lệnh THẬT của mỗi job GitHub Actions (B0-09).
#
# `.github/workflows/ci.yml` chỉ gọi script này; không job nào gõ lệnh cổng trực
# tiếp, để chạy trên runner và trong container verify (`bash tools/verify/run.sh
# shell`) cho cùng kết quả (BE-00 §12, hop-dong.md §2). Ngoại lệ: `build` còn chạy
# được trên máy (Git Bash + Docker Desktop) vì cần build ảnh thật.
#
# Mỗi job là một hàm `job_<tên>`; mỗi bước con gọi `run_step` — trạng thái lấy từ
# MÃ THOÁT THẬT ("đạt"/"hỏng"); bước sau một bước hỏng tự động "chưa chạy" (K25).
# Không `uv sync` ở đây: workflow (hoặc `run.sh`/`in_container.sh`) đã làm; script
# này chỉ gọi `python`/`pytest`/`coverage`/... đang có sẵn trên PATH.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# Prompt [6]: CONTRACT_NODE_DIR mặc định $RUNNER_TEMP/contract-node. `env:` mức job
# trong ci.yml không đặt được biến này (context `runner` chỉ hợp lệ ở mức step,
# actionlint bắt) — job.sh tự mặc định ở đây, vô hại với job không đụng contract.
export CONTRACT_NODE_DIR="${CONTRACT_NODE_DIR:-${RUNNER_TEMP:-/tmp}/contract-node}"

# Đường bind-mount phía host cho `docker run -v`: `pwd` của Git Bash trên Windows in
# ra dạng POSIX (`/c/Users/...`) mà MSYS dịch lại một phần khi nối chuỗi có dấu ":"
# (ENV.md §5) — `pwd -W` (chỉ Git-for-Windows có) cho đường Windows thật, dùng thẳng
# không cần dịch. Trên runner Linux thật, `pwd -W` không tồn tại nên rơi về `pwd`.
_host_pwd() {
  if pwd -W >/dev/null 2>&1; then pwd -W; else pwd; fi
}

# Ghim bằng digest (hop-dong.md, ghi-chu-pins.md — người điều phối đã kiểm lại
# `git ls-remote` / `imagetools inspect`, đè bản sai của khảo sát haiku).
GITLEAKS_IMAGE="zricethezav/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"
TRIVY_IMAGE="aquasec/trivy:0.74.0@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969"
# NO-113: trivy 0.74.0 không ánh xạ CVE của gói `nginx` cài từ kho nginx.org (ảnh `web`, B0-08) —
# CSDL của nó không biết gói này, nên `job_build_trivy web` xanh không chứng minh nginx sạch CVE.
# Bù bằng kiểm `nginx -v` so với bản vá tối thiểu đã tra advisory nginx.org (CVE-2026-42533 vá ở
# 1.30.4; CVE-2026-42945 vá 1.30.1+) — ghim một nơi, cả hai commit FIX-070 và FIX-084 đọc từ đây.
NGINX_MIN_VERSION="1.30.4"
PIP_AUDIT_VERSION="2.10.1"
NET_TIMEOUT_S=300
BUILD_TIMEOUT_S=1800

# ---------------------------------------------------------------------------
# Bảng trạng thái (E.10) — một dòng mỗi bước con, in ra stdout + $GITHUB_STEP_SUMMARY
# ---------------------------------------------------------------------------
STEP_NAMES=()
STEP_STATUS=()
FAILED=0

run_step() {
  local name="$1"
  shift
  if [ "$FAILED" -eq 1 ]; then
    STEP_NAMES+=("$name")
    STEP_STATUS+=("chưa chạy")
    return 0
  fi
  echo "+ $*"
  if "$@"; then
    STEP_NAMES+=("$name")
    STEP_STATUS+=("đạt")
  else
    STEP_NAMES+=("$name")
    STEP_STATUS+=("hỏng")
    FAILED=1
  fi
}

mark_failed() {
  # Bước không chạy được bằng một lệnh đơn (thiếu công cụ) — vẫn một dòng "hỏng",
  # không bỏ qua (K24: không lách cổng bằng cách coi thiếu công cụ là "không áp dụng").
  STEP_NAMES+=("$1")
  STEP_STATUS+=("hỏng")
  FAILED=1
  echo "$1: hỏng — $2" >&2
}

print_table() {
  echo
  printf '%-3s | %-40s | %s\n' "#" "Bước" "Trạng thái"
  printf -- '%s\n' "------------------------------------------------------------------------"
  local i
  for i in "${!STEP_NAMES[@]}"; do
    printf '%-3s | %-40s | %s\n' "$((i + 1))" "${STEP_NAMES[$i]}" "${STEP_STATUS[$i]}"
  done
  echo
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    {
      echo "### job \`$job\`"
      echo
      echo "| # | Bước | Trạng thái |"
      echo "|---|---|---|"
      for i in "${!STEP_NAMES[@]}"; do
        echo "| $((i + 1)) | ${STEP_NAMES[$i]} | ${STEP_STATUS[$i]} |"
      done
    } >>"$GITHUB_STEP_SUMMARY"
  fi
}

# ---------------------------------------------------------------------------
# lint — bước 1, 2, 4; gitleaks; pip-audit (hop-dong.md §2, ghi-chu-cong.md A.7)
# ---------------------------------------------------------------------------

job_lint_gitleaks() {
  # Xanh giả khi không đọc được lịch sử git (worktree Orca: .git là file trỏ
  # đường host, không mount được vào container) — gitleaks không coi "0 commit
  # scanned" là lỗi, tự thoát 0 (/merge-review lượt 1 #8, đo thật: "0 commits
  # scanned … no leaks found"). Chặn TRƯỚC khi quét: không lịch sử thật thì
  # không thể khẳng định "không rò rỉ", phải "hỏng" rõ ràng thay vì im lặng.
  if [ "$(git rev-list --count --all 2>/dev/null || echo 0)" -eq 0 ]; then
    mark_failed "gitleaks" "git rev-list --count --all = 0 — không đọc được lịch sử git thật (worktree/.git hỏng?), không thể quét"
    return
  fi
  # Ảnh verify (container) không có docker CLI, chỉ socket cho Testcontainers —
  # dùng binary gitleaks ghim trên PATH ở đó; runner CI có docker → ảnh ghim digest.
  if command -v docker >/dev/null 2>&1; then
    echo "gitleaks: ảnh Docker ghim digest $GITLEAKS_IMAGE"
    run_step "gitleaks (ảnh, quét cả lịch sử git)" \
      timeout "${NET_TIMEOUT_S}s" docker run --rm -v "$(pwd):/repo" -w /repo \
      "$GITLEAKS_IMAGE" detect --source=. --redact --config=.gitleaks.toml
  elif command -v gitleaks >/dev/null 2>&1; then
    echo "gitleaks: binary trên PATH — $(gitleaks version 2>&1)"
    run_step "gitleaks (binary, quét cả lịch sử git)" \
      timeout "${NET_TIMEOUT_S}s" gitleaks detect --source=. --redact --config=.gitleaks.toml
  else
    mark_failed "gitleaks" "không có docker CLI và không có binary gitleaks trên PATH"
  fi
}

job_lint_pip_audit() {
  # pip-audit thoát 1 khi có BẤT KỲ lỗ hổng nào — kể cả lỗ hổng đã miễn trong
  # audit-allowlist.toml hoặc chưa có bản sửa (đo thật, /merge-review lượt 1
  # #1: jinja2==2.10 → thoát 1 dù có --ignore-vuln). Coi mã 1 là "hỏng" ở đây
  # sẽ không bao giờ để tools.ci.audit chạy tới, làm cơ chế miễn thành mã chết
  # trên runner thật (R-19: sửa gốc, không vá test audit.py riêng). Chỉ coi
  # bước NÀY hỏng khi mã thoát > 1 (lỗi thật của chính pip-audit, vd tham số
  # sai) hoặc JSON rỗng/không ghi được — mã 0 và 1 đều chuyển cho
  # tools.ci.audit tự quyết theo [2]/[6].
  #
  # --no-deps: requirements đã ghim đúng bản (uv export --locked), không cần
  # giải lại cây phụ thuộc; --disable-pip: bỏ bước pip-audit tự nâng cấp
  # pip/wheel/setuptools trong venv tạm của chính nó trước khi audit — bước đó
  # treo trong container verify (đo: timeout ở 120s vẫn chưa xong, mạng tới
  # pypi.org vẫn thông). --vulnerability-service osv: torch/torchvision bản
  # "+cpu" không có trên chỉ mục PyPI mặc định ("Dependency not found on PyPI
  # and could not be audited" — /merge-review #9); OSV tra được theo tên gói +
  # bản mà không cần chỉ mục PyPI. Đo thật (JSON của pip-audit, container
  # verify, /merge-review lượt 1 #9): cả hai đều audit được, không còn
  # "skip_reason" (trước đây None → bỏ qua với thông điệp trên):
  #   torch 2.14.0+cpu: skip_reason=None vulns=0
  #   torchvision 0.29.0+cpu: skip_reason=None vulns=0
  local rc=0
  timeout "${NET_TIMEOUT_S}s" uvx "pip-audit==${PIP_AUDIT_VERSION}" -r /tmp/ci-requirements.txt \
    --no-deps --disable-pip --vulnerability-service osv --format json \
    >/tmp/ci-pip-audit.json 2>/tmp/ci-pip-audit.err || rc=$?
  cat /tmp/ci-pip-audit.err >&2
  if [ "$rc" -gt 1 ]; then
    echo "pip-audit: mã thoát $rc (> 1, lỗi thật — không phải chỉ có lỗ hổng)" >&2
    return 1
  fi
  if [ ! -s /tmp/ci-pip-audit.json ]; then
    echo "pip-audit: JSON rỗng hoặc không ghi được" >&2
    return 1
  fi
  return 0
}

job_lint_audit() {
  # Tách khỏi job_lint (không kèm verify --steps 1,2,4 / gitleaks, cần mạng/lịch
  # sử git thật) để test tự nguồn (`source`) job.sh rồi gọi thẳng hàm này với
  # một `uvx` giả trên PATH — kiểm đúng đường thật mà pip-audit → tools.ci.audit
  # đi qua, không chỉ gọi audit.py riêng (/merge-review lượt 1 #1, test bắt
  # buộc). AUDIT_ALLOWLIST cho phép test trỏ vào allowlist tạm thay vì file
  # thật của repo, không đổi hành vi mặc định khi không đặt biến này.
  #
  # --no-hashes: một dòng override (opencv-python, ENV §3, K29) chỉ có dải bản
  # chứ không ghim — có hash trên các dòng khác sẽ tự bật "--require-hashes"
  # của pip-audit và làm dòng đó hỏng cả lượt audit.
  run_step "uv export (requirements cho pip-audit)" \
    bash -c "uv export --locked --all-packages --no-hashes --format requirements-txt > /tmp/ci-requirements.txt"
  run_step "uvx pip-audit==${PIP_AUDIT_VERSION}" job_lint_pip_audit
  run_step "tools.ci.audit" python -m tools.ci.audit \
    --allowlist "${AUDIT_ALLOWLIST:-tools/ci/audit-allowlist.toml}" --report /tmp/ci-pip-audit.json
}

job_lint() {
  run_step "verify --steps 1,2,4" python -m tools.verify.steps verify --steps 1,2,4
  job_lint_gitleaks
  job_lint_audit
}

# ---------------------------------------------------------------------------
# typecheck — bước 3, 8 ở CHẾ ĐỘ XUẤT (quyết định đã duyệt, hop-dong.md §4)
# ---------------------------------------------------------------------------

job_typecheck() {
  # NO-105: `docs/contracts/openapi.json` là bản tham chiếu ĐÃ COMMIT (khác `openapi.json` gốc,
  # bị `.gitignore`) — bước 8 luôn ở chế độ so sánh trong CI, ép VERIFY_BRANCH=integration bất kể
  # lượt chạy thật là push hay pull_request (quyết định "chế độ xuất" cũ, changes/B0-09.md, đã hết
  # hiệu lực từ khi có bản tham chiếu commit).
  run_step "verify --steps 3,8 (so docs/contracts/openapi.json)" \
    env VERIFY_BRANCH=integration python -m tools.verify.steps verify --steps 3,8
}

# ---------------------------------------------------------------------------
# unit / integration / ml — coverage run pytest --ci-split=<nhóm>
# ---------------------------------------------------------------------------

job_test_group() {
  local group="$1"
  local trace="trace-${group}.jsonl"
  : >"$trace"
  if [ "$group" = "unit" ]; then
    run_step "pytest --collect-only --ci-split=all-check" \
      python -m pytest --collect-only -q --ci-split=all-check
  fi
  if [ "$group" = "integration" ]; then
    # Làm ấm node_modules TRƯỚC pytest: fixture contract_build/appfront_dir sẽ
    # npm ci giữa test nếu chưa có sẵn — tải mạng trong test bị cấm (K, R-29).
    # verify --steps 7 tự thêm bước 0 khi được yêu cầu (_RUNNER_STEPS gồm "5","7"),
    # nhưng integration không gọi --steps 7 — phải gọi --steps 0 riêng
    # (/merge-review lượt 1 #7).
    run_step "verify --steps 0 (làm ấm node_modules)" python -m tools.verify.steps verify --steps 0
    run_step "verify --steps 6 (migrations)" python -m tools.verify.steps verify --steps 6
  fi
  run_step "coverage run pytest --ci-split=${group}" \
    env "CASE_TRACE_FILE=${trace}" \
    coverage run -m pytest "--ci-split=${group}" "--junitxml=junit-${group}.xml"
}

# ---------------------------------------------------------------------------
# contract — Node + AppFront @ SHA; sinh mẫu; bước 7; H2
# ---------------------------------------------------------------------------

job_contract() {
  # CONTRACT_SAMPLES_DIR: nơi fixture `contract_build` ghi mẫu golden. Mặc định
  # dưới RUNNER_TEMP khi chạy tự kiểm ngoài workflow (workflow luôn đặt biến này).
  export CONTRACT_SAMPLES_DIR="${CONTRACT_SAMPLES_DIR:-${RUNNER_TEMP:-/tmp}/contract-samples}"
  mkdir -p "$CONTRACT_SAMPLES_DIR"
  # VERIFY_OUT_DIR (NO-051): `export_contract_samples()` ghi vào đây mỗi khi
  # CONTRACT_SAMPLES_DIR được đặt (vừa xong ở trên) — mặc định của nó `/src-out`
  # chỉ ghi được TRONG container verify; job này chạy `tools.verify.steps` ngoài
  # container (CI thật), nên phải tự trỏ vào một thư mục ghi được.
  export VERIFY_OUT_DIR="${VERIFY_OUT_DIR:-${RUNNER_TEMP:-/tmp}/verify-out}"
  mkdir -p "$VERIFY_OUT_DIR"
  # Làm ấm TRƯỚC pytest — gọi riêng "--steps 0" (không dựa vào "--steps 7" tự
  # thêm bước 0): bước pytest sinh mẫu chạy TRƯỚC "--steps 7" trong hàm này,
  # nên bước 0 tự thêm ở đó vẫn tới sau khi pytest đã tải mạng giữa test rồi
  # (/merge-review lượt 1 #7).
  run_step "verify --steps 0 (làm ấm node_modules)" python -m tools.verify.steps verify --steps 0
  run_step "pytest --ci-split=unit,integration (sinh mẫu)" \
    python -m pytest --ci-split=unit,integration
  run_step "verify --steps 7 (H1 H3 H4 H5)" python -m tools.verify.steps verify --steps 7
  run_step "tools.ci.h2" python -m tools.ci.h2
}

# ---------------------------------------------------------------------------
# commits — Conventional Commits, tên nhánh, trailer Prompt:
# ---------------------------------------------------------------------------

job_commits() {
  run_step "tools.ci.commits" python -m tools.ci.commits
}

# ---------------------------------------------------------------------------
# coverage — needs: [unit, integration, ml]; gộp junit/vết → coverage_gate → 5b
# ---------------------------------------------------------------------------

job_coverage() {
  local trace_out="${RUNNER_TEMP:-/tmp}/ci-case-trace.jsonl"
  run_step "tools.ci.merge_artifacts" python -m tools.ci.merge_artifacts \
    --root artifacts --jobs unit,integration,ml \
    --junit-out /tmp/junit.xml --trace-out "$trace_out"
  run_step "coverage combine" coverage combine artifacts/*/
  run_step "coverage json" coverage json
  run_step "tools.coverage_gate (VERIFY_BRANCH=integration)" \
    env VERIFY_BRANCH=integration python -m tools.coverage_gate
  # Bước 5b đứng riêng (không kèm 5): case_gate đọc thẳng /tmp/junit.xml +
  # /tmp/junit-perf.xml đã có sẵn từ merge_artifacts — hop-dong.md §3, xác nhận
  # bằng steps.py:253-272 (`wanted` chỉ chạy số có trong tập, không tự thêm "5").
  run_step "verify --steps 5b (case_gate, vết gộp)" \
    env VERIFY_BRANCH=integration "CASE_TRACE_FILE=${trace_out}" \
    python -m tools.verify.steps verify --steps 5b
}

# ---------------------------------------------------------------------------
# build — dọn đĩa; build 4 ảnh; import_all trong ảnh; trivy; smoke compose
# ---------------------------------------------------------------------------

job_build_clean_runner_disk() {
  if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
    run_step "dọn đĩa runner (SDK không dùng)" bash -c '
      sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc \
        /opt/hostedtoolcache/CodeQL "$AGENT_TOOLSDIRECTORY" 2>/dev/null || true'
  fi
}

job_build_one_image() {
  local img="$1"
  shift
  local scope="appback-${img}"
  if [ -n "${ACTIONS_RUNTIME_TOKEN:-}" ]; then
    run_step "docker build ${img} (cache gha)" timeout "${BUILD_TIMEOUT_S}s" docker buildx build \
      --cache-from "type=gha,scope=${scope}" --cache-to "type=gha,mode=max,scope=${scope}" \
      --load -t "appback-${img}:ci" -f "deploy/docker/${img}.Dockerfile" "$@" .
  else
    run_step "docker build ${img}" timeout "${BUILD_TIMEOUT_S}s" \
      docker build -t "appback-${img}:ci" -f "deploy/docker/${img}.Dockerfile" "$@" .
  fi
  docker builder prune -f >/dev/null 2>&1 || true
}

job_build_import_all() {
  local app="$1"
  # Mọi service thật (deploy/compose/ci.yml, qua extends base.yml) luôn nhận đủ
  # env khi chạy — đọc settings lúc nhập là fail-fast hợp lệ của packages.messaging,
  # không phải lỗi. import_all không có env nào sẽ ăn nhầm lỗi đó thay vì lỗi
  # thiếu thư viện thật mà case [8] cần bắt. Nạp deploy/compose/env.example (mẫu
  # giá trị an toàn, cùng đúng tên biến ci.yml dùng qua base.yml) để mô phỏng
  # đúng env runtime thật — `docker run --env-file` đọc cùng cú pháp KEY=VALUE,
  # bỏ dòng trống/`#` như compose.
  run_step "import_all ${app} (trong ảnh, env như service thật)" timeout "${NET_TIMEOUT_S}s" docker run --rm \
    --entrypoint python --env-file deploy/compose/env.example \
    -v "$(_host_pwd)/tools:/opt/ci/tools:ro" \
    -e "PYTHONPATH=/app:/opt/ci" -w /app \
    "appback-${app}:ci" -m tools.ci.import_all "$app"
}

job_build_trivy() {
  local img="$1"
  # SARIF ghi trong container --rm mà không mount thì mất khi container xoá
  # (/merge-review lượt 1 #3, đo thật: log build đỏ không còn CVE nào để tra).
  # Mount thư mục host thật để SARIF sống sau khi container thoát; ci.yml tải
  # nó lên artifact ở job build (upload-artifact, if: always() mức step — [9]
  # chỉ cấm always() mức JOB, không cấm bước upload trong một job).
  local trivy_dir
  if [ -n "${RUNNER_TEMP:-}" ]; then
    # Runner CI thật: RUNNER_TEMP là đường Linux tuyệt đối, dùng thẳng.
    trivy_dir="${RUNNER_TEMP}/trivy"
    mkdir -p "$trivy_dir"
  else
    # Máy cục bộ: tạo bằng đường tương đối bình thường rồi mới đổi sang dạng
    # Windows (_host_pwd) cho riêng đối số -v — mkdir không cần đoán MSYS dịch
    # /tmp ra sao.
    mkdir -p .cache/trivy
    trivy_dir="$(_host_pwd)/.cache/trivy"
  fi
  run_step "trivy image ${img}" timeout "${NET_TIMEOUT_S}s" docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "${trivy_dir}:/out" \
    "$TRIVY_IMAGE" image --severity CRITICAL --ignore-unfixed --exit-code 1 \
    --format sarif --output "/out/trivy-${img}.sarif" "appback-${img}:ci"
}

job_build_check_nginx_version() {
  # `nginx -v` in ra stderr ("nginx version: nginx/1.30.4"); không build ảnh thật ở test — test
  # nguồn hàm này với `docker` giả trên PATH (kiểu test pip-audit ở job_lint_pip_audit).
  local actual
  actual="$(docker run --rm --entrypoint nginx appback-web:ci -v 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1)"
  [ -n "$actual" ] || return 1
  printf '%s\n%s\n' "$NGINX_MIN_VERSION" "$actual" | sort -C -V
}

job_build_smoke() {
  local project="appback-ci-job"
  # Chỉ ci.yml (không base.yml): mỗi service trong ci.yml tự `extends: file:
  # base.yml` đúng service nó cần (B0-08 đã kiểm — bao-cao-c2.md — `docker
  # compose -f ci.yml config -q` exit 0). Gộp thêm base.yml đưa nguyên các
  # service "gốc" của base.yml (kể cả ml-gpu, chỉ tồn tại để extends, không có
  # image/build riêng) vào project, làm compose hỏng ngay ở bước cấu hình.
  local compose_files=(--env-file deploy/compose/env.example -f deploy/compose/ci.yml)
  cleanup() {
    docker compose -p "$project" "${compose_files[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  }
  trap cleanup EXIT
  export IMAGE_TAG="ci"
  export WEB_HTTP_PORT="${WEB_HTTP_PORT:-18080}"
  export POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-15432}"
  export PUBLIC_BASE_URL="http://127.0.0.1:${WEB_HTTP_PORT}"
  run_step "compose up --wait" timeout "${NET_TIMEOUT_S}s" \
    docker compose -p "$project" "${compose_files[@]}" up -d --wait
  # NO-118: `api` không còn cổng host riêng (`deploy/compose/ci.yml`) — qua nginx của `web`, proxy
  # `/api/` sang `api:8000` (đúng đường request thật, không tắt qua sau lưng nginx).
  run_step "smoke /api/health" curl -fsS --max-time 5 "http://127.0.0.1:${WEB_HTTP_PORT}/api/health"
  run_step "smoke /api/ready" curl -fsS --max-time 5 "http://127.0.0.1:${WEB_HTTP_PORT}/api/ready"
  run_step "smoke /" curl -fsS --max-time 5 "http://127.0.0.1:${WEB_HTTP_PORT}/"
  # -o vào file tạm thật, không /dev/null: đo được trên Git Bash (Windows) — ghi
  # thân nhị phân (~14 KB) vào /dev/null làm curl thoát 23 "client returned ERROR
  # on write" dù HTTP 200 thật (ghi vào file thường thì đạt) — quirk của MSYS,
  # không phải lỗi server; file thường chạy đúng trên cả Linux lẫn Git Bash.
  local draco_tmp
  draco_tmp="$(mktemp)"
  run_step "smoke /draco/draco_decoder.wasm" \
    curl -fsS --max-time 5 -o "$draco_tmp" "http://127.0.0.1:${WEB_HTTP_PORT}/draco/draco_decoder.wasm"
  rm -f "$draco_tmp"
  cleanup
  trap - EXIT
}

job_build() {
  job_build_clean_runner_disk
  job_build_one_image api
  job_build_one_image worker
  job_build_one_image ml --build-arg ML_VARIANT=cpu

  local web_ctx=".cache/ci-appfront-web-context"
  rm -rf "$web_ctx"
  local sha
  sha="$(tr -d '[:space:]' <tools/contract/APPFRONT_SHA)"
  run_step "web-context.sh (AppFront @ ${sha})" bash deploy/docker/web-context.sh "$sha" "$web_ctx"
  job_build_one_image web --build-context "appfront=${web_ctx}" --build-arg "APPFRONT_SHA=${sha}"
  run_step "nginx -v >= ${NGINX_MIN_VERSION} (NO-113)" job_build_check_nginx_version

  job_build_import_all api
  job_build_import_all worker
  job_build_import_all ml

  if [ "$no_scan" -eq 0 ]; then
    job_build_trivy api
    job_build_trivy worker
    job_build_trivy ml
    job_build_trivy web
  fi

  job_build_smoke
}

# ---------------------------------------------------------------------------
# Điều phối
# ---------------------------------------------------------------------------

main() {
  job="${1:-}"
  shift || true
  no_scan=0
  for arg in "$@"; do
    case "$arg" in
      --no-scan) no_scan=1 ;;
      *) echo "job.sh: cờ lạ '$arg'" >&2; exit 2 ;;
    esac
  done

  case "$job" in
    lint) job_lint ;;
    typecheck) job_typecheck ;;
    unit) job_test_group unit ;;
    integration) job_test_group integration ;;
    ml) job_test_group ml ;;
    contract) job_contract ;;
    build) job_build ;;
    commits) job_commits ;;
    coverage) job_coverage ;;
    *)
      echo "usage: tools/ci/job.sh <lint|typecheck|unit|integration|ml|contract|build|commits|coverage> [--no-scan]" >&2
      exit 2
      ;;
  esac

  print_table
  [ "$FAILED" -eq 0 ]
}

# Sourceable cho test (/merge-review lượt 1 #1, "test bắt buộc đi qua đúng
# đường job.sh"): nguồn file này (`source tools/ci/job.sh`) không tự chạy job
# nào — định nghĩa xong hàm thì dừng, để test gọi thẳng một hàm (vd
# job_lint_audit) với `uvx` giả trên PATH rồi tự đọc $FAILED. Chạy trực tiếp
# (`bash tools/ci/job.sh <job>`, cách CI/người dùng vẫn gọi) không đổi hành vi.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
