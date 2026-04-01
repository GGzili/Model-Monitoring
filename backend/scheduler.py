from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from checker import run_check
from database import get_conn, decrypt_target_row

scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def _job(model_id: int, host: str, port: int, model_name: str):
    run_check(model_id, host, port, model_name)


def _job_id(model_id: int) -> str:
    return f"check_{model_id}"


def add_job(model_id: int, host: str, port: int, interval: int, model_name: str = ""):
    scheduler.add_job(
        _job,
        trigger=IntervalTrigger(seconds=interval),
        id=_job_id(model_id),
        args=[model_id, host, port, model_name],
        replace_existing=True,
        max_instances=1,
    )


def remove_job(model_id: int):
    jid = _job_id(model_id)
    if scheduler.get_job(jid):
        scheduler.remove_job(jid)


def reload_all_jobs():
    """从数据库加载所有已启用的模型并注册定时任务。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, model_api_name, host, port, interval FROM model_targets WHERE enabled = 1"
        ).fetchall()
    for row in rows:
        d = decrypt_target_row(row)
        api_name = (d["model_api_name"] or "").strip() or (d["name"] or "").strip()
        add_job(d["id"], d["host"], d["port"], d["interval"], api_name)


def start():
    reload_all_jobs()
    scheduler.start()


def stop():
    scheduler.shutdown(wait=False)
