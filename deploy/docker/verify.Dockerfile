# Ảnh cổng verify — ENV §2, B0-01 [6]B. Chạy bằng root (mặc định ảnh gốc).
# Không dùng uv/Python/Node của máy Windows: mọi thứ nằm trong ảnh này.

FROM node:20-bookworm-slim AS node

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Node 20 (ảnh uv gốc không có Node — ENV §2)
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# curl, shellcheck (ảnh gốc không có — ENV §2; apt của bookworm-slim đã ghim theo tag ảnh)
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates shellcheck git \
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
