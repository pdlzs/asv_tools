"""cmp command implementation"""

import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from core.config import Config, load_config
from core.executor import execute_on_machine
from core.parallel_executor import execute_parallel, execute_serial, ExecutionResult
from core.downloader import download_results
from core.perf_collector import PerfCollector, perf_config_to_yaml
from core.perf_comparator import PerfComparator
from core.template import render_template, build_export_statements
from core.log_utils import start_log_tee, stop_log_tee
from ssh_utils import test_connection
from asv_compare_wrapper import compare_results


def setup_logging(verbose: bool = False):
    """设置日志输出"""
    import logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(message)s')


def run_collect_for_cmp(config: Config, output_dir: Path,
                        dry_run: bool = False, verbose: bool = False) -> bool:
    """在 cmp 流程中执行 collect 采集

    Args:
        config: cmp 配置
        output_dir: 输出目录
        dry_run: 是否只显示命令不执行
        verbose: 详细输出模式

    Returns:
        是否成功采集所有机器配置
    """
    perf_dir = output_dir / "perf_config"
    perf_dir.mkdir(parents=True, exist_ok=True)

    configs = []
    for machine_name, machine in config.machines.items():
        print(f"\n{'='*50}")
        print(f"采集 {machine_name} 性能配置...")
        print(f"{'='*50}")

        script = config.get_collect_script_for_machine(machine_name)

        # 渲染 export 模板变量 + 前置 export 语句
        if script and config.export:
            script = build_export_statements(config.export) + render_template(script, **config.export)

        if dry_run:
            print(f"[DRY-RUN] 将在 {machine_name} 上执行采集脚本:")
            collector = PerfCollector(
                machine, script, verbose,
                ssh_timeout=config.runtime.ssh_timeout,
                execution_timeout=config.runtime.execution_timeout
            )
            print(collector._build_collect_script())
            continue

        collector = PerfCollector(
            machine, script, verbose,
            ssh_timeout=config.runtime.ssh_timeout,
            execution_timeout=config.runtime.execution_timeout
        )

        # 测试连接
        if not collector.test_connection():
            print(f"[{machine_name}] 连接失败", file=sys.stderr)
            continue

        # 执行采集
        perf_config = collector.collect()
        if perf_config is None:
            print(f"[{machine_name}] 采集失败", file=sys.stderr)
            continue

        configs.append(perf_config)

        # 保存单机配置
        yaml_content = perf_config_to_yaml(perf_config)
        output_file = perf_dir / f"{machine_name}_perf.yaml"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        print(f"[{machine_name}] 配置已保存: {output_file}")

    if dry_run:
        print("\n[DRY-RUN] 采集预览完成")
        return True

    # 生成对比报告
    if len(configs) >= 2:
        print(f"\n{'='*50}")
        print("生成性能配置对比报告...")
        print(f"{'='*50}")

        comparator = PerfComparator(configs)
        report = comparator.compare()

        report_file = perf_dir / "perf_compare.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"对比报告已保存: {report_file}")
    elif len(configs) == 1:
        print("\n仅采集到一台机器配置，跳过对比报告生成")
    else:
        print("\n所有机器采集失败", file=sys.stderr)
        return False

    return len(configs) == len(config.machines)


