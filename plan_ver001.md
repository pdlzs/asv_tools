# ASV Benchmark对比工具实现计划

## 背景

用户需要一个工具来在两台服务器（Zen4和Kunpeng920b）上执行ASV benchmark并进行结果对比。两台服务器已配置SSH免密登录，需要执行自定义脚本（包含conda activate、cd路径、代理配置等），最后生成Excel对比表格。

**要求**：使用bash脚本（主）+ Python（辅助）实现，便于定制化。

## ASV架构理解

**重要**：ASV的工作机制与当前计划理解不同：

1. **ASV结果结构**：
   - 每次运行生成唯一的commit hash（基于时间戳和内容）
   - 结果存储在 `results/` 目录下
   - 每个commit对应一个子目录，包含JSON格式的benchmark结果

2. **asv compare的正确用法**：
   - `asv compare COMMIT1 COMMIT2` - 比较两个commit的结果
   - 需要在ASV项目目录下执行
   - 比较的结果包含详细的时间、统计信息
   - 比较的commit是ASV运行时生成的hash

3. **ASV目录结构**：
   ```
   asv_project_dir/
   ├── .asv.conf              # ASV配置文件
   ├── results/           # 结果存储目录（重要！）
   │   ├── machine_name/  # 机器名称目录
   │   │   ├── commit_hash/  # 每次运行的commit
   │   │   │   ├── benchmarks.json
   │   │   │   ├── machine.json
   │   │   │   └── ...
   │   │   └── ...
   ├── env/               # 虚拟环境目录
   └── ...
   ```

4. **跨服务器对比的挑战**：
   - 两台服务器的结果不能直接"合并"
   - 需要在本地创建虚拟ASV环境来统一管理结果
   - 或者直接解析JSON结果进行对比

## 实现计划

### 方案选择

**推荐方案：直接解析ASV JSON结果（方案B）**

理由：
- ✅ 不依赖本地ASV安装
- ✅ 更灵活，可以自定义对比逻辑
- ✅ 更容易调试和扩展
- ✅ 不需要创建虚拟ASV环境

### 1. 项目目录结构

```
asv_tools/
├── README.md                      # 使用说明
├── servers.yaml                   # 服务器配置文件
├── config.sh                      # 主配置文件
├── run_compare.sh                 # 主执行脚本
├── lib/
│   ├── ssh_utils.sh              # SSH工具函数
│   ├── yaml_parser.sh            # YAML解析工具
│   ├── log_utils.sh              # 日志工具函数
│   └── dependency_checker.sh     # 依赖检查工具
├── python/
│   ├── requirements.txt          # Python依赖
│   ├── excel_generator.py        # Excel生成（基于JSON结果）
│   ├── asv_parser.py             # ASV JSON结果解析器
│   └── benchmark_comparator.py   # Benchmark对比引擎
├── output/                       # 输出目录
├── logs/                         # 日志目录
└── tmp/                          # 临时文件目录
```

### 2. 配置文件

#### servers.yaml (服务器配置)

```yaml
# 服务器配置文件
# 支持多台服务器，通过name匹配

servers:
  zen4:
    host: "zen4.example.com"
    port: 22
    username: "user"
    # ASV项目目录（包含.asv/目录）
    # ASV结果将存储在: asv_project_dir/results/
    asv_project_dir: "/home/user/benchmark"
    # 可选：指定机器名称（默认为hostname）
    # machine_name: "zen4-server"

  kunpeng920b:
    host: "kunpeng920b.example.com"
    port: 22
    username: "user"
    # ASV项目目录（包含.asv/目录）
    asv_project_dir: "/home/user/benchmark"
    # 可选：指定机器名称
    # machine_name: "kunpeng-server"

  # 可以添加更多服务器
  intel_xeon:
    host: "intel.example.com"
    port: 22
    username: "user"
    asv_project_dir: "/home/user/benchmark"

# 默认服务器（用于快速运行）
default_servers: ["zen4", "kunpeng920b"]

# ASV配置
asv:
  # 要比较的commit选择策略
  # latest: 比较最新的commit
  # specific: 比较指定的commit（通过--commit参数）
  compare_strategy: "latest"
  # 比较的commit（仅当strategy为specific时使用）
  # server1_commit: "abc123"
  # server2_commit: "def456"
  # 是否显示所有benchmark（包括未变化的）
  show_all: false
```

#### config.sh (主配置)

```bash
#!/bin/bash
# ASV Benchmark对比工具主配置

# ==================== 依赖检查 ====================

# 必需的命令
REQUIRED_COMMANDS=("ssh" "scp" "python3" "jq")

# ==================== 默认脚本 ====================

# 默认前置脚本（用于所有所有服务器）
# 可以通过命令行参数 --script1/--script2 覆盖
DEFAULT_SCRIPT='
# 激活conda环境
source ~/miniconda3/bin/activate myenv
# 进入工作目录
cd {work_dir}
# 设置代理（可选）
# export http_proxy=http://proxy:port
# export https_proxy=http://proxy:port
# 运行ASV benchmark
asv run --python=same --bench my_benchmark -v
'

# ==================== 输出配置 ====================

# 输出目录
OUTPUT_DIR="./output"

# 临时文件目录
TMP_DIR="./tmp"

# 输出文件名中的自定义标识（可选）
# 例如: "numpy_v2.0", "pandas_opt", "baseline"
CUSTOM_INFO=""

# ==================== 其他配置 ====================

# SSH连接超时（秒）
SSH_TIMEOUT=30

# 日志级别 (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL="INFO"

# 是否保留临时文件
KEEP_TEMP_FILES=false
```

