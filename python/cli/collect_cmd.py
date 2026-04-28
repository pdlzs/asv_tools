"""collect command implementation - performance configuration collection"""

import sys
from datetime import datetime
from pathlib import Path

from core.collect_config import CollectConfig, load_collect_config
from core.perf_collector import PerfCollector, perf_config_to_yaml
from core.perf_comparator import PerfComparator


def setup_logging(verbose: bool = False):
    """设置日志输出"""
    import logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(message)s')


def create_output_dir(config: CollectConfig, args) -> Path:
    """创建输出目录"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 确定自定义标识
    custom_info = args.info if hasattr(args, 'info') and args.info else config.output.custom_info

    if custom_info:
        dir_name = f"perf_config_{timestamp}_{custom_info}"
    else:
        dir_name = f"perf_config_{timestamp}"

    output_dir = Path(args.output_dir if hasattr(args, 'output_dir') and args.output_dir else config.output.dir)
    result_dir = output_dir / dir_name
    result_dir.mkdir(parents=True, exist_ok=True)

    print(f"输出目录: {result_dir}")
    return result_dir


def test_connections(config: CollectConfig, verbose: bool = False) -> bool:
    """测试所有机器的 SSH 连接"""
    from ssh_utils import test_connection

    for name, machine in config.machines.items():
        if machine.is_local:
            print(f"[{name}] 本地执行，跳过连接测试")
            continue

        print(f"[{name}] 测试连接到 {machine.host}...")
        if not test_connection(machine.host, machine.username, machine.port):
            print(f"[{name}] 无法连接到 {machine.host}", file=sys.stderr)
            return False

    print("SSH 连接验证成功")
    return True


def collect_from_machine(machine_name: str, config: CollectConfig,
                         dry_run: bool = False, verbose: bool = False) -> 'PerfConfig':
    """从单台机器采集性能配置"""
    machine = config.machines[machine_name]
    script = config.get_script_for_machine(machine_name)

    collector = PerfCollector(machine, script, verbose)

    if dry_run:
        print(f"[DRY-RUN] 将在 {machine_name} 上执行采集脚本:")
        print(collector._build_collect_script())
        return None

    # 测试连接
    if not collector.test_connection():
        print(f"[{machine_name}] 连接失败", file=sys.stderr)
        return None

    # 执行采集
    return collector.collect()


def save_perf_config(config: 'PerfConfig', output_dir: Path) -> Path:
    """保存单机性能配置到 YAML 文件"""
    yaml_content = perf_config_to_yaml(config)
    output_file = output_dir / f"{config.machine_name}_perf.yaml"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(yaml_content)

    print(f"[{config.machine_name}] 配置已保存: {output_file}")
    return output_file


def save_compare_report(report: str, output_dir: Path, config: CollectConfig) -> Path:
    """保存对比报告"""
    output_file = output_dir / "perf_compare.md"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"对比报告已保存: {output_file}")
    return output_file


def run_collect(args) -> int:
    """主执行流程"""
    # 1. 加载配置
    try:
        config = load_collect_config(args.config_file)
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

    # 5. 测试连接（非 dry-run）
    if not args.dry_run:
        if not test_connections(config, args.verbose):
            return 1

    # 6. 采集各机器配置
    configs = []
    for machine_name in config.machines.keys():
        print(f"\n{'='*50}")
        print(f"采集 {machine_name} 性能配置...")
        print(f"{'='*50}")

        perf_config = collect_from_machine(
            machine_name, config,
            dry_run=args.dry_run,
            verbose=args.verbose
        )

        if args.dry_run:
            continue

        if perf_config is None:
            print(f"[{machine_name}] 采集失败", file=sys.stderr)
            continue

        configs.append(perf_config)

        # 保存单机配置
        save_perf_config(perf_config, output_dir)

    if args.dry_run:
        print("\n[DRY-RUN] 命令预览完成")
        return 0

    # 7. 生成对比报告
    if len(configs) >= 2:
        print(f"\n{'='*50}")
        print("生成性能配置对比报告...")
        print(f"{'='*50}")

        comparator = PerfComparator(configs)
        report = comparator.compare()
        save_compare_report(report, output_dir, config)
    elif len(configs) == 1:
        print("\n仅采集到一台机器配置，跳过对比报告生成")
    else:
        print("\n所有机器采集失败，无法生成报告", file=sys.stderr)
        return 1

    print(f"\n完成！结果保存在: {output_dir}")
    return 0