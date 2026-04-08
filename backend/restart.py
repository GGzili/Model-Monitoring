import time
import threading
import paramiko

SSH_PORT = 22
SSH_CONNECT_TIMEOUT = 10
EXEC_TIMEOUT = 120  # docker exec 启动命令最长等待


def _safe_ssh_port(ssh_port: object) -> int:
    """将 ssh_port 转为合法整数，无效时回退 22。"""
    try:
        sp = int(ssh_port)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        sp = 22
    if not (1 <= sp <= 65535):
        sp = 22
    return sp


def _make_client(host: str, ssh_user: str, ssh_password: str,
                 ssh_port: int = SSH_PORT) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        port=ssh_port,
        username=ssh_user,
        password=ssh_password,
        timeout=SSH_CONNECT_TIMEOUT,
    )
    return client


def _run(client: paramiko.SSHClient, cmd: str, timeout: int = 60) -> tuple[int, str, str]:
    """执行命令，返回 (exit_code, stdout, stderr)。"""
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode(errors="replace").strip()
    err = stderr.read().decode(errors="replace").strip()
    return exit_code, out, err


def _sudo_run(client: paramiko.SSHClient, cmd: str,
             password: str, timeout: int = 60) -> tuple[int, str, str]:
    """用 sudo -S 执行命令，自动输入密码。"""
    full = f"echo {_quote_pass(password)} | sudo -S bash -c {_bash_quote(cmd)}"
    return _run(client, full, timeout)


def _quote_pass(p: str) -> str:
    """对密码做单引号转义，防止 shell 注入。"""
    return "'" + p.replace("'", "'\\''" ) + "'"


def _bash_quote(cmd: str) -> str:
    """用单引号包裹整条命令传给 bash -c。"""
    return "'" + cmd.replace("'", "'\\''" ) + "'"


def restart_single(host: str, container: str, exec_cmd: str,
                   ssh_user: str, ssh_password: str,
                   ssh_port: int = SSH_PORT) -> dict:
    """
    单机模型重启：
      1. sudo docker restart <container>
      2. sudo docker exec <container> bash -c "<exec_cmd>"
    """
    client = None
    try:
        host = (host or "").strip()
        ssh_port = _safe_ssh_port(ssh_port)
        client = _make_client(host, ssh_user, ssh_password, ssh_port)

        # 1. 重启容器
        code, out, err = _sudo_run(client, f"docker restart {container}", ssh_password, timeout=60)
        if code != 0:
            return {"success": False, "message": f"docker restart 失败: {err or out}"}

        # 2. 在容器内执行启动命令
        code, out, err = _sudo_run(
            client,
            f"docker exec -d {container} bash -c {_bash_quote(exec_cmd)}",
            ssh_password,
            timeout=EXEC_TIMEOUT,
        )
        if code != 0:
            return {"success": False, "message": f"docker exec 失败: {err or out}"}

        return {"success": True, "message": "启动命令已下发"}
    except Exception as e:
        return {
            "success": False,
            "message": f"SSH {host}:{ssh_port} 连接或执行失败: {e}",
        }
    finally:
        if client:
            client.close()


def _restart_node(host: str, container: str, exec_cmd: str,
                  ssh_user: str, ssh_password: str, ssh_port: int,
                  results: dict, key: str):
    """线程函数：单节点重启，结果写入 results[key]。"""
    results[key] = restart_single(host, container, exec_cmd, ssh_user, ssh_password, ssh_port)


def _ssh_for_node_b(
    ssh_user: str,
    ssh_password: str,
    ssh_port: int,
    ssh_user_b: str,
    ssh_password_b: str,
    ssh_port_b: int,
) -> tuple[str, str, int]:
    """节点 B：用户非空则用 B 的账号；密码空则回退 A；端口 <=0 则回退 A。"""
    u = (ssh_user_b or "").strip()
    if not u:
        return ssh_user, ssh_password, int(ssh_port)
    p = (ssh_password_b or "").strip()
    pwd = p if p else ssh_password
    port_b = int(ssh_port_b) if ssh_port_b else 0
    port = port_b if port_b > 0 else int(ssh_port)
    return u, pwd, port


def restart_dual(host_a: str, host_b: str,
                 container_a: str, container_b: str,
                 exec_cmd_a: str, exec_cmd_b: str,
                 ssh_user: str, ssh_password: str,
                 ssh_port: int = SSH_PORT,
                 ssh_user_b: str = "",
                 ssh_password_b: str = "",
                 ssh_port_b: int = 0) -> dict:
    """
    双机模型重启：并发在两台服务器上同时执行重启 + 启动命令。
    节点 B 可使用独立 SSH（见 _ssh_for_node_b）。
    """
    ub, pb, port_b = _ssh_for_node_b(
        ssh_user, ssh_password, ssh_port,
        ssh_user_b, ssh_password_b, ssh_port_b,
    )
    results = {}
    t_a = threading.Thread(
        target=_restart_node,
        args=(host_a, container_a, exec_cmd_a, ssh_user, ssh_password, ssh_port, results, "a"),
    )
    t_b = threading.Thread(
        target=_restart_node,
        args=(host_b, container_b, exec_cmd_b, ub, pb, port_b, results, "b"),
    )
    t_a.start()
    t_b.start()
    t_a.join(timeout=EXEC_TIMEOUT + 30)
    t_b.join(timeout=EXEC_TIMEOUT + 30)

    ok_a = results.get("a", {}).get("success", False)
    ok_b = results.get("b", {}).get("success", False)
    msg_a = results.get("a", {}).get("message", "无响应")
    msg_b = results.get("b", {}).get("message", "无响应")

    if ok_a and ok_b:
        return {"success": True, "message": f"双节点均已下发启动命令\nA: {msg_a}\nB: {msg_b}"}
    else:
        return {
            "success": False,
            "message": f"A({'成功' if ok_a else '失败'}): {msg_a}\nB({'成功' if ok_b else '失败'}): {msg_b}",
        }
