"""Configuration handling for performance config collection"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import yaml


@dataclass
class CollectMachineConfig:
    """采集机器配置"""
    name: str
    host: str                           # "local" 表示本地执行
    port: int = 22
    username: Optional[str] = None

    @property
    def display_name(self) -> str:
        """显示名称，默认使用 name"""
        return self.name

    @property
    def is_local(self) -> bool:
        return self.host == "local"


@dataclass
class CollectOutputConfig:
    """输出配置"""
    dir: str = "./perf_results"
    custom_info: Optional[str] = None


@dataclass
class CollectConfig:
    """完整采集配置"""
    machines: Dict[str, CollectMachineConfig]
    scripts: Dict[str, str]             # 每台机器的环境初始化脚本
    output: CollectOutputConfig

    def validate(self) -> List[str]:
        """验证配置，返回错误列表"""
        errors = []

        # 至少需要 1 台机器
        if len(self.machines) < 1:
            errors.append(f"至少需要配置 1 台机器，当前 {len(self.machines)} 台")

        # 验证每台机器的必填字段
        for name, machine in self.machines.items():
            if not machine.host:
                errors.append(f"机器 {name} 缺少 host 配置")
            if not machine.is_local and not machine.username:
                errors.append(f"远程机器 {name} 缺少 username 配置")

        # 验证 scripts（可选）
        for name in self.scripts.keys():
            if name not in self.machines:
                errors.append(f"脚本 {name} 没有对应的机器配置")

        return errors

    def get_script_for_machine(self, machine_name: str) -> Optional[str]:
        """获取指定机器的脚本（可选）"""
        return self.scripts.get(machine_name)


def load_collect_config(config_path: str) -> CollectConfig:
    """加载采集配置 YAML 文件"""
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)

    # 解析 machines
    machines = {}
    for name, m in data.get("machines", {}).items():
        machines[name] = CollectMachineConfig(
            name=name,
            host=m["host"],
            port=m.get("port", 22),
            username=m.get("username")
        )

    # 解析 scripts（可选）
    scripts = data.get("scripts", {})

    # 解析 output
    output_data = data.get("output", {})

    return CollectConfig(
        machines=machines,
        scripts=scripts,
        output=CollectOutputConfig(
            dir=output_data.get("dir", "./perf_results"),
            custom_info=output_data.get("custom_info")
        )
    )