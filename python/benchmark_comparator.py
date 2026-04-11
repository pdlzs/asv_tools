#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional
from asv_parser import parse_asv_results, get_latest_commit, compare_benchmarks


def main():
    parser = argparse.ArgumentParser(description='对比ASV benchmark结果')
    parser.add_argument('--results1', required=True, help='Server1的ASV结果目录')
    parser.add_argument('--results2', required=True, help='Server2的ASV结果目录')
    parser.add_argument('--server1', required=True, help='Server1名称')
    parser.add_argument('--server2', required=True, help='Server2名称')
    parser.add_argument('--machine1', help='Server1的机器名称（可选）')
    parser.add_argument('--machine2', help='Server2的机器名称（可选）')
    parser.add_argument('--commit1', help='Server1的commit hash（默认：最新）')
    parser.add_argument('--commit2', help='Server2的commit hash（默认：最新）')
    parser.add_argument('--strategy', default='latest', choices=['latest', 'specific'],
                       help='commit选择策略')
    parser.add_argument('--show-all', action='store_true',
                       help='显示所有benchmark（包括未变化的）')
    parser.add_argument('--output', required=True, help='输出JSON文件路径')

    args = parser.parse_args()

    print(f"解析 {args.server1} 的ASV结果...")
    results1 = parse_asv_results(args.results1, args.machine1)

    print(f"解析 {args.server2} 的ASV结果...")
    results2 = parse_asv_results(args.results2, args.machine2)

    if args.strategy == 'latest':
        commit1 = get_latest_commit(results1)
        commit2 = get_latest_commit(results2)
    else:
        commit1 = args.commit1
        commit2 = args.commit2

    if not commit1 or not commit2:
        print("错误: 无法找到要比较的commit")
        exit(1)

    print(f"比较commit: {commit1} vs {commit2}")

    comparison = compare_benchmarks(results1, results2, commit1, commit2)

    if not args.show_all:
        comparison = [c for c in comparison if abs(c['diff_percent']) > 1.0]

    report = {
        "server1": args.server1,
        "server2": args.server2,
        "commit1": commit1,
        "commit2": commit2,
        "commit1_info": results1[commit1] if commit1 in results1 else {},
        "commit2_info": results2[commit2] if commit2 in results2 else {},
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

    print(f"对比结果已保存到: {output_path}")
    print(f"总共 {len(comparison)} 个benchmark")
    print(f"  - 更快: {report['summary']['faster']}")
    print(f"  - 更慢: {report['summary']['slower']}")
    print(f"  - 相同: {report['summary']['same']}")


if __name__ == '__main__':
    main()