### 3. 主执行脚本 (run_compare.sh)

```bash
#!/bin/bash
# ASV Benchmark对比工具主脚本
# 用法: ./run_compare.sh <server1> <server2> [--script1 <script_file>] [--script2 <script_file>] [--info <custom_info>] [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# 加载工具函数
source "$SCRIPT_DIR/lib/ssh_utils.sh"
source "$SCRIPT_DIR/lib/yaml_parser.sh"
source "$SCRIPT_DIR/lib/log_utils.sh"
source "$SCRIPT_DIR/lib/dependency_checker.sh"

# 初始化日志
init_log "$LOG_LEVEL"

# 创建必要的目录
mkdir -p "$OUTPUT_DIR"
mkdir -p logs
mkdir -p "$TMP_DIR"

# ==================== 解析命令行参数 ====================

SERVER1=""
SERVER2=""
SCRIPT1=""
SCRIPT2=""
CUSTOM_INFO_ARG=""
DRY_RUN=false

print_usage() {
    echo "用法: $0 <server1> <server2> [选项]"
    echo ""
    echo "选项:"
    echo "  --script1 <file>    Server1的自定义脚本"
    echo "  --script2 <file>    Server2的自定义脚本"
    echo "  --info <string>     输出文件名的自定义标识"
    echo "  --dry-run                    只显示将要执行的命令，不实际执行"
    echo "  --help               显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 zen4 kunpeng920b"
    echo "  $0 zen4 kunpeng920b --info 'numpy_v2.0'"
    echo "  $0 zen4 kunpeng920b --script1 script1.sh --script2 script2.sh"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --script1)
            SCRIPT1="$2"
            shift 2
            ;;
        --script2)
            SCRIPT2="$2"
            shift 2
            ;;
        --info)
            CUSTOM_INFO_ARG="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            print_usage
            exit 0
            ;;
        *)
            if [ -z "$SERVER1" ]; then
                SERVER1="$1"
            elif [ -z "$SERVER2" ]; then
                SERVER2="$1"
            else
                log_error "参数过多: $1"
                print_usage
                exit 1
            fi
            shift
            ;;
    esac
done

# ==================== 依赖检查 ====================

log_info "检查依赖..."
check_dependencies "${REQUIRED_COMMANDS[@]}"

# 检查Python依赖
log_info "检查Python依赖..."
python3 -c "import yaml, openpyxl" 2>/dev/null || {
    log_error "缺少Python依赖，请运行: pip install -r python/requirements.txt"
    exit 1
}

# ==================== 加载服务器配置 ====================

log_info "加载服务器配置..."

# 如果没有指定服务器，使用默认配置
if [ -z "$SERVER1" ] || [ -z "$SERVER2" ]; then
    log_info "未指定服务器，使用默认配置..."
    DEFAULT_SERVERS=$(yaml_get_value "$SCRIPT_DIR/servers.yaml" "default_servers")
    SERVER1=$(echo "$DEFAULT_SERVERS" | jq -r '.[0]')
    SERVER2=$(echo "$DEFAULT_SERVERS" | jq -r '.[1]')
fi

# 加载服务器配置
SERVER1_CONFIG=$(yaml_get_server_config "$SCRIPT_DIR/servers.yaml" "$SERVER1")
SERVER2_CONFIG=$(yaml_get_server_config "$SCRIPT_DIR/servers.yaml" "$SERVER2")

# 验证服务器配置
if [ -z "$SERVER1_CONFIG" ] || [ "$SERVER1_CONFIG" = "null" ]; then
    log_error "找不到服务器配置: $SERVER1"
    exit 1
fi

if [ -z "$SERVER2_CONFIG" ] || [ "$SERVER2_CONFIG" = "null" ]; then
    log_error "找不到服务器配置: $SERVER2"
    exit 1
fi

SERVER1_HOST=$(echo "$SERVER1_CONFIG" | jq -r '.host')
SERVER1_USER=$(echo "$SERVER1_CONFIG" | jq -r '.username')
SERVER1_PORT=$(echo "$SERVER1_CONFIG" | jq -r '.port')
SERVER1_PROJECT_DIR=$(echo "$SERVER1_CONFIG" | jq -r '.asv_project_dir')
SERVER1_MACHINE_NAME=$(echo "$SERVER1_CONFIG" | jq -r '.machine_name // empty')
# ASV结果目录: asv_project_dir/results/
SERVER1_ASV_RESULTS_DIR="${SERVER1_PROJECT_DIR}/results"

SERVER2_HOST=$(echo "$SERVER2_CONFIG" | jq -r '.host')
SERVER2_USER=$(echo "$SERVER2_CONFIG" | jq -r '.username')
SERVER2_PORT=$(echo "$SERVER2_CONFIG" | jq -r '.port')
SERVER2_PROJECT_DIR=$(echo "$SERVER2_CONFIG" | jq -r '.asv_project_dir')
SERVER2_MACHINE_NAME=$(echo "$SERVER2_CONFIG" | jq -r '.machine_name // empty')
# ASV结果目录: asv_project_dir/results/
SERVER2_ASV_RESULTS_DIR="${SERVER2_PROJECT_DIR}/results"

log_info "========== ASV Benchmark对比工具 =========="
log_info "Server1: $SERVER1 ($SERVER1_USER@$SERVER1_HOST:$SERVER1_PORT)"
log_info "Server2: $SERVER2 ($SERVER2_USER@$SERVER2_HOST:$SERVER2_PORT)"

# ==================== SSH连接验证 ====================

log_info "验证SSH连接..."

if ! ssh_test_connection "$SERVER1_HOST" "$SERVER1_USER" "$SERVER1_PORT"; then
    log_error "无法连接到 $SERVER1"
    exit 1
fi

if ! ssh_test_connection "$SERVER2_HOST" "$SERVER2_USER" "$SERVER2_PORT"; then
    log_error "无法连接到 $SERVER2"
    exit 1
fi

log_info "SSH连接验证成功"

# ==================== 生成输出文件名 ====================

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
if [ -n "$CUSTOM_INFO_ARG" ]; then
    CUSTOM_INFO="$CUSTOM_INFO_ARG"
fi

if [ -n "$CUSTOM_INFO" ]; then
    OUTPUT_FILE="${TIMESTAMP}_${SERVER1}_vs_${SERVER2}_${CUSTOM_INFO}.xlsx"
else
    OUTPUT_FILE="${TIMESTAMP}_${SERVER1}_vs_${SERVER2}.xlsx"
fi

OUTPUT_PATH="$OUTPUT_DIR/$OUTPUT_FILE"

log_info "输出文件: $OUTPUT_PATH"

# ==================== 在Server1上执行脚本 ====================

log_info "在 $SERVER1 上执行脚本..."

if [ -n "$SCRIPT1" ]; then
    # 使用自定义脚本
    if [ ! -f "$SCRIPT1" ]; then
        log_error "脚本文件不存在: $SCRIPT1"
        exit 1
    fi
    log_info "使用自定义脚本: $SCRIPT1"
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] 将在 $SERVER1 上执行: bash -s < $SCRIPT1"
    else
        ssh_execute "$SERVER1_HOST" "$SERVER1_USER" "$SERVER1_PORT" \
            "cd $SERVER1_PROJECT_DIR && bash -s" < "$SCRIPT1" || {
            log_error "在 $SERVER1 上执行脚本失败"
            exit 1
        }
    fi
else
    # 使用默认脚本
    log_info "使用默认脚本"
    # 替换变量
    SCRIPT_RENDERED=$(echo "$DEFAULT_SCRIPT" | sed "s|{work_dir}|$SERVER1_PROJECT_DIR|g")
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] 将在 $SERVER1 上执行默认脚本"
    else
        ssh_execute "$SERVER1_HOST" "$SERVER1_USER" "$SERVER1_PORT" \
            "$SCRIPT_RENDERED" || {
            log_error "在 $SERVER1 上执行脚本失败"
            exit 1
        }
    fi
fi

# ==================== 在Server2上执行脚本 ====================

log_info "在 $SERVER2 上执行脚本..."

if [ -n "$SCRIPT2" ]; then
    # 使用自定义脚本
    if [ ! -f "$SCRIPT2" ]; then
        log_error "脚本文件不存在: $SCRIPT2"
        exit 1
    fi
    log_info "使用自定义脚本: $SCRIPT2"
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] 将在 $SERVER2 上执行: bash -s < $SCRIPT2"
    else
        ssh_execute "$SERVER2_HOST" "$SERVER2_USER" "$SERVER2_PORT" \
            "cd $SERVER2_PROJECT_DIR && bash -s" < "$SCRIPT2" || {
            log_error "在 $SERVER2 上执行脚本失败"
            exit 1
        }
    fi
else
    # 使用默认脚本
    log_info "使用默认脚本"
    # 替换变量
    SCRIPT_RENDERED=$(echo "$DEFAULT_SCRIPT" | sed "s|{work_dir}|$SERVER2_PROJECT_DIR|g")
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] 将在 $SERVER2 上执行默认脚本"
    else
        ssh_execute "$SERVER2_HOST" "$SERVER2_USER" "$SERVER2_PORT" \
            "$SCRIPT_RENDERED" || {
            log_error "在 $SERVER2 上执行脚本失败"
            exit 1
        }
    fi
fi

if [ "$DRY_RUN" = true ]; then
    log_info "[DRY-RUN] 跳过后续步骤（dry-run模式）"
    exit 0
fi

# ==================== 获取ASV结果 ====================

log_info "获取ASV结果..."

# 临时目录
TEMP_DIR="$TMP_DIR/asv_compare_${TIMESTAMP}"
mkdir -p "$TEMP_DIR"

# 从Server1下载ASV结果
log_info "从 $SERVER1 下载ASV结果..."
SERVER1_RESULTS_LOCAL="$TEMP_DIR/${SERVER1}_results"
mkdir -p "$SERVER1_RESULTS_LOCAL"

scp_download "$SERVER1_HOST" "$SERVER1_USER" "$SERVER1_PORT" \
    "$SERVER1_ASV_RESULTS_DIR" "$SERVER1_RESULTS_LOCAL" || {
    log_error "从 $SERVER1 下载ASV结果失败"
    exit 1
}

# 从Server2下载ASV结果
log_info "从 $SERVER2 下载ASV结果..."
SERVER2_RESULTS_LOCAL="$TEMP_DIR/${SERVER2}_results"
mkdir -p "$SERVER2_RESULTS_LOCAL"

scp_download "$SERVER2_HOST" "$SERVER2_USER" "$SERVER2_PORT" \
    "$SERVER2_ASV_RESULTS_DIR" "$SERVER2_RESULTS_LOCAL" || {
    log_error "从 $SERVER2 下载ASV结果失败"
    exit 1
}

# 验证结果目录
log_info "验证下载的ASV结果..."
if [ ! -d "$SERVER1_RESULTS_LOCAL" ] || [ -z "$(ls -A $SERVER1_RESULTS_LOCAL)" ]; then
    log_error "Server1的结果目录为空: $SERVER1_RESULTS_LOCAL"
    exit 1
fi

if [ ! -d "$SERVER2_RESULTS_LOCAL" ] || [ -z "$(ls -A $SERVER2_RESULTS_LOCAL)" ]; then
    log_error "Server2的结果目录为空: $SERVER2_RESULTS_LOCAL"
    exit 1
fi

# ==================== 执行ASV结果对比 ====================

log_info "执行ASV结果对比..."

# 获取ASV配置
COMPARE_STRATEGY=$(yaml_get_value "$SCRIPT_DIR/servers.yaml" "asv.compare_strategy" | jq -r '.')
COMPARE_STRATEGY=${COMPARE_STRATEGY:-"latest"}
SHOW_ALL=$(yaml_get_value "$SCRIPT_DIR/servers.yaml" "asv.show_all" | jq -r '.')
SHOW_ALL=${SHOW_ALL:-"false"}

# 构建Python对比命令
COMPARE_CMD="python3 \"$SCRIPT_DIR/python/benchmark_comparator.py\" \
    --results1 \"$SERVER1_RESULTS_LOCAL\" \
    --results2 \"$SERVER2_RESULTS_LOCAL\" \
    --server1 \"$SERVER1\" \
    --server2 \"$SERVER2\" \
    --strategy \"$COMPARE_STRATEGY\" \
    --output \"$OUTPUT_DIR/compare_result_${TIMESTAMP}.json\""

if [ "$SHOW_ALL" = "true" ]; then
    COMPARE_CMD="$COMPARE_CMD --show-all"
fi

# 执行对比
log_info "执行对比命令: $COMPARE_CMD"
eval "$COMPARE_CMD" || {
    log_error "执行ASV结果对比失败"
    exit 1
}

COMPARE_RESULT_FILE="$OUTPUT_DIR/compare_result_${TIMESTAMP}.json"
log_info "对比结果已保存到: $COMPARE_RESULT_FILE"

# ==================== 生成Excel对比报告 ====================

log_info "生成Excel对比报告..."

python3 "$SCRIPT_DIR/python/excel_generator.py" \
    --compare-result "$COMPARE_RESULT_FILE" \
    --output "$OUTPUT_PATH" || {
    log_error "生成Excel报告失败"
    exit 1
}

# ==================== 清理临时文件 ====================

if [ "$KEEP_TEMP_FILES" != "true" ]; then
    log_info "清理临时文件..."
    rm -rf "$TEMP_DIR"
else
    log_info "保留临时文件: $TEMP_DIR"
fi

log_info "完成！报告已保存到: $OUTPUT_PATH"
```

