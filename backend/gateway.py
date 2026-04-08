"""
OpenAI 兼容网关：请求经本站排队后转发到已登记模型的 host:port。
通过每模型并发上限 + 排队上限，缓解 tokenizer 子进程等串行瓶颈导致的假死。
"""
import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional, Tuple

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

import database
from logging_config import get_app_logger

router = APIRouter(tags=["gateway"])
log = get_app_logger()


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host or "-"
    return "-"

UPSTREAM_TIMEOUT = float(os.environ.get("GATEWAY_UPSTREAM_TIMEOUT", "600"))

# 每个 model_targets.id 独立一条「并发槽 + 排队上限」，与其它模型互不共享
_registry: Dict[int, Tuple[int, int, "ConcurrencyGate"]] = {}
_reg_lock = asyncio.Lock()


class ConcurrencyGate:
    """限制同时转发数；超过部分在 acquire 前排队。max_queue=0 表示不限制排队长度。"""

    def __init__(self, concurrent: int, max_queue: int):
        self._sem = asyncio.Semaphore(concurrent)
        self._max_queue = max_queue
        self._waiting = 0
        self._wait_lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire_slot(self):
        async with self._wait_lock:
            if self._max_queue > 0 and self._waiting >= self._max_queue:
                raise HTTPException(
                    status_code=503,
                    detail="Gateway queue full for this model; retry later.",
                )
            self._waiting += 1
        try:
            await self._sem.acquire()
        except BaseException:
            async with self._wait_lock:
                self._waiting -= 1
            raise
        async with self._wait_lock:
            self._waiting -= 1
        try:
            yield
        finally:
            self._sem.release()


def invalidate_gate(model_id: int) -> None:
    _registry.pop(model_id, None)


async def _ensure_gate(model_id: int, concurrent: int, max_queue: int) -> ConcurrencyGate:
    spec = (max(1, concurrent), max(0, max_queue))
    async with _reg_lock:
        cur = _registry.get(model_id)
        if cur is not None and cur[0] == spec[0] and cur[1] == spec[1]:
            return cur[2]
        gate = ConcurrencyGate(spec[0], spec[1])
        _registry[model_id] = (spec[0], spec[1], gate)
        return gate


def _resolve_model_row(model_name: str) -> Optional[Any]:
    """按 OpenAI 请求里的 model 匹配 model_api_name（非空）或 name；仅启用且开放网关的条目。"""
    with database.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM model_targets
            WHERE enabled = 1 AND gateway_enabled = 1
            ORDER BY id
            """
        ).fetchall()
    for r in rows:
        d = database.decrypt_target_row(r)
        rid = (d.get("model_api_name") or "").strip() or (d.get("name") or "").strip()
        if rid == model_name:
            return d
    return None


def _forward_headers(request: Request) -> dict:
    h = {}
    for name in ("authorization", "content-type", "accept", "user-agent"):
        v = request.headers.get(name)
        if v:
            h[name] = v
    return h


@router.get("/v1/models")
async def list_models_openai(request: Request):
    ip = _client_ip(request)
    with database.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, name, model_api_name FROM model_targets
            WHERE enabled = 1 AND gateway_enabled = 1
            ORDER BY id
            """
        ).fetchall()
    now = 1700000000
    data = []
    for r in rows:
        d = database.decrypt_target_row(r)
        mid = (d.get("model_api_name") or "").strip() or (d.get("name") or "").strip()
        data.append(
            {
                "id": mid,
                "object": "model",
                "created": now,
                "owned_by": "model-monitor",
            }
        )
    log.info("GET /v1/models ip=%s exposed_models=%s", ip, len(data))
    return JSONResponse({"object": "list", "data": data})


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body_bytes = await request.body()
    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        log.warning("POST /v1/chat_completions invalid_json ip=%s", _client_ip(request))
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    model_name = payload.get("model")
    if not model_name or not isinstance(model_name, str):
        log.warning("POST /v1/chat_completions missing_model ip=%s", _client_ip(request))
        raise HTTPException(status_code=400, detail="Missing or invalid 'model' field")

    row = _resolve_model_row(model_name)
    if row is None:
        log.warning(
            "POST /v1/chat_completions unknown_or_disabled model=%r ip=%s",
            model_name,
            _client_ip(request),
        )
        raise HTTPException(
            status_code=404,
            detail=f"Unknown or gateway-disabled model: {model_name}",
        )

    stream = bool(payload.get("stream", False))
    log.info(
        "POST /v1/chat/completions model=%r resolved_id=%s stream=%s ip=%s body_bytes=%s",
        model_name,
        row["id"],
        stream,
        _client_ip(request),
        len(body_bytes),
    )

    gate = await _ensure_gate(
        row["id"],
        int(row["gateway_max_concurrent"]),
        int(row["gateway_max_queue"]),
    )

    url = f"http://{row['host']}:{row['port']}/v1/chat/completions"
    headers = _forward_headers(request)
    meta = {
        "model_name": model_name,
        "model_id": row["id"],
        "client_ip": _client_ip(request),
    }

    if stream:
        return await _proxy_stream(gate, url, body_bytes, headers, meta)
    return await _proxy_json(gate, url, body_bytes, headers, meta)


