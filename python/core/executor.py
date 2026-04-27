"""Script executor for both local and remote machines"""

from typing import Optional

from core.config import MachineConfig
from ssh_utils import SSHClient, SSHConfig


def execute_on_machine(
    machine: MachineConfig,
    script: str,
    dry_run: bool = False,
    verbose: bool = False
) -> bool:
    """
    在指定机器上执行脚本

    Args:
        machine: 机器配置
        script: 脚本内容（支持 {work_dir} 占位符）
        dry_run: 是否为干运行模式
        verbose: 是否显示详细输出

    Returns:
        成功返回 True
    """
    # 渲染脚本模板
    rendered_script = script.replace("{work_dir}", machine.asv_project_dir)

    if dry_run:
        print(f"[DRY-RUN] 将在 {machine.name} 上执行:")
        print("-" * 40)
        print(rendered_script)
        print("-" * 40)
        return True

    print(f"在 {machine.name} ({machine.host}) 上执行脚本...")

    # 创建 SSH 客户端
    config = SSHConfig(
        host=machine.host,
        username=machine.username or "",
        port=machine.port,
        timeout=30
    )

    client = SSHClient(config)

    # 测试连接（本地机器会直接返回 True）
    if not client.test_connection():
        print(f"无法连接到 {machine.name}")
        return False

    # 执行脚本
    success, output = client.execute(rendered_script, machine.asv_project_dir)

    if not success:
        print(f"在 {machine.name} 上执行脚本失败")
        print(output)
        return False

    if verbose:
        print(output)

    print(f"在 {machine.name} 上执行完成")
    return True