### 4. 工具函数库

#### lib/ssh_utils.sh

```bash
#!/bin/bash
# SSH工具函数

# SSH连接测试
ssh_test_connection() {
    local host=$1
    local user=$2
    local port=${3:-22}
    local timeout=${SSH_TIMEOUT:-30}

    ssh -o "ConnectTimeout=$timeout" -o "BatchMode=yes" \
        -o "StrictHostKeyChecking=no" -p "$port" "${user}@${host}" \
        "echo 'Connection successful'" >/dev/null 2>&1
}

# 在远程服务器执行命令
ssh_execute() {
    local host=$1
    local user=$2
    local port=$3
    shift 4
    local command="$@"

    ssh -o "ConnectTimeout=$SSH_TIMEOUT" -o "BatchMode=yes" \
        -o "StrictHostKeyChecking=no" -p "$port" "${user}@${host}" "$command"
}

# 从远程服务器下载文件/目录
scp_download() {
    local host=$1
    local user=$2
    local port=$3
    local remote_path=$4
    local local_path=$5

    scp -o "ConnectTimeout=$SSH_TIMEOUT" -o "BatchMode=yes" \
        -o "StrictHostKeyChecking=no" -P "$port" -r "${user}@${host}:${remote_path}" "$local_path"
}

# 上传文件到远程服务器
scp_upload() {
    local host=$1
    local user=$2
    local port=$3
    local local_path=$4
    local remote_path=$5

    scp -o "ConnectTimeout=$SSH_TIMEOUT" -o "BatchMode=yes" \
        -o "StrictHostKeyChecking=no" -P "$port" -r "$local_path" "${user}@${host}:${remote_path}"
}
```

