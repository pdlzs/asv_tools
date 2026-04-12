#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

source "$SCRIPT_DIR/lib/ssh_utils.sh"
source "$SCRIPT_DIR/lib/yaml_parser.sh"
source "$SCRIPT_DIR/lib/log_utils.sh"
source "$SCRIPT_DIR/lib/dependency_checker.sh"

init_log "$LOG_LEVEL"

mkdir -p "$CMP_RESULTS_DIR"
mkdir -p logs

SERVER1=""
SERVER2=""
SCRIPT1=""
SCRIPT2=""
CUSTOM_INFO_ARG=""
DRY_RUN=false
SKIP_RUN=false
USE_OFFICIAL_COMPARE=false

# 用法: execute_script_on_host <host> <user> <port> <work_dir> [script_file]
#   - 若提供 script_file，则读取文件内容并通过 stdin 传递给 bash -s
#   - 若不提供，则从当前标准输入读取脚本内容
execute_script_on_host() {
    local host=$1
    local user=$2
    local port=$3
    local work_dir=$4
    local script_file=${5:-}

    if [ "$host" = "local" ]; then
        # 本地模式：在子 shell 中切换目录并执行
        if [ -n "$script_file" ]; then
            # 自定义脚本：读取文件内容并通过管道传递给 bash -s
            ( cd "$work_dir" && bash -s ) < "$script_file"
        else
            # 默认脚本：从当前标准输入读取
            ( cd "$work_dir" && bash -s )
        fi
    else
        # 远程模式：通过 SSH 执行
        if [ -n "$script_file" ]; then
            ssh -p "$port" "${user}@${host}" "cd $work_dir && bash -s" < "$script_file"
        else
            ssh -p "$port" "${user}@${host}" "cd $work_dir && bash -s"
        fi
    fi
}

print_usage() {
    echo "用法: $0 <server1> <server2> [选项]"
    echo ""
    echo "选项:"
    echo "  --script1 <file>        Server1的自定义脚本"
    echo "  --script2 <file>        Server2的自定义脚本"
    echo "  --info <string>         输出文件名的自定义标识"
    echo "  --dry-run               只显示将要执行的命令，不实际执行"
    echo "  --skip-run              跳过ASV运行步骤，直接使用已有结果"
    echo "  --use-official-compare  使用ASV官方Compare.print_table()输出表格"
    echo "  --help                  显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 zen4 kunpeng920b"
    echo "  $0 zen4 kunpeng920b --info 'numpy_v2.0'"
    echo "  $0 zen4 kunpeng920b --script1 script1.sh --script2 script2.sh"
    echo "  $0 local_test local_test --skip-run  # 使用已有结果"
    echo "  $0 zen4 kunpeng920b --use-official-compare  # 使用官方Compare API"
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
        --skip-run)
            SKIP_RUN=true
            shift
            ;;
        --use-official-compare)
            USE_OFFICIAL_COMPARE=true
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

log_info "检查依赖..."
check_dependencies "${REQUIRED_COMMANDS[@]}"

log_info "检查Python依赖..."
python3 -c "import yaml, openpyxl" 2>/dev/null || {
    log_error "缺少Python依赖，请运行: pip install -r python/requirements.txt"
    exit 1
}

log_info "加载服务器配置..."

if [ -z "$SERVER1" ] || [ -z "$SERVER2" ]; then
    log_info "未指定服务器，使用默认配置..."
    DEFAULT_SERVERS=$(yaml_get_value "$SCRIPT_DIR/servers.yaml" "default_servers")
    SERVER1=$(echo "$DEFAULT_SERVERS" | jq -r '.[0]')
    SERVER2=$(echo "$DEFAULT_SERVERS" | jq -r '.[1]')
fi

SERVER1_CONFIG=$(yaml_get_server_config "$SCRIPT_DIR/servers.yaml" "$SERVER1")
SERVER2_CONFIG=$(yaml_get_server_config "$SCRIPT_DIR/servers.yaml" "$SERVER2")

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
SERVER1_ASV_RESULTS_DIR="${SERVER1_PROJECT_DIR}/results"

SERVER2_HOST=$(echo "$SERVER2_CONFIG" | jq -r '.host')
SERVER2_USER=$(echo "$SERVER2_CONFIG" | jq -r '.username')
SERVER2_PORT=$(echo "$SERVER2_CONFIG" | jq -r '.port')
SERVER2_PROJECT_DIR=$(echo "$SERVER2_CONFIG" | jq -r '.asv_project_dir')
SERVER2_MACHINE_NAME=$(echo "$SERVER2_CONFIG" | jq -r '.machine_name // empty')
SERVER2_ASV_RESULTS_DIR="${SERVER2_PROJECT_DIR}/results"

