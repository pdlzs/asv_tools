#!/usr/bin/env python3
"""
使用 ASV Python API 进行 benchmark 对比
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# 将 ASV 项目目录添加到 Python 路径
def load_asv_module(asv_project_dir: str):
    """加载 ASV 模块"""
    asv_project_path = Path(asv_project_dir).resolve()
    if asv_project_path not in sys.path:
        sys.path.insert(0, str(asv_project_path))

    try:
        from asv import config
        from asv.results import iter_results_for_machine_and_hash
        from asv.machine import iter_machine_files
        from asv.util import load_json
        return config, iter_results_for_machine_and_hash, iter_machine_files, load_json
    except ImportError as e:
        print(f"错误: 无法加载 ASV 模块: {e}")
        print(f"请确保在 {asv_project_dir} 中有 ASV 配置文件 (asv.conf.json)")
        sys.exit(1)


def get_benchmark_results(asv_project_dir: str, commit_hash: str, machine_name: Optional[str] = None) -> Dict:
    """获取指定 commit 的 benchmark 结果"""
    config, _, iter_machine_files, load_json = load_asv_module(asv_project_dir)

    conf = config.Config()
    conf.load(str(Path(asv_project_dir) / "asv.conf.json"))

    # 使用绝对路径
    abs_results_dir = (Path(asv_project_dir) / conf.results_dir).resolve()

    # 如果没有指定机器名称，自动检测
    if machine_name is None:
        machines = []

        if abs_results_dir.exists():
            for machine_dir in abs_results_dir.iterdir():
                if machine_dir.is_dir():
                    machine_file = machine_dir / "machine.json"
                    if machine_file.exists():
                        try:
                            d = load_json(str(machine_file))
                            machines.append(d['machine'])
                        except (json.JSONDecodeError, IOError):
                            continue

        if len(machines) == 0:
            raise ValueError(f"在 {asv_project_dir} 中未找到任何机器结果")
        elif len(machines) == 1:
            machine_name = machines[0]
        else:
            raise ValueError(f"找到多台机器: {machines}，请指定机器名称")

    # 直接解析 JSON 文件获取结果
    results = {}
    machine_dir = abs_results_dir / machine_name

    if not machine_dir.exists():
        raise ValueError(f"机器目录不存在: {machine_dir}")

    # 查找匹配的 commit 文件
    for commit_file in machine_dir.glob("*.json"):
        if commit_file.name == "machine.json":
            continue

        try:
            with open(commit_file, 'r') as f:
                data = json.load(f)

                file_commit_hash = data.get("commit_hash", "")
                if file_commit_hash.startswith(commit_hash):
                    # 找到匹配的 commit
                    benchmark_results = data.get("results", {})

                    for bench_name, bench_data in benchmark_results.items():
                        # 提取时间值
                        time_value = None
                        if isinstance(bench_data, list) and len(bench_data) > 0:
                            # ASV 新格式：[[value], [], ...]
                            value_list = bench_data[0]
                            if isinstance(value_list, list) and len(value_list) > 0:
                                time_value = value_list[0]

                        if time_value is not None:
                            results[bench_name] = {
                                'value': time_value,
                                'stats': {},
                                'params': []
                            }
                    break
        except (json.JSONDecodeError, IOError) as e:
            print(f"警告: 无法解析文件 {commit_file.name}: {e}")
            continue

    return results


def compare_benchmarks(
    results1: Dict,
    results2: Dict,
    commit1: str,
    commit2: str
) -> List[Dict]:
    """对比两台服务器的 benchmark 结果"""
    all_benchmarks = set(results1.keys()) | set(results2.keys())

    comparison = []
    for bench_name in sorted(all_benchmarks):
        data1 = results1.get(bench_name, {})
        data2 = results2.get(bench_name, {})

        time1 = data1.get('value', 0)
        time2 = data2.get('value', 0)

        if time1 > 0:
            speedup = time1 / time2 if time2 > 0 else 0.0
            diff_percent = ((time2 - time1) / time1) * 100
        else:
            speedup = 0.0
            diff_percent = 0.0

        comparison.append({
            "benchmark": bench_name,
            "time1": float(time1) if time1 else 0.0,
            "time2": float(time2) if time2 else 0.0,
            "speedup": float(speedup),
            "diff_percent": float(diff_percent),
            "stats1": data1.get('stats', {}),
            "stats2": data2.get('stats', {}),
        })

    return comparison


def main():
    parser = argparse.ArgumentParser(description='使用 ASV API 对比 benchmark 结果')
    parser.add_argument('--asv-dir1', required=True, help='Server1 的 ASV 项目目录')
    parser.add_argument('--asv-dir2', required=True, help='Server2 的 ASV 项目目录')
    parser.add_argument('--server1', required=True, help='Server1 名称')
    parser.add_argument('--server2', required=True, help='Server2 名称')
    parser.add_argument('--machine1', help='Server1 的机器名称（可选）')
    parser.add_argument('--machine2', help='Server2 的机器名称（可选）')
    parser.add_argument('--commit1', help='Server1 的 commit hash（默认：最新）')
    parser.add_argument('--commit2', help='Server2 的 commit hash（默认：最新）')
    parser.add_argument('--strategy', default='latest', choices=['latest', 'specific'],
                       help='commit 选择策略')
    parser.add_argument('--show-all', action='store_true',
                       help='显示所有 benchmark（包括未变化的）')
    parser.add_argument('--output', required=True, help='输出 JSON 文件路径')

    args = parser.parse_args()

    # 获取最新 commit
    def get_latest_commit(asv_dir: str) -> str:
        """获取最新的 commit hash"""
        config, _, _, load_json = load_asv_module(asv_dir)
        conf = config.Config()
        conf.load(str(Path(asv_dir) / "asv.conf.json"))

        # 直接扫描 results 目录
        results_dir = Path(asv_dir) / conf.results_dir
        commits = set()

        if not results_dir.exists():
            raise ValueError(f"结果目录不存在: {results_dir}")

        # 扫描所有机器目录
        for machine_dir in results_dir.iterdir():
            if machine_dir.is_dir():
                # 扫描所有 commit 文件
                for commit_file in machine_dir.glob("*.json"):
                    if commit_file.name != "machine.json":
                        try:
                            with open(commit_file, 'r') as f:
                                data = json.load(f)
                                commit_hash = data.get("commit_hash", "")
                                if commit_hash:
                                    commits.add(commit_hash)
                        except (json.JSONDecodeError, IOError):
                            continue

        if not commits:
            raise ValueError(f"在 {asv_dir} 中未找到任何 commit 结果")

        # 返回最大的 commit hash（按字典序）
        return max(commits)

    # 确定 commit
    if args.strategy == 'latest':
        commit1 = args.commit1 if args.commit1 else get_latest_commit(args.asv_dir1)
        commit2 = args.commit2 if args.commit2 else get_latest_commit(args.asv_dir2)
    else:
        commit1 = args.commit1
        commit2 = args.commit2

    if not commit1 or not commit2:
        print("错误: 无法找到要比较的 commit")
        sys.exit(1)

    print(f"解析 {args.server1} 的 ASV 结果...")
    results1 = get_benchmark_results(args.asv_dir1, commit1, args.machine1)

    print(f"解析 {args.server2} 的 ASV 结果...")
    results2 = get_benchmark_results(args.asv_dir2, commit2, args.machine2)

    print(f"比较 commit: {commit1} vs {commit2}")

    comparison = compare_benchmarks(results1, results2, commit1, commit2)

    if not args.show_all:
        comparison = [c for c in comparison if abs(c['diff_percent']) > 1.0]

    report = {
        "server1": args.server1,
        "server2": args.server2,
        "commit1": commit1,
        "commit2": commit2,
        "commit1_info": {
            "benchmarks": {k: v['value'] for k, v in results1.items()},
            "machine": args.machine1 or "auto",
            "machine_info": {},
            "path": args.asv_dir1,
        },
        "commit2_info": {
            "benchmarks": {k: v['value'] for k, v in results2.items()},
            "machine": args.machine2 or "auto",
            "machine_info": {},
            "path": args.asv_dir2,
        },
        "benchmarks": comparison,
        "summary": {
            "total": len(comparison),
            "faster": sum(1 for c in comparison if c['diff_percent'] < 0),
            "slower": sum(1 for c in comparison if c['diff_percent'] > 0),
            "same": sum(1 for c in comparison if abs(c['diff_percent']) < 1.0),
        }
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"对⽐结果已保存保存到: {output_path}")
    print(f"总共 {len(comparison)} 个 benchmark")
    print(f"  - 更快: {report['summary']['faster']}")
    print(f"  - 更慢: {report['summary']['slower']}")
    print(f"  - 相同: {report['summary']['same']}")


if __name__ == '__main__':
    main()