#### lib/yaml_parser.sh

```bash
#!/bin/bash
# YAML解析工具（（使用Python）

# 获取YAML文件的值
yaml_get_value() {
    local yaml_file=$1
    local key=$2

    python3 -c "
import yaml
import json
import sys

try:
    with open('$yaml_file', 'r') as f:
        data = yaml.safe_load(f(f)

    # 解析key路径（支持点分隔）
    keys = '$key'.split('.')
    result = data
    for k in keys:
        result = result[k]

    print(json.dumps(result))
except Exception as e:
    print(json.dumps(None), file=sys.stderr)
    sys.exit(1)
" 2>/dev/null || echo "null"
}

# 获取服务器配置
yaml_get_server_config() {
    local yaml_file=$1
    local server_name=$2

    python3 -c "
import yaml
import json
import sys

try:
    with open('$yaml_file', 'r') as f:
        data = yaml.safe_load(f)

    server_config = data['servers']['$server_name']
    print(json.dumps(server_config))
except Exception as e:
    print(json.dumps(None), file=sys.stderr)
    sys.exit(1)
" 2>/dev/null || echo "null"
}
```

#### lib/log_utils.sh

```bash
#!/bin/bash
# 日志工具函数

LOG_LEVEL="INFO"

# 初始化日志
init_log() {
    LOG_LEVEL=$1
    mkdir -p logs
}

# 记录日志
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # 定义日志级别优先级
    declare -A levels=([DEBUG]=0 [INFO]=1 [WARNING]=2 [ERROR]=3)
    local current_level=${levels[$LOG_LEVEL]:-1}
    local msg_level=${levels[$level]:-1}

    # 只记录不低于当前日志级别的消息
    if [ $msg_level -ge $current_level ]; then
        # 输出到控制台
        case $level in
            ERROR)   echo -e "\033[31m[$timestamp] [$level] $message\033[0m" >&2 ;;
            WARNING) echo -e "\033[33m[$timestamp] [$level] $message\033[0m" ;;
            INFO)    echo -e "\033[32m[$timestamp] [$level] $message\033[0m" ;;
            DEBUG)   echo -e "\033[36m[$timestamp] [$level] $message\033[0m" ;;
        esac

        # 输出到日志文件
        echo "[$timestamp] [$level] $message" >> "logs/asv_tools_$(date +%Y%m%d).log"
    fi
}

log_debug() { log "DEBUG" "$@"; }
log_info() { log "INFO" "$@"; }
log_warning() { log "WARNING" "$@"; }
log_error() { log "ERROR" "$@"; }
```

