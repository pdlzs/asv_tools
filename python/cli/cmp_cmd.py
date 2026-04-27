"""cmp command implementation"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.config import Config, load_config
from core.executor import execute_on_machine
from core.downloader import download_results
from ssh_utils import test_connection
from asv_compare_wrapper import compare_results


def setup_logging(verbose: bool = False):
    """设置日志输出"""
    import logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(message)s')


def create_output_dir(config: Config, args) -> Path:
    """创建输出目录"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 确定自定义标识
    custom_info = args.info if args.info else config.output.custom_info

    if custom_info:
        dir_name = f"asv_compare_{timestamp}_{custom_info}"
    else:
        dir_name = f"asv_compare_{timestamp}"

    output_dir = Path(args.output_dir if args.output_dir else config.output.dir)
    result_dir = output_dir / dir_name
    result_dir.mkdir(parents=True, exist_ok=True)

    print(f"输出目录: {result_dir}")
    return result_dir


def run_compare(args) -> int:
    """主执行流程"""
    # 1. 加载配置
    try:
        config = load_config(args.config_file)
    except Exception as e:
        print(f"配置文件加载失败: {e}", file=sys.stderr)
        return 1

    # 2. 验证配置
    errors = config.validate()
    if errors:
        for err in errors:
            print(f"配置错误: {err}", file=sys.stderr)
        return 1

    # 3. 设置日志级别
    setup_logging(args.verbose)

    # 4. 创建输出目录
    output_dir = create_output_dir(config, args)

    # 5. 测试连接
    if not args.dry_run:
        for name, machine in config.machines.items():
            if not machine.is_local:
                print(f"测试连接到 {name} ({machine.host})...")
                if not test_connection(machine.host, machine.username, machine.port):
                    print(f"无法连接到 {name}", file=sys.stderr)
                    return 1
        print("SSH 连接验证成功")

    # 6. 执行脚本（可选跳过）
    if args.skip_run:
        print("跳过 ASV 运行 (--skip-run)")
    elif not args.dry_run:
        for name, machine in config.machines.items():
            script = config.get_script_for_machine(name)
            if not execute_on_machine(machine, script, args.dry_run, args.verbose):
                print(f"在 {name} 上执行脚本失败", file=sys.stderr)
                return 1
    else:
        # dry-run 模式下显示脚本
        for name, machine in config.machines.items():
            script = config.get_script_for_machine(name)
            execute_on_machine(machine, script, dry_run=True, verbose=args.verbose)

    # 7. 下载结果
    machine_names = list(config.machines.keys())
    server1_name = machine_names[0]
    server2_name = machine_names[1]

    # 获取 ASV compare 显示名称（优先使用 hostname）
    server1_display = config.machines[server1_name].display_name
    server2_display = config.machines[server2_name].display_name

    server1_dir = output_dir / f"{server1_name}_results"
    server2_dir = output_dir / f"{server2_name}_results"

    for name, machine in config.machines.items():
        target_dir = output_dir / f"{name}_results"
        if not download_results(machine, target_dir, args.dry_run, args.verbose):
            print(f"从 {name} 下载结果失败", file=sys.stderr)
            return 1

    # 8. 执行对比（非 dry-run 模式）
    if not args.dry_run:
        if not compare_results(
            str(server1_dir),
            str(server2_dir),
            server1_display,
            server2_display,
            output_dir,
            show_all=config.compare.show_all,
            verbose=args.verbose
        ):
            print("ASV 结果对比失败", file=sys.stderr)
            return 1

    print(f"\n完成！结果保存在: {output_dir}")
    return 0