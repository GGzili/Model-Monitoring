from pydantic import BaseModel
from typing import Optional


class ModelTargetCreate(BaseModel):
    name: str
    # 主节点
    host: str
    port: int
    container: str
    exec_cmd: str = ""
    # 双机第二节点（留空=单机）
    host_b: str = ""
    port_b: int = 0
    container_b: str = ""
    exec_cmd_b: str = ""
    # SSH
    ssh_user: str = "appadmin"
    ssh_password: str = ""
    ssh_port: int = 22
    # 检测
    interval: int = 300
    enabled: bool = True


class ModelTargetUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    container: Optional[str] = None
    exec_cmd: Optional[str] = None
    host_b: Optional[str] = None
    port_b: Optional[int] = None
    container_b: Optional[str] = None
    exec_cmd_b: Optional[str] = None
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_port: Optional[int] = None
    interval: Optional[int] = None
    enabled: Optional[bool] = None


class ModelTargetOut(BaseModel):
    id: int
    name: str
    host: str
    port: int
    container: str
    exec_cmd: str
    host_b: str
    port_b: int
    container_b: str
    exec_cmd_b: str
    ssh_user: str
    ssh_password: str
    ssh_port: int
    interval: int
    enabled: bool
    created_at: str

    class Config:
        from_attributes = True


class CheckResultOut(BaseModel):
    id: int
    model_id: int
    status: str
    latency_ms: Optional[int]
    error_msg: Optional[str]
    checked_at: str


class RestartResult(BaseModel):
    success: bool
    message: str
