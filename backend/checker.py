import httpx
import time
from database import get_conn

TIMEOUT = 15  # 秒


def check_model(model_id: int, host: str, port: int) -> dict:
    url = f"http://{host}:{port}/v1/models"
    start = time.monotonic()
    try:
        response = httpx.get(url, timeout=TIMEOUT)
        latency_ms = int((time.monotonic() - start) * 1000)
        if response.status_code == 200:
            return {"status": "ok", "latency_ms": latency_ms, "error_msg": None}
        else:
            return {
                "status": "error",
                "latency_ms": latency_ms,
                "error_msg": f"HTTP {response.status_code}",
            }
    except httpx.TimeoutException:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"status": "timeout", "latency_ms": latency_ms, "error_msg": "Request timed out"}
    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"status": "error", "latency_ms": latency_ms, "error_msg": str(e)}


def run_check(model_id: int, host: str, port: int):
    result = check_model(model_id, host, port)
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
