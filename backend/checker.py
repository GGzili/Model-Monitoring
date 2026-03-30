import httpx
import time
from database import get_conn

TIMEOUT = 15  # 秒

# 探测用的极短消息，尽量减少对模型的负担
_PROBE_MESSAGE = "hi"


def check_model(model_id: int, host: str, port: int, model_name: str) -> dict:
    """向 /v1/chat/completions 发送一次真实推理请求来检测模型是否可用。
    仅靠 /v1/models 返回 200 无法发现 tokenizer 子进程挂死等故障。
    """
    url = f"http://{host}:{port}/v1/chat/completions"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": _PROBE_MESSAGE}],
        "max_tokens": 1,
        "stream": False,
    }
    start = time.monotonic()
    try:
        response = httpx.post(url, json=payload, timeout=TIMEOUT)
        latency_ms = int((time.monotonic() - start) * 1000)
        if response.status_code == 200:
            data = response.json()
            # 部分服务在 HTTP 200 里仍返回 error 字段（如 tokenizer 超时）
            if "error" in data:
                return {
                    "status": "error",
                    "latency_ms": latency_ms,
                    "error_msg": data.get("error") or "unknown error in response",
                }
            return {"status": "ok", "latency_ms": latency_ms, "error_msg": None}
        else:
            try:
                err_detail = response.json().get("error") or f"HTTP {response.status_code}"
            except Exception:
                err_detail = f"HTTP {response.status_code}"
            return {
                "status": "error",
                "latency_ms": latency_ms,
                "error_msg": err_detail,
            }
    except httpx.TimeoutException:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"status": "timeout", "latency_ms": latency_ms, "error_msg": "Request timed out"}
    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"status": "error", "latency_ms": latency_ms, "error_msg": str(e)}


def run_check(model_id: int, host: str, port: int, model_name: str = ""):
    result = check_model(model_id, host, port, model_name)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO check_results (model_id, status, latency_ms, error_msg)
            VALUES (?, ?, ?, ?)
            """,
            (model_id, result["status"], result["latency_ms"], result["error_msg"]),
        )
        # 只保留最近 1000 条记录，避免数据库无限增长
        conn.execute(
            """
            DELETE FROM check_results
            WHERE id IN (
                SELECT id FROM check_results
                WHERE model_id = ?
                ORDER BY id DESC
                LIMIT -1 OFFSET 1000
            )
            """,
            (model_id,),
        )
    return result
