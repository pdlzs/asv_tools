#!/bin/bash
# 日志工具函数

LOG_LEVEL="INFO"

init_log() {
    LOG_LEVEL=$1
    mkdir -p logs
}

log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    declare -A levels=([DEBUG]=0 [INFO]=1 [WARNING]=2 [ERROR]=3)
    local current_level=${levels[$LOG_LEVEL]:-1}
    local msg_level=${levels[$level]:-1}

    if [ $msg_level -ge $current_level ]; then
        case $level in
            ERROR)   echo -e "\033[31m[$timestamp] [$level] $message\033[0m" >&2 ;;
            WARNING) echo -e "\033[33m[$timestamp] [$level] $message\033[0m" ;;
            INFO)    echo -e "\033[32m[$timestamp] [$level] $message\033[0m" ;;
            DEBUG)   echo -e "\033[36m[$timestamp] [$level] $message\033[0m" ;;
        esac

        echo "[$timestamp] [$level] $message" >> "logs/asv_tools_$(date +%Y%m%d).log"
    fi
}

log_debug() { log "DEBUG" "$@"; }
log_info() { log "INFO" "$@"; }
log_warning() { log "WARNING" "$@"; }
log_error() { log "ERROR" "$@"; }