log_info "========== ASV Benchmark对比工具 =========="
log_info "Server1: $SERVER1 ($SERVER1_USER@$SERVER1_HOST:$SERVER1_PORT)"
log_info "Server2: $SERVER2 ($SERVER2_USER@$SERVER2_HOST:$SERVER2_PORT)"

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

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CUSTOM_INFO=""
if [ -n "$CUSTOM_INFO_ARG" ]; then
    CUSTOM_INFO="$CUSTOM_INFO_ARG"
fi

if [ -n "$CUSTOM_INFO" ]; then
    OUTPUT_DIR_NAME="asv_compare_${TIMESTAMP}_${CUSTOM_INFO}"
else
    OUTPUT_DIR_NAME="asv_compare_${TIMESTAMP}"
fi

OUTPUT_DIR_PATH="$CMP_RESULTS_DIR/$OUTPUT_DIR_NAME"
mkdir -p "$OUTPUT_DIR_PATH"

OUTPUT_FILE="${SERVER1}_vs_${SERVER2}.xlsx"
OUTPUT_PATH="$OUTPUT_DIR_PATH/$OUTPUT_FILE"

log_info "输出目录: $OUTPUT_DIR_PATH"

if [ "$SKIP_RUN" = true ]; then
    log_info "跳过ASV运行步骤（--skip-run）"
else
    # ========== 在 SERVER1 上执行脚本 ==========
    log_info "在 $SERVER1 上执行脚本..."

    if [ -n "$SCRIPT1" ]; then
        if [ ! -f "$SCRIPT1" ]; then
            log_error "脚本文件不存在: $SCRIPT1"
            exit 1
        fi
        log_info "使用自定义脚本: $SCRIPT1"
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY-RUN] 将在 $SERVER1 上执行: execute_script_on_host ... < $SCRIPT1"
        else
            execute_script_on_host "$SERVER1_HOST" "$SERVER1_USER" "$SERVER1_PORT" \
                "$SERVER1_PROJECT_DIR" "$SCRIPT1" || {
                log_error "在 $SERVER1 上执行自定义脚本失败"
                exit 1
            }
        fi
    else
        log_info "使用默认脚本"
        SCRIPT_RENDERED=$(echo "$DEFAULT_SCRIPT" | sed "s|{work_dir}|$SERVER1_PROJECT_DIR|g")
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY-RUN] 将在 $SERVER1 上执行默认脚本"
        else
            echo "$SCRIPT_RENDERED" | execute_script_on_host "$SERVER1_HOST" "$SERVER1_USER" "$SERVER1_PORT" \
                "$SERVER1_PROJECT_DIR" || {
                log_error "在 $SERVER1 上执行默认脚本失败"
                exit 1
            }
        fi
    fi

    # ========== 在 SERVER2 上执行脚本 ==========
    log_info "在 $SERVER2 上执行脚本..."

    if [ -n "$SCRIPT2" ]; then
        if [ ! -f "$SCRIPT2" ]; then
            log_error "脚本文件不存在: $SCRIPT2"
            exit 1
        fi
        log_info "使用自定义脚本: $SCRIPT2"
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY-RUN] 将在 $SERVER2 上执行: execute_script_on_host ... < $SCRIPT2"
        else
            execute_script_on_host "$SERVER2_HOST" "$SERVER2_USER" "$SERVER2_PORT" \
                "$SERVER2_PROJECT_DIR" "$SCRIPT2" || {
                log_error "在 $SERVER2 上执行自定义脚本失败"
                exit 1
            }
        fi
    else
        log_info "使用默认脚本"
        SCRIPT_RENDERED=$(echo "$DEFAULT_SCRIPT" | sed "s|{work_dir}|$SERVER2_PROJECT_DIR|g")
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY-RUN] 将在 $SERVER2 上执行默认脚本"
        else
            echo "$SCRIPT_RENDERED" | execute_script_on_host "$SERVER2_HOST" "$SERVER2_USER" "$SERVER2_PORT" \
                "$SERVER2_PROJECT_DIR" || {
                log_error "在 $SERVER2 上执行默认脚本失败"
                exit 1
            }
        fi
    fi
fi

# if [ "$DRY_RUN" = true ]; then
#     log_info "[DRY-RUN] 跳过后续步骤（dry-run模式）"
#     exit 0
# fi

log_info "获取ASV结果..."

log_info "从 $SERVER1 下载ASV结果..."
SERVER1_RESULTS_LOCAL="$OUTPUT_DIR_PATH/${SERVER1}_results"
mkdir -p "$SERVER1_RESULTS_LOCAL"

# 只下载 results 目录
scp_download "$SERVER1_HOST" "$SERVER1_USER" "$SERVER1_PORT" \
    "$SERVER1_ASV_RESULTS_DIR" "$SERVER1_RESULTS_LOCAL" || {
    log_error "从 $SERVER1 下载ASV结果失败"
    exit 1
}

