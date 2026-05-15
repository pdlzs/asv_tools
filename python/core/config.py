"""Configuration handling for ASV benchmark comparison (cmp mode)"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import yaml

from core.machine_config import MachineConfig


@dataclass
class CompareConfig:
    """对比配置"""
    show_all: bool = True
    collect: bool = False          # 是否在 compare 前执行 collect 采集


@dataclass
class OutputConfig:
    """输出配置"""
    dir: str = "./cmp_results"
    custom_info: Optional[str] = None
    skip_excel: bool = False           # 是否跳过生成 Excel 文件
    skip_ratio_na: bool = False        # 是否跳过 Ratio 为 n/a 的行（影响 TXT 和 Excel）


@dataclass
class RuntimeConfig:
    """运行时配置"""
    ssh_timeout: int = 30           # SSH 连接超时 (秒)
    execution_timeout: int = 3600   # 命令执行超时 (秒)，默认 1 小时
    log_level: str = "INFO"


@dataclass
class Config:
    """完整配置"""
    machines: Dict[str, MachineConfig]
    compare_scripts: Dict[str, str]     # ASV compare 执行脚本
    collect_scripts: Dict[str, str]     # collect 采集脚本（可选）
    compare: CompareConfig
    output: OutputConfig
    runtime: RuntimeConfig
    export: Dict[str, str]              # 全局环境变量（可选）

    def validate(self) -> List[str]:
        """验证配置，返回错误列表"""
        errors = []

        # 必须恰好 2 台机器
        if len(self.machines) != 2:
            errors.append(f"必须恰好配置 2 台机器，当前 {len(self.machines)} 台")

        # 验证每台机器的必填字段
        for name, machine in self.machines.items():
            if not machine.host:
                errors.append(f"机器 {name} 缺少 host 配置")
            if not machine.asv_project_dir:
                errors.append(f"机器 {name} 缺少 asv_project_dir 配置")
            if not machine.is_local and not machine.username:
                errors.append(f"远程机器 {name} 缺少 username 配置")

        # 验证每台机器都有对应的 compare_scripts
        for name in self.machines.keys():
            if name not in self.compare_scripts:
                errors.append(f"机器 {name} 缺少对应的 compare_scripts 配置")

        return errors

    def get_compare_script_for_machine(self, machine_name: str) -> str:
        """获取指定机器的 compare 脚本"""
        return self.compare_scripts.get(machine_name, "")

    def get_collect_script_for_machine(self, machine_name: str) -> str:
        """获取指定机器的 collect 脚本（可选）"""
        return self.collect_scripts.get(machine_name, "")


def load_config(config_path: str) -> Config:
    """加载 YAML 配置文件"""
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)

    # 解析 machines
    machines = {}
    for name, m in data.get("machines", {}).items():
        machines[name] = MachineConfig(
            name=name,
            host=m["host"],
            hostname=m.get("hostname"),
            port=m.get("port", 22),
            username=m.get("username"),
            identity_file=m.get("identity_file"),
            asv_project_dir=m.get("asv_project_dir")
        )

    # 解析脚本配置
    # compare_scripts: 优先使用 compare_scripts，兼容旧版 scripts
    compare_scripts = data.get("compare_scripts", data.get("scripts", {}))
    collect_scripts = data.get("collect_scripts", {})

    # 解析其他配置
    compare_data = data.get("compare", {})
    output_data = data.get("output", {})
    runtime_data = data.get("runtime", {})

    return Config(
        machines=machines,
        compare_scripts=compare_scripts,
        collect_scripts=collect_scripts,
        compare=CompareConfig(
            show_all=compare_data.get("show_all", True),
            collect=compare_data.get("collect", False)
        ),
        output=OutputConfig(
            dir=output_data.get("dir", "./cmp_results"),
            custom_info=output_data.get("custom_info"),
            skip_excel=output_data.get("skip_excel", False),
            skip_ratio_na=output_data.get("skip_ratio_na", False)
        ),
        runtime=RuntimeConfig(
            ssh_timeout=runtime_data.get("ssh_timeout", 30),
            execution_timeout=runtime_data.get("execution_timeout", 3600),
            log_level=runtime_data.get("log_level", "INFO")
        ),
        export=data.get("export", {})
    )
