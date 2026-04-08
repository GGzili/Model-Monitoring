#!/bin/bash
set -e
PKG_DIR="$(cd "$(dirname "$0")" && pwd)"

# 构建上下文必须是 dist_package/backend/main.py 与 Dockerfile 同级。
# 若误打成 backend/backend/main.py，镜像里会出现 /app/main.py（旧）与 /app/backend/main.py（新），
# uvicorn main:app 仍加载 /app/main.py，导致 /api/dashboard 仍返回 host/ssh 等字段。
if [ ! -f "$PKG_DIR/backend/main.py" ] && [ -f "$PKG_DIR/backend/backend/main.py" ]; then
    echo "=== 错误：源码多包了一层 backend/backend/，与 Dockerfile 不同级 ==="
    echo "请在本机 dist_package/backend 下合并目录后再执行本脚本，例如："
    echo "  cd \"$PKG_DIR/backend\" && cp -r backend/* . && rm -rf backend"
    echo "（勿删除 wheels/；合并后应存在: $PKG_DIR/backend/main.py）"
    exit 1
fi
if [ ! -f "$PKG_DIR/backend/main.py" ]; then
    echo "=== 错误：未找到 $PKG_DIR/backend/main.py，无法构建后端 ==="
    exit 1
fi

if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
else
    DC="docker-compose"
fi

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

# 复制已构建的 dist（先删旧目录，避免旧 assets 残留进镜像）
rm -rf "$PKG_DIR/frontend/dist"
cp -r "$PKG_DIR/frontend_dist" "$PKG_DIR/frontend/dist"

echo "=== 创建数据目录 ==="
mkdir -p "$PKG_DIR/data"
if [ -d "$PKG_DIR/scripts" ]; then
    echo "=== 运维脚本: $PKG_DIR/scripts/（如 check_ssh_ports.py，见 scripts/README.md）==="
fi

echo "=== 构建镜像（后端 + 前端均 --no-cache；此前若只 build backend，前端会一直用旧 JS）==="
cd "$PKG_DIR"
sudo $DC build --no-cache backend
sudo $DC build --no-cache frontend
sudo $DC up -d

echo "=== 完成！访问 http://$(hostname -I | awk '{print $1}') ==="
