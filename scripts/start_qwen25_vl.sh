#!/bin/bash
# Qwen2.5-VL-72B-Instruct 启动脚本
# 在容器 qwen2.5-72b-vl 内执行
# 由监控平台通过 docker exec 调用：
#   sudo docker exec -d qwen2.5-72b-vl bash -c "bash /start_qwen25_vl.sh"

set -e

cd /usr/local/Ascend/mindie/latest/mindie-service
nohup ./bin/mindieservice_daemon > output_service.log 2>&1 &

echo "Qwen2.5-VL service started, pid=$!"
