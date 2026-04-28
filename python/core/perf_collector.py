"""Performance configuration collector

Collects system performance-related configuration from remote or local machines,
including CPU, memory, BIOS, kernel parameters, and environment settings.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import re
import sys
from pathlib import Path

# 确保能导入 ssh_utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from ssh_utils import SSHClient, SSHConfig
from core.collect_config import CollectMachineConfig


@dataclass
class PerfConfig:
    """性能配置数据结构"""
    machine_name: str                  # 配置文件中的 name
    display_name: str                  # 显示名称（hostname 或 name）
    machine: Dict[str, Any]
    bios: Dict[str, Any]               # 解析后的 BIOS 信息（包含原始输出和解析字段）
    cpu: Dict[str, Any]
    memory: Dict[str, Any]
    kernel_params: Dict[str, Any]
    environment: Dict[str, str]        # python/blas/lapack/gcc
    env_vars: Dict[str, str]           # 性能相关环境变量
    limits: Dict[str, Any]
    collect_time: str = ""


class PerfCollector:
    """性能配置采集器"""

    # 采集脚本模板
    COLLECT_SCRIPT_TEMPLATE = """
{env_setup}

echo '=== MACHINE_INFO ==='
uname -m
cat /etc/os-release 2>/dev/null | grep PRETTY_NAME || echo 'NA: /etc/os-release 不存在'
uname -r
systemd-detect-virt 2>/dev/null || echo 'NA: systemd-detect-virt 不可用'

echo '=== DMIDECODE_PROCESSOR ==='
dmidecode -t processor 2>&1 || echo 'NA: 需要 root 权限运行 dmidecode'

echo '=== DMIDECODE_MEMORY ==='
dmidecode -t memory 2>&1 || echo 'NA: 需要 root 权限运行 dmidecode'

echo '=== DMIDECODE_SYSTEM ==='
dmidecode -t system 2>&1 || echo 'NA: 需要 root 权限运行 dmidecode'

echo '=== CPU_INFO ==='
lscpu 2>&1 || echo 'NA: lscpu 不可用'
# ARM架构的指令集在 /proc/cpuinfo 的 Features 字段
cat /proc/cpuinfo 2>/dev/null | grep -E '^(model name|Model|Features|flags)' | head -5 || echo 'NA: /proc/cpuinfo 不可用'

echo '=== MEMORY_INFO ==='
free -h 2>&1 || echo 'NA: free 不可用'
cat /sys/kernel/mm/transparent_hugepage/enabled 2>&1 || echo 'NA: 透明大页配置不可用'
cat /proc/meminfo 2>&1 | grep -i huge || echo 'NA: 大页配置不可用'
numactl --hardware 2>&1 || echo 'NA: numactl 不可用或无 NUMA 配置'

echo '=== PYTHON_VERSION ==='
python --version 2>&1 || echo 'NA: Python 不可用'

echo '=== GCC_VERSION ==='
(gcc --version 2>&1 | head -1) || echo 'NA: GCC 不可用'

echo '=== BLAS_VERSION ==='
(condarun list 2>/dev/null | grep -E '^blas ') || (pip list 2>/dev/null | grep -i blas) || echo 'NA: BLAS 未安装或检测失败'

echo '=== LAPACK_VERSION ==='
(conda list 2>/dev/null | grep -E '^lapack ') || (pip list 2>/dev/null | grep -i lapack) || echo 'NA: LAPACK 未安装或检测失败'

echo '=== ENV_VARS ==='
env | grep -E '^(OMP|MKL|OPENBLAS|NUMEXPR|BLIS|KMP|VECLIB)' 2>&1 || echo 'NA: 无性能相关环境变量'

echo '=== KERNEL_PARAMS ==='
sysctl vm.swappiness vm.dirty_ratio vm.dirty_background_ratio kernel.shmmax kernel.shmall kernel.sched_autogroup_enabled 2>&1 || echo 'NA: sysctl 不可用'