#### lib/dependency_checker.sh

```bash
#!/bin/bash
# 依赖检查工具

# 检查命令是否存在
check_dependencies() {
    local missing=()

    for cmd in "$@"; do
        if ! command -v "$cmd" &> /dev/null; then
            missing+=("$cmd")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "缺少必需的命令: ${missing[*]}"
        log_error "请安装缺失的命令后重试"
        exit 1
    fi
}
```

### 5. Python辅助脚本

#### python/requirements.txt

```
openpyxl>=3.1.0
pyyaml>=6.0
```

#### python/asv_parser.py

```python
#!/usr/bin/env python3
"""
ASV结果解析器
解析ASV benchmark结果文件
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def parse_asv_results(results_dir: str, machine_name: Optional[str] = None) -> Dict:
    """
    解析ASV结果目录

    Args:
        results_dir: ASV结果目录路径（results/）
        machine_name: 可选的机器名称（用于过滤结果）

    Returns:
        包含所有benchmark结果的字典，按commit组织
        {
            "commit_hash": {
                "benchmarks": {
                    "benchmark_name": {
                        "time": float,
                        "stats": dict,
                        ...
                    },
                    ...
                },
                "machine": str,
                "timestamp": str,
            },
            ...
        }
    """
    results = {}
    results_path = Path(results_dir)

    if not results_path.exists():
        raise FileNotFoundError(f"ASV结果目录不存在: {results_dir}")

    # ASV结果目录结构: results_dir/machine_name/commit_hash/
    machine_dirs = [d for d in results_path.iterdir() if d.is_dir()]

    if machine_name:
        # 过滤指定的机器
        machine_dirs = [d for d in machine_dirs if d.name == machine_name]

    if not machine_dirs:
        raise ValueError(f"在 {results_dir} 中未找到机器结果目录")

    for machine_dir in machine_dirs:
        machine_name = machine_dir.name
        commit_dirs = [d for d in machine_dir.iterdir() if d.is_dir()]

        for commit_dir in commit_dirs:
            commit_hash = commit_dir.name

            # 读取benchmarks.json
            benchmarks_file = commit_dir / "benchmarks.json"
            if not benchmarks_file.exists():
                continue

            try:
                with open(benchmarks_file, 'r') as f:
                    benchmarks_data = json.load(f)

                # 读取machine.json获取机器信息
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
    """
    获取最新的commit hash

    Args:
        results: parse_asv_results返回的结果字典

    Returns:
        最新的commit hash，如果没有结果则返回None
    """
    if not results:
        return None

    # ASV的commit hash通常是时间戳，可以直接比较
    return max(results.keys())


def extract_benchmark_times(commit_data: Dict) -> Dict[str, float]:
    """
    从commit数据中提取benchmark时间

    Args:
        commit_data: 单个commit的数据

    Returns:
        benchmark名称到时间的映射
    """
    benchmarks = {}
    benchmarks_data = commit_data.get("benchmarks", {})

    for bench_name, bench_data in benchmarks_data.items():
        if isinstance(bench_data, dict):
            # ASV结果可能包含多个环境或参数化版本
            # 取第一个有效的时间值
            time_value = None

            # 尝试直接获取time字段
            if "time" in bench_data:
                time_value = bench_data["time"]
            # 尝试获取result字段
            elif "result" in bench_data:
                time_value = bench_data["result"]
            # 尝试获取samples字段的平均值
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
    """
    比较两个ASV结果

    Args:
        results1: Server1的结果字典
        results2: Server2的结果字典
        commit1: Server1的commit hash（None表示使用最新的）
        commit2: Server2的commit hash（None表示使用最新的）

    Returns:
        比较结果列表
        [
            {
                "benchmark": str,
                "time1": float,
                "time2": float,
                "speedup": float,
                "diff_percent": float,
                "stats1": dict,
                "stats2": dict,
            },
            ...
        ]
    """
    # 获取要比较的commit
    if commit1 is None:
        commit1 = get_latest_commit(results1)
    if commit2 is None:
        commit2 = get_latest_commit(results2)

    if commit1 is None or commit2 is None:
        raise ValueError("无法找到要比较的commit")

    # 提取benchmark时间
    times1 = extract_benchmark_times(results1[commit1])
    times2 = extract_benchmark_times(results2[commit2])

    # 找出所有benchmark名称
    all_benchmarks = set(times1.keys()) | set(times2.keys())

    comparison = []
    for bench_name in sorted(all_benchmarks):
        time1 = times1.get(bench_name, 0.0)
        time2 = times2.get(bench_name, 0.0)

        # 计算加速比和差异
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
```

