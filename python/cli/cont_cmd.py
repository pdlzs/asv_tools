#!/usr/bin/env python3
"""ASV continuous 命令实现

在指定机器上对比两个 commit 的性能。
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List

from core.cont_config import load_cont_config
from ssh_utils import SSHClient, SSHConfig


def build_asv_continuous_command(config) -> List[str]:
    """构建 asv continuous 命令"""
    cmd = ["asv", "continuous"]

    # 添加 asv_options（只包含非 None 的选项）
    cmd.extend(config.asv_options.to_cli_args())

    # 添加 commits
    cmd.append(config.commits.base)
    cmd.append(config.commits.branch)

    return cmd


def run_asv_continuous_on_machine(machine, config, script: str, dry_run: bool = False) -> tuple:
    """在指定机器上运行 asv continuous

    Args:
        machine: ContMachineConfig
        config: ContConfig
        script: 执行前的脚本
        dry_run: 只显示命令，不执行

    Returns:
        (success, output, machine_name)
    """
    ssh_config = SSHConfig(
        host=machine.host,
        username=machine.username or "",
        port=machine.port,
        timeout=config.runtime.ssh_timeout
    )
    ssh_client = SSHClient(ssh_config)

    machine_name = machine.display_name
    work_dir = machine.asv_project_dir

    # 构建 asv continuous 命令
    asv_cmd = build_asv_continuous_command(config)

    # 合成完整命令：先执行 script，再执行 asv continuous
    if script:
        # 替换 {work_dir} 占位符
        script = script.replace("{work_dir}", work_dir)
        full_cmd = f"{script}\n{subprocess.list2cmdline(asv_cmd)}"
    else:
        full_cmd = subprocess.list2cmdline(asv_cmd)

    print(f"\n{'='*50}")
    print(f"🔧 机器: {machine_name}")
    print(f"📁 目录: {work_dir}")
    print(f"🔀 对比: {config.commits.base} vs {config.commits.branch}")
    print(f"📋 命令: {full_cmd}")
    print(f"{'='*50}")

    if dry_run:
        print("📋 Dry-run 模式，跳过执行")
        return True, "dry-run", machine_name

    # 执行命令
    success, output = ssh_client.execute(full_cmd, work_dir=work_dir, stream_output=True)

    return success, output, machine_name


def save_output_summary(config, results: List[tuple]) -> None:
    """保存输出摘要"""
    output_dir = Path(config.output.dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    info = config.output.custom_info or "continuous"
    filename = f"{info}_{timestamp}_summary.txt"

    output_file = output_dir / filename

    # 写入摘要
    content_lines = [
        "ASV Continuous Comparison Summary",
        "=" * 50,
        f"Time: {datetime.now().isoformat()}",
        f"Base Commit: {config.commits.base}",
        f"Branch Commit: {config.commits.branch}",
        "",
        "ASV Options:",
    ]

    for name, value in [
        ('bench', config.asv_options.bench),
        ('factor', config.asv_options.factor),
        ('machine', config.asv_options.machine),
        ('python', config.asv_options.python),
        ('split', config.asv_options.split),
        ('only_changed', config.asv_options.only_changed),
        ('show_stderr', config.asv_options.show_stderr),
        ('quick', config.asv_options.quick),
        ('verbose', config.asv_options.verbose),
    ]:
        content_lines.append(f"  {name}: {value or 'default'}")

    content_lines.append("")
    content_lines.append("Results:")
    content_lines.append("-" * 50)

    for machine_name, success, output in results:
        status = "✓ SUCCESS" if success else "✗ FAILED"
        content_lines.append(f"Machine: {machine_name} - {status}")

    output_file.write_text('\n'.join(content_lines))
    print(f"\n📄 输出摘要已保存: {output_file}")


def run_continuous(args) -> int:
    """执行 continuous 对比命令

    Args:
        args: CLI参数

    Returns:
        退出码
    """
    config_file = args.config_file

    # 加载配置
    try:
        config = load_cont_config(config_file)
    except Exception as e:
        print(f"❌ 加载配置文件失败: {e}")
        return 1

    # 验证配置
    errors = config.validate()
    if errors:
        print(f"❌ 配置验证失败:")
        for err in errors:
            print(f"   - {err}")
        return 1

    # 显示配置信息
    print("="*50)
    print("📋 ASV Continuous 配置")
    print("="*50)
    print(f"机器数量: {len(config.machines)}")
    for name, machine in config.machines.items():
        location = "本地" if machine.is_local else f"{machine.username}@{machine.host}:{machine.port}"
        print(f"   - {machine.display_name}: {location}")

    print(f"\n对比 Commits:")
    print(f"   基准: {config.commits.base}")
    print(f"   测试: {config.commits.branch}")

    # 显示 ASV 选项（只显示非 None 的）
    non_default_options = []
    for name, value in [
        ('bench', config.asv_options.bench),
        ('factor', config.asv_options.factor),
        ('machine', config.asv_options.machine),
        ('python', config.asv_options.python),
        ('split', config.asv_options.split),
        ('only_changed', config.asv_options.only_changed),
        ('show_stderr', config.asv_options.show_stderr),
        ('quick', config.asv_options.quick),
        ('verbose', config.asv_options.verbose),
    ]:
        if value is not None:
            non_default_options.append(f"{name}={value}")

    if non_default_options:
        print(f"\nASV 选项: {', '.join(non_default_options)}")
    else:
        print(f"\nASV 选项: 使用官方默认值")

    print(f"\n输出目录: {config.output.dir}")
    print("="*50)

    # 测试 SSH 连接
    print("\n🔍 测试机器连接...")
    for name, machine in config.machines.items():
        if machine.is_local:
            print(f"   ✓ {machine.display_name}: 本地执行")
        else:
            ssh_config = SSHConfig(
                host=machine.host,
                username=machine.username or "",
                port=machine.port,
                timeout=config.runtime.ssh_timeout
            )
            ssh_client = SSHClient(ssh_config)
            if ssh_client.test_connection():
                print(f"   ✓ {machine.display_name}: 连接成功")
            else:
                print(f"   ✗ {machine.display_name}: 连接失败")
                print(f"      请检查 SSH 配置或运行 'python main.py ssh-setup {config_file}'")
                return 1

    # 在每台机器上执行 asv continuous
    results = []
    for name, machine in config.machines.items():
        script = config.get_script_for_machine(name)
        success, output, machine_name = run_asv_continuous_on_machine(
            machine, config, script, dry_run=args.dry_run
        )
        results.append((machine_name, success, output))

    # 汇总结果
    print("\n" + "="*50)
    print("📊 执行结果汇总:")
    print("="*50)

    success_count = sum(1 for _, success, _ in results if success)
    for machine_name, success, output in results:
        status = "✓" if success else "✗"
        print(f"   {status} {machine_name}: {'成功' if success else '失败'}")

    # 保存输出摘要
    if not args.dry_run and config.output.dir:
        save_output_summary(config, results)

    print()
    if success_count == len(results):
        print(f"✅ 全部 {len(results)} 台机器执行成功!")
        return 0
    else:
        print(f"⚠️  {success_count}/{len(results)} 台机器执行成功")
        return 1