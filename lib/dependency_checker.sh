#!/bin/bash
# 依赖检查工具

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
