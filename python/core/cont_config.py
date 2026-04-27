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
class AsvOptionsConfig:
    """ASV continuous 选项配置（所有字段可选，使用官方默认值）"""
    bench: Optional[str] = None
    factor: Optional[float] = None
    machine: Optional[str] = None
    python: Optional[str] = None
    split: Optional[bool] = None
    only_changed: Optional[bool] = None
    show_stderr: Optional[bool] = None
    quick: Optional[bool] = None
    verbose: Optional[bool] = None

    def to_cli_args(self) -> List[str]:
        """转换为 asv continuous CLI 参数（只包含非 None 的选项）"""
        args = []

        if self.bench:
            args.extend(["--bench", self.bench])
        if self.factor is not None:
            args.extend(["--factor", str(self.factor)])
        if self.machine:
            args.extend(["--machine", self.machine])
        if self.python:
            args.extend(["--python", self.python])
        if self.split:
            args.append("--split")
        if self.only_changed:
            args.append("--only-changed")
        if self.show_stderr:
            args.append("--show-stderr")
        if self.quick:
            args.append("--quick")
        if self.verbose:
            args.append("--verbose")

        return args


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
    commits: CommitsConfig
    scripts: Dict[str, str]
    asv_options: AsvOptionsConfig = field(default_factory=AsvOptionsConfig)
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

        # 验证 commits
        if not self.commits.base:
            errors.append("缺少 commits.base 配置")
        if not self.commits.branch:
            errors.append("缺少 commits.branch 配置")

        return errors

    def get_script_for_machine(self, machine_name: str) -> str:
        """获取指定机器的脚本"""
        return self.scripts.get(machine_name, "")


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

    # 解析 commits
    commits_data = data.get("commits", {})
    commits = CommitsConfig(
        base=commits_data.get("base", "HEAD~1"),
        branch=commits_data.get("branch", "HEAD")
    )

    # 解析 scripts
    scripts = data.get("scripts", {})

    # 解析 asv_options（可选）
    asv_data = data.get("asv_options", {})
    asv_options = AsvOptionsConfig(
        bench=asv_data.get("bench"),
        factor=asv_data.get("factor"),
        machine=asv_data.get("machine"),
        python=asv_data.get("python"),
        split=asv_data.get("split"),
        only_changed=asv_data.get("only_changed"),
        show_stderr=asv_data.get("show_stderr"),
        quick=asv_data.get("quick"),
        verbose=asv_data.get("verbose")
    )

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
        asv_options=asv_options,
        output=output,
        runtime=runtime
    )