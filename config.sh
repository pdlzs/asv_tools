#!/bin/bash
# ASV Benchmark对比工具主配置

# ==================== 依赖检查 ====================

# 必需的命令
REQUIRED_COMMANDS=("ssh" "scp" "python3" "jq")

# ==================== 默认脚本 ====================

# 默认前置脚本（用于所有所有服务器）
# 可以通过命令行参数 --script1/--script2 覆盖
DEFAULT_SCRIPT='
# 进入工作目录
cd {work_dir}
# 运行ASV benchmark
asv run -b "bench_reduce" --python=same
'

# ==================== 输出配置 ====================

# 对比结果目录（每次运行创建独立的 asv_compare_xxx 目录）
CMP_RESULTS_DIR="./cmp_results"

# 输出文件名中的自定义标识（可选）
# 例如: "numpy_v2.0", "pandas_opt", "baseline"
CUSTOM_INFO=""

# ==================== 其他配置 ====================

# SSH连接超时（秒）
SSH_TIMEOUT=30

# 日志级别 (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL="INFO"
