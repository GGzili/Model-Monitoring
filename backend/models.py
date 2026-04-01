from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional


class ModelTargetCreate(BaseModel):
    """首次添加模型：除下方「可调项」外，其它字段写入后不可通过 API 修改。"""
    # 展示名可选；空则界面与卡片用 API 模型名
    name: str = ""
    # 推理/网关使用的 model 字段，必填（去空格后非空）
    model_api_name: str
    # 主节点
    host: str
    port: int
    container: str
    exec_cmd: str = ""
    # 双机
    host_b: str = ""
    port_b: int = 0
    container_b: str = ""
    exec_cmd_b: str = ""
    # SSH（仅创建时可写，之后 API 不返回、不可改）
    ssh_user: str = "appadmin"
    ssh_password: str = ""
    ssh_port: int = 22
    # 可调（创建时可设，之后仍可通过 PUT 修改）
    interval: int = 300
    enabled: bool = True
    gateway_enabled: bool = True
    gateway_max_concurrent: int = Field(default=1, ge=1, le=256)
    gateway_max_queue: int = Field(default=64, ge=0, le=100_000)

    @field_validator("model_api_name")
    @classmethod
    def strip_api_name(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("API 模型名不能为空")
        return s

    @field_validator("name", mode="before")
    @classmethod
    def strip_display_name(cls, v):
        if v is None:
            return ""
        return str(v).strip()


class ModelTargetTunableUpdate(BaseModel):
    """创建完成后仅允许修改这些字段。"""
    model_config = ConfigDict(extra="ignore")

    interval: Optional[int] = Field(None, ge=30)
    enabled: Optional[bool] = None
    gateway_enabled: Optional[bool] = None
    gateway_max_concurrent: Optional[int] = Field(None, ge=1, le=256)
    gateway_max_queue: Optional[int] = Field(None, ge=0, le=100_000)


class ModelTargetPublicOut(BaseModel):
    """列表/详情/创建/更新响应：不含 host/port/container/命令/SSH，仅 is_dual 表示是否双机。"""

    id: int
    name: str
    model_api_name: str
    is_dual: bool
    interval: int
    enabled: bool
    gateway_enabled: bool
    gateway_max_concurrent: int
    gateway_max_queue: int
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class DashboardRowOut(ModelTargetPublicOut):
    last_status: str
    last_latency_ms: Optional[int] = None
    last_checked_at: Optional[str] = None


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
