# 联网环境：直接 build 即可。
# 内网/离线：勿单独用本文件构建（pip 会访问 pypi.org）。请用仓库根目录 ./deploy_offline.sh，
# 或确保 Dockerfile 使用 pip install --no-index --find-links=/wheels 且 context 内含 wheels/。
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
