"""Performance configuration comparator

Compares performance configurations from multiple machines and generates
Markdown comparison reports with comprehensive performance-related metrics.
"""

from typing import List, Dict, Any, Optional
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

        # 1. 系统/架构对比（新增）
        lines.append("## 系统架构对比")
        lines.append("")
        lines.append(self._compare_machine())

        # 2. CPU 对比（增强）
        lines.append("## CPU 对比")
        lines.append("")
        lines.append(self._compare_cpu())

        # 3. CPU 频率调节器对比
        lines.append("## CPU 频率调节器对比")
        lines.append("")
        lines.append(self._compare_cpu_freq())

        # 4. CPU 漏洞缓解对比
        lines.append("## CPU 漏洞缓解状态对比")
        lines.append("")
        lines.append(self._compare_cpu_vulnerabilities())

        # 5. NUMA 配置对比
        lines.append("## NUMA 配置对比")
        lines.append("")
        lines.append(self._compare_numa())

        # 6. 内存对比
        lines.append("## 内存对比")
        lines.append("")
        lines.append(self._compare_memory())

        # 7. 透明大页详细配置对比
        lines.append("## 透明大页详细配置对比")
        lines.append("")
        lines.append(self._compare_thp_details())

        # 8. Swap 配置对比
        lines.append("## Swap 配置对比")
        lines.append("")
        lines.append(self._compare_swap_config())

        # 9. 环境对比
        lines.append("## 环境对比")
        lines.append("")
        lines.append(self._compare_environment())

        # 10. 环境变量对比
        lines.append("## 环境变量对比")
        lines.append("")
        lines.append(self._compare_env_vars())

        # 11. 内核参数对比
        lines.append("## 内核参数对比")
        lines.append("")
        lines.append(self._compare_kernel_params())

        # 12. 内核启动参数对比
        lines.append("## 内核启动参数对比 (/proc/cmdline)")
        lines.append("")
        lines.append(self._compare_cmdline())

        # 13. 系统限制对比
        lines.append("## 系统限制对比 (ulimit)")
        lines.append("")
        lines.append(self._compare_limits())

        # 14. 系统服务对比
        lines.append("## 系统服务对比")
        lines.append("")
        lines.append(self._compare_system_services())

        # 15. SELinux 对比
        lines.append("## SELinux 对比")
        lines.append("")
        lines.append(self._compare_selinux())

        # 16. 防火墙对比
        lines.append("## 防火墙对比")
        lines.append("")
        lines.append(self._compare_firewall())

        # 17. BIOS 配置对比
        lines.append("## BIOS 配置")
        lines.append("")
        lines.append(self._compare_bios())

        # 18. 性能影响分析
        lines.append("## 性能影响分析")
        lines.append("")
        lines.append(self._analyze_performance_impact())

        return '\n'.join(lines)

    def _format_machines_header(self) -> str:
        """格式化机器列表标题，包含 display_name 和 host"""
        items = [f"{cfg.display_name} ({cfg.host})" for cfg in self.configs]
        return ' vs '.join(items)

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

        header = rows[0]
        separator = '|' + '|'.join(['---' for _ in header]) + '|'

        lines = []
        lines.append('|' + '|'.join([str(h) for h in header]) + '|')
        lines.append(separator)

        for row in rows[1:]:
            lines.append('|' + '|'.join([str(item) for item in row]) + '|')

        return '\n'.join(lines)

    def _compare_values(self, values: List[str]) -> str:
        """对比多个值，返回差异标记"""
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

    # ========== 新增：系统架构对比 ==========
    def _compare_machine(self) -> str:
        """对比系统架构信息"""
        rows = [self._get_headers()]

        compare_fields = [
            ('架构', 'machine.architecture'),
            ('操作系统', 'machine.os'),
            ('内核版本', 'machine.kernel'),
            ('虚拟化类型', 'machine.virtualization'),
        ]

        for label, path in compare_fields:
            values = [self._get_value(cfg, path) for cfg in self.configs]
            diff = self._compare_values(values)
            rows.append([label] + values + [diff])

        return self._format_table(rows)

    # ========== CPU 对比（增强） ==========
    def _compare_cpu(self) -> str:
        """对比 CPU 信息"""
        rows = [self._get_headers()]

        compare_fields = [
            ('架构', 'cpu.architecture'),
            ('型号', None),  # 特殊处理：优先使用 dmidecode 型号
            ('物理核心', 'cpu.physical_cores'),
            ('逻辑核心', 'cpu.logical_cores'),
            ('线程/核心', 'cpu.threads_per_core'),
            ('Socket 数', 'cpu.sockets'),
            ('当前频率', None),  # 特殊处理：使用 dmidecode current_speed
            ('最大频率', 'cpu.max_mhz'),
            ('最小频率', 'cpu.min_mhz'),
            ('频率 Boost', None),  # 特殊处理：从 raw 解析
            ('BogoMIPS', None),  # 特殊处理：从 raw 解析
            ('虚拟化支持', None),  # 特殊处理：从 raw 解析
            ('L1d 缓存', 'cpu.l1d_cache'),
            ('L1i 缓存', 'cpu.l1i_cache'),
            ('L2 缓存', 'cpu.l2_cache'),
            ('L3 缓存', 'cpu.l3_cache'),
            ('NUMA 节点', 'cpu.numa_nodes'),
            ('关键指令集', 'cpu.key_instruction_sets'),
        ]

        for label, path in compare_fields:
            if label == '型号':
                values = [self._get_cpu_model_from_dmidecode(cfg) for cfg in self.configs]
            elif label == '当前频率':
                values = [self._get_current_freq_from_dmidecode(cfg) for cfg in self.configs]
            elif label == '频率 Boost':
                values = [self._get_freq_boost_from_cpu(cfg) for cfg in self.configs]
            elif label == 'BogoMIPS':
                values = [self._get_bogomips_from_cpu(cfg) for cfg in self.configs]
            elif label == '虚拟化支持':
                values = [self._get_virtualization_from_cpu(cfg) for cfg in self.configs]
            else:
                values = [self._get_value(cfg, path) for cfg in self.configs]
            diff = self._compare_values([self._format_value_for_display(v) for v in values])
            display_values = [self._format_value_for_display(v) for v in values]
            rows.append([label] + display_values + [diff])

        return self._format_table(rows)

    def _get_cpu_model_from_dmidecode(self, config: PerfConfig) -> str:
        """从 dmidecode 获取 CPU 型号，备用 lscpu"""
        bios = config.bios
        if isinstance(bios, dict) and 'processor' in bios:
            proc_info = bios['processor']
            if isinstance(proc_info, dict):
                dmidecode_model = proc_info.get('version', '')
                if dmidecode_model and dmidecode_model != 'NA':
                    return dmidecode_model.strip()
        # 备用：从 lscpu 获取
        lscpu_model = self._get_value(config, 'cpu.model')
        if lscpu_model and lscpu_model != 'NA' and lscpu_model != '-':
            return lscpu_model
        return 'NA'

    def _get_current_freq_from_dmidecode(self, config: PerfConfig) -> str:
        """从 dmidecode 获取当前频率，备用 lscpu"""
        bios = config.bios
        if isinstance(bios, dict) and 'processor' in bios:
            proc_info = bios['processor']
            if isinstance(proc_info, dict):
                dmidecode_freq = proc_info.get('current_speed', '')
                if dmidecode_freq and dmidecode_freq != 'NA':
                    return dmidecode_freq
        # 备用：从 lscpu 获取
        lscpu_freq = self._get_value(config, 'cpu.current_mhz')
        if lscpu_freq and lscpu_freq != 'NA':
            return f"{lscpu_freq} MHz"
        return 'NA'

    def _get_freq_boost_from_cpu(self, config: PerfConfig) -> str:
        """从 lscpu raw 解析频率 boost 状态"""
        cpu_raw = self._get_value(config, 'cpu.raw')
        if cpu_raw and cpu_raw != 'NA':
            if 'Frequency boost: enabled' in cpu_raw or 'Frequency boost:                      enabled' in cpu_raw:
                return 'enabled'
            elif 'Frequency boost: disabled' in cpu_raw or 'Frequency boost:                      disabled' in cpu_raw:
                return 'disabled'
        return 'NA'

    def _get_bogomips_from_cpu(self, config: PerfConfig) -> str:
        """从 lscpu raw 解析 BogoMIPS"""
        cpu_raw = self._get_value(config, 'cpu.raw')
        if cpu_raw and cpu_raw != 'NA':
            import re
            match = re.search(r'BogoMIPS:\s+([\d.]+)', cpu_raw)
            if match:
                return match.group(1)
        return 'NA'

    def _get_virtualization_from_cpu(self, config: PerfConfig) -> str:
        """从 lscpu raw 解析虚拟化支持"""
        cpu_raw = self._get_value(config, 'cpu.raw')
        if cpu_raw and cpu_raw != 'NA':
            if 'Virtualization:                       AMD-V' in cpu_raw:
                return 'AMD-V'
            elif 'Virtualization:' in cpu_raw:
                import re
                match = re.search(r'Virtualization:\s+(\S+)', cpu_raw)
                if match:
                    return match.group(1)
        return 'NA'

    # ========== 新增：NUMA 配置对比（详细） ==========
    def _compare_numa(self) -> str:
        """对比 NUMA 详细配置"""
        lines = []

        # 1. NUMA 节点概览
        lines.append("### NUMA 节点概览")
        lines.append("")
        rows = [self._get_headers()]
        numa_nodes_values = [self._get_value(cfg, 'cpu.numa_nodes') for cfg in self.configs]
        rows.append(['NUMA 节点数'] + numa_nodes_values + [self._compare_values(numa_nodes_values)])

        # 获取各节点内存大小并计算总内存
        numa_totals = []
        for cfg in self.configs:
            numa_sizes = self._get_numa_memory_sizes(cfg)
            total_mem = sum(numa_sizes.values())
            numa_totals.append(f"{total_mem} MB ({total_mem//1024} GB)")
        rows.append(['NUMA 总内存'] + numa_totals + [self._compare_values(numa_totals)])

        lines.append(self._format_table(rows))
        lines.append("")

        # 2. 各 NUMA 节点详情
        lines.append("### 各 NUMA 节点内存配置")
        lines.append("")
        numa_details = [self._get_numa_details(cfg) for cfg in self.configs]
        max_nodes = max(len(d) for d in numa_details)

        rows = [['NUMA 节点'] + [cfg.display_name for cfg in self.configs] + ['对比']]
        for i in range(max_nodes):
            node_label = f"Node {i}"
            values = []
            for d in numa_details:
                if i in d:
                    values.append(f"{d[i]['size']} MB ({d[i]['size']//1024} GB)")
                else:
                    values.append('NA')
            diff = self._compare_values(values)
            rows.append([node_label] + values + [diff])

        lines.append(self._format_table(rows))
        lines.append("")

        # 3. NUMA 节点距离矩阵
        lines.append("### NUMA 节点距离矩阵")
        lines.append("")
        for cfg in self.configs:
            distances = self._get_numa_distances(cfg)
            if distances:
                lines.append(f"**{cfg.display_name}**:")
                lines.append("")
                lines.append(self._format_numa_distance_table(distances))
                lines.append("")

        return '\n'.join(lines)

    def _get_numa_memory_sizes(self, config: PerfConfig) -> Dict[int, int]:
        """从 memory.raw 解析各 NUMA 节点内存大小"""
        memory_raw = self._get_value(config, 'memory.raw')
        if memory_raw and memory_raw != 'NA':
            import re
            sizes = {}
            pattern = r'node (\d+) size: (\d+) MB'
            matches = re.findall(pattern, memory_raw)
            for node, size in matches:
                sizes[int(node)] = int(size)
            return sizes
        return {}

    def _get_numa_details(self, config: PerfConfig) -> Dict[int, Dict[str, Any]]:
        """获取 NUMA 节点详细信息"""
        memory_raw = self._get_value(config, 'memory.raw')
        cpu_raw = self._get_value(config, 'cpu.raw')
        details = {}

        if memory_raw and memory_raw != 'NA':
            import re
            # 解析内存大小
            size_pattern = r'node (\d+) size: (\d+) MB'
            for node, size in re.findall(size_pattern, memory_raw):
                node_id = int(node)
                if node_id not in details:
                    details[node_id] = {}
                details[node_id]['size'] = int(size)

            # 解析空闲内存
            free_pattern = r'node (\d+) free: (\d+) MB'
            for node, free in re.findall(free_pattern, memory_raw):
                node_id = int(node)
                if node_id not in details:
                    details[node_id] = {}
                details[node_id]['free'] = int(free)

        # 解析 CPU 分布
        if cpu_raw and cpu_raw != 'NA':
            import re
            # 修复正则表达式，匹配 CPU 范围如 "0-23" 或 "0 1 2 3" 等
            cpu_pattern = r'NUMA node(\d+) CPU\(s\):\s+([0-9,\s\-]+)'
            for node, cpus in re.findall(cpu_pattern, cpu_raw):
                node_id = int(node)
                if node_id not in details:
                    details[node_id] = {}
                # 简化显示 CPU 范围
                cpu_list = cpus.strip()
                if len(cpu_list) > 30:
                    cpu_list = cpu_list[:30] + '...'
                details[node_id]['cpus'] = cpu_list

        return details

    def _get_numa_distances(self, config: PerfConfig) -> Optional[List[List[int]]]:
        """从 memory.raw 解析 NUMA 节点距离矩阵"""
        memory_raw = self._get_value(config, 'memory.raw')
        if memory_raw and memory_raw != 'NA':
            import re
            # 找到距离矩阵部分
            if 'node distances:' in memory_raw:
                lines = memory_raw.split('\n')
                start_idx = None
                for i, line in enumerate(lines):
                    if 'node distances:' in line:
                        start_idx = i + 1
                        break
                if start_idx:
                    distances = []
                    for i in range(start_idx, len(lines)):
                        line = lines[i].strip()
                        if line.startswith('  ') and ':' in line:
                            parts = line.split(':')[1].strip().split()
                            try:
                                row = [int(x) for x in parts]
                                distances.append(row)
                            except:
                                pass
                        elif not line.startswith('  ') and distances:
                            break
                    return distances
        return None

    def _format_numa_distance_table(self, distances: List[List[int]]) -> str:
        """格式化 NUMA 节点距离表格"""
        if not distances:
            return "NA"

        n = len(distances)
        header = ['Node'] + [str(i) for i in range(n)]
        rows = [header]

        for i, row in enumerate(distances):
            rows.append([str(i)] + [str(x) for x in row])

        return self._format_table(rows)

    # ========== 内存对比（增强） ==========
    def _compare_memory(self) -> str:
        """对比内存信息"""
        rows = [self._get_headers()]

        compare_fields = [
            ('总内存', 'memory.total'),
            ('透明大页', 'memory.transparent_hugepage'),
            ('大页总数', 'memory.hugepages_total'),
            ('大页空闲数', 'memory.hugepages_free'),
            ('大页大小', 'memory.hugepage_size'),
        ]

        for label, path in compare_fields:
            values = [self._get_value(cfg, path) for cfg in self.configs]
            diff = self._compare_values(values)
            rows.append([label] + values + [diff])

        # 计算大页总容量（所有机器）
        hugepage_totals = []
        for cfg in self.configs:
            hugepages_total = self._get_value(cfg, 'memory.hugepages_total')
            hugepage_size = self._get_value(cfg, 'memory.hugepage_size')
            if hugepages_total != 'NA' and hugepage_size != 'NA':
                try:
                    total_huge_mb = int(hugepages_total) * int(hugepage_size.replace(' kB', '')) // 1024
                    hugepage_totals.append(f"{total_huge_mb} MB ({total_huge_mb//1024} GB)")
                except:
                    hugepage_totals.append('NA')
            else:
                hugepage_totals.append('NA')
        rows.append(['大页总容量'] + hugepage_totals + [self._compare_values(hugepage_totals)])

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
        all_vars = set()
        for cfg in self.configs:
            all_vars.update(cfg.env_vars.keys())

        if not all_vars:
            return "无性能相关环境变量设置"

        rows = [self._get_headers()]

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

    # ========== 新增：系统限制对比 ==========
    def _compare_limits(self) -> str:
        """对比系统限制 (ulimit)"""
        all_limits = set()
        for cfg in self.configs:
            all_limits.update(cfg.limits.keys())

        if not all_limits:
            return "无法获取系统限制"

        rows = [self._get_headers()]

        # 按重要性排序
        priority_limits = ['open files', 'max user processes', 'max locked memory',
                          'stack size', 'virtual memory', 'core file size']
        sorted_limits = [l for l in priority_limits if l in all_limits] + \
                       [l for l in sorted(all_limits) if l not in priority_limits]

        for limit in sorted_limits:
            values = [cfg.limits.get(limit, 'NA') for cfg in self.configs]
            diff = self._compare_values(values)
            rows.append([limit] + values + [diff])

        return self._format_table(rows)

    # ========== BIOS 配置对比（精简） ==========
    def _compare_bios(self) -> str:
        """对比 BIOS 配置，逐字段对比"""
        lines = []

        # 1. 系统信息对比
        lines.append("### 系统信息")
        lines.append("")
        rows = [self._get_headers()]
        system_fields = ['Manufacturer', 'Product Name', 'Serial Number']
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

        # 2. CPU 处理器信息对比（精简）
        lines.append("### CPU 处理器信息")
        lines.append("")
        rows = [['属性'] + [cfg.display_name for cfg in self.configs] + ['结论']]

        # 关键处理器字段
        proc_fields = [
            ('版本/型号', 'version', self._analyze_version_difference),
            ('核心数', 'core_count', self._analyze_core_difference),
            ('线程数', 'thread_count', self._analyze_thread_difference),
            ('电压', 'voltage', self._analyze_voltage_difference),
            ('最大速度', 'max_speed', self._analyze_speed_difference),
            ('当前速度', 'current_speed', None),
            ('制造商', 'manufacturer', self._analyze_manufacturer_difference),
            ('家族', 'family', self._analyze_family_difference),
        ]

        for label, field, analyzer in proc_fields:
            row = [label]
            values = []
            for cfg in self.configs:
                bios = cfg.bios
                if isinstance(bios, dict) and 'processor' in bios:
                    proc_info = bios['processor']
                    if isinstance(proc_info, dict):
                        values.append(proc_info.get(field, 'NA'))
                    else:
                        values.append('NA')
                else:
                    values.append('NA')
            row.extend(values)
            if analyzer:
                row.append(analyzer(values))
            else:
                row.append('-')
            rows.append(row)

        lines.append(self._format_table(rows))
        lines.append("")

        # 3. 内存信息对比（精简）
        lines.append("### 内存信息对比")
        lines.append("")
        rows = [['特性'] + [cfg.display_name for cfg in self.configs] + ['结论']]

        mem_fields = [
            ('单条容量', 'common_size', self._analyze_size_difference),
            ('内存速率', 'common_speed', self._analyze_speed_difference),
            ('最大支持容量', 'max_capacity', self._analyze_max_capacity_difference),
            ('实际内存条数', 'valid_device_count', self._analyze_device_count_difference),
            ('SMBIOS 版本', 'smbios_version', self._analyze_smbios_difference),
            ('内存类型', 'common_type', None),
            ('纠错码 (ECC)', 'ecc_type', self._analyze_ecc_difference),
        ]

        for label, field, analyzer in mem_fields:
            row = [label]
            values = []
            for cfg in self.configs:
                bios = cfg.bios
                if isinstance(bios, dict) and 'memory' in bios:
                    mem_info = bios['memory']
                    if isinstance(mem_info, dict):
                        values.append(mem_info.get(field, 'NA'))
                    else:
                        values.append('NA')
                else:
                    values.append('NA')
            row.extend(values)
            if analyzer:
                row.append(analyzer(values))
            else:
                row.append('-')
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
                for key in ['processor', 'memory', 'system']:
                    info = bios.get(key, {})
                    if isinstance(info, dict):
                        raw = info.get('raw', 'NA')
                    else:
                        raw = 'NA'
                    lines.append(f"**dmidecode -t {key}:**")
                    lines.append("```")
                    lines.append(raw[:1000] + '...' if len(raw) > 1000 else raw)
                    lines.append("```")
                    lines.append("")
        lines.append("</details>")

        return '\n'.join(lines)

    # ========== CPU 频率调节器对比 ==========
    def _compare_cpu_freq(self) -> str:
        """对比 CPU 频率调节器配置"""
        rows = [self._get_headers()]

        compare_fields = [
            ('驱动', 'cpu_freq.driver'),
            ('当前调节器', 'cpu_freq.governor'),
        ]

        for label, path in compare_fields:
            values = [self._get_value(cfg, path) for cfg in self.configs]
            diff = self._compare_values(values)
            rows.append([label] + values + [diff])

        # available_governors
        gov_values = []
        for cfg in self.configs:
            govs = self._get_value(cfg, 'cpu_freq.available_governors')
            if isinstance(govs, list):
                gov_values.append(', '.join(govs))
            else:
                gov_values.append(str(govs))
        diff = self._compare_values(gov_values)
        rows.append(['可用调节器'] + gov_values + [diff])

        return self._format_table(rows)

    # ========== CPU 漏洞缓解对比 ==========
    def _compare_cpu_vulnerabilities(self) -> str:
        """对比 CPU 漏洞缓解状态"""
        all_vulns = set()
        for cfg in self.configs:
            all_vulns.update(cfg.cpu_vulnerabilities.keys())

        if not all_vulns:
            return "无法获取 CPU 漏洞缓解信息"

        rows = [self._get_headers()]

        for vuln in sorted(all_vulns):
            values = [cfg.cpu_vulnerabilities.get(vuln, 'NA') for cfg in self.configs]
            diff = self._compare_values(values)
            rows.append([vuln] + values + [diff])

        return self._format_table(rows)

    # ========== 透明大页详细配置对比 ==========
    def _compare_thp_details(self) -> str:
        """对比透明大页详细配置"""
        rows = [self._get_headers()]

        compare_fields = [
            ('THP defrag', 'thp_details.defrag'),
            ('THP shmem', 'thp_details.shmem_enabled'),
        ]

        for label, path in compare_fields:
            values = [self._get_value(cfg, path) for cfg in self.configs]
            diff = self._compare_values(values)
            rows.append([label] + values + [diff])

        return self._format_table(rows)

    # ========== 内核启动参数对比 ==========
    def _compare_cmdline(self) -> str:
        """对比内核启动参数 (/proc/cmdline)"""
        cmdlines = [cfg.cmdline for cfg in self.configs]
        if all(c == 'NA' for c in cmdlines):
            return "无法获取内核启动参数"

        lines = []
        for cfg in self.configs:
            lines.append(f"**{cfg.display_name}**:")
            lines.append("```")
            lines.append(cfg.cmdline if cfg.cmdline != 'NA' else '不可用')
            lines.append("```")
            lines.append("")

        # 解析关键参数进行对比
        key_params = ['mitigations', 'nosmt', 'isolcpus', 'nohz_full', 'rcu_nocbs',
                      'transparent_hugepage', 'hugepages', 'nr_cpus', 'mem', 'console',
                      'quiet', 'splash', 'audit', 'selinux']

        rows = [self._get_headers()]
        for param in key_params:
            values = []
            for cfg in self.configs:
                cmdline = cfg.cmdline
                if cmdline and cmdline != 'NA':
                    found = 'NOT SET'
                    for token in cmdline.split():
                        if token.startswith(param + '=') or token == param:
                            found = token
                            break
                    values.append(found)
                else:
                    values.append('NA')
            if any(v != 'NOT SET' and v != 'NA' for v in values):
                diff = self._compare_values(values)
                rows.append([param] + values + [diff])

        if len(rows) > 1:
            lines.append("**关键参数对比**:")
            lines.append("")
            lines.append(self._format_table(rows))

        return '\n'.join(lines)

    # ========== 系统服务对比 ==========
    def _compare_system_services(self) -> str:
        """对比系统服务状态"""
        all_services = set()
        for cfg in self.configs:
            all_services.update(cfg.system_services.keys())

        if not all_services:
            return "无法获取系统服务状态"

        rows = [self._get_headers()]

        for service in sorted(all_services):
            values = [cfg.system_services.get(service, 'NA') for cfg in self.configs]
            diff = self._compare_values(values)
            rows.append([service] + values + [diff])

        return self._format_table(rows)

    # ========== SELinux 对比 ==========
    def _compare_selinux(self) -> str:
        """对比 SELinux 状态"""
        rows = [self._get_headers()]

        # SELinux 状态
        status_values = []
        for cfg in self.configs:
            selinux = cfg.selinux
            if isinstance(selinux, dict):
                status_values.append(selinux.get('status', 'NA'))
            else:
                status_values.append('NA')
        rows.append(['SELinux 状态'] + status_values + [self._compare_values(status_values)])

        # SELinux 模式
        mode_values = []
        for cfg in self.configs:
            selinux = cfg.selinux
            if isinstance(selinux, dict):
                mode_values.append(selinux.get('mode', 'NA'))
            else:
                mode_values.append('NA')
        rows.append(['SELinux 模式'] + mode_values + [self._compare_values(mode_values)])

        return self._format_table(rows)

    # ========== 防火墙对比 ==========
    def _compare_firewall(self) -> str:
        """对比防火墙状态"""
        rows = [self._get_headers()]

        # firewalld 状态
        firewalld_values = []
        for cfg in self.configs:
            firewall = cfg.firewall
            if isinstance(firewall, dict) and 'firewalld' in firewall:
                fw_info = firewall['firewalld']
                if isinstance(fw_info, dict):
                    state = fw_info.get('state', 'NA')
                    available = fw_info.get('available', False)
                    if not available:
                        firewalld_values.append('未安装')
                    else:
                        firewalld_values.append(state)
                else:
                    firewalld_values.append('NA')
            else:
                firewalld_values.append('NA')
        rows.append(['firewalld'] + firewalld_values + [self._compare_values(firewalld_values)])

        # ufw 状态
        ufw_values = []
        for cfg in self.configs:
            firewall = cfg.firewall
            if isinstance(firewall, dict) and 'ufw' in firewall:
                ufw_info = firewall['ufw']
                if isinstance(ufw_info, dict):
                    state = ufw_info.get('state', 'NA')
                    available = ufw_info.get('available', False)
                    if not available:
                        ufw_values.append('未安装')
                    else:
                        ufw_values.append(state)
                else:
                    ufw_values.append('NA')
            else:
                ufw_values.append('NA')
        rows.append(['ufw'] + ufw_values + [self._compare_values(ufw_values)])

        # iptables 可用性
        iptables_values = []
        for cfg in self.configs:
            firewall = cfg.firewall
            if isinstance(firewall, dict) and 'iptables' in firewall:
                ipt_info = firewall['iptables']
                if isinstance(ipt_info, dict):
                    available = ipt_info.get('available', False)
                    iptables_values.append('可用' if available else '不可用')
                else:
                    iptables_values.append('NA')
            else:
                iptables_values.append('NA')
        rows.append(['iptables'] + iptables_values + [self._compare_values(iptables_values)])

        return self._format_table(rows)

    # ========== Swap 配置对比 ==========
    def _compare_swap_config(self) -> str:
        """对比 Swap 配置"""
        rows = [self._get_headers()]

        swap_counts = [str(self._get_value(cfg, 'swap_config.swap_count')) for cfg in self.configs]
        rows.append(['Swap 设备数'] + swap_counts + [self._compare_values(swap_counts)])

        # Total swap size
        swap_sizes = []
        for cfg in self.configs:
            devices = self._get_value(cfg, 'swap_config.devices')
            if isinstance(devices, list):
                total = 0
                for d in devices:
                    if isinstance(d, dict) and 'size' in d:
                        try:
                            total += int(d['size'].rstrip('GMBK'))
                        except ValueError:
                            pass
                swap_sizes.append(f"{total} G" if total > 0 else 'NA')
            else:
                swap_sizes.append('NA')
        rows.append(['Swap 总大小'] + swap_sizes + [self._compare_values(swap_sizes)])

        return self._format_table(rows)

    def _analyze_performance_impact(self) -> str:
        """分析性能影响"""
        lines = []
        lines.append("### 主要差异点")
        lines.append("")

        item_num = 1

        # 分析架构差异
        architectures = [self._get_value(cfg, 'cpu.architecture') for cfg in self.configs]
        if len(set(architectures)) > 1:
            lines.append(f"{item_num}. **架构差异**: {', '.join(architectures)}")
            lines.append("   - 不同架构的指令集和优化策略不同")
            lines.append("   - x86_64 通常使用 AVX/AVX2/AVX-512，ARM64 使用 NEON/SVE")
            lines.append("")
            item_num += 1

        # 分析频率 Boost 状态
        boost_states = [self._get_freq_boost_from_cpu(cfg) for cfg in self.configs]
        valid_boosts = [b for b in boost_states if b != 'NA']
        if len(valid_boosts) >= 2 and valid_boosts[0] != valid_boosts[1]:
            lines.append(f"{item_num}. **频率 Boost 状态差异**: {', '.join(valid_boosts)}")
            lines.append("   - enabled: CPU 可动态提升频率以获得更高性能")
            lines.append("   - disabled: CPU 固定频率运行，功耗和热量更稳定")
            lines.append("")
            item_num += 1

        # 分析大页配置
        hugepages = [self._get_value(cfg, 'memory.hugepages_total') for cfg in self.configs]
        valid_hugepages = [h for h in hugepages if h != 'NA']
        if len(valid_hugepages) >= 2 and valid_hugepages[0] != valid_hugepages[1]:
            lines.append(f"{item_num}. **大页配置差异**: {', '.join(valid_hugepages)} 页")
            lines.append("   - 大页可减少内存分页开销，提升内存密集型应用性能")
            lines.append("   - 对于数据库、大数据分析等应用影响显著")
            lines.append("")
            item_num += 1

        # 分析 NUMA 节点数
        numa_nodes = [self._get_value(cfg, 'cpu.numa_nodes') for cfg in self.configs]
        valid_numas = [n for n in numa_nodes if n != 'NA']
        if len(valid_numas) >= 2 and valid_numas[0] != valid_numas[1]:
            lines.append(f"{item_num}. **NUMA 节点数差异**: {', '.join(valid_numas)} 个节点")
            lines.append("   - 多 NUMA 节点需注意内存绑定优化，避免跨节点访问")
            lines.append("   - NUMA 节点数影响内存访问延迟和带宽")
            lines.append("")
            item_num += 1

        # 分析内存条数
        device_counts = []
        for cfg in self.configs:
            bios = cfg.bios
            if isinstance(bios, dict) and 'memory' in bios:
                mem_info = bios['memory']
                if isinstance(mem_info, dict):
                    device_counts.append(mem_info.get('valid_device_count', 'NA'))
                else:
                    device_counts.append('NA')
            else:
                device_counts.append('NA')
        valid_counts = [str(c) for c in device_counts if c != 'NA']
        if len(valid_counts) >= 2 and valid_counts[0] != valid_counts[1]:
            lines.append(f"{item_num}. **内存条数差异**: {', '.join(valid_counts)} 条")
            lines.append("   - 内存条数影响内存通道利用率")
            lines.append("   - 更多内存条可提供更高的内存带宽")
            lines.append("")
            item_num += 1

        # 分析内存速率
        speeds = []
        for cfg in self.configs:
            bios = cfg.bios
            if isinstance(bios, dict) and 'memory' in bios:
                mem_info = bios['memory']
                if isinstance(mem_info, dict):
                    speeds.append(mem_info.get('common_speed', 'NA'))
                else:
                    speeds.append('NA')
            else:
                speeds.append('NA')
        valid_speeds = [s for s in speeds if s != 'NA']
        if len(valid_speeds) >= 2 and valid_speeds[0] != valid_speeds[1]:
            lines.append(f"{item_num}. **内存速率差异**: {', '.join(valid_speeds)}")
            lines.append("   - 更高内存速率可提供更高的内存带宽")
            lines.append("")
            item_num += 1

        # 分析 BLAS 库差异
        blas_versions = [self._get_value(cfg, 'environment.blas') for cfg in self.configs]
        if len(set([v for v in blas_versions if v != 'NA'])) > 1:
            lines.append(f"{item_num}. **BLAS 库差异**:")
            for cfg, blas in zip(self.configs, blas_versions):
                lines.append(f"   - {cfg.display_name}: {blas}")
            lines.append("   - MKL 在 Intel CPU 上通常有 20-40% 矩阵运算优势")
            lines.append("   - OpenBLAS 是跨平台开源选择，ARM 平台常用")
            lines.append("")
            item_num += 1

        # 分析核心数差异
        cores = [self._get_value(cfg, 'cpu.physical_cores') for cfg in self.configs]
        valid_cores = [int(c) for c in cores if c != 'NA' and c.isdigit()]
        if len(valid_cores) >= 2 and valid_cores[0] != valid_cores[1]:
            diff = valid_cores[1] - valid_cores[0]
            lines.append(f"{item_num}. **核心数差异**: {valid_cores[0]} vs {valid_cores[1]} ({'+' if diff > 0 else ''}{diff})")
            lines.append("   - 核心数直接影响并行计算能力")
            lines.append("")
            item_num += 1

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
                lines.append(f"{item_num}. **线程数配置差异**:")
                for name, omp, mkl in thread_vars:
                    lines.append(f"   - {name}: OMP={omp}, MKL={mkl}")
                lines.append("   - 线程数应与物理核心数匹配以获得最佳性能")
                lines.append("")
                item_num += 1

        # 分析 ulimit 差异
        open_files = [cfg.limits.get('open files', 'NA') for cfg in self.configs]
        valid_open_files = [o for o in open_files if o != 'NA']
        if len(valid_open_files) >= 2 and valid_open_files[0] != valid_open_files[1]:
            lines.append(f"{item_num}. **文件描述符限制差异**: {', '.join(valid_open_files)}")
            lines.append("   - 较低的 open files 限制可能限制高并发应用")
            lines.append("")
            item_num += 1

        # 分析 CPU 频率调节器差异
        governors = [self._get_value(cfg, 'cpu_freq.governor') for cfg in self.configs]
        valid_govs = [g for g in governors if g != 'NA']
        if len(valid_govs) >= 2 and valid_govs[0] != valid_govs[1]:
            lines.append(f"{item_num}. **CPU 频率调节器差异**: {', '.join(valid_govs)}")
            lines.append("   - performance: CPU 锁定最高频率，适合延迟敏感负载")
            lines.append("   - ondemand/schedutil: 按需调频，兼顾功耗与性能")
            lines.append("   - 不同的 governor 可能导致显著的性能差异（5-20%）")
            lines.append("")
            item_num += 1

        # 分析 CPU 漏洞缓解差异
        miti_statuses = []
        for cfg in self.configs:
            miti = cfg.cpu_vulnerabilities.get('spec_store_bypass',
                     cfg.cpu_vulnerabilities.get('spectre_v2',
                     cfg.cpu_vulnerabilities.get('meltdown', '')))
            miti_statuses.append(miti if miti else 'NA')
        if len(set(miti_statuses)) > 1:
            lines.append(f"{item_num}. **CPU 漏洞缓解差异**: {', '.join(miti_statuses)}")
            lines.append("   - 开启缓解（如 `Mitigation: ...`）可能降低 3-15% 性能")
            lines.append("   - 关闭缓解可获得更高性能但降低安全性")
            lines.append("")
            item_num += 1

        # 分析 THP defrag
        thp_defrags = [self._get_value(cfg, 'thp_details.defrag') for cfg in self.configs]
        valid_defrags = [d for d in thp_defrags if d != 'NA']
        if len(valid_defrags) >= 2 and valid_defrags[0] != valid_defrags[1]:
            lines.append(f"{item_num}. **透明大页 defrag 差异**: {', '.join(valid_defrags)}")
            lines.append("   - always: 积极整理大页碎片，可能引入延迟抖动")
            lines.append("   - madvise: 仅在应用主动请求时整理，更可控")
            lines.append("   - defer: 延迟整理，适合较大的内存负载")
            lines.append("")
            item_num += 1

        # 分析 tuned 服务
        tuned_statuses = [cfg.system_services.get('tuned', 'NA') for cfg in self.configs]
        valid_tuned = [t for t in tuned_statuses if t != 'NA' and 'not installed' not in t]
        if len(set(valid_tuned)) > 1:
            lines.append(f"{item_num}. **tuned 性能策略差异**:")
            for cfg, status in zip(self.configs, tuned_statuses):
                lines.append(f"   - {cfg.display_name}: {status}")
            lines.append("   - tuned 策略控制多种内核参数，不同策略会导致性能差异")
            lines.append("")
            item_num += 1

        # 分析内核启动参数 mitigations
        mitigation_cmdlines = []
        for cfg in self.configs:
            cmdline = cfg.cmdline
            if cmdline and cmdline != 'NA':
                has_mitigations = 'mitigations=off' in cmdline
                mitigation_cmdlines.append('off' if has_mitigations else 'on (default)')
            else:
                mitigation_cmdlines.append('NA')
        if len(set(mitigation_cmdlines)) > 1:
            lines.append(f"{item_num}. **内核 mitigations 参数差异**: {', '.join(mitigation_cmdlines)}")
            lines.append("   - mitigations=off 可提升性能（5-30%），但禁用 CPU 安全缓解")
            lines.append("   - 默认开启所有缓解措施以保证安全性")
            lines.append("")
            item_num += 1

        if item_num == 1:
            lines.append("各机器配置基本一致，无明显性能差异因素。")

        return '\n'.join(lines)

    # ========== 分析方法 ==========
    def _analyze_size_difference(self, sizes: List[str]) -> str:
        """分析单条容量差异"""
        valid_sizes = [s for s in sizes if s != 'NA']
        if len(valid_sizes) < 2:
            return '数据不完整'
        if all(s == valid_sizes[0] for s in valid_sizes):
            return '容量相同'
        return '单条容量不同'

    def _analyze_speed_difference(self, speeds: List[str]) -> str:
        """分析速率差异"""
        valid_speeds = [s for s in speeds if s != 'NA']
        if len(valid_speeds) < 2:
            return '数据不完整'
        if all(s == valid_speeds[0] for s in valid_speeds):
            return '速率相同'
        return '速率不同'

    def _analyze_max_capacity_difference(self, max_caps: List[str]) -> str:
        """分析最大支持容量差异"""
        valid_caps = [c for c in max_caps if c != 'NA']
        if len(valid_caps) < 2:
            return '数据不完整'
        if all(c == valid_caps[0] for c in valid_caps):
            return '扩展上限相同'
        return '扩展上限不同'

    def _analyze_device_count_difference(self, counts: List[str]) -> str:
        """分析内存条数差异"""
        valid_counts = [c for c in counts if c != 'NA']
        if len(valid_counts) < 2:
            return '数据不完整'
        if all(c == valid_counts[0] for c in valid_counts):
            return '内存条数相同'
        try:
            count_values = [int(c) for c in valid_counts]
            diff = count_values[0] - count_values[1]
            if diff > 0:
                return f'{self.configs[0].display_name} 多 {diff} 条'
            else:
                return f'{self.configs[1].display_name} 多 {-diff} 条'
        except:
            pass
        return '内存条数不同'

    def _analyze_smbios_difference(self, versions: List[str]) -> str:
        """分析 SMBIOS 版本差异"""
        valid_versions = [v for v in versions if v != 'NA']
        if len(valid_versions) < 2:
            return '数据不完整'
        if all(v == valid_versions[0] for v in valid_versions):
            return '固件版本相同'
        return '固件版本不同'

    def _analyze_voltage_difference(self, voltages: List[str]) -> str:
        """分析电压差异"""
        valid_volts = [v for v in voltages if v != 'NA']
        if len(valid_volts) < 2:
            return '数据不完整'
        if all(v == valid_volts[0] for v in valid_volts):
            return '电压配置相同'
        return '电压配置不同'

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

    def _analyze_manufacturer_difference(self, manufacturers: List[str]) -> str:
        """分析制造商差异"""
        valid_mfrs = [m for m in manufacturers if m != 'NA']
        if len(valid_mfrs) < 2:
            return '数据不完整'
        if all(m == valid_mfrs[0] for m in valid_mfrs):
            return '制造商相同'
        # 简化制造商名
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