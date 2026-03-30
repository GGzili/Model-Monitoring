# 模型监测平台

面向多台服务器上 **LLM 推理服务** 的轻量运维工具：健康探测、仪表盘、SSH 远程重启，以及可选的 **OpenAI 兼容网关**（按模型限并发与排队，缓解 tokenizer 等串行瓶颈导致的假死）。

**Model Monitor** — health checks, dashboard, Docker-based remote restart, and an optional gated `/v1` proxy for OpenAI-compatible clients.

---

## 功能概览

| 能力 | 说明 |
|------|------|
| 定时探测 | 对 `http://{host}:{port}/v1/chat/completions` 发送极简推理请求（`max_tokens: 1`），记录延迟与状态 |
| 仪表盘 | 卡片展示各模型最近状态、延迟、检测时间；支持复制「网关调用名」 |
| 立即检测 | 手动触发单次探测 |
| 远程重启 | SSH（密码 + `sudo`）执行 `docker restart` 与容器内启动命令 |
| 双机 | 两台服务器上并发执行同一套重启流程 |
| 历史 | 延迟折线图与检测记录 |
| 配置 | 模型 CRUD，SQLite 持久化 |
| **网关** | `POST /v1/chat/completions`、`GET /v1/models`；每模型独立 **最大并发** 与 **消息队列容量**；需「监测启用」且「开放网关」 |

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11、FastAPI、APScheduler、httpx、Paramiko |
| 前端 | Vue 3、Element Plus、ECharts |
| 存储 | SQLite |
| 部署 | Docker Compose；Nginx 反代 `/api` 与 `/v1` |

---

## 快速开始（监控机可联网）

```bash
git clone <本仓库 URL> model-monitor
cd model-monitor
docker compose up -d --build
```

- 前端：<http://localhost:4444>（或 `<监控机IP>:4444`）
- 后端 API：<http://localhost:3333>（或 `:3333`）

数据文件默认挂载为项目下的 `./data/monitor.db`。

---

## 目录结构

```
model-monitor/
├── backend/
│   ├── main.py          # FastAPI 入口与路由
│   ├── gateway.py       # OpenAI 兼容网关（/v1）
│   ├── database.py      # SQLite
│   ├── models.py        # Pydantic
│   ├── checker.py       # 健康探测
│   ├── scheduler.py     # 定时任务
│   ├── restart.py       # SSH 重启
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   ├── nginx.conf       # /api、/v1 反代到后端
│   └── Dockerfile
├── scripts/             # 参考与网关压测脚本（见 scripts/README.md）
├── docker-compose.yml
├── pack.ps1 / pack.bat  # Windows 离线打包（见下文）
├── deploy_offline.sh    # Linux 离线部署入口
└── LICENSE              # MIT
```

---

## 网关（OpenAI 兼容）

客户端将原先生到模型推理地址的请求，改为打到监控站：

- **URL**：`http://<监控机>:4444/v1/chat/completions`（与页面同域，经 Nginx）
- **请求体 `model`**：须与界面中的 **网关调用名** 一致（「API 模型名」非空则用其值，否则用「名称」）
- **前提**：该模型在配置中 **启用监测** 且 **开放网关**

每模型可配置 **最大并发**（同时转发到后端的请求数）与 **消息队列容量**（超出并发时排队；满则 `503`；`0` 表示不限制排队长度）。双机模型网关当前仅使用 **主节点 A** 的 `host:port`。

环境变量（可选）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `GATEWAY_UPSTREAM_TIMEOUT` | `600` | 转发到上游的单次超时（秒） |
| `DB_PATH` | `/data/monitor.db` | 数据库路径（容器内） |

压测脚本：`scripts/test_gateway_limit.py`（宿主机需 `httpx`，见 `scripts/requirements-test.txt`）。

---

## 离线打包与内网部署

### Windows 上生成 `dist_package/`

需本机安装 Python、Node.js；Docker 用于导出基础镜像（或使用 `-SkipDockerPull` / `-SkipDockerSave`，见脚本注释）。

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
cd model-monitor
.\pack.ps1
# 或 pack.bat。本机已有 python:3.11-slim / nginx:alpine：.\pack.ps1 -SkipDockerPull
# 已手动放入 dist_package\images\*.tar：.\pack.ps1 -SkipDockerSave
```

产物包含 `wheels/`、`images/*.tar`、`frontend_dist/`、`backend/`、`docker-compose.yml`、`deploy_offline.sh` 等。将 **`dist_package` 打成 zip** 拷到内网。

### Linux 监控机上部署

**不要**在服务器上运行 `pack.ps1`。解压后执行：

```bash
unzip dist_package.zip
cd dist_package
chmod +x deploy_offline.sh
./deploy_offline.sh
```

升级时保留 **`data/monitor.db`**：解压前建议 `docker compose down` 并备份数据库，再覆盖除 `data/` 外的文件后重新执行 `./deploy_offline.sh`。

若仅 `docker-compose` 可用：

```bash
sed -i 's/docker compose/docker-compose/g' deploy_offline.sh
./deploy_offline.sh
```

---

## 配置说明（添加模型）

| 字段 | 说明 |
|------|------|
| 名称 / API 模型名 | 展示名与探测、网关使用的模型 ID（网关优先 API 模型名） |
| 服务器 IP、检测端口 | 主节点 A；探测与网关转发目标 |
| 容器名、容器内启动命令 | 用于远程重启后的 `docker exec` |
| 双机 | 可选节点 B；重启时两台并发；网关仍只走 A |
| SSH 用户、密码、端口 | 密码存入数据库，用于 `sudo` |
| 检测间隔 | 秒，最小 30 |
| 启用 | 关闭后不参与探测与网关 |
| 开放网关、最大并发、消息队列容量 | 见上文「网关」 |

`docker-compose.yml` 中可将后端挂载 `~/.ssh` 供密钥场景使用；默认示例为密码流程。

---

## 重启流程

1. SSH 连接目标机  
2. `sudo docker restart <容器名>`  
3. `sudo docker exec -d <容器名> bash -c "<容器内启动命令>"`  

双机时对 A、B 并发执行上述步骤。

---

## HTTP API

### 管理接口（前缀 `/api`，前端与 Nginx 默认反代）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dashboard` | 仪表盘汇总 |
| GET | `/api/models` | 模型列表 |
| POST | `/api/models` | 创建 |
| PUT | `/api/models/{id}` | 更新 |
| DELETE | `/api/models/{id}` | 删除 |
| POST | `/api/models/{id}/check` | 立即检测 |
| POST | `/api/models/{id}/restart` | 重启 |
| GET | `/api/models/{id}/history` | 历史记录 |

### 网关（与 OpenAI 客户端兼容）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/models` | 列出已开放网关的模型 |
| POST | `/v1/chat/completions` | 排队限流后转发到上游 |

---

## 安全提示

- **SSH 密码、模型配置保存在 SQLite 明文**；请勿把数据库或备份暴露到不可信环境。  
- 默认 **CORS 宽松**、**无鉴权**，仅建议在 **内网 / 受信网络** 使用。面向公网时请自行增加认证、HTTPS、网络隔离等措施。

---

## 本地开发

```bash
# 后端
cd backend && pip install -r requirements.txt && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 前端（需将 vite 代理指向后端）
cd frontend && npm install && npm run dev
```

---

## 开源协议

采用 **MIT License**（见仓库根目录 `LICENSE`）。若你 fork 时尚未包含该文件，可复制标准 MIT 全文并填写版权年份与权利人。

欢迎 Issue / PR 改进文档与功能。

---

## 相关文档

- 各推理框架的容器内启动命令示例：`scripts/README.md`
