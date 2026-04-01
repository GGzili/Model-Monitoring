import os
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import database
import scheduler
from checker import run_check
from models import (
    ModelTargetCreate,
    ModelTargetTunableUpdate,
    ModelTargetPublicOut,
    DashboardRowOut,
    CheckResultOut,
    RestartResult,
)
from restart import restart_single, restart_dual
import gateway as gw


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="模型监测平台", lifespan=lifespan)
app.include_router(gw.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 模型管理 ────────────────────────────────────────────────

@app.get("/api/models", response_model=List[ModelTargetPublicOut])
def list_models():
    with database.get_conn() as conn:
        rows = conn.execute("SELECT * FROM model_targets ORDER BY id").fetchall()
    return [
        database.model_target_public_dict(database.decrypt_target_row(r)) for r in rows
    ]


@app.post("/api/models", response_model=ModelTargetPublicOut)
def create_model(body: ModelTargetCreate):
    plain = {
        "name": (body.name or "").strip(),
        "host": body.host,
        "port": body.port,
        "container": body.container,
        "exec_cmd": body.exec_cmd or "",
        "host_b": body.host_b or "",
        "port_b": body.port_b,
        "container_b": body.container_b or "",
        "exec_cmd_b": body.exec_cmd_b or "",
        "ssh_user": body.ssh_user,
        "ssh_password": body.ssh_password,
        "interval": body.interval,
        "enabled": int(body.enabled),
        "model_api_name": body.model_api_name,
        "gateway_enabled": int(body.gateway_enabled),
        "gateway_max_concurrent": body.gateway_max_concurrent,
        "gateway_max_queue": body.gateway_max_queue,
    }
    enc = database.encrypt_target_row(plain)
    with database.get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO model_targets
              (name, host, port, container, exec_cmd,
               host_b, port_b, container_b, exec_cmd_b,
               ssh_user, ssh_password, interval, enabled, model_api_name,
               gateway_enabled, gateway_max_concurrent, gateway_max_queue)
            VALUES (?,?,?,?,?, ?,?,?,?, ?,?,?,?,?,?,?,?)
            """,
            (
                enc["name"],
                enc["host"],
                enc["port"],
                enc["container"],
                enc["exec_cmd"],
                enc["host_b"],
                enc["port_b"],
                enc["container_b"],
                enc["exec_cmd_b"],
                enc["ssh_user"],
                enc["ssh_password"],
                enc["interval"],
                enc["enabled"],
                enc["model_api_name"],
                enc["gateway_enabled"],
                enc["gateway_max_concurrent"],
                enc["gateway_max_queue"],
            ),
        )
        row = conn.execute(
            "SELECT * FROM model_targets WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    dec = database.decrypt_target_row(row)
    if body.enabled:
        api_name = (dec["model_api_name"] or "").strip() or (dec["name"] or "").strip()
        scheduler.add_job(dec["id"], dec["host"], dec["port"], dec["interval"], api_name)
    gw.invalidate_gate(row["id"])
    return database.model_target_public_dict(dec)


@app.get("/api/models/{model_id}", response_model=ModelTargetPublicOut)
def get_model(model_id: int):
    with database.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM model_targets WHERE id = ?", (model_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Model not found")
    return database.model_target_public_dict(database.decrypt_target_row(row))


@app.put("/api/models/{model_id}", response_model=ModelTargetPublicOut)
def update_model(model_id: int, body: ModelTargetTunableUpdate):
    raw = {k: v for k, v in body.model_dump().items() if v is not None}
    if not raw:
        raise HTTPException(status_code=400, detail="No fields to update")
    fields = {}
    for k, v in raw.items():
        if k in ("enabled", "gateway_enabled"):
            fields[k] = int(v)
        else:
            fields[k] = v
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    with database.get_conn() as conn:
        conn.execute(
            f"UPDATE model_targets SET {set_clause} WHERE id = ?",
            (*fields.values(), model_id),
        )
        row = conn.execute(
            "SELECT * FROM model_targets WHERE id = ?", (model_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Model not found")
    dec = database.decrypt_target_row(row)
    if dec["enabled"]:
        api_name = (dec["model_api_name"] or "").strip() or (dec["name"] or "").strip()
        scheduler.add_job(dec["id"], dec["host"], dec["port"], dec["interval"], api_name)
    else:
        scheduler.remove_job(model_id)
    gw.invalidate_gate(model_id)
    return database.model_target_public_dict(dec)


@app.delete("/api/models/{model_id}")
def delete_model(model_id: int):
    scheduler.remove_job(model_id)
    gw.invalidate_gate(model_id)
    with database.get_conn() as conn:
        conn.execute("DELETE FROM check_results WHERE model_id = ?", (model_id,))
        conn.execute("DELETE FROM model_targets WHERE id = ?", (model_id,))
    return {"ok": True}


# ── 立即检测 ─────────────────────────────────────────────────

@app.post("/api/models/{model_id}/check", response_model=CheckResultOut)
def check_now(model_id: int):
    with database.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM model_targets WHERE id = ?", (model_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Model not found")
    dec = database.decrypt_target_row(row)
    api_name = (dec["model_api_name"] or "").strip() or (dec["name"] or "").strip()
    run_check(model_id, dec["host"], dec["port"], api_name)
    with database.get_conn() as conn:
        last = conn.execute(
            "SELECT * FROM check_results WHERE model_id = ? ORDER BY id DESC LIMIT 1",
            (model_id,),
        ).fetchone()
    return dict(last)


# ── 重启模型 ─────────────────────────────────────────────────

@app.post("/api/models/{model_id}/restart", response_model=RestartResult)
def restart(model_id: int):
    with database.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM model_targets WHERE id = ?", (model_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Model not found")

    dec = database.decrypt_target_row(row)
    is_dual = bool((dec.get("host_b") or "").strip())
    if is_dual:
        result = restart_dual(
            host_a=dec["host"],
            host_b=dec["host_b"],
            container_a=dec["container"],
            container_b=dec["container_b"],
            exec_cmd_a=dec["exec_cmd"],
            exec_cmd_b=dec["exec_cmd_b"],
            ssh_user=dec["ssh_user"],
            ssh_password=dec["ssh_password"],
            ssh_port=dec["ssh_port"],
        )
    else:
        result = restart_single(
            host=dec["host"],
            container=dec["container"],
            exec_cmd=dec["exec_cmd"],
            ssh_user=dec["ssh_user"],
            ssh_password=dec["ssh_password"],
            ssh_port=dec["ssh_port"],
        )
    return result


# ── 历史记录 ─────────────────────────────────────────────────

@app.get("/api/models/{model_id}/history", response_model=List[CheckResultOut])
def get_history(model_id: int, limit: Optional[int] = 100):
    with database.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM check_results
            WHERE model_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (model_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ── 仪表盘汇总 ───────────────────────────────────────────────

@app.get("/api/dashboard", response_model=List[DashboardRowOut])
def dashboard():
    with database.get_conn() as conn:
        models = conn.execute("SELECT * FROM model_targets ORDER BY id").fetchall()
        result = []
        for m in models:
            last = conn.execute(
                """
                SELECT status, latency_ms, checked_at
                FROM check_results WHERE model_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (m["id"],),
            ).fetchone()
            base = database.model_target_public_dict(database.decrypt_target_row(m))
            result.append({
                **base,
                "last_status": last["status"] if last else "unknown",
                "last_latency_ms": last["latency_ms"] if last else None,
                "last_checked_at": last["checked_at"] if last else None,
            })
    return result
