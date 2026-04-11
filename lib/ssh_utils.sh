#!/bin/bash
# SSH工具函数

ssh_test_connection() {
    local host=$1
    local user=$2
    local port=${3:-22}
    local timeout=${SSH_TIMEOUT:-30}

    # 本地模式（跳过SSH）
    if [ "$host" = "local" ]; then
        echo "Local mode: skipping SSH connection test"
        return 0
    fi

    ssh -o "ConnectTimeout=$timeout" -o "BatchMode=yes" \
        -o "StrictHostKeyChecking=no" -p "$port" "${user}@${host}" \
        "echo 'Connection successful'" >/dev/null 2>&1
}

ssh_execute() {
    local host=$1
    local user=$2
    local port=$3
    shift 3
    local command="$@"

    # 本地模式（直接执行）
    if [ "$host" = "local" ]; then
        bash -c "$command"
        return $?
    fi

    ssh -o "ConnectTimeout=$SSH_TIMEOUT" -o "BatchMode=yes" \
        -o "StrictHostKeyChecking=no" -p "$port" "${user}@${host}" "$command"
}

scp_download() {
    local host=$1
    local user=$2
    local port=$3
    local remote_path=$4
    local local_path=$5

    # 本地模式（直接复制）
    if [ "$host" = "local" ]; then
        cp -r "$remote_path" "$local_path"
        return $?
    fi

    scp -o "ConnectTimeout=$SSH_TIMEOUT" -o "BatchMode=yes" \
        -o "StrictHostKeyChecking=no" -P "$port" -r "${user}@${host}:${remote_path}" "$local_path"
}

scp_upload() {
    local host=$1
    local user=$2
    local port=$3
    local local_path=$4
    local remote_path=$5

    scp -o "ConnectTimeout=$SSH_TIMEOUT" -o "BatchMode=yes" \
        -o "StrictHostKeyChecking=no" -P "$port" -r "$local_path" "${user}@${host}:${remote_path}"
}
