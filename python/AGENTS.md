# PYTHON MODULES

**Parent:** ../AGENTS.md

## OVERVIEW
Python 核心模块 - ASV 结果解析、Benchmark 对比、Excel 报告生成

## STRUCTURE
```
python/
├── asv_parser.py           # ASV 结果解析（129行）
├── benchmark_comparator.py # Benchmark 对比逻辑（81行）
├── excel_generator.py       # Excel 报告生成（186行）
└── requirements.txt         # Python 依赖
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| 解析 ASV 结果 | `asv_parser.py` | parse_asv_results, get_latest_commit, extract_benchmark_times |
| 对比 Benchmark | `benchmark_comparator.py` | CLI 入口，调用 asv_parser |
| 生成 Excel 报告 | `excel_generator.py` | 带颜色标识的对比报告 |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| parse_asv_results | function | asv_parser.py | 解析 ASV 结果目录，返回 {commit: data} |
| get_latest_commit | function | asv_parser.py | 获取最新 commit hash |
| extract_benchmark_times | function | asv_parser.py | 从 commit 数据提取 benchmark 时间 |
| compare_benchmarks | function | asv_parser.py | 比较两台服务器的 benchmark 结果 |
| generate_excel | function | excel_generator.py | 生成 Excel 对比报告（2个 sheet） |
| load_compare_result | function | excel_generator.py | 加载 JSON 对比结果 |

## CONVENTIONS

### Python 版本
- Python 3.6+ 兼容
- 使用类型提示（typing 模块）

### 数据结构
- ASV 结果：`{commit: {"benchmarks": {...}, "machine": str, "machine_info": {...}, "path": str}}`
- 对比结果：`[{"benchmark": str, "time1": float, "time2": float, "speedup": float, "diff_percent": float, ...}]`

### 错误处理
- 使用 try/except 捕获 JSON 解析错误
- FileNotFoundError 和 ValueError 用于输入验证

## ANTI-PATTERNS

- ❌ 无单元测试
- ❌ 无类型检查（mypy）
- ❌ 硬编码颜色值（Excel 报告中）

## NOTES

### ASV 结果格式
```
results/
├── <machine_name>/
│   └── <commit_hash>/
│       ├── benchmarks.json  # Benchmark 时间数据
│       └── machine.json     # 机器信息（可选）
```

### Benchmark 数据提取
- 优先级：`time` > `result` > `samples`（平均值）
- 支持 `samples` 数组自动计算平均值

### Excel 报告结构
- **概览** sheet：服务器信息、性能统计、加速比统计
- **详细对比** sheet：每个 benchmark 的详细数据，带颜色标识
  - 明显变快（>10%）：绿色
  - 变快（<10%）：浅绿
  - 相同：灰色
  - 变慢（<10%）：浅红
  - 明显变慢（>10%）：红色
