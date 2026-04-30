# ASV Benchmark 对比工具

在多台服务器上执行 ASV benchmark 并进行结果对比的工具，支持跨机器对比、Commit 对比和性能配置采集三种模式。

## 功能特性

- **跨机器对比 (cmp)**: 在两台服务器上运行 ASV benchmark，使用 `asv compare` 对比结果，生成 TXT/Excel 报告
- **Commit 对比 (cont)**: 在指定机器上对比两个 commit 的性能，使用 `asv continuous` 命令
- **性能配置采集 (collect)**: 采集各机器的 CPU/BIOS/内存/内核/环境变量等配置，生成 YAML + Markdown 对比报告
- **SSH 免密配置**: 一键配置多台远程服务器的 SSH 免密登录

## 安装

### 前置要求

- Python 3.6+
- SSH 免密登录（如需远程服务器，可使用 `ssh-setup` 命令一键配置）
- ASV (airspeed velocity)

### 安装依赖

```bash
pip install -r python/requirements.txt
```

## 使用方法

### 基本命令

```bash
cd python

# 跨机器对比
python main.py cmp ../cmp.yaml

# Commit 对比
python main.py cont ../cont.yaml

# 性能配置采集
python main.py collect ../collect.yaml

# 配置 SSH 免密登录
python main.py ssh-setup ../cmp.yaml
```

### 通用选项

| 选项 | 说明 |
|------|------|
| `--delay, -d TIME` | 延迟执行（如 `-d 10s`, `-d 30m`, `-d 6h`） |
| `--dry-run, -n` | 显示将要执行的命令，不实际执行 |
| `--verbose, -v` | 详细输出模式 |

### cmp 特有选项

| 选项 | 说明 |
|------|------|
| `--skip-run, -s` | 跳过 ASV 运行，直接使用已有结果对比 |
| `--output-dir, -o` | 覆盖配置文件中的输出目录 |
| `--info, -i` | 自定义标识（覆盖配置文件） |

### collect 特有选项

| 选项 | 说明 |
|------|------|
| `--force, -f` | 强制执行，跳过工具可用性检查 |
| `--output-dir, -o` | 输出目录 |

### 示例

```bash
# 跳过 ASV 运行，直接对比已有结果
python main.py cmp cmp.yaml --skip-run

# 延迟 30 分钟后执行
python main.py cont cont.yaml -d 30m

# 测试配置
python main.py cmp cmp.yaml --dry-run

# 详细输出
python main.py cmp cmp.yaml -v

# 强制执行采集（跳过工具检查）
python main.py collect collect.yaml --force

# 本地测试
python main.py cmp ../cmp_local.yaml --skip-run
python main.py cont ../cont_local.yaml --dry-run
python main.py collect ../collect_local.yaml --dry-run
```

## 配置

### 全局环境变量 (export)

三种模式均支持 YAML 顶层 `export:` 字段，定义自定义环境变量。这些变量在 scripts 中可通过 `{VAR_NAME}` 模板占位符引用，运行时自动导出为 shell 环境变量：

```yaml
export:
  BENCH_NAME: "bench_reduce"
  PYTHON_VER: "same"

compare_scripts:
  server1: |
    asv run -b "{BENCH_NAME}" --python={PYTHON_VER}
```

### cmp 配置

```yaml
# 全局环境变量（可选）
export:
  BENCH_NAME: "bench_reduce"
  PYTHON_VER: "same"

# 机器配置（必须恰好 2 台）
machines:
  server1:
    host: "zen4.example.com"           # 或 "local" 本地执行
    hostname: "z4"                     # 可选，ASV compare 显示名称
    port: 22                           # 可选，默认 22
    username: "user"                   # 远程必填
    asv_project_dir: "/home/user/benchmark"  # 必填

  server2:
    host: "kunpeng920b.example.com"
    hostname: "kp920"
    port: 22
    username: "user"
    asv_project_dir: "/home/user/benchmark"

# 执行脚本（必填）
# 支持 {work_dir} 和 export 变量占位符
compare_scripts:
  server1: |
    source ~/miniconda3/bin/activate myenv
    cd {work_dir}
    rm -rf results
    asv run -b "{BENCH_NAME}" --python={PYTHON_VER}

  server2: |
    source ~/miniconda3/bin/activate myenv
    cd {work_dir}
    rm -rf results
    asv run -b "{BENCH_NAME}" --python={PYTHON_VER}

# 采集脚本（可选，compare.collect=true 时使用）
collect_scripts:
  server1: |
    source ~/miniconda3/bin/activate myenv
    eval "$COLLECT_ENV"

# 对比选项（可选）
compare:
  show_all: true           # 是否显示未变化的 benchmark，默认 true
  collect: false           # 是否在 compare 前采集性能配置，默认 false

# 输出配置（可选）
output:
  dir: "./cmp_results"
  custom_info: "numpy_test"

# 运行时配置（可选）
runtime:
  ssh_timeout: 30
  log_level: "INFO"
```

### cont 配置

```yaml
# 全局环境变量（可选）
export:
  BENCH_NAME: "bench_reduce"
  PYTHON_VER: "same"

# 机器配置（至少 1 台）
machines:
  server1:
    host: "zen4.example.com"
    hostname: "z4"
    port: 22
    username: "user"
    asv_project_dir: "/home/user/benchmark"

  server2:
    host: "kunpeng920b.example.com"
    hostname: "kp920"
    port: 22
    username: "user"
    asv_project_dir: "/home/user/benchmark"

# 对比的 commit（可选，提供 {base} {branch} 模板变量）
commits:
  base: "HEAD~1"
  branch: "HEAD"

# 执行脚本（可选）
# 支持 {work_dir} {base} {branch} 和 export 变量占位符
cont_scripts:
  server1: |
    cd {work_dir}
    asv continuous {base} {branch} -b "{BENCH_NAME}" --python={PYTHON_VER}

  server2: |
    cd {work_dir}
    asv continuous {base} {branch} -b "{BENCH_NAME}" --python={PYTHON_VER}

# 输出配置（可选）
output:
  dir: "./cont_results"
  custom_info: "numpy_test"

# 运行时配置（可选）
runtime:
  ssh_timeout: 30
  log_level: "INFO"
```

