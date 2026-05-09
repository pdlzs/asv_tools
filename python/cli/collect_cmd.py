"""collect command implementation - performance configuration collection"""

import sys
from datetime import datetime
from pathlib import Path

from core.collect_config import CollectConfig, load_collect_config
from core.perf_collector import PerfCollector, perf_config_to_yaml
from core.perf_comparator import PerfComparator
from core.template import render_template, build_export_statements


def setup_logging(verbose: bool = False):
    """设置日志输出"""
    import logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(message)s')


# 工具检查配置
REQUIRED_TOOLS = [
    # 基础工具（几乎都有，不检查）
]

OPTIONAL_TOOLS = [
    {
        'name': 'lscpu',
        'check_cmd': 'lscpu --version 2>/dev/null || which lscpu',
        'install_hint': '通常系统自带。缺失时: apt install util-linux (Ubuntu) 或 yum install util-linux (CentOS)',
        'category': 'CPU 信息',
    },
    {
        'name': 'dmidecode',
        'check_cmd': 'which dmidecode',
        'install_hint': 'apt install dmidecode (Ubuntu) 或 yum install dmidecode (CentOS)。需要 root 权限运行',
        'category': 'BIOS 信息',
        'need_root': True,
    },
    {
        'name': 'numactl',
        'check_cmd': 'which numactl',
        'install_hint': 'apt install numactl (Ubuntu) 或 yum install numactl (CentOS)',
        'category': 'NUMA 拓扑',
    },
    {
        'name': 'python',
        'check_cmd': 'which python || which python3',
        'install_hint': '系统应已安装 Python。若缺失: apt install python3',
        'category': 'Python 版本',
    },
    {
        'name': 'gcc',
        'check_cmd': 'which gcc',
        'install_hint': 'apt install gcc (Ubuntu) 或 yum install gcc (CentOS)',
        'category': 'GCC 版本',
    },
    {
        'name': 'conda',
        'check_cmd': 'which conda',
        'install_hint': '从 https://docs.conda.io 安装 Miniconda 或 Anaconda',
        'category': 'BLAS/LAPACK 检测',
        'alternative': 'pip',
    },
]


def check_tools_on_machine(machine_name: str, config: CollectConfig, verbose: bool = False) -> tuple[bool, list]:
    """
    检查单台机器上的工具可用性

    先执行 scripts（激活环境），再检查工具可用性

    Returns:
        (all_ok, missing_tools): 全部可用返回 True，缺失工具列表
    """
    from ssh_utils import SSHClient, SSHConfig

    machine = config.machines[machine_name]
    script = config.get_script_for_machine(machine_name)

    ssh_config = SSHConfig(
        host=machine.host,
        username=machine.username or "",
        port=machine.port,
        timeout=config.runtime.ssh_timeout,
        execution_timeout=config.runtime.execution_timeout
    )
    client = SSHClient(ssh_config)

    # 构建检查脚本：先执行 scripts（激活环境），再检查工具
    check_script = ""

    # 1. 前置 export 语句
    check_script += build_export_statements(config.export)

    # 2. 执行 scripts（激活环境）- 渲染 export 模板变量
    if script:
        rendered_script = render_template(script, **config.export)
        check_script += f"""
# === 环境初始化 ===
{rendered_script}
"""
    else:
        check_script += "# 无环境初始化脚本\n"

    # 2. 等待环境激活后，开始检查工具
    check_script += """
# === 工具检查 ===
echo 'TOOL_CHECK_START'
"""
    for tool in OPTIONAL_TOOLS:
        check_script += f"""
echo 'CHECK_TOOL: {tool['name']}'
{tool['check_cmd']} >/dev/null 2>&1 && echo 'RESULT: OK' || echo 'RESULT: MISSING'
"""
    check_script += "echo 'TOOL_CHECK_END'\n"

    # 执行检查（不输出到终端，避免干扰解析）
    success, output = client.execute(check_script, stream_output=False)

    if not success:
        return False, [{'name': 'connection', 'category': '连接', 'hint': f'无法连接到 {machine.host}'}]

    if verbose:
        print(f"[{machine_name}] 工具检查输出:\n{output}")

    # 解析结果：只解析 TOOL_CHECK_START 和 TOOL_CHECK_END 之间的内容
    missing_tools = []
    in_check_section = False
    current_tool = None

    for line in output.split('\n'):
        if line.strip() == 'TOOL_CHECK_START':
            in_check_section = True
            continue
        elif line.strip() == 'TOOL_CHECK_END':
            break

        if not in_check_section:
            continue

        if line.startswith('CHECK_TOOL:'):
            current_tool = line.split(':', 1)[1].strip()
        elif line.startswith('RESULT:'):
            result = line.split(':', 1)[1].strip()
            if result == 'MISSING' and current_tool:
                # 找到对应的工具信息
                for tool in OPTIONAL_TOOLS:
                    if tool['name'] == current_tool:
                        missing_tools.append({
                            'name': tool['name'],
                            'category': tool['category'],
                            'hint': tool['install_hint'],
                            'need_root': tool.get('need_root', False),
                        })
                        break

    return len(missing_tools) == 0, missing_tools


def print_tool_check_report(results: dict):
    """打印工具检查报告"""
    print("\n" + "=" * 60)
    print("工具检查报告")
    print("=" * 60)

    for machine_name, (ok, missing) in results.items():
        print(f"\n[{machine_name}]")
        if ok:
            print("  ✓ 所有工具可用")
        else:
            print("  ⚠️ 缺失以下工具:")
            for tool in missing:
                if tool['name'] == 'connection':
                    print(f"    - {tool['category']}: {tool['hint']}")
                else:
                    print(f"    - {tool['name']} ({tool['category']})")
                    print(f"      安装提示: {tool['hint']}")
                    if tool.get('need_root'):
                        print(f"      注意: 需要 root 权限运行")

    # 汇总
    all_ok = all(r[0] for r in results.values())
    if not all_ok:
        print("\n" + "-" * 60)
        print("部分工具缺失，采集结果中对应项将显示 NA。")
        print("如需强制执行，请使用 --force 参数跳过检查。")
        print("-" * 60)

    return all_ok


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
        if not test_connection(machine.host, machine.username, machine.port, machine.identity_file):
            print(f"[{name}] 无法连接到 {machine.host}", file=sys.stderr)
            return False

    print("SSH 连接验证成功")
    return True


def collect_from_machine(machine_name: str, config: CollectConfig,
                         dry_run: bool = False, verbose: bool = False) -> 'PerfConfig':
    """从单台机器采集性能配置"""
    machine = config.machines[machine_name]
    script = config.get_script_for_machine(machine_name)

    # 渲染 export 模板变量 + 前置 export 语句
    if script and config.export:
        script = build_export_statements(config.export) + render_template(script, **config.export)

    collector = PerfCollector(
        machine, script, verbose,
        ssh_timeout=config.runtime.ssh_timeout,
        execution_timeout=config.runtime.execution_timeout
    )

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

    # 6. 工具检查（非 dry-run 且非 force）
    if not args.dry_run and not args.force:
        print("\n检查工具可用性...")
        tool_check_results = {}
        for machine_name in config.machines.keys():
            ok, missing = check_tools_on_machine(machine_name, config, args.verbose)
            tool_check_results[machine_name] = (ok, missing)

        all_ok = print_tool_check_report(tool_check_results)
        if not all_ok:
            print("\n工具检查未通过，请安装缺失工具或使用 --force 强制执行")
            return 1

    # 7. 采集各机器配置
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

    # 8. 生成对比报告
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