echo '=== LIMITS ==='
ulimit -a 2>&1 || echo 'NA: ulimit 不可用'

echo '=== COLLECT_DONE ==='
"""

    def __init__(self, machine: CollectMachineConfig,
                 script: Optional[str] = None,
                 verbose: bool = False):
        self.machine = machine
        self.script = script
        self.verbose = verbose
        self.ssh_client = self._create_ssh_client()

    def _create_ssh_client(self) -> SSHClient:
        """创建 SSH 客户端"""
        config = SSHConfig(
            host=self.machine.host,
            username=self.machine.username or "",
            port=self.machine.port
        )
        return SSHClient(config)

    def collect(self) -> PerfConfig:
        """采集所有配置"""
        if self.verbose:
            print(f"[{self.machine.name}] 开始采集性能配置...")

        # 构建采集脚本
        script = self._build_collect_script()

        # 执行采集
        success, output = self.ssh_client.execute(script, stream_output=self.verbose)

        if not success:
            print(f"[{self.machine.name}] 采集失败")
            return self._create_empty_config("采集失败")

        # 解析输出
        return self._parse_output(output)

    def _build_collect_script(self) -> str:
        """构建采集脚本"""
        env_setup = self.script if self.script else ""
        return self.COLLECT_SCRIPT_TEMPLATE.format(env_setup=env_setup)

    def _split_sections(self, output: str) -> Dict[str, str]:
        """将输出按分隔符拆分为各节"""
        sections = {}
        current_section = None
        current_content = []

        for line in output.split('\n'):
            if line.startswith('=== ') and line.endswith(' ==='):
                # 保存前一节
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                # 开始新节
                current_section = line[4:-4]  # 去掉 '=== ' 和 ' ==='
                current_content = []
            elif line == '=== COLLECT_DONE ===':
                # 保存最后一节
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                break
            else:
                current_content.append(line)

        return sections

    def _parse_output(self, output: str) -> PerfConfig:
        """解析采集输出，每项独立处理，失败项记录 NA"""
        sections = self._split_sections(output)

        from datetime import datetime
        collect_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 解析 dmidecode 输出
        bios_info = self._parse_bios_info(
            sections.get('DMIDECODE_PROCESSOR', 'NA'),
            sections.get('DMIDECODE_MEMORY', 'NA'),
            sections.get('DMIDECODE_SYSTEM', 'NA')
        )

        return PerfConfig(
            machine_name=self.machine.name,
            display_name=self.machine.display_name,
            machine=self._parse_machine_info(sections.get('MACHINE_INFO', 'NA')),
            bios=bios_info,
            cpu=self._parse_cpu_info(sections.get('CPU_INFO', 'NA')),
            memory=self._parse_memory_info(sections.get('MEMORY_INFO', 'NA')),
            kernel_params=self._parse_kernel_params(sections.get('KERNEL_PARAMS', 'NA')),
            environment={
                'python': self._parse_version(sections.get('PYTHON_VERSION', 'NA')),
                'gcc': self._parse_version(sections.get('GCC_VERSION', 'NA')),
                'blas': sections.get('BLAS_VERSION', 'NA').strip(),
                'lapack': sections.get('LAPACK_VERSION', 'NA').strip(),
            },
            env_vars=self._parse_env_vars(sections.get('ENV_VARS', 'NA')),
            limits=self._parse_limits(sections.get('LIMITS', 'NA')),
            collect_time=collect_time
        )

    def _parse_machine_info(self, raw: str) -> Dict[str, Any]:
        """解析机器信息"""
        info = {'raw': raw}
        if raw == 'NA':
            return info

        lines = raw.split('\n')
        for line in lines:
            if line.startswith('PRETTY_NAME='):
                info['os'] = line.split('=')[1].strip('"')
            elif not line.startswith('NA:') and 'Architecture:' not in line:
                # uname -m 输出在第一行
                if line.strip() in ['x86_64', 'aarch64', 'armv7l', 'i686']:
                    info['architecture'] = line.strip()
                # 内核版本
                elif re.match(r'^\d+\.\d+', line.strip()):
                    info['kernel'] = line.strip()
                # 虚拟化
                elif line.strip() in ['none', 'kvm', 'vmware', 'xen', 'docker', 'container']:
                    info['virtualization'] = line.strip()

        return info

    def _parse_bios_info(self, processor_raw: str, memory_raw: str, system_raw: str) -> Dict[str, Any]:
        """
        解析 dmidecode 输出，提取关键 BIOS 配置字段

        dmidecode 输出格式：
        Handle 0x0027, DMI type 4, 48 bytes
        Processor Information
            Socket Designation: CPU0
            Type: Central Processor
            ...

        Returns:
            包含解析字段和原始输出的字典
        """
        bios_info = {
            'processor': {'raw': processor_raw},
            'memory': {'raw': memory_raw},
            'system': {'raw': system_raw},
        }

        # 解析 Processor Information（扩展字段）
        if processor_raw and not processor_raw.startswith('NA:'):
            processor_info = self._parse_dmidecode_processor(processor_raw)
            bios_info['processor'].update(processor_info)

        # 解析 Memory Device
        if memory_raw and not memory_raw.startswith('NA:'):
            memory_devices = self._parse_dmidecode_memory(memory_raw)
            bios_info['memory'].update(memory_devices)

        # 解析 System Information
        if system_raw and not system_raw.startswith('NA:'):
            bios_info['system'].update(self._parse_dmidecode_section(
                system_raw,
                ['Manufacturer', 'Product Name', 'Version', 'Serial Number', 'UUID',
                 'Wake-up Type', 'SKU Number', 'Family']
            ))

        return bios_info

    def _parse_dmidecode_processor(self, raw: str) -> Dict[str, Any]:
        """
        解析 dmidecode CPU 处理器信息

        提取 Handle、DMI type、以及所有关键字段
        """
        result = {'raw': raw}
        lines = raw.split('\n')

        current_handle = None
        current_type = None
        in_processor = False
        flags = []

        for line in lines:
            line = line.rstrip()

            # Handle 行: Handle 0x0027, DMI type 4, 48 bytes
            if line.startswith('Handle '):
                # 解析 Handle 信息
                handle_match = re.match(r'Handle\s+(0x[0-9A-Fa-f]+)', line)
                if handle_match:
                    result['handle'] = handle_match.group(1)
                # 解析 DMI type
                type_match = re.search(r'DMI type\s+(\d+)', line)
                if type_match:
                    result['dmi_type'] = type_match.group(1)
                # 解析大小
                size_match = re.search(r'(\d+)\s+bytes', line)
                if size_match:
                    result['size_bytes'] = size_match.group(1)
                continue

            # 类型行: Processor Information
            if not line.startswith(' ') and not line.startswith('\t') and line.strip() and ':' not in line:
                if line.strip() == 'Processor Information':
                    in_processor = True
                current_type = line.strip()
                continue

            # 字段行
            if in_processor and (line.startswith('    ') or line.startswith('\t')):
                stripped = line.strip()
                if ':' in stripped:
                    parts = stripped.split(':', 1)
                    key = parts[0].strip()
                    value = parts[1].strip() if len(parts) > 1 else ''

                    # 映射关键字段
                    field_mapping = {
                        'Socket Designation': 'socket',
                        'Type': 'type',
                        'Family': 'family',
                        'Manufacturer': 'manufacturer',
                        'ID': 'id',
                        'Signature': 'signature',
                        'Version': 'version',
                        'Voltage': 'voltage',
                        'External Clock': 'external_clock',
                        'Max Speed': 'max_speed',
                        'Current Speed': 'current_speed',
                        'Status': 'status',
                        'Upgrade': 'upgrade',
                        'L1 Cache Handle': 'l1_cache_handle',
                        'L2 Cache Handle': 'l2_cache_handle',
                        'L3 Cache Handle': 'l3_cache_handle',
                        'Core Count': 'core_count',
                        'Core Enabled': 'core_enabled',
                        'Thread Count': 'thread_count',
                        'Flags': 'flags_raw',
                    }

                    if key in field_mapping:
                        result[field_mapping[key]] = value

                    # 特殊处理 Flags（多行列表）
                    if key == 'Flags':
                        flags = [value]
                        # 继续读取后续的标志行（缩进更深的行）
                        continue

                # 如果是 Flags 后续行（更深层缩进，如 8 个空格）
                elif flags and (line.startswith('        ') or line.count(' ') > 6):
                    # 这是 Flag 的后续值
                    flag_val = line.strip()
                    if flag_val and not flag_val.startswith(':'):
                        flags.append(flag_val)

            # 如果遇到新的类型行，结束当前处理器信息
            if not line.startswith(' ') and not line.startswith('\t') and line.strip() and ':' not in line and in_processor:
                in_processor = False

        # 保存解析后的 Flags
        if flags:
            result['flags'] = ', '.join(flags)
            result['flags_list'] = flags
            # 提取关键指令集
            key_flags = []
            flag_str = ' '.join(flags).lower()
            for f in ['avx512', 'avx2', 'avx', 'fma', 'sse4_2', 'sse4_1', 'sse2', 'sse', 'neon', 'sve']:
                if f in flag_str:
                    key_flags.append(f.upper().replace('_', '-'))
            result['key_instruction_sets'] = key_flags

        return result

    def _parse_dmidecode_section(self, raw: str, target_fields: List[str]) -> Dict[str, Any]:
        """
        解析 dmidecode 某一类型的信息

        Args:
            raw: dmidecode 原始输出
            target_fields: 需要提取的字段名列表

        Returns:
            提取的字段字典
        """
        result = {}
        lines = raw.split('\n')

        current_handle = None
        current_type = None

        for line in lines:
            line = line.rstrip()

            # Handle 行: Handle 0x0027, DMI type 4, 48 bytes
            if line.startswith('Handle '):
                current_handle = line
                continue

            # 类型行: Processor Information / Memory Device / System Information
            if not line.startswith(' ') and not line.startswith('\t') and line.strip() and ':' not in line:
                current_type = line.strip()
                continue

            # 字段行:    Socket Designation: CPU0
            if line.startswith('    ') or line.startswith('\t'):
                stripped = line.strip()
                if ':' in stripped:
                    # 处理可能的嵌套字段（如 Flags: 后面的列表）
                    parts = stripped.split(':', 1)
                    key = parts[0].strip()
                    value = parts[1].strip() if len(parts) > 1 else ''

                    # 检查是否是目标字段
                    if key in target_fields:
                        result[key] = value

        return result

    def _parse_dmidecode_memory(self, raw: str) -> Dict[str, Any]:
        """
        解析 dmidecode 内存信息

        提取 Physical Memory Array、Memory Device 信息以及 SMBIOS 版本
        """
        result = {}
        lines = raw.split('\n')

        current_type = None
        physical_array = {}
        smbios_version = None

        for line in lines:
            line = line.rstrip()

            # SMBIOS 版本: "# SMBIOS 3.5.0 present" 或 "SMBIOS 3.5.0 present"
            if 'SMBIOS' in line and 'present' in line:
                match = re.search(r'SMBIOS\s+(\d+\.\d+\.\d+)', line)
                if match:
                    smbios_version = match.group(1)

            # 类型行
            if not line.startswith(' ') and not line.startswith('\t') and line.strip() and ':' not in line:
                current_type = line.strip()
                continue

            # 字段行
            if line.startswith('    ') or line.startswith('\t'):
                stripped = line.strip()
                if ':' in stripped:
                    parts = stripped.split(':', 1)
                    key = parts[0].strip()
                    value = parts[1].strip() if len(parts) > 1 else ''

                    if current_type == 'Physical Memory Array':
                        if key == 'Maximum Capacity':
                            physical_array['max_capacity'] = value
                        elif key == 'Number Of Devices':
                            physical_array['num_devices'] = value
                        elif key == 'Error Correction Type':
                            physical_array['ecc_type'] = value

        # SMBIOS 版本
        if smbios_version:
            result['smbios_version'] = smbios_version

        # Physical Memory Array 信息
        result['max_capacity'] = physical_array.get('max_capacity', 'NA')
        result['num_devices'] = physical_array.get('num_devices', 'NA')
        result['ecc_type'] = physical_array.get('ecc_type', 'NA')

        # 解析所有内存设备
        result['devices'] = self._extract_memory_devices(raw)

        # 统计内存设备共性（用于对比）
        if result['devices']:
            # 找出最常见的配置
            common_size = None
            common_speed = None
            common_type = None
            common_part_number = None

            size_counts = {}
            speed_counts = {}
            type_counts = {}
            part_counts = {}

            for dev in result['devices']:
                if isinstance(dev, dict):
                    size = dev.get('Size', 'Unknown')
                    speed = dev.get('Speed', 'Unknown')
                    mem_type = dev.get('Type', 'Unknown')
                    part = dev.get('Part Number', 'Unknown')

                    size_counts[size] = size_counts.get(size, 0) + 1
                    speed_counts[speed] = speed_counts.get(speed, 0) + 1
                    type_counts[mem_type] = type_counts.get(mem_type, 0) + 1
                    if part and part != 'Unknown' and not part.startswith('No'):
                        part_counts[part] = part_counts.get(part, 0) + 1

            # 取最常见的值作为代表
            if size_counts:
                common_size = max(size_counts.items(), key=lambda x: x[1])[0]
            if speed_counts:
                common_speed = max(speed_counts.items(), key=lambda x: x[1])[0]
            if type_counts:
                common_type = max(type_counts.items(), key=lambda x: x[1])[0]
            if part_counts:
                common_part_number = max(part_counts.items(), key=lambda x: x[1])[0]

            result['common_size'] = common_size or 'NA'
            result['common_speed'] = common_speed or 'NA'
            result['common_type'] = common_type or 'NA'
            result['common_part_number'] = common_part_number or 'NA'
            result['size_distribution'] = size_counts
            result['speed_distribution'] = speed_counts
            result['type_distribution'] = type_counts

        return result

    def _extract_memory_devices(self, raw: str) -> List[Dict[str, str]]:
        """提取所有内存设备信息"""
        devices = []
        lines = raw.split('\n')

        current_device = {}
        in_device = False

        for line in lines:
            line = line.rstrip()

            if line.strip() == 'Memory Device':
                # 开始新的设备
                if current_device and any(current_device.values()):
                    devices.append(current_device)
                current_device = {}
                in_device = True
                continue

            if in_device and (line.startswith('    ') or line.startswith('\t')):
                stripped = line.strip()
                if ':' in stripped:
                    parts = stripped.split(':', 1)
                    key = parts[0].strip()
                    value = parts[1].strip() if len(parts) > 1 else ''

                    # 只记录关键字段
                    if key in ['Size', 'Form Factor', 'Type', 'Type Detail', 'Speed',
                               'Manufacturer', 'Serial Number', 'Part Number']:
                        current_device[key] = value

            # 如果遇到新的类型行，结束当前设备
            if not line.startswith(' ') and not line.startswith('\t') and line.strip() and ':' not in line:
                if in_device and current_device and any(current_device.values()):
                    devices.append(current_device)
                    current_device = {}
                    in_device = False

        # 保存最后一个设备
        if current_device and any(current_device.values()):
            devices.append(current_device)

        return devices

    def _parse_cpu_info(self, raw: str) -> Dict[str, Any]:
        """解析 CPU 信息（lscpu 输出）"""
        info = {'raw': raw}
        if raw == 'NA':
            return info

        lines = raw.split('\n')
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # 映射关键字段
                key_mapping = {
                    'Model name': 'model',
                    'Architecture': 'architecture',
                    'CPU(s)': 'logical_cores',
                    'Core(s) per socket': 'cores_per_socket',
                    'Socket(s)': 'sockets',
                    'Thread(s) per core': 'threads_per_core',
                    'CPU MHz': 'current_mhz',
                    'CPU max MHz': 'max_mhz',
                    'CPU min MHz': 'min_mhz',
                    'L1d cache': 'l1d_cache',
                    'L1i cache': 'l1i_cache',
                    'L2 cache': 'l2_cache',
                    'L3 cache': 'l3_cache',
                    'NUMA node(s)': 'numa_nodes',
                    'Flags': 'flags',
                }

                if key in key_mapping:
                    info[key_mapping[key]] = value

        # 解析物理核心数
        if 'sockets' in info and 'cores_per_socket' in info:
            try:
                info['physical_cores'] = int(info['sockets']) * int(info['cores_per_socket'])
            except ValueError:
                pass

        # 解析关键指令集（x86 和 ARM 分别处理）
        if 'flags' in info:
            # x86_64: lscpu Flags 或 /proc/cpuinfo flags
            flags = info['flags']
            key_flags = []
            for f in ['avx512', 'avx2', 'avx', 'fma', 'sse4_2', 'sse4_1', 'sse2', 'sse']:
                if f in flags.lower():
                    key_flags.append(f.upper().replace('_', '-'))
            info['key_instruction_sets'] = key_flags
        elif 'features' in info:
            # ARM64: /proc/cpuinfo Features
            features = info['features']
            key_flags = []
            arm_features_map = {
                'neon': 'NEON',
                'asimd': 'ASIMD',  # Advanced SIMD (NEON的扩展)
                'sve': 'SVE',      # Scalable Vector Extension
                'sve2': 'SVE2',
                'fp': 'FP',
                'aes': 'AES',
                'pmull': 'PMULL',
                'sha1': 'SHA1',
                'sha2': 'SHA2',
                'crc32': 'CRC32',
                'atomics': 'ATOMICS',
                'fphp': 'FPHP',
                'asimdhp': 'ASIMDHP',
                'asimddp': 'ASIMDDP',
            }
            for feat, name in arm_features_map.items():
                if feat in features.lower():
                    key_flags.append(name)
            info['key_instruction_sets'] = key_flags
        else:
            # 尝试从原始输出中解析 Features（ARM）
            for line in raw.split('\n'):
                if line.startswith('Features'):
                    features = line.split(':', 1)[1].strip() if ':' in line else ''
                    key_flags = []
                    arm_features_map = {
                        'neon': 'NEON',
                        'asimd': 'ASIMD',
                        'sve': 'SVE',
                        'sve2': 'SVE2',
                        'fp': 'FP',
                        'aes': 'AES',
                        'sha1': 'SHA1',
                        'sha2': 'SHA2',
                    }
                    for feat, name in arm_features_map.items():
                        if feat in features.lower():
                            key_flags.append(name)
                    info['key_instruction_sets'] = key_flags
                    info['features'] = features
                    break

        return info

    def _parse_memory_info(self, raw: str) -> Dict[str, Any]:
        """解析内存信息"""
        info = {'raw': raw}
        if raw == 'NA':
            return info

        lines = raw.split('\n')
        for line in lines:
            # 解析 free 输出
            if line.startswith('Mem:'):
                parts = line.split()
                if len(parts) >= 2:
                    info['total'] = parts[1]
            # 解析大页配置（HugePages_Total、HugePages_Free、Hugepagesize）
            elif ':' in line:
                # 格式: HugePages_Total:       0 或 Hugepagesize:       2048 kB
                parts = line.split(':')
                if len(parts) >= 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    if key == 'HugePages_Total':
                        info['hugepages_total'] = value
                    elif key == 'HugePages_Free':
                        info['hugepages_free'] = value
                    elif key == 'Hugepagesize':
                        info['hugepage_size'] = value
            # 透明大页配置
            elif '[' in line and ('always' in line or 'madvise' in line or 'never' in line):
                # 格式: always [madvise] never
                match = re.search(r'\[(\w+)\]', line)
                if match:
                    info['transparent_hugepage'] = match.group(1)
                match = re.search(r'\[(\w+)\]', line)
                if match:
                    info['transparent_hugepage'] = match.group(1)
            elif 'node' in line.lower() and 'size' in line.lower():
                # NUMA 信息
                info['numa_info'] = line.strip()

        return info

    def _parse_version(self, raw: str) -> str:
        """解析版本号"""
        if raw == 'NA' or raw.startswith('NA:') or '/bin/sh:' in raw or 'not found' in raw:
            return 'NA'
        raw = raw.strip()
        # Python: Python 3.10.12 -> 3.10.12
        # GCC: gcc (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0 -> 11.4.0
        match = re.search(r'(\d+\.\d+\.\d+)', raw)
        if match:
            return match.group(1)
        # 简化版本号
        match = re.search(r'(\d+\.\d+)', raw)
        if match:
            return match.group(1)
        return 'NA'

    def _parse_env_vars(self, raw: str) -> Dict[str, str]:
        """解析环境变量"""
        if raw == 'NA' or raw.startswith('NA:'):
            return {}
        env_vars = {}
        for line in raw.split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
        return env_vars

    def _parse_kernel_params(self, raw: str) -> Dict[str, str]:
        """解析内核参数"""
        if raw == 'NA' or raw.startswith('NA:'):
            return {}
        params = {}
        for line in raw.split('\n'):
            if '=' in line and not line.startswith('NA:'):
                # sysctl 输出格式: vm.swappiness = 10
                parts = line.split('=')
                if len(parts) >= 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    params[key] = value
        return params

    def _parse_limits(self, raw: str) -> Dict[str, str]:
        """解析系统限制"""
        if raw == 'NA' or raw.startswith('NA:'):
            return {}
        limits = {}
        for line in raw.split('\n'):
            # ulimit -a 输出格式: time(seconds)        unlimited 或 core file size (blocks, -c) 0
            if line.strip():
                # 尝试匹配带括号格式
                match = re.match(r'(.+?)\s+\(.+?\)\s+(.+)', line)
                if match:
                    name = match.group(1).strip()
                    value = match.group(2).strip()
                    limits[name] = value
                else:
                    # 尝试匹配简单格式: name value
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0]
                        value = parts[1]
                        limits[name] = value
        return limits

    def _create_empty_config(self, error_msg: str) -> PerfConfig:
        """创建空配置（用于失败情况）"""
        return PerfConfig(
            machine_name=self.machine.name,
            display_name=self.machine.display_name,
            machine={'error': error_msg},
            bios={'processor': {'error': error_msg}, 'memory': {'error': error_msg}, 'system': {'error': error_msg}},
            cpu={'error': error_msg},
            memory={'error': error_msg},
            kernel_params={'error': error_msg},
            environment={'python': 'NA', 'gcc': 'NA', 'blas': 'NA', 'lapack': 'NA'},
            env_vars={},
            limits={'error': error_msg},
            collect_time=""
        )

    def test_connection(self) -> bool:
        """测试 SSH 连接"""
        return self.ssh_client.test_connection()


def perf_config_to_yaml(config: PerfConfig) -> str:
    """将 PerfConfig 转换为 YAML 格式"""
    import yaml

    data = {
        '采集时间': config.collect_time,
        '主机标识': config.machine_name,
        '显示名称': config.display_name,
        'machine': config.machine,
        'bios': config.bios,
        'cpu': config.cpu,
        'memory': config.memory,
        'kernel_params': config.kernel_params,
        'environment': config.environment,
        'env_vars': config.env_vars,
        'limits': config.limits,
    }

    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)