#### python/benchmark_comparator.py

```python
#!/usr/bin/env python3
"""
Benchmark对比引擎
对比两台服务器的ASV结果并生成JSON报告
"""

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

    # 解析ASV结果
    print(f"解析 {args.server1} 的ASV结果...")
    results1 = parse_asv_results(args.results1, args.machine1)

    print(f"解析 {args.server2} 的ASV结果...")
    results2 = parse_asv_results(args.results2, args.machine2)

    # 获取commit信息
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

    # 执行对比
    comparison = compare_benchmarks(results1, results2, commit1, commit2)

    # 过滤结果
    if not args.show_all:
        # 只显示有显著变化的结果（差异 > 1%）
        comparison = [c for c in comparison if abs(c['diff_percent']) > 1.0]

    # 生成报告
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

    # 保存结果
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
```

#### python/excel_generator.py

```python
#!/usr/bin/env python3
"""
Excel对比报告生成器
读取JSON对比结果并生成Excel对比表格
"""

import argparse
import json
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from pathlib import Path
from typing import List, Dict


def load_compare_result(result_file: str) -> Dict:
    """
    加载对比结果JSON文件

    Args:
        result_file: 对比结果JSON文件路径

    Returns:
        对比结果字典
    """
    with open(result_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_excel(compare_result: Dict, output_path: str) -> None:
    """
    生成Excel报告

    Args:
        compare_result: 对比结果字典（从benchmark_comparator.py生成）
        output_path: 输出文件路径
    """
    wb = openpyxl.Workbook()

    # 删除默认sheet
    if 'Sheet' in wb.sheetnames:
        wb.remove(wb['Sheet'])

    # 定义样式
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF', size=11)
    title_font = Font(bold=True, size=14, color='000000')
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # 提取数据
    server1_name = compare_result['server1']
    server2_name = compare_result['server2']
    commit1 = compare_result['commit1']
    commit2 = compare_result['commit2']
    results = compare_result['benchmarks']
    summary = compare_result['summary']

    # ==================== 创建概览sheet ====================

    ws_summary = wb.create_sheet("概览")

    # 写入标题
    ws_summary['A1'] = "ASV Benchmark对比报告"
    ws_summary['A1'].font = title_font
    ws_summary.merge_cells('A1:E1')

    # 写入基本信息
    ws_summary['A3'] = "Server1:"
    ws_summary['B3'] = server1_name
    ws_summary['A3'].font = Font(bold=True)

    ws_summary['A4'] = "Server2:"
    ws_summary['B4'] = server2_name
    ws_summary['A4'].font = Font(bold=True)

    ws_summary['A5'] = "Commit1:"
    ws_summary['B5'] = commit1[:8]  # 显示前8位
    ws_summary['A5'].font = Font(bold=True)

    ws_summary['A6'] = "Commit2:"
    ws_summary['B6'] = commit2[:8]
    ws_summary['A6'].font = Font(bold=True)

    ws_summary['A8'] = "Benchmark数量:"
    ws_summary['B8'] = str(len(results))
    ws_summary['A8'].font = Font(bold=True)

    ws_summary['A4'] = "Server2:"
    ws_summary['B4'] = server2_name
    ws_summary['A4'].font = Font(bold=True)

    ws_summary['A5'] = "Benchmark数量:"
    ws_summary['B5'] = str(len(results))
    ws_summary['A5'].font = Font(bold=True)

    # 写入统计信息
    ws_summary['A10'] = "性能统计"
    ws_summary['A10'].font = Font(bold=True, size=12)

    ws_summary['A11'] = f"{server2_name} 更快:"
    ws_summary['B11'] = str(summary['faster'])

    ws_summary['A12'] = f"{server2_name} 更慢:"
    ws_summary['B12'] = str(summary['slower'])

    ws_summary['A13'] = "性能相同:"
    ws_summary['B13'] = str(summary['same'])

    # 计算加速比统计
    if results:
        speedups = [r['speedup'] for r in results if r['speedup'] > 0]
        if speedups:
            avg_speedup = sum(speedups) / len(speedups)
            max_speedup = max(speedups)
            min_speedup = min(speedups)

            # 找出最快和最慢的benchmark
            fastest = max(results, key=lambda x: x['speedup'])
            slowest = min(results, key=lambda x: x['speedup'])

            ws_summary['A15'] = "加速比统计"
            ws_summary['A15'].font = Font(bold=True, size=12)

            ws_summary['A16'] = "平均加速比:"
            ws_summary['B16'] = f"{avg_speedup:.2f}x"

            ws_summary['A17'] = "最大加速比:"
            ws_summary['B17'] = f"{max_speedup:.2f}x"

            ws_summary['A18'] = "最小加速比:"
            ws_summary['B18'] = f"{min_speedup:.2f}x"

            ws_summary['A20'] = "最快benchmark:"
            ws_summary['B20'] = fastest['benchmark']
            ws_summary['C20'] = f"({fastest['speedup']:.2f}x)"

            ws_summary['A21'] = "最慢benchmark:"
            ws_summary['B21'] = slowest['benchmark']
            ws_summary['C21'] = f"({slowest['speedup']:.2f}x)"

    # 调整列宽
    ws_summary.column_dimensions['A'].width = 20
    ws_summary.column_dimensions['B'].width = 20

    # ==================== 创建详细对比sheet ====================

    ws_detail = wb.create_sheet("详细对比")

    # 写入表头
    headers = ['Benchmark', f'{server1_name}时间(s)', f'{server2_name}时间(s)',
               '加速比', '差异(%)', '性能评估']

    for i, header in enumerate(headers, 1):
        cell = ws_detail.cell(1, i, header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border

    # 写入数据
    for i, item in enumerate(results, 2):
        ws_detail.cell(i, 1, item['benchmark'])
        ws_detail.cell(i, 2, f"{item['time1']:.6f}")
        ws_detail.cell(i, 3, f"{item['time2']:.6f}")
        ws_detail.cell(i, 4, f"{item['speedup']:.2f}")
        ws_detail.cell(i, 5, f"{item['diff_percent']:.2f}")

        # 性能评估
        diff = item['diff_percent']
        if diff > 10:
            assessment = "明显变慢"
            fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
        elif diff > 0:
            assessment = "变慢"
            fill = PatternFill(start_color='FFE6E6', end_color='FFE6E6', fill_type='solid')
        elif diff < -10:
            assessment = "明显变快"
            fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
        elif diff < 0:
            assessment = "变快"
            fill = PatternFill(start_color='E6F7E6', end_color='E6F7E6', fill_type='solid')
        else:
            assessment = "相同"
            fill = PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid')

        ws_detail.cell(i, 6, assessment)

        # 设置行样式
        for col in range(1, 7):
            cell = ws_detail.cell(i, col)
            cell.border = border
            cell.alignment = Alignment(horizontal='left' if col == 1 else 'center', vertical='center')

        # 设置背景色
        for col in range(1, 7):
            ws_detail.cell(i, col).fill = fill

    # 调整列宽
    ws_detail.column_dimensions['A'].width = 40
    ws_detail.column_dimensions['B'].width = 15
    ws_detail.column_dimensions['C'].width = 15
    ws_detail.column_dimensions['D'].width = 10
    ws_detail.column_dimensions['E'].width = 10
    ws_detail.column_dimensions['F'].width = 12

    # 冻结首行
    ws_detail.freeze_panes = 'A2'

    # ==================== 保存文件 ====================

    wb.save(output_path)
    print(f"Excel报告已保存到: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='生成Excel对比报告')
    parser.add_argument('--compare-result', required=True, help='对比结果JSON文件（从benchmark_comparator.py生成）')
    parser.add_argument('--output', required=True, help='输出Excel文件')

    args = parser.parse_args()

    # 加载对比结果
    compare_result = load_compare_result(args.compare_result)

    if not compare_result or 'benchmarks' not in compare_result:
        print("错误: 未能加载对比结果")
        exit(1)

    # 生成Excel
    generate_excel(compare_result, args.output)


if __name__ == '__main__':
    main()
```

