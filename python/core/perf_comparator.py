"""Performance configuration comparator

Compares performance configurations from multiple machines and generates
Markdown comparison reports.
"""

from typing import List, Dict, Any
from core.perf_collector import PerfConfig


class PerfComparator:
    """性能配置对比器"""

    def __init__(self, configs: List[PerfConfig]):
        self.configs = configs

    def compare(self) -> str:
        """生成对比报告 Markdown"""
        if len(self.configs) < 2:
            return "# 性能配置报告\n\n仅采集到一台机器配置，无法对比。"

        lines = []
        lines.append("# 性能配置对比报告")
        lines.append("")
        lines.append(f"**对比主机**: {self._format_machines_header()}")
        lines.append(f"**采集时间**: {self._get_collect_times()}")
        lines.append("")

        # CPU 对比
        lines.append("## CPU 对比")
        lines.append("")
        lines.append(self._compare_cpu())

        # 内存对比
        lines.append("## 内存对比")
        lines.append("")
        lines.append(self._compare_memory())

        # 环境对比
        lines.append("## 环境对比")
        lines.append("")
        lines.append(self._compare_environment())

        # 环境变量对比
        lines.append("## 环境变量对比")
        lines.append("")
        lines.append(self._compare_env_vars())

        # 内核参数对比
        lines.append("## 内核参数对比")
        lines.append("")
        lines.append(self._compare_kernel_params())

        # BIOS 配置对比（仅简要对比关键信息）
        lines.append("## BIOS 配置")
        lines.append("")
        lines.append(self._compare_bios())

        # 性能影响分析
        lines.append("## 性能影响分析")
        lines.append("")
        lines.append(self._analyze_performance_impact())

        return '\n'.join(lines)

    def _format_machines_header(self) -> str:
        """格式化机器列表标题"""
        names = [cfg.machine_name for cfg in self.configs]
        return ' vs '.join(names)

    def _get_collect_times(self) -> str:
        """获取采集时间"""
        times = [cfg.collect_time for cfg in self.configs if cfg.collect_time]
        return ', '.join(times) if times else '未知'

    def _get_headers(self) -> List[str]:
        """生成表格列标题"""
        return ['配置项'] + [cfg.machine_name for cfg in self.configs] + ['差异']

    def _format_table(self, rows: List[List[str]]) -> str:
        """格式化 Markdown 表格"""
        if not rows:
            return ""

        # 第一行是表头
        header = rows[0]
        separator = '|' + '|'.join(['---' for _ in header]) + '|'

        lines = []
        lines.append('|' + '|'.join(header) + '|')
        lines.append(separator)

        for row in rows[1:]:
            lines.append('|' + '|'.join(row) + '|')

        return '\n'.join(lines)

    def _compare_values(self, values: List[str]) -> str:
        """对比多个值，返回差异标记"""
        # 过滤掉 NA
        valid_values = [v for v in values if v and v != 'NA' and not v.startswith('NA:')]

        if len(valid_values) < 2:
            return '⚠️ 数据不完整'

        if all(v == valid_values[0] for v in valid_values):
            return '✓ 相同'

        return '⚠️ 不同'

    def _get_value(self, config: PerfConfig, path: str) -> str:
        """从配置中获取指定路径的值"""
        parts = path.split('.')
        obj = config

        for part in parts[:-1]:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                return 'NA'

        final_key = parts[-1]
        if hasattr(obj, final_key):
            val = getattr(obj, final_key)
        elif isinstance(obj, dict) and final_key in obj:
            val = obj[final_key]
        else:
            return 'NA'

        if val is None:
            return 'NA'
        if isinstance(val, dict):
            return str(val.get('raw', 'NA'))[:50] + '...' if val.get('raw') else 'NA'
        return str(val)

    def _compare_cpu(self) -> str:
        """对比 CPU 信息"""
        rows = [self._get_headers()]

        compare_fields = [
            ('架构', 'cpu.architecture'),
            ('型号', 'cpu.model'),
            ('物理核心', 'cpu.physical_cores'),
            ('逻辑核心', 'cpu.logical_cores'),
            ('线程/核心', 'cpu.threads_per_core'),
            ('当前频率', 'cpu.current_mhz'),
            ('最大频率', 'cpu.max_mhz'),
            ('L1d 缓存', 'cpu.l1d_cache'),
            ('L2 缓存', 'cpu.l2_cache'),
            ('L3 缓存', 'cpu.l3_cache'),
            ('NUMA 节点', 'cpu.numa_nodes'),
            ('关键指令集', 'cpu.key_instruction_sets'),
        ]

        for label, path in compare_fields:
            values = [self._get_value(cfg, path) for cfg in self.configs]
            diff = self._compare_values(values)
            # 处理列表类型的显示
            display_values = []
            for v in values:
                if isinstance(v, list):
                    display_values.append(', '.join(v))
                else:
                    display_values.append(str(v))
            rows.append([label] + display_values + [diff])

        return self._format_table(rows)

    def _compare_memory(self) -> str:
        """对比内存信息"""
        rows = [self._get_headers()]

        compare_fields = [
            ('总内存', 'memory.total'),
            ('透明大页', 'memory.transparent_hugepage'),
            ('大页总数', 'memory.hugepages_total'),
            ('大页大小', 'memory.hugepage_size'),
        ]

        for label, path in compare_fields:
            values = [self._get_value(cfg, path) for cfg in self.configs]
            diff = self._compare_values(values)
            rows.append([label] + values + [diff])

        return self._format_table(rows)

    def _compare_environment(self) -> str:
        """对比环境配置"""
        rows = [self._get_headers()]

        compare_fields = [
            ('Python', 'environment.python'),
            ('GCC', 'environment.gcc'),
            ('BLAS', 'environment.blas'),
            ('LAPACK', 'environment.lapack'),
        ]

        for label, path in compare_fields:
            values = [self._get_value(cfg, path) for cfg in self.configs]
            diff = self._compare_values(values)
            rows.append([label] + values + [diff])

        return self._format_table(rows)

    def _compare_env_vars(self) -> str:
        """对比环境变量"""
        # 收集所有出现的环境变量
        all_vars = set()
        for cfg in self.configs:
            all_vars.update(cfg.env_vars.keys())

        if not all_vars:
            return "无性能相关环境变量设置"

        rows = [self._get_headers()]

        # 按重要性排序
        priority_vars = ['OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
                        'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS', 'KMP_AFFINITY']
        sorted_vars = [v for v in priority_vars if v in all_vars] + \
                     [v for v in sorted(all_vars) if v not in priority_vars]

        for var in sorted_vars:
            values = [cfg.env_vars.get(var, '-') for cfg in self.configs]
            diff = self._compare_values([v if v != '-' else 'NA' for v in values])
            rows.append([var] + values + [diff])

        return self._format_table(rows)

    def _compare_kernel_params(self) -> str:
        """对比内核参数"""
        # 收集所有出现的参数
        all_params = set()
        for cfg in self.configs:
            all_params.update(cfg.kernel_params.keys())

        if not all_params:
            return "无法获取内核参数"

        rows = [self._get_headers()]

        for param in sorted(all_params):
            values = [cfg.kernel_params.get(param, 'NA') for cfg in self.configs]
            diff = self._compare_values(values)
            rows.append([param] + values + [diff])

        return self._format_table(rows)

    def _compare_bios(self) -> str:
        """对比 BIOS 配置（简要说明）"""
        lines = []
        for cfg in self.configs:
            bios = cfg.bios
            processor_info = bios.get('dmidecode_processor', 'NA')
            memory_info = bios.get('dmidecode_memory', 'NA')
            system_info = bios.get('dmidecode_system', 'NA')

            lines.append(f"### {cfg.machine_name}")
            lines.append("")
            lines.append("**dmidecode -t processor 输出:**")
            lines.append("")
            lines.append("```")
            lines.append(processor_info[:500] + '...' if len(processor_info) > 500 else processor_info)
            lines.append("```")
            lines.append("")
            lines.append("**dmidecode -t memory 输出:**")
            lines.append("")
            lines.append("```")
            lines.append(memory_info[:500] + '...' if len(memory_info) > 500 else memory_info)
            lines.append("```")
            lines.append("")
            lines.append("**dmidecode -t system 输出:**")
            lines.append("")
            lines.append("```")
            lines.append(system_info[:500] + '...' if len(system_info) > 500 else system_info)
            lines.append("```")
            lines.append("")
            lines.append("---")
            lines.append("")

        return '\n'.join(lines)

    def _analyze_performance_impact(self) -> str:
        """分析性能影响"""
        lines = []
        lines.append("### 主要差异点")
        lines.append("")

        # 分析 CPU 架构差异
        architectures = [self._get_value(cfg, 'cpu.architecture') for cfg in self.configs]
        if len(set(architectures)) > 1:
            lines.append(f"1. **架构差异**: {', '.join(architectures)}")
            lines.append("   - 不同架构的指令集和优化策略不同")
            lines.append("   - x86_64 通常使用 AVX/AVX2/AVX-512，ARM64 使用 NEON/SVE")
            lines.append("")

        # 分析 BLAS 库差异
        blas_versions = [self._get_value(cfg, 'environment.blas') for cfg in self.configs]
        if len(set([v for v in blas_versions if v != 'NA'])) > 1:
            lines.append("2. **BLAS 库差异**:")
            for i, (cfg, blas) in enumerate(zip(self.configs, blas_versions)):
                lines.append(f"   - {cfg.machine_name}: {blas}")
            lines.append("   - MKL 在 Intel CPU 上通常有 20-40% 矩阵运算优势")
            lines.append("   - OpenBLAS 是跨平台开源选择，ARM 平台常用")
            lines.append("")

        # 分析核心数差异
        cores = [self._get_value(cfg, 'cpu.physical_cores') for cfg in self.configs]
        valid_cores = [int(c) for c in cores if c != 'NA' and c.isdigit()]
        if len(valid_cores) >= 2 and valid_cores[0] != valid_cores[1]:
            diff = valid_cores[1] - valid_cores[0]
            lines.append(f"3. **核心数差异**: {valid_cores[0]} vs {valid_cores[1]} ({'+' if diff > 0 else ''}{diff})")
            lines.append("   - 核心数直接影响并行计算能力")
            lines.append("")

        # 分析 NUMA 配置
        numa_nodes = [self._get_value(cfg, 'cpu.numa_nodes') for cfg in self.configs]
        if len(set([v for v in numa_nodes if v != 'NA'])) > 1:
            lines.append("4. **NUMA 配置差异**:")
            for cfg, numa in zip(self.configs, numa_nodes):
                lines.append(f"   - {cfg.machine_name}: {numa} 个节点")
            lines.append("   - 多 NUMA 节点需注意内存绑定优化，避免跨节点访问")
            lines.append("")

        # 分析环境变量
        thread_vars = []
        for cfg in self.configs:
            omp = cfg.env_vars.get('OMP_NUM_THREADS', '-')
            mkl = cfg.env_vars.get('MKL_NUM_THREADS', '-')
            if omp != '-' or mkl != '-':
                thread_vars.append((cfg.machine_name, omp, mkl))

        if len(thread_vars) > 1:
            omp_values = [t[1] for t in thread_vars]
            if len(set([v for v in omp_values if v != '-'])) > 1:
                lines.append("5. **线程数配置差异**:")
                for name, omp, mkl in thread_vars:
                    lines.append(f"   - {name}: OMP={omp}, MKL={mkl}")
                lines.append("   - 线程数应与物理核心数匹配以获得最佳性能")
                lines.append("")

        if not lines:
            lines.append("各机器配置基本一致，无明显性能差异因素。")

        return '\n'.join(lines)