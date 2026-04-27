# ASV Benchmark 对比工具

一个用于在多台服务器上执行 ASV benchmark 并进行结果对比的工具。

## 功能特性

- 单配置文件定义完整对比任务
- 支持本地和远程服务器
- 使用 ASV 官方 Compare API 生成对比表格
- 输出 TXT 和 Excel 格式报告

## 安装

### 前置要求

- Python 3.6+
- SSH 免密登录配置（如需远程服务器）
- ASV (airspeed velocity)

### 安装依赖

```bash
pip install -r python/requirements.txt
```

## 配置

创建 `cmp.yaml` 配置文件：

```yaml
machines:
  server1:
    host: "zen4.example.com"      # 或 "local" 表示本地执行
    port: 22
    username: "user"
    asv_project_dir: "/home/user/benchmark"

  server2:
    host: "kunpeng920b.example.com"
    port: 22
    username: "user"
    asv_project_dir: "/home/user/benchmark"

scripts:
  server1: |
    source ~/miniconda3/bin/activate myenv
    cd {work_dir}
    rm -rf results
    asv run -b "bench_app" --python=same

  server2: |
    source ~/miniconda3/bin/activate myenv
    cd {work_dir}
    rm -rf results
    asv run -b "bench_reduce" --python=same

compare:
  show_all: true                  # 是否显示未变化的 benchmark

output:
  dir: "./cmp_results"
  custom_info: "numpy_test"       # 可选，自定义标识

runtime:
  ssh_timeout: 30
  log_level: "INFO"
```

### 本地测试配置

使用 `host: "local"` 跳过 SSH，直接本地执行：

```yaml
machines:
  server1:
    host: "local"
    username: "user"
    asv_project_dir: "/path/to/benchmark"

  server2:
    host: "local"
    username: "user"
    asv_project_dir: "/path/to/benchmark"

scripts:
  server1: |
    cd {work_dir}
    rm -rf results
    asv run --python=same

  server2: |
    cd {work_dir}
    rm -rf results
    asv run --python=same

compare:
  show_all: true
```

### 配置字段说明

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `machines.*.host` | 是 | - | 主机名或 "local" |
| `machines.*.port` | 否 | 22 | SSH 端口 |
| `machines.*.username` | 远程必填 | - | SSH 用户名 |
| `machines.*.asv_project_dir` | 是 | - | ASV 项目目录 |
| `scripts.*` | 是 | - | 每台机器的执行脚本，支持 `{work_dir}` 占位符 |
| `compare.show_all` | 否 | true | 是否显示未变化的 benchmark |
| `output.dir` | 否 | "./cmp_results" | 输出目录 |
| `output.custom_info` | 否 | - | 自定义标识 |
| `runtime.ssh_timeout` | 否 | 30 | SSH 超时秒数 |
| `runtime.log_level` | 否 | "INFO" | 日志级别 |

## 使用方法

### 基本使用

```bash
cd python
python main.py cmp ../cmp.yaml
```

### 命令选项

| 选项 | 说明 |
|------|------|
| `--skip-run, -s` | 跳过 ASV 运行，直接使用已有结果对比 |
| `--dry-run, -n` | 显示将要执行的命令，不实际执行 |
| `--verbose, -v` | 详细输出模式 |
| `--output-dir, -o` | 覆盖配置文件中的输出目录 |
| `--info, -i` | 自定义标识（覆盖配置文件） |

### 示例

```bash
# 跳过 ASV 运行，直接对比已有结果
python main.py cmp cmp.yaml --skip-run

# 测试配置
python main.py cmp cmp.yaml --dry-run

# 详细输出
python main.py cmp cmp.yaml -v

# 自定义输出目录和标识
python main.py cmp cmp.yaml -o ./my_results -i "numpy_v2"
```

## 输出

工具在 `cmp_results/` 目录下生成以下文件：

- `TIMESTAMP_server1_vs_server2_table.txt` - ASV 对比表格（文本格式）
- `TIMESTAMP_server1_vs_server2_table.xlsx` - Excel 对比表格

## 故障排除

### SSH 连接失败

确保已配置 SSH 免密登录：

```bash
ssh-copy-id user@server
```

### Python 依赖缺失

安装依赖：

```bash
pip install -r python/requirements.txt
```

### ASV 结果未找到

检查配置文件中的 `asv_project_dir` 是否正确。

## 许可证

MIT License