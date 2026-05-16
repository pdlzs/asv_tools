"""并行执行器 - 在多台机器上并行执行脚本"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
import threading
import time
import sys

from core.machine_config import MachineConfig
from core.executor import execute_on_machine


@dataclass
class ExecutionResult:
    """执行结果"""
    machine_name: str
    success: bool
    output: str
    duration: float  # 执行时长（秒）


class ProgressDisplay:
    """多行进度状态显示器 - 显示状态、时长和最新输出"""

    def __init__(self, machine_names: List[str], show_last_lines: int = 2):
        """
        Args:
            machine_names: 机器名称列表（按顺序）
            show_last_lines: 显示每台机器最近几行输出（默认 2 行）
        """
        self.machine_names = machine_names
        self.show_last_lines = show_last_lines
        self.status: Dict[str, str] = {name: "等待" for name in machine_names}
        self.durations: Dict[str, float] = {name: 0.0 for name in machine_names}
        self.start_times: Dict[str, float] = {}
        self.last_lines: Dict[str, List[str]] = {name: [] for name in machine_names}
        self._lock = threading.Lock()
        self._initialized = False
        # 每台机器显示: 1行状态 + show_last_lines行输出 = (1 + show_last_lines) 行
        self._lines_per_machine = 1 + show_last_lines
        self._total_lines = len(machine_names) * self._lines_per_machine

    def start(self, machine_name: str):
        """标记机器开始执行"""
        with self._lock:
            self.status[machine_name] = "执行中"
            self.start_times[machine_name] = time.time()
            self.last_lines[machine_name] = []

            # 第一次初始化时打印空行占位
            if not self._initialized:
                for _ in range(self._total_lines):
                    print()
                self._initialized = True

            self._update_display()

    def add_output_line(self, machine_name: str, line: str):
        """添加输出行（用于回调）"""
        with self._lock:
            # 保存最新几行
            self.last_lines[machine_name].append(line)
            if len(self.last_lines[machine_name]) > self.show_last_lines:
                self.last_lines[machine_name] = self.last_lines[machine_name][-self.show_last_lines:]
            self._update_display()

    def finish(self, machine_name: str, success: bool):
        """标记机器执行完成"""
        with self._lock:
            if machine_name in self.start_times:
                self.durations[machine_name] = time.time() - self.start_times[machine_name]
            self.status[machine_name] = "完成" if success else "失败"
            self._update_display()

    def _update_display(self):
        """更新多行状态显示"""
        # ANSI 控制码：
        # \033[{n}A - 向上移动 n 行
        # \033[K   - 清除当前行到行尾
        # \033[G   - 移动到行首

        all_lines = []
        for name in self.machine_names:
            state = self.status.get(name, "等待")
            duration = self.durations.get(name, 0.0)

            # 计算实时时长
            if state == "执行中" and name in self.start_times:
                duration = time.time() - self.start_times[name]

            mins, secs = int(duration // 60), int(duration % 60)
            status_icon = {"执行中": "⏳", "完成": "✓", "失败": "✗", "等待": "○"}.get(state, "○")

            # 状态行
            status_line = f"\033[G\033[K {status_icon} [{name}] {state}... {mins:02d}:{secs:02d}"
            all_lines.append(status_line)

            # 输出行（最近几行）
            last_output = self.last_lines.get(name, [])
            for _ in range(self.show_last_lines):
                all_lines.append("\033[G\033[K")  # 空行占位

            # 填充最近的输出
            for i, line in enumerate(last_output[-self.show_last_lines:]):
                # 截断过长的行（显示宽度）
                display_line = line[:80] if len(line) > 80 else line
                # 输出行用灰色或普通颜色，与状态行区分
                idx = len(all_lines) - self.show_last_lines + i
                all_lines[idx] = f"\033[G\033[K   · {display_line}"

        # 向上移动 total_lines 行，然后逐行打印更新
        if self._initialized:
            sys.stdout.write(f"\033[{self._total_lines}A")
            for line in all_lines:
                sys.stdout.write(line + "\n")
            sys.stdout.flush()

    def create_callback(self, machine_name: str) -> Callable:
        """为指定机器创建输出回调函数"""
        def callback(line: str):
            self.add_output_line(machine_name, line)
        return callback


def execute_single_machine(
    machine: MachineConfig,
    script: str,
    export_vars: Optional[Dict[str, str]] = None,
    ssh_timeout: int = 30,
    execution_timeout: int = 3600,
    progress: Optional[ProgressDisplay] = None
) -> ExecutionResult:
    """
    在单台机器上执行脚本（用于并行执行的工作函数）

    Args:
        machine: 机器配置
        script: 脚本内容
        export_vars: 全局环境变量
        ssh_timeout: SSH 连接超时
        execution_timeout: 执行超时
        progress: 进度显示器（可选）

    Returns:
        ExecutionResult 执行结果
    """
    from ssh_utils import SSHClient, SSHConfig
    from core.template import render_template, build_export_statements

    start_time = time.time()
    output_lines = []

    # 渲染模板
    template_vars = {"work_dir": machine.asv_project_dir}
    if export_vars:
        template_vars.update(export_vars)
    rendered_script = render_template(script, **template_vars)
    prefix = build_export_statements(export_vars or {})
    final_script = prefix + rendered_script

    # 创建 SSH 客户端
    config = SSHConfig(
        host=machine.host,
        username=machine.username or "",
        port=machine.port,
        identity_file=machine.identity_file,
        timeout=ssh_timeout,
        execution_timeout=execution_timeout
    )
    client = SSHClient(config)

    # 创建输出回调（用于进度显示）
    output_callback = None
    if progress:
        progress.start(machine.name)
        output_callback = progress.create_callback(machine.name)

    # 测试连接
    if not client.test_connection():
        duration = time.time() - start_time
        if progress:
            progress.finish(machine.name, False)
        return ExecutionResult(
            machine_name=machine.name,
            success=False,
            output=f"无法连接到 {machine.name}",
            duration=duration
        )

    # 执行脚本（使用回调实时更新进度，不实时打印到终端）
    def capture_callback(line: str):
        output_lines.append(line)
        if output_callback:
            output_callback(line)

    success, output = client.execute(
        final_script,
        machine.asv_project_dir,
        stream_output=False,  # 不实时打印到终端
        output_callback=capture_callback  # 通过回调捕获并更新进度
    )

    duration = time.time() - start_time

    if progress:
        progress.finish(machine.name, success)

    return ExecutionResult(
        machine_name=machine.name,
        success=success,
        output='\n'.join(output_lines),
        duration=duration
    )


def execute_parallel(
    machines: Dict[str, MachineConfig],
    scripts: Dict[str, str],
    export_vars: Optional[Dict[str, str]] = None,
    ssh_timeout: int = 30,
    execution_timeout: int = 3600,
    show_progress: bool = True,
    progress_lines: int = 10
) -> List[ExecutionResult]:
    """
    并行执行多台机器上的脚本

    Args:
        machines: 机器配置字典 {name: MachineConfig}
        scripts: 脚本字典 {name: script_content}
        export_vars: 全局环境变量
        ssh_timeout: SSH 连接超时
        execution_timeout: 执行超时
        show_progress: 是否显示进度
        progress_lines: 显示每台机器最近几行输出（默认 10）

    Returns:
        执行结果列表（按 machines 的顺序）
    """
    machine_names = list(machines.keys())
    results: Dict[str, ExecutionResult] = {}

    # 创建进度显示器
    progress = ProgressDisplay(machine_names, show_last_lines=progress_lines) if show_progress else None

    print(f"并行执行 {len(machines)} 台机器上的脚本...")

    # 使用 ThreadPoolExecutor 并行执行
    with ThreadPoolExecutor(max_workers=len(machines)) as executor:
        # 提交所有任务
        future_to_name = {}
        for name in machine_names:
            machine = machines[name]
            script = scripts.get(name, "")
            future = executor.submit(
                execute_single_machine,
                machine,
                script,
                export_vars,
                ssh_timeout,
                execution_timeout,
                progress
            )
            future_to_name[future] = name

        # 等待所有任务完成
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                result = future.result()
                results[name] = result
            except Exception as e:
                duration = 0.0
                if progress and name in progress.start_times:
                    duration = time.time() - progress.start_times[name]
                results[name] = ExecutionResult(
                    machine_name=name,
                    success=False,
                    output=f"执行异常: {str(e)}",
                    duration=duration
                )
                if progress:
                    progress.finish(name, False)

    # 按原始顺序返回结果
    ordered_results = [results[name] for name in machine_names]
    return ordered_results


def execute_serial(
    machines: Dict[str, MachineConfig],
    scripts: Dict[str, str],
    export_vars: Optional[Dict[str, str]] = None,
    ssh_timeout: int = 30,
    execution_timeout: int = 3600
) -> List[ExecutionResult]:
    """
    串行执行多台机器上的脚本（兼容模式）

    Args:
        machines: 机器配置字典
        scripts: 脚本字典
        export_vars: 全局环境变量
        ssh_timeout: SSH 连接超时
        execution_timeout: 执行超时

    Returns:
        执行结果列表（按 machines 的顺序）
    """
    machine_names = list(machines.keys())
    results = []

    print(f"串行执行 {len(machines)} 台机器上的脚本...")

    for name in machine_names:
        machine = machines[name]
        script = scripts.get(name, "")

        # 使用原来的 execute_on_machine（实时输出）
        start_time = time.time()
        success = execute_on_machine(
            machine,
            script,
            dry_run=False,
            verbose=False,
            stream_output=True,  # 实时输出
            export_vars=export_vars,
            ssh_timeout=ssh_timeout,
            execution_timeout=execution_timeout
        )
        duration = time.time() - start_time

        # 注意：execute_on_machine 不返回 output，这里用空字符串
        # 因为实时输出模式下日志已经打印到终端了
        results.append(ExecutionResult(
            machine_name=name,
            success=success,
            output="",  # 实时输出模式下日志已打印
            duration=duration
        ))

    return results