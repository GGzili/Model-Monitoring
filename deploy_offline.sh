#!/bin/bash
set -e
PKG_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== 加载 Docker 镜像 ==="
sudo docker load -i "$PKG_DIR/images/python3.11-slim.tar"
sudo docker load -i "$PKG_DIR/images/nginx-alpine.tar"

echo "=== 修改 Dockerfile：使用离线 wheels ==="
# 替换 backend Dockerfile，改为离线安装
cat > "$PKG_DIR/backend/Dockerfile" <<'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY wheels/ /wheels/
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# 复制 wheels 到 backend 目录（Dockerfile COPY 需要在 build context 内）
cp -r "$PKG_DIR/wheels" "$PKG_DIR/backend/wheels"

echo "=== 替换前端 Dockerfile：直接用 dist ==="
cat > "$PKG_DIR/frontend/Dockerfile" <<'EOF'
FROM nginx:alpine
COPY dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
EOF

# 复制已构建的 dist
cp -r "$PKG_DIR/frontend_dist/" "$PKG_DIR/frontend/dist/"

echo "=== 创建数据目录 ==="
mkdir -p "$PKG_DIR/data"

echo "=== 启动服务 ==="
cd "$PKG_DIR"
sudo docker compose up -d --build

echo "=== 完成！访问 http://$(hostname -I | awk '{print $1}') ==="
