"""SSH utilities using subprocess (no external dependencies)

Provides SSH operations for remote command execution and file transfer.
Uses subprocess to call ssh/scp commands directly.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import subprocess
import shutil
from pathlib import Path


@dataclass
class SSHConfig:
    """SSH 连接配置"""
    host: str
    username: str
    port: int = 22
    timeout: int = 30

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
            result = subprocess.run(
                [
                    "ssh",
                    "-o", f"ConnectTimeout={self.config.timeout}",
                    "-o", "BatchMode=yes",
                    "-o", "StrictHostKeyChecking=no",
                    "-p", str(self.config.port),
                    f"{self.config.username}@{self.config.host}",
                    "echo 'Connection successful'"
                ],
                capture_output=True,
                timeout=self.config.timeout + 5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, Exception):
            return False

    def execute(self, command: str, work_dir: Optional[str] = None, stream_output: bool = True) -> Tuple[bool, str]:
        """
        执行命令

        Args:
            command: 要执行的命令
            work_dir: 工作目录
            stream_output: 是否实时输出到终端（默认 True）

        Returns:
            (success, output) 元组
        """
        if self.config.is_local:
            return self._execute_local(command, work_dir, stream_output)
        else:
            return self._execute_remote(command, work_dir, stream_output)

    def _execute_local(self, command: str, work_dir: Optional[str], stream_output: bool) -> Tuple[bool, str]:
        """本地执行命令"""
        import sys
        try:
            if stream_output:
                # 实时输出到终端
                result = subprocess.run(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=work_dir,
                    bufsize=1  # 行缓冲
                )
                output = result.stdout
                # 实时打印输出
                for line in output.splitlines():
                    print(line)
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

    def _execute_remote(self, command: str, work_dir: Optional[str], stream_output: bool) -> Tuple[bool, str]:
        """远程执行命令"""
        import sys
        full_command = f"cd {work_dir} && bash -s" if work_dir else "bash -s"

        try:
            if stream_output:
                # 实时输出模式
                process = subprocess.Popen(
                    [
                        "ssh",
                        "-o", f"ConnectTimeout={self.config.timeout}",
                        "-o", "BatchMode=yes",
                        "-o", "StrictHostKeyChecking=no",
                        "-p", str(self.config.port),
                        f"{self.config.username}@{self.config.host}",
                        full_command
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                process.stdin.write(command)
                process.stdin.close()

                output_lines = []
                for line in process.stdout:
                    print(line, end='')
                    output_lines.append(line)

                process.wait()
                output = ''.join(output_lines)
                return process.returncode == 0, output
            else:
                # 捕获输出模式
                result = subprocess.run(
                    [
                        "ssh",
                        "-o", f"ConnectTimeout={self.config.timeout}",
                        "-o", "BatchMode=yes",
                        "-o", "StrictHostKeyChecking=no",
                        "-p", str(self.config.port),
                        f"{self.config.username}@{self.config.host}",
                        full_command
                    ],
                    input=command,
                    capture_output=True,
                    text=True,
                    timeout=3600  # 1 hour timeout for long ASV runs
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
            result = subprocess.run(
                [
                    "scp",
                    "-o", f"ConnectTimeout={self.config.timeout}",
                    "-o", "BatchMode=yes",
                    "-o", "StrictHostKeyChecking=no",
                    "-P", str(self.config.port),
                    "-r",
                    f"{self.config.username}@{self.config.host}:{remote_path}",
                    local_path
                ],
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


def test_connection(host: str, username: str, port: int = 22, timeout: int = 30) -> bool:
    """测试 SSH 连接"""
    config = SSHConfig(host=host, username=username, port=port, timeout=timeout)
    client = SSHClient(config)
    return client.test_connection()