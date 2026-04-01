import sqlite3
import os
from contextlib import contextmanager
from typing import Any, Mapping, Union

import field_crypto

DB_PATH = os.environ.get("DB_PATH", "/data/monitor.db")

RowLike = Union[sqlite3.Row, Mapping[str, Any]]


def decrypt_target_row(row: RowLike) -> dict:
    """将一行解密为明文 dict（供调度、SSH、网关内部使用）。"""
    d = dict(row)
    return field_crypto.decrypt_row(d)


def encrypt_target_row(d: dict) -> dict:
    """写入前加密敏感文本字段。"""
    return field_crypto.encrypt_row(d)


def model_target_public_dict(d: dict) -> dict:
    """列表/详情/仪表盘 API：不含 host/port/container/exec/SSH，仅 is_dual 表示是否双机。"""
    return {
        "id": d["id"],
        "name": d.get("name") or "",
        "model_api_name": (d.get("model_api_name") or "").strip(),
        "is_dual": bool((d.get("host_b") or "").strip()),
        "interval": int(d["interval"]),
        "enabled": bool(d["enabled"]),
        "gateway_enabled": bool(d["gateway_enabled"]),
        "gateway_max_concurrent": int(d["gateway_max_concurrent"]),
        "gateway_max_queue": int(d["gateway_max_queue"]),
        "created_at": d.get("created_at") or "",
    }


def init_db():
    field_crypto.init_field_crypto()
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS model_targets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                -- 主节点
                host         TEXT NOT NULL,
                port         INTEGER NOT NULL,
                container    TEXT NOT NULL,
                exec_cmd     TEXT NOT NULL DEFAULT '',
                -- 双机第二节点（为空则视为单机）
                host_b       TEXT NOT NULL DEFAULT '',
                port_b       INTEGER NOT NULL DEFAULT 0,
                container_b  TEXT NOT NULL DEFAULT '',
                exec_cmd_b   TEXT NOT NULL DEFAULT '',
                -- SSH 认证
                ssh_user     TEXT NOT NULL DEFAULT 'appadmin',
                ssh_password TEXT NOT NULL DEFAULT '',
                ssh_port     INTEGER NOT NULL DEFAULT 22,
                -- 检测
                interval     INTEGER NOT NULL DEFAULT 300,
                enabled      INTEGER NOT NULL DEFAULT 1,
                model_api_name TEXT NOT NULL DEFAULT '',
                -- 网关：经本站 /v1 转发时的并发与排队上限
                gateway_enabled       INTEGER NOT NULL DEFAULT 1,
                gateway_max_concurrent INTEGER NOT NULL DEFAULT 1,
                gateway_max_queue     INTEGER NOT NULL DEFAULT 64,
                created_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS check_results (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id   INTEGER NOT NULL,
                status     TEXT NOT NULL,
                latency_ms INTEGER,
                error_msg  TEXT,
                checked_at TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY(model_id) REFERENCES model_targets(id)
            );
        """)
        # 兼容旧数据库：若 model_api_name 列不存在则添加
        for col_sql in (
            "ALTER TABLE model_targets ADD COLUMN model_api_name TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE model_targets ADD COLUMN gateway_enabled INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE model_targets ADD COLUMN gateway_max_concurrent INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE model_targets ADD COLUMN gateway_max_queue INTEGER NOT NULL DEFAULT 64",
        ):
            try:
                conn.execute(col_sql)
            except Exception:
                pass


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