### collect 配置

```yaml
# 全局环境变量（可选）
export:
  ENV_NAME: "numpy_bench"

# 机器配置（至少 1 台）
machines:
  server1:
    host: "zen4.example.com"
    hostname: "zen4"                    # 对比报告中的显示名称
    port: 22
    username: "user"
    # collect 不需要 asv_project_dir

  server2:
    host: "kunpeng950.example.com"
    hostname: "kunpeng950"
    port: 22
    username: "user"

# 环境初始化脚本（可选）
# 必须在脚本中执行 eval "$COLLECT_ENV" 以采集环境信息
collect_scripts:
  server1: |
    source ~/miniconda3/bin/activate numpy_bench
    eval "$COLLECT_ENV"

  server2: |
    docker exec numpy_container sh -c "$COLLECT_ENV"

# 输出配置（可选）
output:
  dir: "./collect_results"
  custom_info: "zen4_vs_kp950"
```

> **collect 采集内容**: BIOS (dmidecode)、CPU (型号/核心/缓存/指令集/NUMA)、内存 (大页/透明大页)、内核参数、环境配置 (Python/GCC/BLAS/LAPACK)、环境变量、系统限制 (ulimit)、系统服务 (irqbalance/tuned)、Swap 配置

### 配置字段对照表

#### 机器配置 (machines — 三种模式统一)

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `host` | 是 | - | 主机名或 `"local"` 本地执行 |
| `hostname` | 否 | name 值 | 显示名称（报告中的机器标识） |
| `port` | 否 | 22 | SSH 端口 |
| `username` | 远程必填 | - | SSH 用户名 |
| `asv_project_dir` | cmp/cont 必填 | - | ASV 项目目录 |

#### 脚本字段及各模式专属字段

| 字段 | 模式 | 必填 | 说明 |
|------|------|------|------|
| `export` | 三种模式 | 否 | 全局环境变量，可在 scripts 中以 `{VAR}` 引用 |
| `compare_scripts` | cmp | 是 | ASV compare 执行脚本，支持 `{work_dir}` 和 export 变量 |
| `collect_scripts` | cmp / collect | 否 | 环境初始化脚本 |
| `cont_scripts` | cont | 否 | ASV continuous 执行脚本，支持 `{work_dir}` `{base}` `{branch}` 和 export 变量 |
| `commits` | cont | 否 | `{base}` `{branch}` 模板变量来源 |
| `compare.show_all` | cmp | 否 | 默认 true |
| `compare.collect` | cmp | 否 | 默认 false |
| `output.dir` | 三种模式 | 否 | 输出目录 |
| `output.custom_info` | 三种模式 | 否 | 输出目录名中的自定义标识 |
| `runtime.ssh_timeout` | cmp / cont | 否 | SSH 超时秒数，默认 30 |
| `runtime.log_level` | cmp / cont | 否 | 日志级别，默认 INFO |

## 输出

### cmp 模式

在 `<output.dir>/asv_compare_<timestamp>_<info>/` 下生成：

- `server1_vs_server2_table.txt` — ASV 对比表格（文本格式）
- `server1_vs_server2_table.xlsx` — Excel 对比表格
- `server1_results/`、`server2_results/` — 各机器原始结果
- `perf_config/` — 性能配置对比报告（当 `compare.collect: true` 时）

### cont 模式

在 `<output.dir>/` 下生成：

- `<info>_<timestamp>_summary.txt` — 执行结果汇总

### collect 模式

在 `<output.dir>/perf_config_<timestamp>_<info>/` 下生成：

- `<machine_name>_perf.yaml` — 各机器性能配置
- `perf_compare.md` — Markdown 对比报告（多机器时）

## 代码架构

```
python/
├── main.py                  # CLI 入口，argparse 子命令
├── cli/
│   ├── cmp_cmd.py           # cmp 子命令
│   ├── cont_cmd.py          # cont 子命令
│   ├── collect_cmd.py       # collect 子命令
│   └── ssh_setup_cmd.py     # ssh-setup 子命令
├── core/
│   ├── machine_config.py    # 统一的 MachineConfig（三种模式共用）
│   ├── template.py          # 模板渲染 + export 语句生成
│   ├── config.py            # cmp 配置解析
│   ├── cont_config.py       # cont 配置解析
│   ├── collect_config.py    # collect 配置解析
│   ├── executor.py          # 脚本执行器
│   ├── downloader.py        # 结果下载器（SCP）
│   ├── perf_collector.py    # 性能配置采集器
│   └── perf_comparator.py   # 性能配置对比器
├── ssh_utils.py             # SSH 客户端（subprocess）
└── asv_compare_wrapper.py   # ASV compare 包装器
```

## 故障排除

### SSH 连接失败

使用 `ssh-setup` 命令一键配置免密登录：

```bash
python main.py ssh-setup ../cmp.yaml
```

或手动配置：

```bash
ssh-copy-id user@server
```

### 工具检查失败（collect 模式）

采集模式会检查远程服务器的工具可用性。缺失工具时可：

1. 按提示安装对应工具
2. 使用 `--force` 强制跳过检查（缺失项显示为 NA）

### ASV 结果未找到

检查配置文件中的 `asv_project_dir` 是否正确，确保 `results/` 目录存在。

## 许可证

MIT License
