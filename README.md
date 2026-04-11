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
    asv_project_dir: "/path/to/benchmark"

  kunpeng920b:
    host: "another-server.com"
    port: 22
    username: "your-username"
    asv_project_dir: "/path/to/benchmark"

default_servers: ["zen4", "kunpeng920b"]
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

## 输出

工具会在 `output/` 目录下生成以下文件：

- `TIMESTAMP_server1_vs_server2.xlsx` - Excel对比报告
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

检查 `servers.yaml` 中的 `asv_project_dir` 配置是否正确。

## 许可证

MIT License
