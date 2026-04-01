# 模型监测平台

面向多台服务器上 **LLM 推理服务** 的轻量运维工具：健康探测、仪表盘、SSH 远程重启，以及可选的 **OpenAI 兼容网关**（按模型限并发与排队，缓解 tokenizer 等串行瓶颈导致的假死）。

**Model Monitor** — health checks, dashboard, Docker-based remote restart, and an optional gated `/v1` proxy for OpenAI-compatible clients.

**仓库：** [https://github.com/GGzili/Model-Monitoring](https://github.com/GGzili/Model-Monitoring)

---

## 功能概览

| 能力 | 说明 |
|------|------|
| 定时探测 | 对 `http://{host}:{port}/v1/chat/completions` 发送极简推理请求（`max_tokens: 1`），记录延迟与状态 |
| 仪表盘 | 卡片展示各模型最近状态、延迟、检测时间；支持复制「网关调用名」（不展示 IP/容器等敏感连接信息） |
| 立即检测 | 手动触发单次探测 |
| 远程重启 | SSH（密码 + `sudo`）执行 `docker restart` 与容器内启动命令 |
| 双机 | 两台服务器上并发执行同一套重启流程 |
| 历史 | 延迟折线图与检测记录 |
| 配置 | 模型 CRUD，SQLite 持久化；敏感文本字段可选 **Fernet 加密落库** |
| **网关** | `POST /v1/chat/completions`、`GET /v1/models`；每模型独立 **最大并发** 与 **消息队列容量**；需「监测启用」且「开放网关」 |

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11、FastAPI、APScheduler、httpx、Paramiko、cryptography（Fernet） |
| 前端 | Vue 3、Element Plus、ECharts |
| 存储 | SQLite |
| 部署 | Docker Compose；Nginx 反代 `/api` 与 `/v1` |

---

## 快速开始（监控机可联网）

```bash
git clone https://github.com/GGzili/Model-Monitoring.git model-monitor
cd model-monitor
docker compose up -d --build
```

- 前端：<http://localhost:4444>（或 `<监控机IP>:4444`）
- 后端 API：<http://localhost:3333>（或 `:3333`）

数据文件默认挂载为项目下的 `./data/monitor.db`。

---

## 环境变量（后端）

| 变量 | 默认 | 说明 |
|------|------|------|
| `DB_PATH` | `/data/monitor.db` | 数据库路径（容器内） |
| `MONITOR_FERNET_KEY` | 空 | 设置后，名称/host/容器/命令/SSH 等 **文本字段** 以 Fernet 加密写入 SQLite；**须备份密钥**，与库文件一致才能解密 |
| `GATEWAY_UPSTREAM_TIMEOUT` | `600` | 网关转发上游超时（秒） |

生成密钥：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`docker-compose.yml` 已预留 `MONITOR_FERNET_KEY=${MONITOR_FERNET_KEY:-}`，可在项目根目录 `.env` 中配置。

端口（`port` / `port_b` / `ssh_port`）仍为整型明文列；未设置密钥时敏感文本以明文写入（启动会打日志警告）。

---

## 目录结构

```
model-monitor/
├── backend/
│   ├── main.py           # FastAPI 入口与路由
│   ├── gateway.py        # OpenAI 兼容网关（/v1）
│   ├── database.py       # SQLite、加解密与对外 API 字典
│   ├── field_crypto.py   # Fernet 字段加密（可选）
│   ├── models.py         # Pydantic
│   ├── checker.py        # 健康探测
│   ├── scheduler.py      # 定时任务
│   ├── restart.py        # SSH 重启
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ModelFormAdd.vue   # 添加模型（完整表单）
│   │   │   └── ModelFormEdit.vue  # 调整运行参数（仅网关与队列）
│   │   └── ...
│   ├── nginx.conf        # /api、/v1 反代到后端
│   └── Dockerfile
├── scripts/              # 参考与网关压测（见 scripts/README.md）
├── docker-compose.yml
├── pack.ps1 / pack.bat   # Windows 离线打包
├── deploy_offline.sh     # Linux 内网部署（会重建后端 + 前端镜像）
└── LICENSE               # MIT
```

---

## 网关（OpenAI 兼容）

客户端将原先生到模型推理地址的请求，改为打到监控站：

- **URL**：`http://<监控机>:4444/v1/chat/completions`（与页面同域，经 Nginx）
- **请求体 `model`**：须与界面中的 **网关调用名** 一致（「API 模型名」非空则用其值，否则用「名称」）
- **前提**：该模型在配置中 **启用监测** 且 **开放网关**

每模型可配置 **最大并发** 与 **消息队列容量**（满则 `503`；`0` 表示不限制排队长度）。双机模型网关当前仅使用 **主节点 A** 的 `host:port`。

压测脚本：`scripts/test_gateway_limit.py`（宿主机需 `httpx`，见 `scripts/requirements-test.txt`）。

---

## 离线打包与内网部署

### Windows：生成 `dist_package/`

需本机安装 **Python、Node.js**；Docker 用于导出基础镜像（可用 `-SkipDockerPull` / `-SkipDockerSave`，见脚本头注释）。

在**仓库根目录**执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
cd model-monitor
.\pack.ps1
# 或双击 / 调用 pack.bat（参数相同）
# 本机已有 python:3.11-slim / nginx:alpine：.\pack.ps1 -SkipDockerPull
# 已放入 dist_package\images\*.tar：.\pack.ps1 -SkipDockerSave
```

**`pack.ps1` 已包含完整前端流程，无需再手动 `npm run build`：**

1. 在 `frontend\` 执行 `npm install` + `npm run build`
2. 清空并更新 **`dist_package\frontend_dist\`**（与 `frontend\dist\` 一致，避免旧 chunk 残留）

产物还包含 `wheels/`、`images/*.tar`、`backend/`、`frontend/`（源码）、`docker-compose.yml`、`deploy_offline.sh` 等。将 **`dist_package` 打成 zip**（勿提交 zip 到 Git，见 `.gitignore`）拷到内网。

### Linux 监控机：部署

**不要**在服务器上运行 `pack.ps1`。解压后：

```bash
unzip dist_package.zip
cd dist_package
chmod +x deploy_offline.sh
./deploy_offline.sh
```

脚本会：`docker load` 基础镜像、改写后端 Dockerfile 使用离线 `wheels`、**清空并复制 `frontend_dist` → `frontend/dist`**，然后：

- **`docker compose build --no-cache backend`**
- **`docker compose build --no-cache frontend`**（务必执行；仅重建后端会导致前端仍是旧 JS）
- **`docker compose up -d`**

若只有旧版 `docker-compose` 命令：

```bash
sed -i 's/docker compose/docker-compose/g' deploy_offline.sh
./deploy_offline.sh
```

### 离线包目录：`backend/main.py` 须与 Dockerfile 同级

若错误打成 `dist_package/backend/backend/main.py`，镜像内会出现 `/app/main.py`（旧）与 `/app/backend/main.py`（新），`uvicorn main:app` 仍加载旧入口。脚本会在检测到该结构时退出并提示合并目录。

### 升级与缓存

- 升级时建议保留 **`data/monitor.db`** 并备份 **`MONITOR_FERNET_KEY`**（若启用加密）。
- 部署后界面异常：浏览器 **Ctrl+F5**；确认 **`deploy_offline.sh` 已重建 frontend 镜像**。

---

## 配置说明（添加 / 编辑模型）

| 阶段 | 说明 |
|------|------|
| **首次添加** | 填写 API 模型名、显示名、主/备机、容器与启动命令、SSH、网关与检测等；连接信息写入后 **不可** 通过管理 API 修改 |
| **界面「调整运行参数」**（编辑按钮） | **仅** 开放网关、最大并发、消息队列容量（独立 `ModelFormEdit` 组件，无其它表单项） |
| **`PUT /api/models/{id}`** | 仍仅接受：`interval`、`enabled`、`gateway_enabled`、`gateway_max_concurrent`、`gateway_max_queue`（界面编辑当前只提交网关三项，间隔与启用可通过 API 修改） |

列表/详情/仪表盘等 JSON **不返回** `host`、`port`、`container`、启动命令、SSH；仅返回 `is_dual` 等公开字段。

---

## 重启流程

1. SSH 连接目标机  
2. `sudo docker restart <容器名>`  
3. `sudo docker exec -d <容器名> bash -c "<容器内启动命令>"`  

双机时对 A、B 并发执行上述步骤。

---

## HTTP API

### 管理接口（前缀 `/api`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dashboard` | 仪表盘汇总（公开字段 + `last_*`） |
| GET | `/api/models` | 模型列表（公开字段） |
| POST | `/api/models` | 创建 |
| PUT | `/api/models/{id}` | 仅更新可调字段（见上表） |
| DELETE | `/api/models/{id}` | 删除 |
| POST | `/api/models/{id}/check` | 立即检测 |
| POST | `/api/models/{id}/restart` | 重启 |
| GET | `/api/models/{id}/history` | 历史记录 |

### 网关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/models` | 列出已开放网关的模型 |
| POST | `/v1/chat/completions` | 排队限流后转发到上游 |

---

## 安全提示

- **加密 ≠ 鉴权**：设置 `MONITOR_FERNET_KEY` 可降低「拷走 DB 文件」后的可读性；**不能**阻止能访问 Web/API 的人调用接口。默认 **无登录**，请放在 **内网 / VPN**，或在前端加反代鉴权。
- 默认 **CORS 宽松**；面向公网时请自行增加 **HTTPS、认证、网络隔离**。
- 勿将 `.env`、数据库备份、密钥提交到 Git（见 `.gitignore`）。

---

## 本地开发

```bash
# 后端
cd backend && pip install -r requirements.txt
# Windows 可 set MONITOR_FERNET_KEY=...
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 前端（Vite 代理需指向后端）
cd frontend && npm install && npm run dev
```

---

## 开源协议

采用 **MIT License**（见仓库根目录 `LICENSE`）。

欢迎 Issue / PR 改进文档与功能。

---

## 相关文档

- 各推理框架的容器内启动命令示例：`scripts/README.md`
