#!/bin/bash
# YAML解析工具（使用Python）

yaml_get_value() {
    local yaml_file=$1
    local key=$2

    python3 -c "
import yaml
import json
import sys

try:
    with open('$yaml_file', 'r') as f:
        data = yaml.safe_load(f)

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
