#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网关排队 / 上限测试脚本

用法（先在前台把某模型的网关设为：最大并发=1，最大排队数=1）：
  python scripts/test_gateway_limit.py --url http://127.0.0.1:4444 \\
    --model qwen2.5-72b-vl --workers 8 --hold-sec 15

说明：
  - 并发=1、排队=1 时，同一时刻最多「1 个正在转发 + 1 个在等槽位」；
    第 3 个及以后的在进队前会被 503（Gateway queue full）。
  - --hold-sec 会请求较大的 max_tokens，尽量让上游多算一会儿，便于叠高并发；
    若上游极快仍难复现，可把「最大排队数」改成 0 测纯排队（无 503），或改小 hold / 加大 workers。

直连后端（不经 nginx）示例：
  python scripts/test_gateway_limit.py --url http://127.0.0.1:3333 --model <API模型名> --workers 6
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any
from urllib.parse import urljoin

try:
    import httpx
except ImportError:
    print("需要: pip install httpx", file=sys.stderr)
    sys.exit(1)


def build_payload(model: str, hold_sec: int) -> dict[str, Any]:
    # max_tokens 拉大，让单次请求占用上游更久（仍取决于模型速度）
    tokens = max(32, min(512, hold_sec * 24))
    return {
        "model": model,
        "messages": [{"role": "user", "content": "用一句话介绍深度学习。"}],
        "stream": False,
        "max_tokens": tokens,
    }


async def one_request(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    idx: int,
    timeout: float,
) -> tuple[int, int, str]:
    t0 = time.perf_counter()
    err = ""
    try:
        r = await client.post(url, json=payload, timeout=timeout)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        body_preview = r.text[:200].replace("\n", " ")
        if r.status_code >= 400:
            err = body_preview
        return r.status_code, elapsed_ms, err
    except httpx.TimeoutException:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return 0, elapsed_ms, "client timeout"
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return 0, elapsed_ms, str(e)


def chat_completions_url(base: str) -> str:
    b = base.rstrip("/")
    if b.endswith("/v1/chat/completions"):
        return b
    if b.endswith("/v1"):
        return b + "/chat/completions"
    return urljoin(b + "/", "v1/chat/completions")


async def run_burst(args: argparse.Namespace) -> None:
    url = chat_completions_url(args.url)
    payload = build_payload(args.model, args.hold_sec)

    print("POST", url)
    print("model:", args.model)
    print("workers:", args.workers, "| hold_sec(提示):", args.hold_sec)
    print("payload:", json.dumps(payload, ensure_ascii=False))
    print("---")

    timeout = httpx.Timeout(args.timeout, connect=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [
            one_request(client, url, payload, i, args.timeout)
            for i in range(args.workers)
        ]
        t0 = time.perf_counter()
        results = await asyncio.gather(*tasks)
        total_ms = int((time.perf_counter() - t0) * 1000)

    counts: dict[int | str, int] = {}
    for status, elapsed_ms, err in results:
        key = status if status else "ERR"
        counts[key] = counts.get(key, 0) + 1

    print(f"全部完成， wall {total_ms} ms\n")
    print("状态码统计:", dict(sorted(counts.items(), key=lambda x: str(x[0]))))
    print("--- 逐条 ---")
    for i, (status, elapsed_ms, err) in enumerate(results):
        line = f"#{i+1:02d}  HTTP {status or '-'}  {elapsed_ms:5d} ms"
        if err:
            line += f"  | {err}"
        print(line)

    if 503 in counts:
        print("\n[OK] 出现 503：已达到网关「最大排队」拒绝策略。")
    else:
        print(
            "\n提示：若未出现 503，请把该模型「最大并发转发=1」「最大排队数=1」，"
            "并增大 --workers 或 --hold-sec；或上游响应太快，可换更慢的推理参数。"
        )


def main() -> None:
    p = argparse.ArgumentParser(description="测试网关并发/排队上限（503）")
    p.add_argument(
        "--url",
        default="http://127.0.0.1:4444",
        help="站点根或任意前缀，如 http://ip:4444 或 http://ip:3333",
    )
    p.add_argument("--model", required=True, help="与平台「API 模型名」或「名称」一致")
    p.add_argument("--workers", type=int, default=8, help="同时发出的请求数")
    p.add_argument(
        "--hold-sec",
        type=int,
        default=12,
        help="用于推算 max_tokens，让单次请求尽量多占上游一段时间",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="单请求客户端超时（秒）",
    )
    args = p.parse_args()
    asyncio.run(run_burst(args))


if __name__ == "__main__":
    main()