### 6. README.md

```markdown
# ASV Benchmark对比工具

一个用于在多台服务器上执行ASV benchmark并进行结果对比的工具。

## 功能特性

- 支持多台服务器配置
- 支持自定义执行脚本
- 自动下载ASV结果并生成对比报告
- 生成详细的Excel对比报告
- 支持Docker容器场景
- 支持dry-run模式测试

## 安装

### 前置要求

- Bash 4.0+
- Python 3.6+
- SSH免密登录配置
- jq (JSON处理工具)

### 安装步骤

1. 克隆或下载此工具
2. 安装Python依赖：
   ```bash
   pip install -r python/requirements.txt
   ```

## 配置

### 服务器配置 (servers.yaml)

编辑 `servers.yaml` 文件，添加你的服务器配置：

```yaml
servers:
  zen4:
    host: "your-server.com"
    port: 22
    username: "your-username"
    work_dir: "/path/to/benchmark"
    asv_results_dir: "/path/to/benchmark/results"

  kunpeng920b:
    host: "another-server.com"
    port: 22
    username: "your-username"
    work_dir: "/path/to/benchmark"
    asv_results_dir: "/path/to/benchmark/results"

default_servers: ["zen4", "kunpeng920b"]
```

### 主配置 (config.sh)

编辑 `config.sh` 文件，配置默认脚本和输出选项：

```bash
# 修改默认脚本以匹配你的环境
DEFAULT_SCRIPT='
source ~/miniconda3/bin/activate myenv
cd {work_dir}
asv run --python=same --bench my_benchmark -v
'
```

## 使用方法

### 基本使用

使用默认服务器运行：
```bash
./run_compare.sh
```

指定服务器运行：
```bash
./run_compare.sh zen4 kunpeng920b
```

### 使用自定义脚本

为每台服务器创建自定义脚本：

```bash
# 创建Server1脚本
cat > script1.sh << 'EOF'
source ~/miniconda3/bin/activate myenv
cd /home/user/project
asv run --python=same --bench my_benchmark -v
EOF

