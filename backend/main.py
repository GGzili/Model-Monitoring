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
    ModelTargetUpdate,
    ModelTargetOut,
    CheckResultOut,
    RestartResult,
)
from restart import restart_single, restart_dual


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="模型监测平台", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 模型管理 ────────────────────────────────────────────────

@app.get("/api/models", response_model=List[ModelTargetOut])
def list_models():
    with database.get_conn() as conn:
        rows = conn.execute("SELECT * FROM model_targets ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/models", response_model=ModelTargetOut)
def create_model(body: ModelTargetCreate):
    with database.get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO model_targets
              (name, host, port, container, exec_cmd,
               host_b, port_b, container_b, exec_cmd_b,
               ssh_user, ssh_password, interval, enabled)
            VALUES (?,?,?,?,?, ?,?,?,?, ?,?,?,?)
            """,
            (
                body.name, body.host, body.port, body.container, body.exec_cmd,
                body.host_b, body.port_b, body.container_b, body.exec_cmd_b,
                body.ssh_user, body.ssh_password, body.interval, int(body.enabled),
            ),
        )
        row = conn.execute(
            "SELECT * FROM model_targets WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    if body.enabled:
        scheduler.add_job(row["id"], row["host"], row["port"], row["interval"])
    return dict(row)


@app.get("/api/models/{model_id}", response_model=ModelTargetOut)
def get_model(model_id: int):
    with database.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM model_targets WHERE id = ?", (model_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Model not found")
    return dict(row)


@app.put("/api/models/{model_id}", response_model=ModelTargetOut)
def update_model(model_id: int, body: ModelTargetUpdate):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
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
    if row["enabled"]:
        scheduler.add_job(row["id"], row["host"], row["port"], row["interval"])
    else:
        scheduler.remove_job(model_id)
    return dict(row)


@app.delete("/api/models/{model_id}")
def delete_model(model_id: int):
    scheduler.remove_job(model_id)
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
    run_check(model_id, row["host"], row["port"])
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

    is_dual = bool(row["host_b"])
    if is_dual:
        result = restart_dual(
            host_a=row["host"],
            host_b=row["host_b"],
            container_a=row["container"],
            container_b=row["container_b"],
            exec_cmd_a=row["exec_cmd"],
            exec_cmd_b=row["exec_cmd_b"],
            ssh_user=row["ssh_user"],
            ssh_password=row["ssh_password"],
            ssh_port=row["ssh_port"],
        )
    else:
        result = restart_single(
            host=row["host"],
            container=row["container"],
            exec_cmd=row["exec_cmd"],
            ssh_user=row["ssh_user"],
            ssh_password=row["ssh_password"],
            ssh_port=row["ssh_port"],
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

@app.get("/api/dashboard")
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
            result.append({
                **dict(m),
                "is_dual": bool(m["host_b"]),
                "last_status": last["status"] if last else "unknown",
                "last_latency_ms": last["latency_ms"] if last else None,
                "last_checked_at": last["checked_at"] if last else None,
            })
    return result
