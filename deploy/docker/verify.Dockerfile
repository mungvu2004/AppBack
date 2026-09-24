# Ảnh cổng verify — ENV §2, B0-01 [6]B. Chạy bằng root (mặc định ảnh gốc).
# Không dùng uv/Python/Node của máy Windows: mọi thứ nằm trong ảnh này.

# Ghim tag + digest (NO-175, K29): tag trần trôi theo bản phát hành mới nhất — uv 0.9.30 mới hơn
# đổi cách hiển thị marker trong `uv.lock` một-môi-trường (mọi dòng `{ name = ... }` thêm
# `marker = "platform_machine == 'x86_64' and sys_platform == 'linux'"`), làm `run.sh lock` sinh
# diff hàng trăm dòng dù không gói nào đổi bản — FIX-102. Digest tra bằng
# `docker buildx imagetools inspect <tag>` (không đoán, K7 — haiku hay bịa digest).
FROM node:26-bookworm-slim@sha256:662933cf47f013bc8e4beb31a6116448427a82057ba7c42c97e4c5ba766504c2 AS node
# ^ v26.10.0

FROM ghcr.io/astral-sh/uv:0.9.30-python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58

# Node 26 (ảnh uv gốc không có Node — ENV §2)
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# curl, shellcheck, libatomic1 (ảnh gốc không có — ENV §2; apt của bookworm-slim đã ghim theo tag ảnh;
# libatomic1 vì Node 26 chép sang nền Python thiếu nó, NO-126)
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates shellcheck git libatomic1 \
 && rm -rf /var/lib/apt/lists/*

# gitleaks — phiên bản ghim, kiểm checksum (ENV §2, K không tải mạng lúc verify;
# đây là lúc BUILD ảnh, không phải lúc verify)
ARG GITLEAKS_VERSION=8.30.1
ARG GITLEAKS_SHA256=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
RUN curl -fsSL -o /tmp/gitleaks.tar.gz \
      "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
 && echo "${GITLEAKS_SHA256}  /tmp/gitleaks.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/gitleaks.tar.gz -C /usr/local/bin gitleaks \
 && rm /tmp/gitleaks.tar.gz \
 && gitleaks version

WORKDIR /tmp/w

# tools/verify/in_container.sh chạy từ /src (mount đọc-ghi tại chỗ gọi), làm ba
# việc rồi mới đứng ở /tmp/w — xem BE-01 [6]C.
ENTRYPOINT ["bash", "/src/tools/verify/in_container.sh"]
