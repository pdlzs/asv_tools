# ASV Benchmark对比工具

一个用于在多台服务器上执行ASV benchmark并进行结果对比的工具。

## 功能特性

- 支持多台服务器配置
- 支持自定义执行脚本
- 自动下载ASV结果并生成对比报告
- 使用ASV官方Compare API生成对比表格
- 支持Docker容器场景
- 支持dry-run模式测试
- 支持skip-run模式（直接使用已有结果）

## 安装

### 前置要求

- Bash 4.0+
- Python 3.6+
- SSH免密登录配置（如需远程服务器）
- jq (JSON处理工具)
- ASV (airspeed velocity)

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
    asv_project_dir: "/path/to/benchmark"

  kunpeng920b:
    host: "another-server.com"
    port: 22
    username: "your-username"
    asv_project_dir: "/path/to/benchmark"

default_servers: ["zen4", "kunpeng920b"]
```

### 本地测试配置

使用 `host: "local"` 可以跳过SSH，直接本地执行：

```yaml
servers:
  local_test:
    host: "local"
    username: "your-username"
    asv_project_dir: "/path/to/benchmark"
```

### 主配置 (config.sh)

编辑 `config.sh` 文件，配置默认脚本和输出选项：

```bash
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
cat > script1.sh << 'EOF'
source ~/miniconda3/bin/activate myenv
cd /home/user/project
asv run --python=same --bench my_benchmark -v
EOF

cat > script2.sh << 'EOF'
source ~/miniconda3/bin/activate myenv
cd /home/user/project
asv run --python=same --bench my_benchmark -v
EOF

./run_compare.sh zen4 kunpeng920b --script1 script1.sh --script2 script2.sh
```

### Docker容器场景

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

### 添加自定义标识

```bash
./run_compare.sh zen4 kunpeng920b --info "numpy_v2.0"
```

### Dry-run模式

测试配置而不实际执行：
```bash
./run_compare.sh zen4 kunpeng920b --dry-run
```

### Skip-run模式

跳过ASV运行，直接使用已有结果对比：
```bash
./run_compare.sh local_test local_test --skip-run
```

## 输出

工具会在 `cmp_results/` 目录下生成以下文件：

- `TIMESTAMP_server1_vs_server2_table.txt` - ASV官方对比表格（文本格式）
- `TIMESTAMP_server1_vs_server2_table.xlsx` - Excel对比表格

## ASV对比表格说明

ASV官方Compare API生成的表格包含：

- Benchmark名称
- Before（基准值）
- After（对比值）
- Change（变化百分比）
- 统计信息

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

检查 `servers.yaml` 中的 `asv_project_dir` 配置是否正确。

### ASV模块加载失败

确保ASV已正确安装：
```bash
pip install asv
```

## 许可证

MIT License