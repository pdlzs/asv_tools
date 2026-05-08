"""Script executor for both local and remote machines"""

from typing import Dict, Optional

from core.machine_config import MachineConfig
from core.template import render_template, build_export_statements
from ssh_utils import SSHClient, SSHConfig


def execute_on_machine(
    machine: MachineConfig,
    script: str,
    dry_run: bool = False,
    verbose: bool = False,
    stream_output: bool = True,
    export_vars: Optional[Dict[str, str]] = None,
    ssh_timeout: int = 30,
    execution_timeout: int = 3600
) -> bool:
    """
    在指定机器上执行脚本

    Args:
        machine: 机器配置
        script: 脚本内容（支持 {work_dir} 和 export 变量占位符）
        dry_run: 是否为干运行模式
        verbose: 是否显示详细输出
        stream_output: 是否实时输出脚本执行结果
        export_vars: 全局环境变量字典（可选）
        ssh_timeout: SSH 连接超时 (秒)
        execution_timeout: 命令执行超时 (秒)

    Returns:
        成功返回 True
    """
    # DEBUG: 打印机器信息
    print(f"[DEBUG] execute_on_machine: machine={machine.name}, host={machine.host}, port={machine.port}")
    print(f"[DEBUG] ssh_timeout={ssh_timeout}, execution_timeout={execution_timeout}")

    # 拼装模板变量上下文
    template_vars = {"work_dir": machine.asv_project_dir}
    if export_vars:
        template_vars.update(export_vars)

    # 渲染模板
    rendered_script = render_template(script, **template_vars)

    # 前置 export 语句
    prefix = build_export_statements(export_vars or {})
    final_script = prefix + rendered_script

    # DEBUG: 打印脚本长度
    print(f"[DEBUG] 最终脚本长度: {len(final_script)} 字符")

    if dry_run:
        print(f"[DRY-RUN] 将在 {machine.name} 上执行:")
        print("-" * 40)
        print(final_script)
        print("-" * 40)
        return True

    print(f"在 {machine.name} ({machine.host}) 上执行脚本...")
    print("-" * 40)

    # 创建 SSH 客户端
    config = SSHConfig(
        host=machine.host,
        username=machine.username or "",
        port=machine.port,
        timeout=ssh_timeout,
        execution_timeout=execution_timeout
    )

    client = SSHClient(config)

    # 测试连接（本地机器会直接返回 True）
    if not client.test_connection():
        print(f"[DEBUG] 连接测试失败")
        print(f"无法连接到 {machine.name}")
        return False

    print(f"[DEBUG] 连接测试成功")

    # 执行脚本
    success, output = client.execute(final_script, machine.asv_project_dir, stream_output=stream_output)

    print("-" * 40)

    # DEBUG: 打印执行结果
    print(f"[DEBUG] execute 返回: success={success}")
    if not success:
        print(f"[DEBUG] 失败原因: {output}")

    if not success:
        print(f"在 {machine.name} 上执行脚本失败")
        return False

    print(f"在 {machine.name} 上执行完成")
    return True
