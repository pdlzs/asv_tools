"""SSH utilities using subprocess (no external dependencies)

Provides SSH operations for remote command execution and file transfer.
Uses subprocess to call ssh/scp commands directly.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Callable
import subprocess
import shutil
from pathlib import Path


@dataclass
class SSHConfig:
    """SSH 连接配置"""
    host: str
    username: str
    port: int = 22
    identity_file: Optional[str] = None     # SSH 密钥文件路径
    timeout: int = 30              # 连接超时 (秒)
    execution_timeout: int = 3600  # 执行超时 (秒)，默认 1 小时

    @property
    def is_local(self) -> bool:
        return self.host == "local"


class SSHClient:
    """SSH 客户端，使用 subprocess 调用 ssh/scp"""

    def __init__(self, config: SSHConfig):
        self.config = config

    def test_connection(self) -> bool:
        """测试 SSH 连接"""
        if self.config.is_local:
            return True

        try:
            ssh_cmd = [
                "ssh",
                "-o", f"ConnectTimeout={self.config.timeout}",
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=no",
                "-p", str(self.config.port)
            ]
            if self.config.identity_file:
                ssh_cmd.extend(["-i", self.config.identity_file])
            ssh_cmd.append(f"{self.config.username}@{self.config.host}")
            ssh_cmd.append("echo 'Connection successful'")

            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                timeout=self.config.timeout + 5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, Exception):
            return False

    def execute(self, command: str, work_dir: Optional[str] = None,
                stream_output: bool = True,
                output_callback: Optional[Callable] = None) -> Tuple[bool, str]:
        """
        执行命令

        Args:
            command: 要执行的命令
            work_dir: 工作目录
            stream_output: 是否实时输出到终端（默认 True）
            output_callback: 输出回调函数（可选），每输出一行调用 callback(machine_name, line)

        Returns:
            (success, output) 元组
        """
        if self.config.is_local:
            return self._execute_local(command, work_dir, stream_output, output_callback)
        else:
            return self._execute_remote(command, work_dir, stream_output, output_callback)

    def _execute_local(self, command: str, work_dir: Optional[str],
                        stream_output: bool, output_callback: Optional[Callable]) -> Tuple[bool, str]:
        """本地执行命令"""
        import sys
        try:
            if stream_output or output_callback:
                # 实时输出到终端或回调
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=work_dir,
                    bufsize=1  # 行缓冲
                )

                output_lines = []
                for line in process.stdout:
                    if stream_output:
                        print(line, end='')
                    if output_callback:
                        output_callback(line.rstrip())
                    output_lines.append(line)

                process.wait()
                output = ''.join(output_lines)
                return process.returncode == 0, output
            else:
                # 捕获输出
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=work_dir
                )
                output = result.stdout + result.stderr
                return result.returncode == 0, output
        except Exception as e:
            return False, str(e)

    def _execute_remote(self, command: str, work_dir: Optional[str],
                         stream_output: bool, output_callback: Optional[Callable]) -> Tuple[bool, str]:
        """远程执行命令"""
        import sys
        import threading
        import time
        full_command = f"cd {work_dir} && bash -s" if work_dir else "bash -s"

        try:
            if stream_output or output_callback:
                # 实时输出或回调模式
                ssh_cmd = [
                    "ssh",
                    "-o", f"ConnectTimeout={self.config.timeout}",
                    "-o", "ServerAliveInterval=30",
                    "-o", "ServerAliveCountMax=480",
                    "-o", "BatchMode=yes",
                    "-o", "StrictHostKeyChecking=no",
                    "-p", str(self.config.port)
                ]
                if self.config.identity_file:
                    ssh_cmd.extend(["-i", self.config.identity_file])
                ssh_cmd.append(f"{self.config.username}@{self.config.host}")
                ssh_cmd.append(full_command)

                process = subprocess.Popen(
                    ssh_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=0
                )

                output_lines = []

                def read_stdout():
                    """线程函数：读取 stdout 并处理"""
                    try:
                        for line in process.stdout:
                            if stream_output:
                                print(line, end='')
                            if output_callback:
                                output_callback(line.rstrip())
                            output_lines.append(line)
                    except Exception:
                        pass

                # 启动 stdout 读取线程
                reader_thread = threading.Thread(target=read_stdout, daemon=True)
                reader_thread.start()

                # 发送脚本到 stdin
                process.stdin.write(command)
                process.stdin.flush()
                time.sleep(0.1)
                process.stdin.close()

                # 等待进程完成或超时
                try:
                    process.wait(timeout=self.config.execution_timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    return False, f"命令执行超时 ({self.config.execution_timeout}秒)"

                # 等待 stdout 线程完成
                reader_thread.join(timeout=5)

                output = ''.join(output_lines)
                return process.returncode == 0, output
            else:
                # 捕获输出模式 - 也添加 keepalive (适应长时间运行)
                ssh_cmd = [
                    "ssh",
                    "-o", f"ConnectTimeout={self.config.timeout}",
                    "-o", "ServerAliveInterval=30",
                    "-o", "ServerAliveCountMax=480",
                    "-o", "BatchMode=yes",
                    "-o", "StrictHostKeyChecking=no",
                    "-p", str(self.config.port)
                ]
                if self.config.identity_file:
                    ssh_cmd.extend(["-i", self.config.identity_file])
                ssh_cmd.append(f"{self.config.username}@{self.config.host}")
                ssh_cmd.append(full_command)

                result = subprocess.run(
                    ssh_cmd,
                    input=command,
                    capture_output=True,
                    text=True,
                    timeout=self.config.execution_timeout
                )
                output = result.stdout + result.stderr
                return result.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, str(e)

    def download(self, remote_path: str, local_path: str) -> bool:
        """
        下载文件/目录

        Args:
            remote_path: 远程路径
            local_path: 本地目标路径

        Returns:
            成功返回 True
        """
        if self.config.is_local:
            # 本地复制
            try:
                remote = Path(remote_path)
                local = Path(local_path)
                if remote.is_dir():
                    # 复制目录内容到 local_path
                    if local.exists():
                        shutil.rmtree(local)
                    shutil.copytree(remote, local)
                else:
                    shutil.copy2(remote, local)
                return True
            except Exception as e:
                print(f"本地复制失败: {e}")
                return False

        # 远程下载
        try:
            scp_cmd = [
                "scp",
                "-o", f"ConnectTimeout={self.config.timeout}",
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=no",
                "-P", str(self.config.port),
                "-r"
            ]
            if self.config.identity_file:
                scp_cmd.extend(["-i", self.config.identity_file])
            scp_cmd.append(f"{self.config.username}@{self.config.host}:{remote_path}")
            scp_cmd.append(local_path)

            result = subprocess.run(
                scp_cmd,
                capture_output=True,
                timeout=300  # 5 minutes timeout for download
            )
            if result.returncode != 0:
                print(f"下载失败: {result.stderr.decode()}")
                return False
            return True
        except Exception as e:
            print(f"下载失败: {e}")
            return False


def test_connection(host: str, username: str, port: int = 22, identity_file: Optional[str] = None, timeout: int = 30) -> bool:
    """测试 SSH 连接"""
    config = SSHConfig(host=host, username=username, port=port, identity_file=identity_file, timeout=timeout)
    client = SSHClient(config)
    return client.test_connection()