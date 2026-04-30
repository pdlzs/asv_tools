"""日志工具 - 同时输出到终端和文件"""

import sys
from pathlib import Path
from typing import Optional


class TeeOutput:
    """同时输出到终端和文件（类似 tee 命令）- 同时捕获 stdout 和 stderr"""

    def __init__(self, log_file: Path, stream_type: str = 'stdout'):
        """
        Args:
            log_file: 日志文件路径
            stream_type: 'stdout' 或 'stderr'
        """
        self.log_file = log_file
        self.log_fd = open(log_file, 'a', encoding='utf-8')
        self.stream_type = stream_type

        if stream_type == 'stdout':
            self.original_stream = sys.stdout
        else:
            self.original_stream = sys.stderr

    def write(self, message: str):
        """写入消息到终端和文件"""
        self.original_stream.write(message)
        self.log_fd.write(message)
        self.log_fd.flush()

    def flush(self):
        """刷新缓冲区"""
        self.original_stream.flush()
        self.log_fd.flush()

    def close(self):
        """关闭日志文件，恢复原始输出"""
        self.log_fd.close()
        if self.stream_type == 'stdout':
            sys.stdout = self.original_stream
        else:
            sys.stderr = self.original_stream


def start_log_tee(output_dir: Path, log_filename: str) -> Optional[TeeOutput]:
    """
    开始日志 Tee 输出（同时捕获 stdout 和 stderr）

    Args:
        output_dir: 输出目录
        log_filename: 日志文件名

    Returns:
        TeeOutput 实例（stdout），用于后续关闭
    """
    log_file = output_dir / log_filename

    # 创建 stderr Tee（写入同一文件）
    stderr_tee = TeeOutput(log_file, 'stderr')
    sys.stderr = stderr_tee

    # 创建 stdout Tee
    stdout_tee = TeeOutput(log_file, 'stdout')
    sys.stdout = stdout_tee

    # 保存 stderr_tee 到 stdout_tee 中，方便一起关闭
    stdout_tee._stderr_tee = stderr_tee

    return stdout_tee


def stop_log_tee(tee: Optional[TeeOutput]):
    """
    停止日志 Tee 输出

    Args:
        tee: TeeOutput 实例
    """
    if tee:
        # 先关闭 stderr tee
        if hasattr(tee, '_stderr_tee'):
            tee._stderr_tee.close()
        # 再关闭 stdout tee
        tee.close()