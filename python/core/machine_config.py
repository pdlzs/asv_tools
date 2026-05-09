"""统一的机器配置数据类 — 三种模式共用"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MachineConfig:
    """单台机器配置 — cmp / cont / collect 三种模式统一使用"""
    name: str
    host: str                               # "local" 表示本地执行
    hostname: Optional[str] = None           # 显示名称（可选）
    port: int = 22
    username: Optional[str] = None
    identity_file: Optional[str] = None      # SSH 密钥文件路径（可选）
    asv_project_dir: Optional[str] = None    # ASV 项目目录（collect 模式不需要）

    @property
    def display_name(self) -> str:
        """显示名称，优先使用 hostname"""
        return self.hostname if self.hostname else self.name

    @property
    def is_local(self) -> bool:
        return self.host == "local"
