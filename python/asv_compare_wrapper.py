#!/usr/bin/env python3
"""
使用 ASV 官方 Compare API 进行 benchmark 对比
"""
import argparse
import io
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional


def load_asv_module(asv_project_dir: str):
    """加载 ASV 模块"""
    asv_project_path = Path(asv_project_dir).resolve()
    if asv_project_path not in sys.path:
        sys.path.insert(0, str(asv_project_path))

    try:
        from asv import config
        from asv.commands.compare import Compare
        return config, Compare
    except ImportError as e:
        print(f"错误: 无法加载 ASV 模块: {e}")
        print(f"请确保在 {asv_project_dir} 中有 ASV 配置文件 (asv.conf.json)")
        sys.exit(1)


def get_latest_commit(asv_dir: str, config) -> str:
    """获取最新的 commit hash（按时间戳排序）"""
    conf = config.Config()
    conf.load(str(Path(asv_dir) / "asv.conf.json"))

    results_dir = Path(asv_dir) / conf.results_dir
    commit_data = []  # [(commit_hash, date)]

    if not results_dir.exists():
        raise ValueError(f"结果目录不存在: {results_dir}")

    # 扫描所有机器目录
    for machine_dir in results_dir.iterdir():
        if machine_dir.is_dir():
            for commit_file in machine_dir.glob("*.json"):
                if commit_file.name != "machine.json":
                    try:
                        with open(commit_file, 'r') as f:
                            data = json.load(f)
                            commit_hash = data.get("commit_hash", "")
                            # ASV 结果 JSON 中 date 字段可能是：
                            # - datetime 对象序列化后的格式 {"$datetime": "..."}
                            # - 直接的时间戳数字
                            # - 字典格式 {"$date": "..."}
                            date_val = data.get("date", None)
                            if commit_hash:
                                # 提取实际时间戳用于排序
                                timestamp = extract_timestamp(date_val)
                                if timestamp is not None:
                                    commit_data.append((commit_hash, timestamp))
                    except (json.JSONDecodeError, IOError):
                        continue

    if not commit_data:
        raise ValueError(f"在 {asv_dir} 中未找到任何 commit 结果")

    # 按时间戳排序，返回最新的 commit hash
    commit_data.sort(key=lambda x: x[1], reverse=True)
    return commit_data[0][0]


def extract_timestamp(date_val):
    """从 ASV date 字段提取时间戳"""
    if date_val is None:
        return None

    # 如果是数字（直接时间戳）
    if isinstance(date_val, (int, float)):
        return date_val

    # 如果是字典格式 {"$datetime": "2023-01-01T00:00:00"} 或 {"$date": "..."}
    if isinstance(date_val, dict):
        for key in ['$datetime', '$date', 'datetime', 'date']:
            if key in date_val:
                try:
                    # 尝试解析 ISO 格式时间字符串
                    from datetime import datetime
                    dt_str = date_val[key]
                    if isinstance(dt_str, dict):
                        # 可能嵌套 {"$datetime": {"year": 2023, ...}}
                        if '$datetime' in dt_str:
                            dt_info = dt_str['$datetime']
                            return datetime(**dt_info).timestamp()
                    else:
                        # ISO 格式字符串
                        return datetime.fromisoformat(dt_str.replace('Z', '+00:00')).timestamp()
                except (ValueError, TypeError):
                    pass

    # 如果是字符串（ISO 格式）
    if isinstance(date_val, str):
        try:
            from datetime import datetime
            return datetime.fromisoformat(date_val.replace('Z', '+00:00')).timestamp()
        except ValueError:
            pass

    return None


def detect_machine(asv_dir: str) -> str:
    """自动检测机器名称"""
    machines = []
    for path in Path(asv_dir).glob("results/*/machine.json"):
        try:
            d = json.loads(path.read_text())
            machines.append(d['machine'])
        except (json.JSONDecodeError, IOError):
            continue

    if len(machines) == 0:
        raise ValueError("未找到任何机器结果")
    elif len(machines) == 1:
        return machines[0]
    else:
        print(f"警告: 找到多台机器: {machines}，使用第一台: {machines[0]}")
        return machines[0]