def create_output_dir(config: Config, args) -> Tuple[Path, str]:
    """创建输出目录

    Returns:
        (output_dir, timestamp) 元组
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 确定自定义标识（支持 export 变量模板渲染）
    # 优先使用命令行参数，其次配置文件，都支持模板渲染
    custom_info = args.info or config.output.custom_info
    if custom_info and config.export:
        custom_info = render_template(custom_info, **config.export)

    if custom_info:
        dir_name = f"asv_compare_{timestamp}_{custom_info}"
    else:
        dir_name = f"asv_compare_{timestamp}"

    output_dir = Path(args.output_dir if args.output_dir else config.output.dir)
    result_dir = output_dir / dir_name
    result_dir.mkdir(parents=True, exist_ok=True)

    print(f"输出目录: {result_dir}")
    return result_dir, timestamp


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
    output_dir, timestamp = create_output_dir(config, args)

    # 获取服务器显示名称
    machine_names = list(config.machines.keys())
    server1_display = config.machines[machine_names[0]].display_name
    server2_display = config.machines[machine_names[1]].display_name

    # 5. 开始日志 Tee（保存终端输出到文件）
    log_filename = f"{server1_display}_vs_{server2_display}_{timestamp}.log.txt"
    tee = start_log_tee(output_dir, log_filename)

    try:
        # 6. 测试连接
        if not args.dry_run:
            for name, machine in config.machines.items():
                if not machine.is_local:
                    print(f"测试连接到 {name} ({machine.host})...")
                    if not test_connection(machine.host, machine.username, machine.port, machine.identity_file):
                        print(f"无法连接到 {name}", file=sys.stderr)
                        return 1
            print("SSH 连接验证成功")

        # 7. 执行 collect 采集（可选）
        if config.compare.collect and not args.skip_run:
            print("\n采集性能配置 (collect=true)...")
            if not run_collect_for_cmp(config, output_dir, args.dry_run, args.verbose):
                print("性能配置采集失败", file=sys.stderr)
                return 1

        # 8. 执行脚本（可选跳过）
        if args.skip_run:
            print("跳过 ASV 运行 (--skip-run)")
        elif not args.dry_run:
            # 构建脚本字典
            scripts = {name: config.get_compare_script_for_machine(name) for name in config.machines}

            if config.output.parallel:
                # 并行执行
                results = execute_parallel(
                    machines=config.machines,
                    scripts=scripts,
                    export_vars=config.export,
                    ssh_timeout=config.runtime.ssh_timeout,
                    execution_timeout=config.runtime.execution_timeout,
                    show_progress=True,
                    progress_lines=config.output.progress_lines
                )

                # 输出各机器的日志（按顺序）
                for result in results:
                    print(f"\n{'='*50}")
                    print(f"{result.machine_name} 执行日志 (耗时: {result.duration:.1f}s)")
                    print(f"{'='*50}")
                    if result.output:
                        print(result.output)
                    if result.success:
                        print(f"[{result.machine_name}] 执行完成")
                    else:
                        print(f"[{result.machine_name}] 执行失败", file=sys.stderr)

                # 检查是否全部成功
                if not all(r.success for r in results):
                    print("部分机器执行失败", file=sys.stderr)
                    return 1
            else:
                # 串行执行（保持原有逻辑，实时输出）
                for name, machine in config.machines.items():
                    script = config.get_compare_script_for_machine(name)
                    if not execute_on_machine(
                        machine, script, args.dry_run, args.verbose,
                        export_vars=config.export,
                        ssh_timeout=config.runtime.ssh_timeout,
                        execution_timeout=config.runtime.execution_timeout
                    ):
                        print(f"在 {name} 上执行脚本失败", file=sys.stderr)
                        return 1
        else:
            # dry-run 模式下显示脚本
            for name, machine in config.machines.items():
                script = config.get_compare_script_for_machine(name)
                execute_on_machine(
                    machine, script, dry_run=True, verbose=args.verbose,
                    export_vars=config.export,
                    ssh_timeout=config.runtime.ssh_timeout,
                    execution_timeout=config.runtime.execution_timeout
                )

        # 9. 下载结果
        server1_name = machine_names[0]
        server2_name = machine_names[1]

        server1_dir = output_dir / f"{server1_name}_results"
        server2_dir = output_dir / f"{server2_name}_results"

        for name, machine in config.machines.items():
            target_dir = output_dir / f"{name}_results"
            if not download_results(
                machine, target_dir, args.dry_run, args.verbose,
                ssh_timeout=config.runtime.ssh_timeout
            ):
                print(f"从 {name} 下载结果失败", file=sys.stderr)
                return 1

        # 10. 执行对比（非 dry-run 模式）
        if not args.dry_run:
            if not compare_results(
                str(server1_dir),
                str(server2_dir),
                server1_display,
                server2_display,
                output_dir,
                show_all=config.compare.show_all,
                verbose=args.verbose,
                timestamp=timestamp,
                skip_excel=config.output.skip_excel,
                skip_ratio_na=config.output.skip_ratio_na
            ):
                print("ASV 结果对比失败", file=sys.stderr)
                return 1

        print(f"\n完成！结果保存在: {output_dir}")
        print(f"日志文件: {log_filename}")
        return 0

    finally:
        # 11. 关闭日志 Tee
        stop_log_tee(tee)