"""Configuration handling for ASV continuous comparison"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import yaml


@dataclass
class ContMachineConfig:
    """单台机器配置"""
    name: str
    host: str                           # "local" 表示本地执行
    asv_project_dir: str
    hostname: Optional[str] = None      # 显示名称（可选）
    port: int = 22
    username: Optional[str] = None

    @property
    def display_name(self) -> str:
        """显示名称，优先使用 hostname"""
        return self.hostname if self.hostname else self.name

    @property
    def is_local(self) -> bool:
        return self.host == "local"


@dataclass
class CommitsConfig:
    """两个 commit 对比配置"""
    base: str        # 基准 commit
    branch: str      # 测试 commit


@dataclass
class ContOutputConfig:
    """输出配置"""
    dir: str = "./cont_results"
    custom_info: Optional[str] = None


@dataclass
class ContRuntimeConfig:
    """运行时配置"""
    ssh_timeout: int = 30
    log_level: str = "INFO"
    timeout: int = 3600


@dataclass
class ContConfig:
    """ASV continuous 完整配置"""
    machines: Dict[str, ContMachineConfig]
    scripts: Dict[str, str]
    commits: Optional[CommitsConfig] = None  # 可选，作为模板变量
    output: ContOutputConfig = field(default_factory=ContOutputConfig)
    runtime: ContRuntimeConfig = field(default_factory=ContRuntimeConfig)

    def validate(self) -> List[str]:
        """验证配置，返回错误列表"""
        errors = []

        if not self.machines:
            errors.append("缺少 machines 配置")

        # 验证每台机器的必填字段
        for name, machine in self.machines.items():
            if not machine.host:
                errors.append(f"机器 {name} 缺少 host 配置")
            if not machine.asv_project_dir:
                errors.append(f"机器 {name} 缺少 asv_project_dir 配置")
            if not machine.is_local and not machine.username:
                errors.append(f"远程机器 {name} 缺少 username 配置")

        return errors

    def get_script_for_machine(self, machine_name: str) -> str:
        """获取指定机器的脚本，替换模板变量"""
        script = self.scripts.get(machine_name, "")
        machine = self.machines.get(machine_name)
        if machine:
            script = script.replace("{work_dir}", machine.asv_project_dir)
        if self.commits:
            script = script.replace("{base}", self.commits.base)
            script = script.replace("{branch}", self.commits.branch)
        return script


def load_cont_config(config_path: str) -> ContConfig:
    """加载 YAML 配置文件"""
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)

    # 解析 machines
    machines = {}
    for name, m in data.get("machines", {}).items():
        machines[name] = ContMachineConfig(
            name=name,
            host=m["host"],
            asv_project_dir=m["asv_project_dir"],
            hostname=m.get("hostname"),
            port=m.get("port", 22),
            username=m.get("username")
        )

    # 解析 commits（可选，作为模板变量）
    commits_data = data.get("commits", {})
    commits = None
    if commits_data:
        commits = CommitsConfig(
            base=commits_data.get("base", "HEAD~1"),
            branch=commits_data.get("branch", "HEAD")
        )

    # 解析 scripts
    scripts = data.get("scripts", {})

    # 解析 output（可选）
    output_data = data.get("output", {})
    output = ContOutputConfig(
        dir=output_data.get("dir", "./cont_results"),
        custom_info=output_data.get("custom_info")
    )

    # 解析 runtime（可选）
    runtime_data = data.get("runtime", {})
    runtime = ContRuntimeConfig(
        ssh_timeout=runtime_data.get("ssh_timeout", 30),
        log_level=runtime_data.get("log_level", "INFO"),
        timeout=runtime_data.get("timeout", 3600)
    )

    return ContConfig(
        machines=machines,
        commits=commits,
        scripts=scripts,
        output=output,
        runtime=runtime
    )