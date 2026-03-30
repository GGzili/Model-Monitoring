import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "/data/monitor.db")


def init_db():
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
