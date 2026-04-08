#!/usr/bin/env python3
"""
列出 model_targets 中每条记录的 ssh_port / ssh_port_b（SQLite 整型列，不经 Fernet）。

用于在服务器上核对：前端填的 SSH 端口是否已写入库；重启仍连 22 时先看这里。

用法（宿主机，项目根目录）:
  python scripts/check_ssh_ports.py ./data/monitor.db

用法（backend 容器内，未拷贝本脚本时可直接一行 Python）:
  docker compose exec backend python -c "import sqlite3;c=sqlite3.connect('/data/monitor.db');print(c.execute('SELECT id,ssh_port,ssh_port_b FROM model_targets').fetchall())"

宿主机（compose 把 ./data 挂到容器 /data 时，库在宿主机项目下）:
  python scripts/check_ssh_ports.py ./data/monitor.db
"""
from __future__ import annotations

import os
import sqlite3
import sys


def main() -> int:
    path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("DB_PATH", "/data/monitor.db")
    )
    if not os.path.isfile(path):
        print(f"文件不存在: {path}", file=sys.stderr)
        return 1
    conn = sqlite3.connect(path)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(model_targets)").fetchall()}
        if "ssh_port" not in cols:
            print("表 model_targets 无 ssh_port 列，库结构异常。", file=sys.stderr)
            return 1
        if "ssh_port_b" in cols:
            rows = conn.execute(
                "SELECT id, ssh_port, ssh_port_b FROM model_targets ORDER BY id"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, ssh_port FROM model_targets ORDER BY id"
            ).fetchall()
    except sqlite3.OperationalError as e:
        print(f"查询失败: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    if not rows:
        print("(无记录)")
        return 0
    has_b = len(rows[0]) > 2
    if has_b:
        print(f"{'id':>6}  {'ssh_port':>10}  {'ssh_port_b':>12}")
        for rid, sp, spb in rows:
            print(f"{rid:6d}  {sp!s:>10}  {spb!s:>12}")
    else:
        print(f"{'id':>6}  {'ssh_port':>10}  (无 ssh_port_b 列，请重启 backend 以执行迁移)")
        for rid, sp in rows:
            print(f"{rid:6d}  {sp!s:>10}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
