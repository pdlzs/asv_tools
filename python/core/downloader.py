"""Result downloader for ASV benchmark results"""

import json
import shutil
from pathlib import Path
from typing import Optional

from core.config import MachineConfig
from ssh_utils import SSHClient, SSHConfig


def download_results(
    machine: MachineConfig,
    local_output_dir: Path,
    dry_run: bool = False,
    verbose: bool = False
) -> bool:
    """
    从机器下载 ASV 结果

    Args:
        machine: 机器配置
        local_output_dir: 本地输出目录
        dry_run: 是否为干运行模式
        verbose: 是否显示详细输出

    Returns:
        成功返回 True
    """
    remote_results_dir = f"{machine.asv_project_dir}/results"

    if dry_run:
        print(f"[DRY-RUN] 将从 {machine.name} 下载:")
        print(f"  远程: {remote_results_dir}")
        print(f"  本地: {local_output_dir}")
        return True

    print(f"从 {machine.name} 下载 ASV 结果...")

    # 确保本地目录存在
    local_output_dir.mkdir(parents=True, exist_ok=True)

    # 创建 SSH 客户端
    config = SSHConfig(
        host=machine.host,
        username=machine.username or "",
        port=machine.port,
        timeout=30
    )

    client = SSHClient(config)

    # 下载 results 目录
    # scp 会将 remote_results_dir 复制为 local_output_dir/results
    # 我们需要将其复制到 local_output_dir 本身
    temp_target = local_output_dir.parent / f"{local_output_dir.name}_tmp"

    if not client.download(remote_results_dir, str(temp_target)):
        print(f"从 {machine.name} 下载结果失败")
        return False

    # 移动结果到正确位置
    # temp_target 是 results 目录本身，移动到 local_output_dir/results
    final_results = local_output_dir / "results"
    if final_results.exists():
        shutil.rmtree(final_results)

    # temp_target 可能是文件或目录
    if temp_target.is_dir():
        shutil.move(str(temp_target), str(final_results))
    else:
        final_results.mkdir(parents=True)
        shutil.move(str(temp_target), str(final_results / temp_target.name))

    # 生成 asv.conf.json
    asv_conf = {
        "version": 1,
        "project": "benchmark",
        "repo": ".",
        "results_dir": "results"
    }

    conf_path = local_output_dir / "asv.conf.json"
    with open(conf_path, 'w') as f:
        json.dump(asv_conf, f, indent=2)

    # 复制 benchmarks.json（如果存在）
    benchmarks_src = final_results / "benchmarks.json"
    benchmarks_dst = local_output_dir / "benchmarks.json"
    if benchmarks_src.exists():
        shutil.copy2(benchmarks_src, benchmarks_dst)
        if verbose:
            print("已复制 benchmarks.json 到项目根目录")

    # 不修改 commit_hash，保留原始值以便 ASV compare 正确识别

    print(f"从 {machine.name} 下载结果完成")
    return True


