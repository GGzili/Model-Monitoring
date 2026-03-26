# 模型监测平台

对部署在多台服务器上的 LLM 推理服务进行存活检测与手动重启管理。

## 功能

- 定时向各模型的 `/v1/models` 接口发送心跳探测（默认每 5 分钟）
- 仪表盘展示全部模型状态、延迟、最近检测时间
- 立即检测（手动触发一次探测）
- 手动重启：通过 SSH 远程执行 `docker restart` + 容器内启动命令
- 支持双机模型：并发 SSH 两台服务器同步重启
- 历史延迟折线图
- 模型增删改查，所有配置持久化存储

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI + APScheduler |
| 前端 | Vue 3 + Element Plus + ECharts |
| 存储 | SQLite |
| 部署 | Docker Compose |
| 远程执行 | Paramiko（SSH 密码认证 + sudo）|

## 目录结构

```
模型监测/
├── backend/
│   ├── main.py          # FastAPI 入口 + 全部 API 路由
│   ├── database.py      # SQLite 建表
│   ├── models.py        # Pydantic 数据模型
│   ├── checker.py       # /v1/models 心跳检测
│   ├── scheduler.py     # APScheduler 定时任务
│   ├── restart.py       # SSH 远程重启（支持单机/双机）
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue              # 仪表盘主页面
│   │   ├── api/index.js         # Axios 封装
│   │   └── components/
│   │       ├── ModelForm.vue    # 添加/编辑模型表单
│   │       └── HistoryChart.vue # 历史延迟折线图
│   ├── nginx.conf
│   ├── vite.config.js
│   ├── package.json
│   └── Dockerfile
├── scripts/             # 各模型启动脚本参考（不被平台直接调用）
├── docker-compose.yml
├── pack.ps1             # Windows 离线打包脚本
├── deploy_offline.sh    # Linux 离线部署脚本
└── data/               # SQLite 数据库（运行后自动生成）
```

### 更新前端

当前端代码有改动时，在 Windows 上重新构建并传到服务器：

```powershell
# Windows 上重新构建
cd "模型监测\frontend"
npm run build

# 传到服务器
scp -P 32580 -r dist appadmin@<监控机IP>:/opt/Model_Monitoring/dist_package/frontend/
```

然后在服务器上重新构建前端镜像：

```bash
cd /opt/Model_Monitoring/dist_package
docker-compose up -d --build frontend
```

### 更新后端

当后端代码有改动时，直接覆盖服务器上对应文件，然后：

```bash
cd /opt/Model_Monitoring/dist_package
docker-compose up -d --build backend
```
```

---

## 构建与部署

### 场景一：监控机可以联网

```bash
cd 模型监测
docker compose up -d --build
```

浏览器访问 `http://<监控机IP>:4444`。

---

### 场景二：监控机内网离线（推荐）

#### 第一步：在 Windows 上打包（需要 Python、Node.js、Docker Desktop）

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
cd "模型监测"
.\pack.ps1
```

脚本完成后生成 `dist_package/` 目录，包含：
- `wheels/` — Python 依赖 whl 包
- `images/` — Docker 镜像 tar 文件
- `frontend_dist/` — 前端编译产物
- `backend/` — 后端源码
- `deploy_offline.sh` — 部署脚本

将 `dist_package/` 打包成 zip 传到监控机。

#### 第二步：在监控机上部署

```bash
unzip dist_package.zip
cd dist_package
chmod +x deploy_offline.sh
./deploy_offline.sh
```

> 如果 `docker compose` 报错，改用 `docker-compose`：
> ```bash
> sed -i 's/docker compose/docker-compose/g' deploy_offline.sh
> ./deploy_offline.sh
> ```

浏览器访问 `http://<监控机IP>:4444`。

---

## 添加模型

点击右上角「+ 添加模型」，按以下说明填写：

| 字段 | 说明 |
|------|------|
| 名称 | 模型显示名称 |
| 服务器 IP | 模型服务所在服务器 IP |
| 检测端口 | 模型对外的 HTTP 端口（需支持 `/v1/models`）|
| 容器名 | docker 容器名称 |
| 容器内启动命令 | 在容器内执行的模型启动命令，平台会包装为 `sudo docker exec -d <容器名> bash -c "<命令>"`  |
| 双机开关 | 打开后显示节点 B 配置，两台服务器并发重启 |
| SSH 用户 | SSH 登录用户名（如 appadmin）|
| SSH 密码 | 用于 sudo 提权的密码 |
| 检测间隔 | 心跳探测间隔秒数（最小 30 秒）|

### 容器内启动命令示例

**Qwen2.5-VL（mindie）：**
```
cd /usr/local/Ascend/mindie/latest/mindie-service && nohup ./bin/mindieservice_daemon > output_service.log 2>&1 &
```

**Qwen3-VL（vllm-ascend）：**
```
cd /root && export ASCEND_RT_VISIBLE_DEVICES=4,5,6,7 && export HCCL_OP_EXPANSION_MODE=AIV && nohup vllm serve /root/models --host 0.0.0.0 --port 2025 --tensor-parallel-size 4 --max-num-seqs 16 --max-num-batched-tokens 4096 --block-size 128 --trust-remote-code --no-enable-prefix-caching --gpu-memory-utilization 0.8 --max-model-len 262144 --served-model-name qwen3-vl-32b > ./qwen3-vl-32b.log 2>&1 &
```

**DeepSeek-V3.1（双机，两节点相同命令）：**
```
cd /home && source start_env.sh && cd /usr/local/Ascend/mindie/latest/mindie-service && ./bin/mindieservice_daemon
```

---

## 重启流程说明

点击「重启模型」后，平台执行：

1. SSH 连接到目标服务器（端口可在添加模型时配置，默认 22）
2. `sudo docker restart <容器名>` — 重启容器
3. `sudo docker exec -d <容器名> bash -c "<容器内启动命令>"` — 启动模型进程

双机模型会同时对两台服务器并发执行以上步骤。

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dashboard` | 获取所有模型最新状态 |
| GET | `/api/models` | 模型列表 |
| POST | `/api/models` | 添加模型 |
| PUT | `/api/models/{id}` | 更新模型 |
| DELETE | `/api/models/{id}` | 删除模型 |
| POST | `/api/models/{id}/check` | 立即检测 |
| POST | `/api/models/{id}/restart` | 重启模型 |
| GET | `/api/models/{id}/history` | 历史检测记录 |
