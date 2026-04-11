#!/usr/bin/env python3
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def parse_asv_results(results_dir: str, machine_name: Optional[str] = None) -> Dict:
    results = {}
    results_path = Path(results_dir)

    if not results_path.exists():
        raise FileNotFoundError(f"ASV结果目录不存在: {results_dir}")

    machine_dirs = [d for d in results_path.iterdir() if d.is_dir()]

    if machine_name:
        machine_dirs = [d for d in machine_dirs if d.name == machine_name]

    if not machine_dirs:
        raise ValueError(f"在 {results_dir} 中未找到机器结果目录")

    for machine_dir in machine_dirs:
        machine_name = machine_dir.name

        result_files = [f for f in machine_dir.glob("*.json") if f.name != "machine.json"]

        if result_files:
            for result_file in result_files:
                try:
                    with open(result_file, 'r') as f:
                        data = json.load(f)

                    commit_hash = data.get("commit_hash", "")
                    if not commit_hash:
                        commit_hash = result_file.name.split("-")[0]

                    benchmarks_data = data.get("results", {})

                    machine_file = machine_dir / "machine.json"
                    machine_info = {}
                    if machine_file.exists():
                        with open(machine_file, 'r') as f:
                            machine_info = json.load(f)

                    results[commit_hash] = {
                        "benchmarks": benchmarks_data,
                        "machine": machine_name,
                        "machine_info": machine_info,
                        "path": str(machine_dir),
                    }

                except (json.JSONDecodeError, IOError) as e:
                    print(f"警告: 无法解析文件 {result_file.name}: {e}")
                    continue
        else:
            commit_dirs = [d for d in machine_dir.iterdir() if d.is_dir()]

            for commit_dir in commit_dirs:
                commit_hash = commit_dir.name

                benchmarks_file = commit_dir / "benchmarks.json"
                if not benchmarks_file.exists():
                    continue

                try:
                    with open(benchmarks_file, 'r') as f:
                        benchmarks_data = json.load(f)

                    machine_file = commit_dir / "machine.json"
                    machine_info = {}
                    if machine_file.exists():
                        with open(machine_file, 'r') as f:
                            machine_info = json.load(f)

                    results[commit_hash] = {
                        "benchmarks": benchmarks_data,
                        "machine": machine_name,
                        "machine_info": machine_info,
                        "path": str(commit_dir),
                    }

                except (json.JSONDecodeError, IOError) as e:
                    print(f"警告: 无法解析commit {commit_hash}: {e}")
                    continue

    return results


def get_latest_commit(results: Dict) -> Optional[str]:
    if not results:
        return None

    return max(results.keys())


def extract_benchmark_times(commit_data: Dict) -> Dict[str, float]:
    benchmarks = {}
    benchmarks_data = commit_data.get("benchmarks", {})

    for bench_name, bench_data in benchmarks_data.items():
        time_value = None

        # 处理 ASV 新版本格式：列表格式 [[value], [], version, timestamp, duration, ...]
        if isinstance(bench_data, list) and len(bench_data) > 0:
            # 第一个元素是结果值列表
            result_list = bench_data[0]
            if isinstance(result_list, list) and len(result_list) > 0:
                time_value = result_list[0]

        # 处理旧版本格式：字典格式
        elif isinstance(bench_data, dict):
            if "time" in bench_data:
                time_value = bench_data["time"]
            elif "result" in bench_data:
                time_value = bench_data["result"]
            elif "samples" in bench_data and bench_data["samples"]:
                samples = bench_data["samples"]
                if isinstance(samples, list) and samples:
                    time_value = sum(samples) / len(samples) if all(isinstance(s, (int, float)) for s in samples) else None

        if time_value is not None and isinstance(time_value, (int, float)):
            benchmarks[bench_name] = float(time_value)

    return benchmarks


def compare_benchmarks(
    results1: Dict,
    results2: Dict,
    commit1: Optional[str] = None,
    commit2: Optional[str] = None
) -> List[Dict]:
    if commit1 is None:
        commit1 = get_latest_commit(results1)
    if commit2 is None:
        commit2 = get_latest_commit(results2)

    if commit1 is None or commit2 is None:
        raise ValueError("无法找到要比较的commit")

    times1 = extract_benchmark_times(results1[commit1])
    times2 = extract_benchmark_times(results2[commit2])

    all_benchmarks = set(times1.keys()) | set(times2.keys())

    comparison = []
    for bench_name in sorted(all_benchmarks):
        time1 = times1.get(bench_name, 0.0)
        time2 = times2.get(bench_name, 0.0)

        if time1 > 0:
            speedup = time1 / time2 if time2 > 0 else 0.0
            diff_percent = ((time2 - time1) / time1) * 100
        else:
            speedup = 0.0
            diff_percent = 0.0

        comparison.append({
            "benchmark": bench_name,
            "time1": time1,
            "time2": time2,
            "speedup": speedup,
            "diff_percent": diff_percent,
            "stats1": results1[commit1]["benchmarks"].get(bench_name, {}),
            "stats2": results2[commit2]["benchmarks"].get(bench_name, {}),
        })

    return comparison