# 生成空白的 asv.conf.json
cat > "$SERVER1_RESULTS_LOCAL/asv.conf.json" << 'EOF'
{
    "version": 1,
    "project": "benchmark",
    "repo": ".",
    "results_dir": "results"
}
EOF

# 如果 benchmarks.json 在 results/ 目录下，复制到项目根目录（ASV Compare API 需要）
if [ -f "$SERVER1_RESULTS_LOCAL/results/benchmarks.json" ]; then
    cp "$SERVER1_RESULTS_LOCAL/results/benchmarks.json" "$SERVER1_RESULTS_LOCAL/benchmarks.json"
    log_info "已复制 benchmarks.json 到项目根目录（ASV Compare API 需要）"
fi

log_info "从 $SERVER2 下载ASV结果..."
SERVER2_RESULTS_LOCAL="$OUTPUT_DIR_PATH/${SERVER2}_results"
mkdir -p "$SERVER2_RESULTS_LOCAL"

# 只下载 results 目录
scp_download "$SERVER2_HOST" "$SERVER2_USER" "$SERVER2_PORT" \
    "$SERVER2_ASV_RESULTS_DIR" "$SERVER2_RESULTS_LOCAL" || {
    log_error "从 $SERVER2 下载ASV结果失败"
    exit 1
}

# 生成空白的 asv.conf.json
cat > "$SERVER2_RESULTS_LOCAL/asv.conf.json" << 'EOF'
{
    "version": 1,
    "project": "benchmark",
    "repo": ".",
    "results_dir": "results"
}
EOF

# 如果 benchmarks.json 在 results/ 目录下，复制到项目根目录（ASV Compare API 需要）
if [ -f "$SERVER2_RESULTS_LOCAL/results/benchmarks.json" ]; then
    cp "$SERVER2_RESULTS_LOCAL/results/benchmarks.json" "$SERVER2_RESULTS_LOCAL/benchmarks.json"
    log_info "已复制 benchmarks.json 到项目根目录（ASV Compare API 需要）"
fi

log_info "验证下载的ASV结果..."
if [ ! -d "$SERVER1_RESULTS_LOCAL" ] || [ -z "$(ls -A $SERVER1_RESULTS_LOCAL)" ]; then
    log_error "Server1的结果目录为空: $SERVER1_RESULTS_LOCAL"
    exit 1
fi

if [ ! -d "$SERVER2_RESULTS_LOCAL" ] || [ -z "$(ls -A $SERVER2_RESULTS_LOCAL)" ]; then
    log_error "Server2的结果目录为空: $SERVER2_RESULTS_LOCAL"
    exit 1
fi

log_info "执行ASV结果对比..."

COMPARE_STRATEGY=$(yaml_get_value "$SCRIPT_DIR/servers.yaml" "asv.compare_strategy" | jq -r '.')
COMPARE_STRATEGY=${COMPARE_STRATEGY:-"latest"}
SHOW_ALL=$(yaml_get_value "$SCRIPT_DIR/servers.yaml" "asv.show_all" | jq -r '.')
SHOW_ALL=${SHOW_ALL:-"false"}

COMPARE_CMD="python3 \"$SCRIPT_DIR/python/asv_compare_wrapper.py\" \
    --asv-dir1 \"$SERVER1_RESULTS_LOCAL\" \
    --asv-dir2 \"$SERVER2_RESULTS_LOCAL\" \
    --server1 \"$SERVER1\" \
    --server2 \"$SERVER2\" \
    --strategy \"$COMPARE_STRATEGY\" \
    --output \"$OUTPUT_DIR_PATH/compare_result.json\""

if [ "$SHOW_ALL" = "true" ]; then
    COMPARE_CMD="$COMPARE_CMD --show-all"
fi

if [ "$USE_OFFICIAL_COMPARE" = "true" ]; then
    COMPARE_CMD="$COMPARE_CMD --use-official-compare"
fi

log_info "执行对比命令: $COMPARE_CMD"
eval "$COMPARE_CMD" || {
    log_error "执行ASV结果对比失败"
    exit 1
}

COMPARE_RESULT_FILE="$OUTPUT_DIR_PATH/compare_result.json"
log_info "对比结果已保存到: $COMPARE_RESULT_FILE"

log_info "生成Excel对比报告..."

python3 "$SCRIPT_DIR/python/excel_generator.py" \
    --compare-result "$COMPARE_RESULT_FILE" \
    --output "$OUTPUT_PATH" || {
    log_error "生成Excel报告失败"
    exit 1
}

log_info "完成！报告已保存到: $OUTPUT_PATH"