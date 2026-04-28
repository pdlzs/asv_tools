# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

ASV Benchmark 对比工具，提供两种对比模式：
1. **跨机器对比 (cmp)**: 在多台服务器上执行 ASV benchmark 并对比结果，使用 `asv compare` 命令
2. **Commit 对比 (cont)**: 在指定机器上对比两个 commit 的性能，使用 `asv continuous` 命令。支持单机或多机执行

输出 TXT 和 Excel 格式报告。

## 常用命令

### 安装依赖
```bash
pip install -r python/requirements.txt
```

### 跨机器对比 (cmp)
```bash
cd python
python main.py cmp ../cmp.yaml
```

### Commit 对比 (cont)
```bash
cd python
python main.py cont ../cont.yaml
```
在指定机器上对比两个 commit 的性能，支持单机或多机执行。使用 `asv continuous` 命令。

### 配置SSH免密登录
```bash
cd python
python main.py ssh-setup ../cmp.yaml
```
一键配置cmp.yaml中所有远程服务器的SSH免密登录。会自动检测或生成SSH密钥，并将公钥复制到远程服务器。

### 常用选项
- `--delay TIME, -d`: 延时执行，支持 `s`（秒）、`m`（分钟）、`h`（小时），如 `-d 10s`、`-d 30m`、`-d 6h`
- `--skip-run, -s`: 跳过 ASV 运行，直接使用已有结果对比 (仅 cmp)
- `--dry-run, -n`: 显示将执行的命令，不实际执行
- `--verbose, -v`: 详细输出模式

### 本地测试
```bash
cd python
python main.py cmp ../cmp_local.yaml --skip-run
python main.py cont ../cont_local.yaml --dry-run
```

## 代码架构

```
python/
├── main.py              # CLI 入口，使用 argparse 子命令
├── cli/
│   ├── cmp_cmd.py       # cmp 子命令实现，跨机器对比
│   ├── cont_cmd.py      # cont 子命令实现，单机 commit 对比
│   └── ssh_setup_cmd.py # ssh-setup 子命令，一键配置免密登录
├── core/
│   ├── config.py        # cmp 配置解析 (YAML → dataclass)
│   ├── cont_config.py   # cont 配置解析
│   ├── executor.py      # 脚本执行器
│   └── downloader.py    # 结果下载器
├── ssh_utils.py         # SSH 工具 (subprocess 调用 ssh/scp)
└── asv_compare_wrapper.py  # ASV compare 包装器
```

### 执行流程

**cmp 命令**:
1. `main.py` 解析 CLI 参数，调用 cmp 子命令
2. `cmp_cmd.py` 执行主流程：加载配置 → 验证 → 测试连接 → 执行脚本 → 下载结果 → ASV compare
3. `executor.py` 在本地或远程执行 shell 脚本（脚本支持 `{work_dir}` 占位符）
4. `downloader.py` 通过 scp 下载 results 目录
5. `asv_compare_wrapper.py` 合并结果、创建临时 git repo、调用 `asv compare -m machine commit1 commit2`

**cont 命令**:
1. `main.py` 解析 CLI 参数，调用 cont 子命令
2. `cont_cmd.py` 加载配置 → 验证 → 测试连接 → 执行脚本 → 调用 `asv continuous base branch`

### 关键设计

**cmp 模式**:
- 必须恰好 2 台机器，每台机器需 host、asv_project_dir，远程机器需 username
- `host: "local"` 表示本地执行，跳过 SSH
- commit hash 修改: 为区分不同服务器结果，修改 commit_hash 添加服务器前缀 (如 `server1-abc123`)
- ASV compare: 创建临时 merged_asv 目录，初始化 git repo，调用 `asv compare`

**cont 模式**:
- 支持一台或多台机器，每台机器上运行相同的 commit 对比
- `host: "local"` 表示本地执行，远程机器需配置 username
- scripts 用于设置环境（如激活 conda），支持 `{work_dir}` 占位符
- asv_options 不指定则使用官方默认值
- 支持所有 `asv continuous` 选项：bench, factor, machine, python, split, only_changed 等

## 配置文件格式

**cmp 配置** (`cmp.yaml`):
- `machines`: 服务器配置（必须 2 台），支持 `host: "local"` 本地执行
- `scripts`: 每台机器的执行脚本，支持 `{work_dir}` 占位符
- `compare.show_all`: 是否显示未变化的 benchmark
- `output.dir`: 输出目录，默认 `./cmp_results`

**cont 配置** (`cont.yaml`):
- `machines`: 服务器配置（1台或多台），支持 `host: "local"` 本地执行
- `commits.base`: 基准 commit
- `commits.branch`: 测试 commit
- `scripts`: 每台机器的执行脚本，支持 `{work_dir}` 占位符
- `asv_options`: ASV 选项（可选，不指定使用官方默认值）
- `output.dir`: 输出目录