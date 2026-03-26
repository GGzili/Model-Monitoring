#!/bin/bash
# Qwen3-VL-30B-A3B-Instruct 启动脚本
# 在容器 Qwen3-VL 内执行
# 由监控平台通过 docker exec 调用：
#   sudo docker exec -d Qwen3-VL bash -c "bash /start_qwen3_vl.sh"

set -e

cd /root

export ASCEND_RT_VISIBLE_DEVICES=4,5,6,7
export HCCL_OP_EXPANSION_MODE=AIV

nohup vllm serve /root/models \
  --host 0.0.0.0 \
  --port 2025 \
  --tensor-parallel-size 4 \
  --max-num-seqs 16 \
  --max-num-batched-tokens 4096 \
  --block-size 128 \
  --trust-remote-code \
  --no-enable-prefix-caching \
  --gpu-memory-utilization 0.8 \
  --max-model-len 262144 \
  --served-model-name qwen3-vl-32b > ./qwen3-vl-32b.log 2>&1 &

echo "Qwen3-VL service started, pid=$!"
