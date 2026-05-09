"""Configuration handling for performance config collection (collect mode)"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import yaml

from core.machine_config import MachineConfig


@dataclass
class CollectOutputConfig:
    """输出配置"""
    dir: str = "./perf_results"
    custom_info: Optional[str] = None


@dataclass
class CollectRuntimeConfig:
    """运行时配置"""
    ssh_timeout: int = 30           # SSH 连接超时 (秒)
    execution_timeout: int = 300    # 命令执行超时 (秒)，默认 5 分钟（采集命令较快）
    log_level: str = "INFO"


@dataclass
class CollectConfig:
    """完整采集配置"""
    machines: Dict[str, MachineConfig]
    collect_scripts: Dict[str, str]             # 每台机器的环境初始化脚本
    output: CollectOutputConfig
    runtime: CollectRuntimeConfig               # 运行时配置
    export: Dict[str, str]                      # 全局环境变量（可选）

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

        # 验证 scripts（可选）中的机器名都在 machines 中
        for name in self.collect_scripts.keys():
            if name not in self.machines:
                errors.append(f"脚本 {name} 没有对应的机器配置")

        return errors

    def get_script_for_machine(self, machine_name: str) -> Optional[str]:
        """获取指定机器的脚本（可选）"""
        return self.collect_scripts.get(machine_name)


def load_collect_config(config_path: str) -> CollectConfig:
    """加载采集配置 YAML 文件"""
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)

    # 解析 machines
    machines = {}
    for name, m in data.get("machines", {}).items():
        machines[name] = MachineConfig(
            name=name,
            host=m["host"],
            hostname=m.get("hostname"),       # 可选的显示名称
            port=m.get("port", 22),
            username=m.get("username"),
            identity_file=m.get("identity_file")
        )

    # 解析 collect_scripts（兼容旧版 scripts 字段名）
    collect_scripts = data.get("collect_scripts", data.get("scripts", {}))

    # 解析 output
    output_data = data.get("output", {})

    # 解析 runtime
    runtime_data = data.get("runtime", {})

    return CollectConfig(
        machines=machines,
        collect_scripts=collect_scripts,
        output=CollectOutputConfig(
            dir=output_data.get("dir", "./perf_results"),
            custom_info=output_data.get("custom_info")
        ),
        runtime=CollectRuntimeConfig(
            ssh_timeout=runtime_data.get("ssh_timeout", 30),
            execution_timeout=runtime_data.get("execution_timeout", 300),
            log_level=runtime_data.get("log_level", "INFO")
        ),
        export=data.get("export", {})
    )
