# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

ASV Benchmark 对比工具，提供三种模式：
1. **跨机器对比 (cmp)**: 在多台服务器上执行 ASV benchmark 并对比结果，使用 `asv compare` 命令
2. **Commit 对比 (cont)**: 在指定机器上对比两个 commit 的性能，使用 `asv continuous` 命令。支持单机或多机执行
3. **性能配置采集 (collect)**: 采集各机器的性能相关配置（CPU、内存、BIOS、环境等）并对比差异

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

### 性能配置采集 (collect)
```bash
cd python
python main.py collect ../collect.yaml
```
采集各机器的性能相关配置（CPU、内存、BIOS、内核参数、conda 环境等），输出 YAML 配置文件和 Markdown 对比报告。

**采集内容**：
- BIOS 配置（dmidecode 全量输出）
- CPU 信息（型号、核心数、缓存、指令集、NUMA）
- 内存配置（总内存、大页、透明大页）
- 内核参数（swappiness、dirty_ratio、shmmax 等）
- 环境配置（Python、GCC、BLAS、LAPACK 版本）
- 性能相关环境变量（OMP_NUM_THREADS、MKL_NUM_THREADS 等）
- 系统限制（ulimit）

**容错设计**：单项采集失败不影响其他项，失败项记录为 NA。

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
│   ├── collect_cmd.py   # collect 子命令实现，性能配置采集
│   └── ssh_setup_cmd.py # ssh-setup 子命令，一键配置免密登录
├── core/
│   ├── machine_config.py # 统一的机器配置数据类（三种模式共用）
│   ├── template.py       # 统一的模板渲染（{var} 占位符替换 + export 语句生成）
│   ├── config.py        # cmp 配置解析 (YAML → dataclass)
│   ├── cont_config.py   # cont 配置解析
│   ├── collect_config.py# collect 配置解析
│   ├── perf_collector.py# 性能配置采集器
│   ├── perf_comparator.py# 性能配置对比器
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
2. `cont_cmd.py` 加载配置 → 验证 → 测试连接 → 执行脚本（脚本中自定义 asv continuous 命令）

**collect 命令**:
1. `main.py` 解析 CLI 参数，调用 collect 子命令
2. `collect_cmd.py` 加载配置 → 验证 → 测试连接 → 采集配置 → 保存 YAML → 生成对比报告
3. `perf_collector.py` 通过 SSH 执行采集脚本，解析输出
4. `perf_comparator.py` 对比多个配置，生成 Markdown 报告

### 关键设计

**cmp 模式**:
- 必须恰好 2 台机器，每台机器需 host、asv_project_dir，远程机器需 username
- `host: "local"` 表示本地执行，跳过 SSH
- commit hash 修改: 为区分不同服务器结果，修改 commit_hash 添加服务器前缀 (如 `server1-abc123`)
- ASV compare: 创建临时 merged_asv 目录，初始化 git repo，调用 `asv compare`

**cont 模式**:
- 支持一台或多台机器，每台机器上运行相同的 commit 对比
- `host: "local"` 表示本地执行，远程机器需配置 username
- cont_scripts 完全控制执行内容，支持 `{work_dir}`、`{base}`、`{branch}` 占位符
- commits 为可选配置，提供 `{base}` 和 `{branch}` 模板变量

**机器配置统一**: 三种模式共用 `core/machine_config.py` 中的 `MachineConfig` 数据类。

**export 全局环境变量**: 三种模式均支持 YAML 顶层 `export:` 字段，定义的环境变量在 scripts 中可用作 `{VAR}` 模板占位符，运行时自动导出为 shell 环境变量。

## 配置文件格式

**cmp 配置** (`cmp.yaml`):
- `export`: 全局环境变量（可选），可在 scripts 中以 `{VAR}` 引用
- `machines`: 服务器配置（必须 2 台），支持 `host: "local"` 本地执行
- `compare_scripts`: 每台机器的 ASV compare 执行脚本（兼容旧版 `scripts` 字段），支持 `{work_dir}` 和 export 变量占位符
- `collect_scripts`: 每台机器的 collect 采集脚本（可选），用于环境初始化
- `compare.show_all`: 是否显示未变化的 benchmark
- `compare.collect`: 是否在 compare 前执行 collect 采集（默认 false）
- `output.dir`: 输出目录，默认 `./cmp_results`

**collect 采集输出**: 当 `compare.collect: true` 时，采集结果保存在输出目录的 `perf_config/` 子目录下。

**cont 配置** (`cont.yaml`):
- `export`: 全局环境变量（可选）
- `machines`: 服务器配置（1台或多台），支持 `host: "local"` 本地执行
- `commits`: 可选，提供 `{base}` 和 `{branch}` 模板变量
- `cont_scripts`: 每台机器的执行脚本，支持 `{work_dir}`、`{base}`、`{branch}` 和 export 变量占位符
- `output.dir`: 输出目录

**collect 配置** (`collect.yaml`):
- `export`: 全局环境变量（可选）
- `machines`: 服务器配置（1台或多台），支持 `host: "local"` 本地执行
- `machines.hostname`: 显示名称（可选，用于对比报告标识机器，默认使用 name）
- `collect_scripts`: 每台机器的环境初始化脚本（如激活 conda、设置环境变量）
- `output.dir`: 输出目录，默认 `./collect_results`
- `output.custom_info`: 自定义标识，用于输出文件名

**collect 常用选项**:
- `--force, -f`: 强制执行，跳过工具可用性检查
- `--dry-run, -n`: 显示命令不执行
- `--verbose, -v`: 详细输出

**工具检查**: 执行前会检查服务器端工具可用性（lscpu、dmidecode、numactl、python、gcc、conda），缺失工具会给出安装提示，使用 `--force` 可跳过检查强制执行。