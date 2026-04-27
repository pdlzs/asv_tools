# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

ASV Benchmark 对比工具，用于在多台服务器上执行 ASV (airspeed velocity) benchmark 并对比结果。使用 ASV 官方 `asv compare` 命令进行对比，输出 TXT 和 Excel 格式报告。

## 常用命令

### 安装依赖
```bash
pip install -r python/requirements.txt
```

### 运行对比
```bash
cd python
python main.py cmp ../cmp.yaml
```

### 常用选项
- `--skip-run, -s`: 跳过 ASV 运行，直接使用已有结果对比
- `--dry-run, -n`: 显示将执行的命令，不实际执行
- `--verbose, -v`: 详细输出模式

### 本地测试
```bash
cd python
python main.py cmp ../cmp_local.yaml --skip-run
```

## 代码架构

```
python/
├── main.py              # CLI 入口，使用 argparse 子命令
├── cli/
│   └── cmp_cmd.py       # cmp 子命令实现，主执行流程
├── core/
│   ├── config.py        # 配置解析 (YAML → dataclass)
│   ├── executor.py      # 脚本执行器
│   └── downloader.py    # 结果下载器
├── ssh_utils.py         # SSH 工具 (subprocess 调用 ssh/scp)
└── asv_compare_wrapper.py  # ASV compare 包装器
```

### 执行流程

1. `main.py` 解析 CLI 参数，调用对应子命令
2. `cmp_cmd.py` 执行主流程：加载配置 → 验证 → 测试连接 → 执行脚本 → 下载结果 → ASV compare
3. `executor.py` 在本地或远程执行 shell 脚本（脚本支持 `{work_dir}` 占位符）
4. `downloader.py` 通过 scp 下载 results 目录
5. `asv_compare_wrapper.py` 合并结果、创建临时 git repo、调用 `asv compare`

### 关键设计

- **配置验证**: 必须恰好 2 台机器，每台机器需 host、asv_project_dir，远程机器需 username
- **本地执行**: `host: "local"` 表示本地执行，跳过 SSH
- **commit hash 修改**: 为区分不同服务器结果，修改 commit_hash 添加服务器前缀 (如 `server1-abc123`)
- **ASV compare**: 创建临时 merged_asv 目录，初始化 git repo，调用 `asv compare -m machine commit1 commit2`

## 配置文件格式

参考 `cmp.yaml` 或 `cmp_local.yaml` 示例。关键字段：
- `machines`: 服务器配置，支持 `host: "local"` 本地执行
- `scripts`: 每台机器的执行脚本，支持 `{work_dir}` 占位符
- `compare.show_all`: 是否显示未变化的 benchmark
- `output.dir`: 输出目录，默认 `./cmp_results`