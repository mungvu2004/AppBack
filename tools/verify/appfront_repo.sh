# Nguồn (source) cho run.sh và deploy/docker/web-context.sh — NO-325.
# Repo AppFront nằm cạnh checkout chính của AppBack (`F:/App/AppBack` ↔ `F:/App/AppFront`), kể cả khi
# đang đứng trong worktree phụ ở nơi khác: lấy từ `--git-common-dir` (luôn là `<checkout chính>/.git`),
# không từ vị trí worktree. Đường in ra ở dạng git của máy (mixed `F:/...` trên Windows), dùng được cho `git -C`.

# appfront_repo_default <thư mục trong repo AppBack> — in đường repo AppFront mặc định.
appfront_repo_default() {
  local common_dir
  # `cd` chứ không `git -C`: MSYS_NO_PATHCONV=1 (run.sh) giữ đường `/f/...` mà git Windows không hiểu (NO-205).
  common_dir="$(cd "$1" && git rev-parse --path-format=absolute --git-common-dir)"
  printf '%s/AppFront\n' "$(dirname "$(dirname "$common_dir")")"
}