def generate_excel_from_table(table_output: str, output_dir: Path, server1: str, server2: str):
    """从 ASV 表格输出生成 Excel 文件"""
    try:
        import openpyxl
        import openpyxl.utils
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        print("警告: 未安装 openpyxl，跳过 Excel 表格生成")
        return

    lines = [line for line in table_output.split('\n') if line.strip()]

    table_start_idx = -1
    for i, line in enumerate(lines):
        if '|' in line and 'Change' in line and 'Before' in line:
            table_start_idx = i
            break

    if table_start_idx == -1:
        print("警告: 无法解析表格，跳过 Excel 生成")
        return

    table_lines = lines[table_start_idx:]
    excel_output_path = output_dir / f"{server1}_vs_{server2}_table.xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ASV Compare Table"

    for i, line in enumerate(table_lines):
        if not line.strip():
            continue

        cols = [col.strip() for col in line.split('|')]
        cols = cols[1:-1]  # 移除首尾空列

        for j, col in enumerate(cols):
            cell = ws.cell(row=i+1, column=j+1, value=col)

            if i == 0:
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
                cell.alignment = Alignment(horizontal='center')
            elif i == 1:
                cell.fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")

    for col_idx, column in enumerate(ws.columns, start=1):
        max_length = 0
        column_cells = [cell for cell in column]
        for cell in column_cells:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2) * 1.2
        adjusted_width = min(adjusted_width, 50)
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = adjusted_width

    wb.save(excel_output_path)
    print(f"表格已保存到: {excel_output_path}")


def main():
    parser = argparse.ArgumentParser(description='使用 ASV 官方 API 对比 benchmark 结果')
    parser.add_argument('--asv-dir1', required=True, help='Server1 的 ASV 项目目录')
    parser.add_argument('--asv-dir2', required=True, help='Server2 的 ASV 项目目录')
    parser.add_argument('--server1', required=True, help='Server1 名称')
    parser.add_argument('--server2', required=True, help='Server2 名称')
    parser.add_argument('--machine', help='机器名称（可选，默认自动检测）')
    parser.add_argument('--commit1', help='Server1 的 commit hash（默认：最新）')
    parser.add_argument('--commit2', help='Server2 的 commit hash（默认：最新）')
    parser.add_argument('--strategy', default='latest', choices=['latest', 'specific'],
                       help='commit 选择策略')
    parser.add_argument('--show-all', action='store_true',
                       help='显示所有 benchmark（包括未变化的）')
    parser.add_argument('--output', required=True, help='输出文件路径（用于确定输出目录）')

    args = parser.parse_args()

    config, Compare = load_asv_module(args.asv_dir1)

    # 确定 commit
    if args.strategy == 'latest':
        commit1 = args.commit1 if args.commit1 else get_latest_commit(args.asv_dir1, config)
        commit2 = args.commit2 if args.commit2 else get_latest_commit(args.asv_dir2, config)
    else:
        commit1 = args.commit1
        commit2 = args.commit2

    if not commit1 or not commit2:
        print("错误: 无法找到要比较的 commit")
        sys.exit(1)

    print(f"比较 commit: {commit1} vs {commit2}")

    # 确定机器名称
    machine = args.machine
    if machine is None:
        machine = detect_machine(args.asv_dir1)

    print(f"使用机器: {machine}")

    # 加载配置
    conf = config.Config()
    conf.load(str(Path(args.asv_dir1) / "asv.conf.json"))

    # 执行官方 Compare API
    print("使用 ASV 官方 Compare API 进行对比...")

    original_stdout = sys.stdout
    captured_output = io.StringIO()
    sys.stdout = captured_output

    original_cwd = os.getcwd()
    os.chdir(args.asv_dir1)

    try:
        Compare.print_table(
            conf=conf,
            hash_1=commit1,
            hash_2=commit2,
            factor=1.0,
            split=False,
            only_changed=not args.show_all,
            sort='default',
            machine=machine,
            env_names=None,
            commit_names={
                commit1: f"{args.server1}",
                commit2: f"{args.server2}",
            }
        )
    except Exception as e:
        os.chdir(original_cwd)
        sys.stdout = original_stdout
        print(f"错误: Compare API 执行失败: {e}")
        sys.exit(1)

    os.chdir(original_cwd)
    sys.stdout = original_stdout
    table_output = captured_output.getvalue()
    print(table_output, end='')

    # 保存 txt 文件
    output_dir = Path(args.output)
    txt_output_path = output_dir / f"{args.server1}_vs_{args.server2}_table.txt"
    with open(txt_output_path, 'w', encoding='utf-8') as f:
        f.write(table_output)
    print(f"\n表格已保存到: {txt_output_path}")

    # 生成 Excel 文件
    generate_excel_from_table(table_output, output_dir, args.server1, args.server2)


if __name__ == '__main__':
    main()