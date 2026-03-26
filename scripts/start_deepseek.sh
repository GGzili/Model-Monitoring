#!/bin/bash
# DeepSeek-V3.1 单节点启动脚本
# 在容器 dsV3.1 内执行，两台服务器（节点A、节点B）使用同一脚本
# 由监控平台通过 docker exec 调用：
#   sudo docker exec -d dsV3.1 bash -c "bash /start_deepseek.sh"
# 注意：需提前将本脚本复制进容器，或直接将命令写入监控平台的 exec_cmd 字段

set -e

cd /home && source start_env.sh

cd /usr/local/Ascend/mindie/latest/mindie-service
./bin/mindieservice_daemon