# 创建Server2脚本
cat > script2.sh << 'EOF'
source ~/miniconda3/bin/activate myenv
cd /home/user/project
asv run --python=same --bench my_benchmark -v
EOF

# 运行
./run_compare.sh zen4 kunpeng920b --script1 script1.sh --script2 script2.sh
```

### Docker容器场景

```bash
# 创建Docker执行脚本
cat > docker_script.sh << 'EOF'
docker exec -it my_container bash -c '
    source /opt/conda/bin/activate myenv
    cd /workspace/project
    asv run --python=same --bench my_benchmark -v
'
EOF

# 运行
./run_compare.sh zen4 kunpeng920b --script1 docker_script.sh --script2 docker_script.sh
```

### 添加自定义标识

```bash
./run_compare.sh zen4 kunpeng920b --info "numpy_v2.0"
# 输出文件: 20240411_123045_zen4_vs_kunpeng920b_numpy_v2.0.xlsx
```

### Dry-run模式

测试配置而不实际执行：
```bash
./run_compare.sh zen4 kunpeng920b --dry-run
```

## 输出

工具会在 `output/` 目录下生成以下文件：

- `TIMESTAMP_server1_vs_server2.xlsx` - Excel对比
- `compare_result_TIMESTAMP.json` - JSON格对比结果（包含详细数据）

## Excel报告内容

Excel报告包含两个sheet：

1. **概览** - 统计信息和摘要
   - 服务器信息
   - Benchmark数量
   - 性能统计（更快/更慢/相同）
   - 加速比统计（平均/最大/最小）
   - 最快和最慢的benchmark

2. **详细对比** - 每个benchmark的详细数据
   - Benchmark名称
   - Server1时间
   - Server2时间
   - 加速比
   - 差异百分比
   - 性能评估（带颜色标识）

## 故障排除

### SSH连接失败

确保已配置SSH免密登录：
```bash
ssh-copy-id user@server
```

### Python依赖缺失

安装依赖：
```bash
pip install -r python/requirements.txt
```

### ASV结果未找到

检查 `servers.yaml` 中的 `asv_results_dir` 配置是否正确。

## 许可证

MIT License
```

### 7. 使用方式总结

#### 基本使用

```bash
# 1. 编辑服务器配置
vim servers.yaml

# 2. 编辑主配置（可选）
vim config.sh

# 3. 使用默认服务器运行
./run_compare.sh

# 4. 指定服务器运行
./run_compare.sh zen4 kunpeng920b
```

#### 使用自定义脚本

```bash
# 创建自定义脚本
cat > my_script1.sh << 'EOF'
# 激活conda环境
source ~/miniconda3/bin/activate myenv
# 进入工作目录
cd /home/user/project
# 执行ASV命令
asv run --python=same --bench my_benchmark -v
EOF

# 使用自定义脚本运行
./run_compare.sh zen4 kunpeng920b --script1 my_script1.sh --script2 my_script2.sh
```

#### Docker容器场景

```bash
# 创建Docker执行脚本
cat > docker_script.sh << 'EOF'
# 在Docker容器中执行
docker exec -it my_container bash -c '
    source /opt/conda/bin/activate myenv
    cd /workspace/project
    asv run --python=same --bench my_benchmark -v
'
EOF

# 使用Docker脚本运行
./run_compare.sh zen4 kunpeng920b --script1 docker_script.sh --script2 docker_script.sh
```

#### 使用自定义标识

```bash
# 添加自定义标识到输出文件名
./run_compare.sh zen4 kunpeng920b --info "numpy_v2.0"
# 输出文件: 20240411_123045_zen4_vs_kunpeng920b_numpy_v2.0.xlsx
```

### 8. 关键文件列表

- `/mnt/c/Users/Luo/Code/asv_tools/run_compare.sh` - 主执行脚本
- `/mnt/c/Users/Luo/Code/asv_tools/servers.yaml` - 服务器配置
- `/mnt/c/Users/Luo/Code/asv_tools/config.sh` - 主配置
- `/mnt/c/Users/Luo/Code/asv_tools/lib/ssh_utils.sh` - SSH工具
- `/mnt/c/Users/Luo/Code/asv_tools/lib/yaml_parser.sh` - YAML解析
- `/mnt/c/Users/Luo/Code/asv_tools/lib/log_utils.sh` - 日志工具
- `/mnt/c/Users/Luo/Code/asv_tools/lib/dependency_checker.sh` - 依赖检查
- `/mnt/c/Users/Luo/Code/asv_tools/python/excel_generator.py` - Excel生成
- `/mnt/c/Users/Luo/Code/asv_tools/python/asv_parser.py` - ASV结果解析
- `/mnt/c/Users/Luo/Code/asv_tools/README.md` - 使用说明

### 9. 验证方式

1. 配置服务器信息：编辑 `servers.yaml`
2. 配置主配置：编辑 `config.sh`（可选）
3. 安装Python依赖：`pip install -r python/requirements.txt`
4. 测试SSH连接：`ssh user@server`
5. Dry-run测试：`./run_compare.sh zen4 kunpeng920b --dry-run`
6. 运行：`./run_compare.sh zen4 kunpeng920b`
7. 检查输出：`output/` 目录下的Excel文件
