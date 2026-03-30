# 启动脚本说明

本目录的脚本仅作参考，**不会被监控平台直接调用**。

监控平台通过前端配置的「容器内启动命令」字段，执行方式为：

```bash
sudo docker exec -d <容器名> bash -c "<容器内启动命令>"
```

所有字段均在前端「添加模型」/「编辑模型」表单中配置，无需改代码。

---

## 网关压测脚本 `test_gateway_limit.py`（可选）

在**监控机本机 Python**上跑时需要 `httpx`。内网离线时：

**有网的机器上**（与监控机同为 **Linux x86_64** 时，用下面平台参数；若是 Windows 仅下载给本机用可去掉 `--platform`）：

```bash
pip download -r scripts/requirements-test.txt -d httpx_wheels \
  --platform manylinux2014_x86_64 --python-version 311 --only-binary=:all:
```

将目录 `httpx_wheels/` 拷到内网，在监控机上：

```bash
pip install --no-index --find-links=./httpx_wheels -r scripts/requirements-test.txt
```

若你已打过 **`dist_package`**，也可直接用包里的 **`wheels/`**（与后端依赖一起下载的，已含 `httpx` 及依赖）：

```bash
pip install --no-index --find-links=/opt/Model_Monitoring/dist_package/wheels httpx
```

---

## 各模型配置示例

### 1. DeepSeek-V3.1（双机模型）

| 字段 | 节点 A | 节点 B |
|------|--------|--------|
| 服务器 IP | 192.168.1.101 | 192.168.1.102 |
| 检测端口 | 1025 | 1025 |
| 容器名 | dsV3.1 | dsV3.1 |
| 容器内启动命令 | 见下方 | 同左 |
| SSH 用户 | appadmin | appadmin |

容器内启动命令：
```bash
cd /home && source start_env.sh && cd /usr/local/Ascend/mindie/latest/mindie-service && ./bin/mindieservice_daemon
```

> 启用「双机」开关，节点 B 启动命令留空则自动复用节点 A 的命令。

---

### 2. Qwen2.5-VL-72B-Instruct（单机）

| 字段 | 值 |
|------|----|
| 服务器 IP | 192.168.1.103 |
| 检测端口 | 你的服务端口 |
| 容器名 | qwen2.5-72b-vl |
| 容器内启动命令 | 见下方 |

容器内启动命令：
```bash
cd /usr/local/Ascend/mindie/latest/mindie-service && nohup ./bin/mindieservice_daemon > output_service.log 2>&1 &
```

---

### 3. Qwen3-VL-30B-A3B-Instruct（单机）

| 字段 | 值 |
|------|----|
| 服务器 IP | 192.168.1.103 |
| 检测端口 | 2025 |
| 容器名 | Qwen3-VL |
| 容器内启动命令 | 见下方 |

容器内启动命令：
```bash
export ASCEND_RT_VISIBLE_DEVICES=4,5,6,7 && export HCCL_OP_EXPANSION_MODE=AIV && cd /root && nohup vllm serve /root/models --host 0.0.0.0 --port 2025 --tensor-parallel-size 4 --max-num-seqs 16 --max-num-batched-tokens 4096 --block-size 128 --trust-remote-code --no-enable-prefix-caching --gpu-memory-utilization 0.8 --max-model-len 262144 --served-model-name qwen3-vl-32b > ./qwen3-vl-32b.log 2>&1 &
```
