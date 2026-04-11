# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-11
**Project:** ASV Benchmark 对比工具

## OVERVIEW
ASV Benchmark 对比工具 - 在多台服务器上执行 ASV benchmark 并生成 Excel 对比报告（Bash + Python 混合）

## STRUCTURE
```
asv_tools/
├── lib/              # Bash 工具库（SSH、YAML、日志、依赖检查）
├── python/           # Python 核心模块（解析、对比、报告生成）
├── logs/             # 运行日志
├── output/           # Excel 对比报告输出
├── tmp/              # 临时文件
├── config.sh         # 主配置（默认脚本、输出目录、SSH 超时）
├── servers.yaml      # 服务器配置（多台服务器连接信息）
├── run_compare.sh    # 主入口脚本
└── README.md         # 项目文档
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| 主执行流程 | `run_compare.sh` | SSH 连接、脚本执行、结果下载、对比分析 |
| 服务器配置 | `servers.yaml` | 定义服务器 host、port、username、asv_project_dir |
| 主配置 | `config.sh` | 默认脚本模板、输出目录、SSH 超时、日志级别 |
| ASV 结果解析 | `python/asv_parser.py` | 解析 benchmarks.json，提取 benchmark 时间 |
| Benchmark 对比 | `python/benchmark_comparator.py` | 比较两台服务器的 benchmark 结果 |
| Excel 报告生成 | `python/excel_generator.py` | 生成带颜色标识的 Excel 对比报告 |
| SSH 工具 | `lib/ssh_utils.sh` | ssh_test_connection, ssh_execute, scp_download, scp_upload |
| YAML 解析 | `lib/yaml_parser.sh` | yaml_get_value, yaml_get_server_config |
| 日志工具 | `lib/log_utils.sh` | log_debug, log_info, log_warning, log_error |
| 依赖检查 | `lib/dependency_checker.sh` | check_dependencies |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| parse_asv_results | function | python/asv_parser.py | 解析 ASV 结果目录 |
| get_latest_commit | function | python/asv_parser.py | 获取最新 commit hash |
| extract_benchmark_times | function | python/asv_parser.py | 提取 benchmark 时间数据 |
| compare_benchmarks | function | python/asv_parser.py | 比较两台服务器的 benchmark |
| generate_excel | function | python/excel_generator.py | 生成 Excel 对比报告 |
| ssh_test_connection | function | lib/ssh_utils.sh | 测试 SSH 连接 |
| ssh_execute | function | lib/ssh_utils.sh | 远程执行命令 |
| scp_download | function | lib/ssh_utils.sh | 下载远程文件 |
| yaml_get_server_config | function | lib/yaml_parser.sh | 获取服务器配置 |

## CONVENTIONS

### Bash 脚本
- 使用 `set -euo pipefail` 严格模式
- 函数命名：小写加下划线（如 `ssh_test_connection`）
- 日志函数：`log_info`, `log_error`, `log_warning`, `log_debug`
- 配置通过 `source` 加载（config.sh, lib/*.sh）

### Python 脚本
- Python 3.6+ 兼容
- 使用标准库 + openpyxl + pyyaml
- 类型提示（typing 模块）

### 配置文件
- `servers.yaml`: 定义服务器配置（host, port, username, asv_project_dir）
- `config.sh`: 定义默认脚本、输出目录、SSH 超时、日志级别
- `python/requirements.txt`: Python 依赖（openpyxl>=3.1.0, pyyaml>=6.0）

### 输出文件
- Excel 报告：`TIMESTAMP_server1_vs_server2[_CUSTOM_INFO].xlsx`
- JSON 对比结果：`compare_result_TIMESTAMP.json`

## ANTI-PATTERNS (THIS PROJECT)

### 安全
- ❌ SSH 使用 `StrictHostKeyChecking=no`（仅用于受信任环境）
- ❌ 密码不存储在配置文件中（使用 SSH 免密登录）

### 依赖管理
- ❌ requirements.txt 未使用版本锁定（建议使用 pip freeze）
- ❌ 无 .gitignore 文件（应忽略 __pycache__/, *.pyc, logs/, tmp/）

### 测试
- ❌ 无 tests/ 目录
- ❌ 无单元测试或集成测试

## UNIQUE STYLES

### 混合语言架构
- Bash 作为主入口和协调器
- Python 处理核心逻辑（数据解析、对比、报告生成）
- 通过 subprocess 调用 Python 模块

### SSH 远程执行
- 使用 `ssh -o BatchMode=yes` 避免交互式提示
- 支持自定义脚本通过 stdin 传递（`bash -s < script.sh`）
- 支持 Docker 容器场景（通过 `docker exec`）

### ASV 结果结构
- ASV 结果目录：`asv_project_dir/results/`
- 结果结构：`results/<machine>/<commit>/benchmarks.json`
- 机器名称可通过 `machine_name` 配置项指定

## COMMANDS
```bash
# 基本使用
./run_compare.sh <server1> <server2>

# 使用自定义脚本
./run_compare.sh zen4 kunpeng920b --script1 script1.sh --script2 script2.sh

# 添加自定义标识
./run_compare.sh zen4 kunpeng920b --info "numpy_v2.0"

# Dry-run 模式
./run_compare.sh zen4 kunpeng920b --dry-run

# 安装 Python 依赖
pip install -r python/requirements.txt
```

## NOTES

### 前置要求
- Bash 4.0+
- Python 3.6+
- SSH 免密登录配置
- jq（JSON 处理工具）

### Docker 容器场景
```bash
cat > docker_script.sh << 'EOF'
docker exec -it my_container bash -c '
    source /opt/conda/bin/activate myenv
    cd /workspace/project
    asv run --python=same --bench my_benchmark -v
'
EOF
./run_compare.sh zen4 kunpeng920b --script1 docker_script.sh --script2 docker_script.sh
```

### 配置模板
- 默认脚本使用变量替换：`{work_dir}` 会被替换为实际的工作目录
- 服务器配置支持多台服务器，通过名称匹配

### 输出目录
- `cmp_results/`: 对比结果目录（每次运行创建独立的 asv_compare_xxx 目录）
- `logs/`: 运行日志（按日期归档）
