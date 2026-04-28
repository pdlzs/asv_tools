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
        """格式化机器列表标题，使用 display_name"""
        names = [cfg.display_name for cfg in self.configs]
        return ' vs '.join(names)

    def _get_collect_times(self) -> str:
        """获取采集时间"""
        times = [cfg.collect_time for cfg in self.configs if cfg.collect_time]
        return ', '.join(times) if times else '未知'

    def _get_headers(self) -> List[str]:
        """生成表格列标题，使用 display_name"""
        return ['配置项'] + [cfg.display_name for cfg in self.configs] + ['差异']

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

    def _get_value(self, config: PerfConfig, path: str) -> Any:
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
        # 保持列表类型不变，用于后续显示处理
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            return str(val.get('raw', 'NA'))[:50] + '...' if val.get('raw') else 'NA'
        return str(val)

    def _format_value_for_display(self, val: Any) -> str:
        """将值格式化为表格显示格式"""
        if isinstance(val, list):
            if len(val) == 0:
                return 'NA'
            return ', '.join(val[:5]) + ('...' if len(val) > 5 else '')
        elif val == 'NA' or (isinstance(val, str) and val.startswith('NA:')):
            return 'NA'
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
            diff = self._compare_values([self._format_value_for_display(v) for v in values])
            # 使用格式化方法处理显示
            display_values = [self._format_value_for_display(v) for v in values]
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
        """对比 BIOS 配置，逐字段对比"""
        lines = []

        # 1. 系统信息对比
        lines.append("### 系统信息")
        lines.append("")
        rows = [self._get_headers()]
        system_fields = ['Manufacturer', 'Product Name', 'Version', 'Serial Number', 'UUID']
        for field in system_fields:
            values = []
            for cfg in self.configs:
                bios = cfg.bios
                if isinstance(bios, dict) and 'system' in bios:
                    system_info = bios['system']
                    if isinstance(system_info, dict):
                        values.append(system_info.get(field, 'NA'))
                    else:
                        values.append('NA')
                else:
                    values.append('NA')
            diff = self._compare_values(values)
            rows.append([field] + values + [diff])
        lines.append(self._format_table(rows))
        lines.append("")

        # 2. CPU 处理器信息对比（详细表格）
        lines.append("### CPU 处理器信息")
        lines.append("")

        # 收集所有处理器信息
        proc_stats = []
        for cfg in self.configs:
            bios = cfg.bios
            if isinstance(bios, dict) and 'processor' in bios:
                proc_info = bios['processor']
                if isinstance(proc_info, dict):
                    proc_stats.append({
                        'display_name': cfg.display_name,
                        'handle': proc_info.get('handle', 'NA'),
                        'dmi_type': proc_info.get('dmi_type', 'NA'),
                        'size_bytes': proc_info.get('size_bytes', 'NA'),
                        'socket': proc_info.get('socket', 'NA'),
                        'type': proc_info.get('type', 'NA'),
                        'family': proc_info.get('family', 'NA'),
                        'manufacturer': proc_info.get('manufacturer', 'NA'),
                        'id': proc_info.get('id', 'NA'),
                        'signature': proc_info.get('signature', 'NA'),
                        'version': proc_info.get('version', 'NA'),
                        'voltage': proc_info.get('voltage', 'NA'),
                        'external_clock': proc_info.get('external_clock', 'NA'),
                        'max_speed': proc_info.get('max_speed', 'NA'),
                        'current_speed': proc_info.get('current_speed', 'NA'),
                        'core_count': proc_info.get('core_count', 'NA'),
                        'core_enabled': proc_info.get('core_enabled', 'NA'),
                        'thread_count': proc_info.get('thread_count', 'NA'),
                        'key_instruction_sets': proc_info.get('key_instruction_sets', []),
                        'flags': proc_info.get('flags', 'NA'),
                    })
                else:
                    proc_stats.append(self._get_empty_proc_stat(cfg.display_name))
            else:
                proc_stats.append(self._get_empty_proc_stat(cfg.display_name))

        # 构建表格
        rows = [['属性'] + [s['display_name'] for s in proc_stats] + ['结论']]

        # Handle
        row = ['Handle']
        for s in proc_stats:
            row.append(s['handle'])
        row.append('-')
        rows.append(row)

        # DMI 类型
        row = ['DMI 类型']
        for s in proc_stats:
            row.append(s['dmi_type'])
        row.append('DMI type 4 表示处理器信息')
        rows.append(row)

        # 插槽标识
        row = ['插槽标识']
        for s in proc_stats:
            row.append(s['socket'])
        row.append(self._analyze_socket_difference([s['socket'] for s in proc_stats]))
        rows.append(row)

        # 类型
        row = ['类型']
        for s in proc_stats:
            row.append(s['type'])
        row.append('-')
        rows.append(row)

        # 家族
        row = ['家族']
        families = [s['family'] for s in proc_stats]
        for s in proc_stats:
            row.append(s['family'])
        row.append(self._analyze_family_difference(families))
        rows.append(row)

        # 制造商
        row = ['制造商']
        manufacturers = [s['manufacturer'] for s in proc_stats]
        for s in proc_stats:
            # 截断过长的制造商名
            mfr = s['manufacturer']
            if len(mfr) > 30:
                row.append(mfr[:27] + '...')
            else:
                row.append(mfr)
        row.append(self._analyze_manufacturer_difference(manufacturers))
        rows.append(row)

        # ID
        row = ['ID']
        for s in proc_stats:
            row.append(s['id'])
        row.append('-')
        rows.append(row)

        # 签名
        row = ['签名']
        for s in proc_stats:
            row.append(s['signature'])
        row.append('-')
        rows.append(row)

        # 版本
        row = ['版本']
        versions = [s['version'] for s in proc_stats]
        for s in proc_stats:
            row.append(s['version'])
        row.append(self._analyze_version_difference(versions))
        rows.append(row)

        # 核心数
        row = ['核心数']
        core_counts = [s['core_count'] for s in proc_stats]
        for s in proc_stats:
            row.append(s['core_count'])
        row.append(self._analyze_core_difference(core_counts))
        rows.append(row)

        # 线程数
        row = ['线程数']
        thread_counts = [s['thread_count'] for s in proc_stats]
        for s in proc_stats:
            row.append(s['thread_count'])
        row.append(self._analyze_thread_difference(thread_counts))
        rows.append(row)

        # 电压
        row = ['电压']
        voltages = [s['voltage'] for s in proc_stats]
        for s in proc_stats:
            row.append(s['voltage'])
        row.append(self._analyze_voltage_difference(voltages))
        rows.append(row)

        # 外部时钟
        row = ['外部时钟']
        for s in proc_stats:
            row.append(s['external_clock'])
        row.append('-')
        rows.append(row)

        # 最大速度
        row = ['最大速度']
        max_speeds = [s['max_speed'] for s in proc_stats]
        for s in proc_stats:
            row.append(s['max_speed'])
        row.append(self._analyze_speed_difference(max_speeds))
        rows.append(row)

        # 当前速度
        row = ['当前速度']
        for s in proc_stats:
            row.append(s['current_speed'])
        row.append('-')
        rows.append(row)

        # 关键指令集
        row = ['关键指令集']
        key_isets = [s['key_instruction_sets'] for s in proc_stats]
        for s in proc_stats:
            if s['key_instruction_sets']:
                row.append(', '.join(s['key_instruction_sets'][:5]))
            else:
                row.append('NA')
        row.append(self._analyze_instruction_set_difference(key_isets))
        rows.append(row)

        lines.append(self._format_table(rows))
        lines.append("")

        # 3. 内存信息对比（合并表格）
        lines.append("### 内存信息对比")
        lines.append("")

        # 收集所有内存信息
        mem_stats = []
        for cfg in self.configs:
            bios = cfg.bios
            if isinstance(bios, dict) and 'memory' in bios:
                mem_info = bios['memory']
                if isinstance(mem_info, dict):
                    mem_stats.append({
                        'display_name': cfg.display_name,
                        'smbios_version': mem_info.get('smbios_version', 'NA'),
                        'max_capacity': mem_info.get('max_capacity', 'NA'),
                        'num_devices': mem_info.get('num_devices', 'NA'),
                        'ecc_type': mem_info.get('ecc_type', 'NA'),
                        'common_size': mem_info.get('common_size', 'NA'),
                        'common_speed': mem_info.get('common_speed', 'NA'),
                        'common_type': mem_info.get('common_type', 'NA'),
                        'common_part_number': mem_info.get('common_part_number', 'NA'),
                        'size_distribution': mem_info.get('size_distribution', {}),
                        'speed_distribution': mem_info.get('speed_distribution', {}),
                    })
                else:
                    mem_stats.append(self._get_empty_mem_stat(cfg.display_name))
            else:
                mem_stats.append(self._get_empty_mem_stat(cfg.display_name))

        # 获取 CPU 电压信息（用于对比）
        voltages = []
        for cfg in self.configs:
            bios = cfg.bios
            if isinstance(bios, dict) and 'processor' in bios:
                proc_info = bios['processor']
                if isinstance(proc_info, dict):
                    voltages.append(proc_info.get('Voltage', 'NA'))
                else:
                    voltages.append('NA')
            else:
                voltages.append('NA')

        # 构建表格
        rows = [['特性'] + [s['display_name'] for s in mem_stats] + ['结论']]

        # 1. 单条容量
        row = ['单条容量']
        sizes = [s['common_size'] for s in mem_stats]
        for s in mem_stats:
            if s['common_size'] != 'NA':
                row.append(s['common_size'])
            else:
                row.append('NA')
        row.append(self._analyze_size_difference(sizes))
        rows.append(row)

        # 2. 内存速率
        row = ['内存速率']
        speeds = [s['common_speed'] for s in mem_stats]
        for s in mem_stats:
            if s['common_speed'] != 'NA':
                row.append(s['common_speed'])
            else:
                row.append('NA')
        row.append(self._analyze_speed_difference(speeds))
        rows.append(row)

        # 3. 最大支持容量
        row = ['最大支持容量']
        max_caps = [s['max_capacity'] for s in mem_stats]
        for s in mem_stats:
            row.append(s['max_capacity'])
        row.append(self._analyze_max_capacity_difference(max_caps))
        rows.append(row)

        # 4. SMBIOS 版本
        row = ['SMBIOS 版本']
        for s in mem_stats:
            row.append(s['smbios_version'])
        row.append(self._analyze_smbios_difference([s['smbios_version'] for s in mem_stats]))
        rows.append(row)

        # 5. 电压（从 CPU 处理器信息）
        row = ['CPU 电压']
        for v in voltages:
            row.append(v)
        row.append(self._analyze_voltage_difference(voltages))
        rows.append(row)

        # 6. 型号 (Part No.)
        row = ['型号 (Part No.)']
        for s in mem_stats:
            if s['common_part_number'] != 'NA':
                # 截断过长的型号
                part = s['common_part_number']
                if len(part) > 20:
                    row.append(part[:17] + '...')
                else:
                    row.append(part)
            else:
                row.append('NA')
        row.append(self._analyze_part_number_difference([s['common_part_number'] for s in mem_stats]))
        rows.append(row)

        # 7. 纠错码 (ECC)
        row = ['纠错码 (ECC)']
        for s in mem_stats:
            row.append(s['ecc_type'])
        row.append(self._analyze_ecc_difference([s['ecc_type'] for s in mem_stats]))
        rows.append(row)

        lines.append(self._format_table(rows))
        lines.append("")

        # 4. 原始输出（可展开查看）
        lines.append("### 原始 dmidecode 输出")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>点击展开查看完整 dmidecode 输出</summary>")
        lines.append("")
        for cfg in self.configs:
            bios = cfg.bios
            lines.append(f"#### {cfg.display_name}")
            lines.append("")
            if isinstance(bios, dict):
                # processor
                proc_raw = bios.get('processor', {})
                if isinstance(proc_raw, dict):
                    raw = proc_raw.get('raw', 'NA')
                else:
                    raw = 'NA'
                lines.append("**dmidecode -t processor:**")
                lines.append("```")
                lines.append(raw[:1000] + '...' if len(raw) > 1000 else raw)
                lines.append("```")
                lines.append("")

                # memory
                mem_raw = bios.get('memory', {})
                if isinstance(mem_raw, dict):
                    raw = mem_raw.get('raw', 'NA')
                else:
                    raw = 'NA'
                lines.append("**dmidecode -t memory:**")
                lines.append("```")
                lines.append(raw[:1000] + '...' if len(raw) > 1000 else raw)
                lines.append("```")
                lines.append("")

                # system
                sys_raw = bios.get('system', {})
                if isinstance(sys_raw, dict):
                    raw = sys_raw.get('raw', 'NA')
                else:
                    raw = 'NA'
                lines.append("**dmidecode -t system:**")
                lines.append("```")
                lines.append(raw[:1000] + '...' if len(raw) > 1000 else raw)
                lines.append("```")
                lines.append("")
            else:
                lines.append("dmidecode 输出: NA")
                lines.append("")
        lines.append("</details>")

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
                lines.append(f"   - {cfg.display_name}: {blas}")
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
                lines.append(f"   - {cfg.display_name}: {numa} 个节点")
            lines.append("   - 多 NUMA 节点需注意内存绑定优化，避免跨节点访问")
            lines.append("")

        # 分析环境变量
        thread_vars = []
        for cfg in self.configs:
            omp = cfg.env_vars.get('OMP_NUM_THREADS', '-')
            mkl = cfg.env_vars.get('MKL_NUM_THREADS', '-')
            if omp != '-' or mkl != '-':
                thread_vars.append((cfg.display_name, omp, mkl))

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

    def _get_empty_mem_stat(self, display_name: str) -> Dict[str, Any]:
        """获取空的内存统计结构"""
        return {
            'display_name': display_name,
            'smbios_version': 'NA',
            'max_capacity': 'NA',
            'num_devices': 'NA',
            'ecc_type': 'NA',
            'common_size': 'NA',
            'common_speed': 'NA',
            'common_type': 'NA',
            'common_part_number': 'NA',
            'size_distribution': {},
            'speed_distribution': {},
        }

    def _analyze_size_difference(self, sizes: List[str]) -> str:
        """分析单条容量差异"""
        valid_sizes = [s for s in sizes if s != 'NA']
        if len(valid_sizes) < 2:
            return '数据不完整'

        if all(s == valid_sizes[0] for s in valid_sizes):
            return '容量相同'

        # 尝试解析容量数值进行对比
        try:
            size_values = []
            for s in valid_sizes:
                if 'GB' in s:
                    size_values.append(int(s.replace('GB', '').strip()))
                elif 'MB' in s:
                    size_values.append(int(s.replace('MB', '').strip()) // 1024)

            if len(size_values) >= 2:
                ratio = size_values[0] / size_values[1]
                if ratio > 1:
                    return f'{self.configs[0].display_name} 单条容量是 {self.configs[1].display_name} 的 {ratio:.1f} 倍'
                elif ratio < 1:
                    return f'{self.configs[1].display_name} 单条容量是 {self.configs[0].display_name} 的 {1/ratio:.1f} 倍'
        except:
            pass

        return '单条容量不同'

    def _analyze_speed_difference(self, speeds: List[str]) -> str:
        """分析内存速率差异"""
        valid_speeds = [s for s in speeds if s != 'NA']
        if len(valid_speeds) < 2:
            return '数据不完整'

        if all(s == valid_speeds[0] for s in valid_speeds):
            return '速率相同'

        # 尝试解析速率数值
        try:
            speed_values = []
            for s in valid_speeds:
                if 'MT/s' in s:
                    speed_values.append(int(s.replace('MT/s', '').strip()))
                elif 'MHz' in s:
                    speed_values.append(int(s.replace('MHz', '').strip()))

            if len(speed_values) >= 2:
                diff = speed_values[0] - speed_values[1]
                if diff > 0:
                    return f'{self.configs[0].display_name} 速度更快 (+{diff} MT/s)'
                else:
                    return f'{self.configs[1].display_name} 速度更快 (+{-diff} MT/s)'
        except:
            pass

        return '速率不同'

    def _analyze_max_capacity_difference(self, max_caps: List[str]) -> str:
        """分析最大支持容量差异"""
        valid_caps = [c for c in max_caps if c != 'NA']
        if len(valid_caps) < 2:
            return '数据不完整'

        if all(c == valid_caps[0] for c in valid_caps):
            return '扩展上限相同'

        # 尝试解析容量
        try:
            cap_values = []
            for c in valid_caps:
                if 'TB' in c:
                    cap_values.append(int(c.replace('TB', '').strip()))
                elif 'GB' in c:
                    cap_values.append(int(c.replace('GB', '').strip()) // 1024)

            if len(cap_values) >= 2:
                if cap_values[0] > cap_values[1]:
                    return f'{self.configs[0].display_name} 主板扩展上限更高'
                else:
                    return f'{self.configs[1].display_name} 主板扩展上限更高'
        except:
            pass

        return '扩展上限不同'

    def _analyze_smbios_difference(self, versions: List[str]) -> str:
        """分析 SMBIOS 版本差异"""
        valid_versions = [v for v in versions if v != 'NA']
        if len(valid_versions) < 2:
            return '数据不完整'

        if all(v == valid_versions[0] for v in valid_versions):
            return '固件版本相同'

        # 版本号比较
        try:
            v_nums = [tuple(map(int, v.split('.'))) for v in valid_versions]
            if v_nums[0] > v_nums[1]:
                return f'{self.configs[0].display_name} 固件版本较新'
            else:
                return f'{self.configs[1].display_name} 固件版本较新'
        except:
            pass

        return '固件版本不同'

    def _analyze_voltage_difference(self, voltages: List[str]) -> str:
        """分析电压差异"""
        valid_volts = [v for v in voltages if v != 'NA']
        if len(valid_volts) < 2:
            return '数据不完整'

        if all(v == valid_volts[0] for v in valid_volts):
            return '电压配置相同'

        # 检查是否有动态范围
        has_range_0 = 'V' in valid_volts[0] and ('-' in valid_volts[0] or '动态' in valid_volts[0])
        has_range_1 = 'V' in valid_volts[1] and ('-' in valid_volts[1] or '动态' in valid_volts[1])

        if has_range_0 and not has_range_1:
            return f'{self.configs[0].display_name} 支持更精细的电压调节'
        elif has_range_1 and not has_range_0:
            return f'{self.configs[1].display_name} 支持更精细的电压调节'

        return '电压配置不同'

    def _analyze_part_number_difference(self, part_numbers: List[str]) -> str:
        """分析内存型号差异"""
        valid_parts = [p for p in part_numbers if p != 'NA']
        if len(valid_parts) < 2:
            return '数据不完整'

        if all(p == valid_parts[0] for p in valid_parts):
            # 检查制造商
            return '内存型号相同'

        # 提取制造商信息
        manufacturers = []
        for p in valid_parts:
            if 'M3' in p:
                manufacturers.append('三星')
            elif 'HMA' in p:
                manufacturers.append('海力士')
            elif 'KVR' in p:
                manufacturers.append('金士顿')

        if len(set(manufacturers)) > 1:
            return '不同制造商的内存规格'
        elif manufacturers:
            return f'相同制造商的不同规格 ({manufacturers[0]})'

        return '内存型号不同'

    def _analyze_ecc_difference(self, ecc_types: List[str]) -> str:
        """分析 ECC 类型差异"""
        valid_eccs = [e for e in ecc_types if e != 'NA']
        if len(valid_eccs) < 2:
            return '数据不完整'

        if all(e == valid_eccs[0] for e in valid_eccs):
            if 'ECC' in valid_eccs[0]:
                return '均为服务器级纠错内存'
            else:
                return 'ECC 配置相同'

        return '纠错类型不同'

    def _get_empty_proc_stat(self, display_name: str) -> Dict[str, Any]:
        """获取空的处理器统计结构"""
        return {
            'display_name': display_name,
            'handle': 'NA',
            'dmi_type': 'NA',
            'size_bytes': 'NA',
            'socket': 'NA',
            'type': 'NA',
            'family': 'NA',
            'manufacturer': 'NA',
            'id': 'NA',
            'signature': 'NA',
            'version': 'NA',
            'voltage': 'NA',
            'external_clock': 'NA',
            'max_speed': 'NA',
            'current_speed': 'NA',
            'core_count': 'NA',
            'core_enabled': 'NA',
            'thread_count': 'NA',
            'key_instruction_sets': [],
            'flags': 'NA',
        }

    def _analyze_socket_difference(self, sockets: List[str]) -> str:
        """分析插槽标识差异"""
        valid_sockets = [s for s in sockets if s != 'NA']
        if len(valid_sockets) < 2:
            return '数据不完整'
        if all(s == valid_sockets[0] for s in valid_sockets):
            return '插槽标识相同'
        return '插槽标识不同'

    def _analyze_family_difference(self, families: List[str]) -> str:
        """分析 CPU 家族差异"""
        valid_families = [f for f in families if f != 'NA']
        if len(valid_families) < 2:
            return '数据不完整'
        if all(f == valid_families[0] for f in valid_families):
            return 'CPU 家族相同'

        # 判断架构类型
        arch_info = []
        for f in valid_families:
            if 'Zen' in f:
                arch_info.append('AMD Zen')
            elif 'ARM' in f or 'Kunpeng' in f:
                arch_info.append('ARM')
            elif 'Intel' in f or 'Core' in f:
                arch_info.append('Intel')

        if len(set(arch_info)) > 1:
            return '不同架构家族'

        return '同架构不同世代'

    def _analyze_manufacturer_difference(self, manufacturers: List[str]) -> str:
        """分析制造商差异"""
        valid_mfrs = [m for m in manufacturers if m != 'NA']
        if len(valid_mfrs) < 2:
            return '数据不完整'
        if all(m == valid_mfrs[0] for m in valid_mfrs):
            return '制造商相同'

        # 提取简短制造商名
        mfr_names = []
        for m in valid_mfrs:
            if 'AMD' in m:
                mfr_names.append('AMD')
            elif 'Intel' in m:
                mfr_names.append('Intel')
            elif 'HiSilicon' in m:
                mfr_names.append('华为海思')
            elif 'Advanced Micro' in m:
                mfr_names.append('AMD')
            else:
                mfr_names.append(m[:20])

        if len(set(mfr_names)) > 1:
            return '不同制造商'

        return '制造商相同'

    def _analyze_version_difference(self, versions: List[str]) -> str:
        """分析 CPU 版本差异"""
        valid_versions = [v for v in versions if v != 'NA']
        if len(valid_versions) < 2:
            return '数据不完整'
        if all(v == valid_versions[0] for v in valid_versions):
            return 'CPU 版本相同'
        return '不同 CPU 型号'

    def _analyze_core_difference(self, core_counts: List[str]) -> str:
        """分析核心数差异"""
        valid_cores = [c for c in core_counts if c != 'NA']
        if len(valid_cores) < 2:
            return '数据不完整'
        if all(c == valid_cores[0] for c in valid_cores):
            return '核心数相同'

        # 尝试解析数值
        try:
            core_values = [int(c) for c in valid_cores if c.isdigit()]
            if len(core_values) >= 2:
                diff = core_values[0] - core_values[1]
                if diff > 0:
                    return f'{self.configs[0].display_name} 多 {diff} 核心'
                else:
                    return f'{self.configs[1].display_name} 多 {-diff} 核心'
        except:
            pass

        return '核心数不同'

    def _analyze_thread_difference(self, thread_counts: List[str]) -> str:
        """分析线程数差异"""
        valid_threads = [t for t in thread_counts if t != 'NA']
        if len(valid_threads) < 2:
            return '数据不完整'
        if all(t == valid_threads[0] for t in valid_threads):
            return '线程数相同'

        # 尝试解析数值
        try:
            thread_values = [int(t) for t in valid_threads if t.isdigit()]
            if len(thread_values) >= 2:
                diff = thread_values[0] - thread_values[1]
                if diff > 0:
                    return f'{self.configs[0].display_name} 多 {diff} 线程'
                else:
                    return f'{self.configs[1].display_name} 多 {-diff} 线程'
        except:
            pass

        return '线程数不同'

    def _analyze_instruction_set_difference(self, instruction_sets: List[List[str]]) -> str:
        """分析指令集差异"""
        valid_isets = [isets for isets in instruction_sets if isets]
        if len(valid_isets) < 2:
            return '数据不完整'

        # 检查架构特征
        has_avx = [any('AVX' in i for i in isets) for isets in valid_isets]
        has_sve = [any('SVE' in i for i in isets) for isets in valid_isets]

        if all(has_avx) and not any(has_sve):
            return '均为 x86 架构，支持 AVX 系列指令集'
        elif all(has_sve) and not any(has_avx):
            return '均为 ARM 架构，支持 SVE 系列指令集'
        elif has_avx[0] and has_sve[1]:
            return '不同架构指令集（x86 AVX vs ARM SVE）'
        elif has_sve[0] and has_avx[1]:
            return '不同架构指令集（ARM SVE vs x86 AVX）'

        # 比较具体指令集差异
        common_isets = set(valid_isets[0]) & set(valid_isets[1])
        unique_isets = [set(isets) - common_isets for isets in valid_isets]

        if not any(unique_isets):
            return '关键指令集相同'

        return '关键指令集存在差异'