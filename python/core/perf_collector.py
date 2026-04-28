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
    machine_name: str
    machine: Dict[str, Any]
    bios: Dict[str, str]              # dmidecode 原始输出
    cpu: Dict[str, Any]
    memory: Dict[str, Any]
    kernel_params: Dict[str, Any]
    environment: Dict[str, str]       # python/blas/lapack/gcc
    env_vars: Dict[str, str]          # 性能相关环境变量
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

echo '=== MEMORY_INFO ==='
free -h 2>&1 || echo 'NA: free 不可用'
cat /sys/kernel/mm/transparent_hugepage/enabled 2>&1 || echo 'NA: 透明大页配置不可用'
cat /proc/meminfo 2>&1 | grep -E 'HugePages|Hugepagesize' || echo 'NA: 大页配置不可用'
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

        return PerfConfig(
            machine_name=self.machine.name,
            machine=self._parse_machine_info(sections.get('MACHINE_INFO', 'NA')),
            bios={
                'dmidecode_processor': sections.get('DMIDECODE_PROCESSOR', 'NA'),
                'dmidecode_memory': sections.get('DMIDECODE_MEMORY', 'NA'),
                'dmidecode_system': sections.get('DMIDECODE_SYSTEM', 'NA'),
            },
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

        # 解析关键指令集
        if 'flags' in info:
            flags = info['flags']
            key_flags = []
            for f in ['avx512', 'avx2', 'avx', 'fma', 'sse4', 'sse2', 'sse']:
                if f in flags.lower():
                    key_flags.append(f.upper().replace('_', '-'))
            info['key_instruction_sets'] = key_flags

        return info

    def _parse_memory_info(self, raw: str) -> Dict[str, Any]:
        """解析内存信息"""
        info = {'raw': raw}
        if raw == 'NA':
            return info

        lines = raw.split('\n')
        for line in lines:
            if line.startswith('Mem:'):
                parts = line.split()
                if len(parts) >= 2:
                    info['total'] = parts[1]
            elif 'HugePages_Total:' in line:
                info['hugepages_total'] = line.split(':')[1].strip()
            elif 'Hugepagesize:' in line:
                info['hugepage_size'] = line.split(':')[1].strip()
            elif line.startswith('[always') or line.startswith('[madvise') or line.startswith('[never'):
                # 透明大页配置，[always] 表示当前值
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
            machine={'error': error_msg},
            bios={'error': error_msg},
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
        '主机名': config.machine_name,
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