async def _proxy_json(
    gate: ConcurrencyGate,
    url: str,
    body: bytes,
    headers: dict,
    meta: Dict[str, Any],
) -> Response:
    async with gate.acquire_slot():
        try:
            async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT) as client:
                r = await client.post(url, content=body, headers=headers)
        except httpx.TimeoutException:
            log.warning(
                "gateway chat upstream_timeout model=%r id=%s ip=%s stream=false",
                meta["model_name"],
                meta["model_id"],
                meta["client_ip"],
            )
            raise HTTPException(status_code=504, detail="Upstream timeout")
        except httpx.RequestError as e:
            log.warning(
                "gateway chat upstream_error model=%r id=%s ip=%s stream=false err=%s",
                meta["model_name"],
                meta["model_id"],
                meta["client_ip"],
                e,
            )
            raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

    log.info(
        "gateway chat done model=%r id=%s ip=%s stream=false upstream_http=%s resp_bytes=%s",
        meta["model_name"],
        meta["model_id"],
        meta["client_ip"],
        r.status_code,
        len(r.content),
    )
    media = r.headers.get("content-type", "application/json")
    return Response(content=r.content, status_code=r.status_code, media_type=media)


async def _proxy_stream(
    gate: ConcurrencyGate,
    url: str,
    body: bytes,
    headers: dict,
    meta: Dict[str, Any],
) -> StreamingResponse:
    async def stream_with_slot() -> AsyncIterator[bytes]:
        async with gate.acquire_slot():
            try:
                async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT) as client:
                    async with client.stream("POST", url, content=body, headers=headers) as r:
                        log.info(
                            "gateway chat upstream model=%r id=%s ip=%s stream=true upstream_http=%s",
                            meta["model_name"],
                            meta["model_id"],
                            meta["client_ip"],
                            r.status_code,
                        )
                        async for chunk in r.aiter_bytes():
                            yield chunk
            except httpx.TimeoutException:
                log.warning(
                    "gateway chat upstream_timeout model=%r id=%s ip=%s stream=true",
                    meta["model_name"],
                    meta["model_id"],
                    meta["client_ip"],
                )
                raise HTTPException(status_code=504, detail="Upstream timeout")
            except httpx.RequestError as e:
                log.warning(
                    "gateway chat upstream_error model=%r id=%s ip=%s stream=true err=%s",
                    meta["model_name"],
                    meta["model_id"],
                    meta["client_ip"],
                    e,
                )
                raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

    return StreamingResponse(
        stream_with_slot(),
        media_type="text/event-stream",
    )
