#!/usr/bin/env python3
"""SSH免密登录配置命令

一键配置cmp.yaml中所有远程服务器的SSH免密登录。
"""

import subprocess
import sys
import shutil
from pathlib import Path
from typing import List, Optional, Tuple


def get_default_ssh_pubkey() -> Optional[Path]:
    """获取默认的SSH公钥路径"""
    ssh_dir = Path.home() / ".ssh"

    # 按优先级检查常见的公钥类型
    key_files = ["id_ed25519.pub", "id_rsa.pub", "id_ecdsa.pub", "id_dsa.pub"]

    for key_file in key_files:
        pubkey_path = ssh_dir / key_file
        if pubkey_path.exists():
            return pubkey_path

    return None


def get_default_ssh_privkey() -> Optional[Path]:
    """获取默认的SSH私钥路径"""
    ssh_dir = Path.home() / ".ssh"

    key_files = ["id_ed25519", "id_rsa", "id_ecdsa", "id_dsa"]

    for key_file in key_files:
        privkey_path = ssh_dir / key_file
        if privkey_path.exists():
            return privkey_path

    return None


def generate_ssh_key(key_type: str = "ed25519") -> Tuple[bool, str]:
    """生成SSH密钥对

    Args:
        key_type: 密钥类型 (ed25519, rsa)

    Returns:
        (success, message)
    """
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(mode=0o700, exist_ok=True)

    if key_type == "ed25519":
        key_path = ssh_dir / "id_ed25519"
        cmd = ["ssh-keygen", "-t", "ed25519", "-f", str(key_path), "-N", ""]
    else:
        key_path = ssh_dir / "id_rsa"
        cmd = ["ssh-keygen", "-t", "rsa", "-b", "4096", "-f", str(key_path), "-N", ""]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True, f"SSH密钥已生成: {key_path}"
        else:
            return False, f"生成密钥失败: {result.stderr}"
    except Exception as e:
        return False, f"生成密钥时出错: {e}"


def read_pubkey(pubkey_path: Path) -> Optional[str]:
    """读取公钥内容"""
    try:
        return pubkey_path.read_text().strip()
    except Exception:
        return None


def has_ssh_copy_id() -> bool:
    """检查 ssh-copy-id 工具是否存在"""
    return shutil.which("ssh-copy-id") is not None


def check_ssh_connection(host: str, username: str, port: int, timeout: int = 10) -> bool:
    """测试SSH免密登录是否可用"""
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o", f"ConnectTimeout={timeout}",
                "-o", "BatchMode=yes",  # 关键：禁用密码交互，测试免密登录
                "-o", "StrictHostKeyChecking=no",
                "-p", str(port),
                f"{username}@{host}",
                "echo 'ok'"
            ],
            capture_output=True,
            timeout=timeout + 5
        )
        return result.returncode == 0
    except Exception:
        return False


def copy_pubkey_with_ssh_copy_id(host: str, username: str, port: int, pubkey_path: Path) -> Tuple[bool, str]:
    """使用 ssh-copy-id 复制公钥"""
    try:
        result = subprocess.run(
            [
                "ssh-copy-id",
                "-i", str(pubkey_path),
                "-p", str(port),
                f"{username}@{host}"
            ],
            capture_output=False,  # 允许交互输入密码
            timeout=60
        )
        return result.returncode == 0, "ssh-copy-id completed"
    except subprocess.TimeoutExpired:
        return False, "操作超时"
    except Exception as e:
        return False, str(e)


def copy_pubkey_manual(host: str, username: str, port: int, pubkey: str, timeout: int = 30) -> Tuple[bool, str]:
    """手动通过SSH添加公钥到authorized_keys（ssh-copy-id不存在时的备用方案）"""
    # 构建远程命令：确保 .ssh 目录存在并设置权限，然后追加公钥
    remote_cmd = (
        "mkdir -p ~/.ssh && "
        "chmod 700 ~/.ssh && "
        f"echo '{pubkey}' >> ~/.ssh/authorized_keys && "
        "chmod 600 ~/.ssh/authorized_keys"
    )

    try:
        print(f"   正在手动添加公钥到远程服务器...")
        print(f"   需要输入远程服务器密码:")

        result = subprocess.run(
            [
                "ssh",
                "-o", f"ConnectTimeout={timeout}",
                "-o", "StrictHostKeyChecking=no",
                "-p", str(port),
                f"{username}@{host}",
                remote_cmd
            ],
            capture_output=False,  # 允许交互输入密码
            timeout=60
        )
        return result.returncode == 0, "manual copy completed"
    except subprocess.TimeoutExpired:
        return False, "操作超时"
    except Exception as e:
        return False, str(e)


def setup_passwordless_ssh(host: str, username: str, port: int, pubkey_path: Path, timeout: int = 30) -> Tuple[bool, str]:
    """配置SSH免密登录

    Args:
        host: 远程主机
        username: 用户名
        port: SSH端口
        pubkey_path: 公钥路径
        timeout: 超时时间

    Returns:
        (success, message)
    """
    pubkey = read_pubkey(pubkey_path)
    if not pubkey:
        return False, f"✗ 无法读取公钥: {pubkey_path}"

    # 先测试当前是否已经可以免密登录（跳过已配置的服务器）
    if check_ssh_connection(host, username, port, timeout):
        return True, f"✓ {username}@{host}:{port} 已经可以免密登录，跳过"

    print(f"\n正在配置 {username}@{host}:{port} 的免密登录...")

    # 选择复制公钥的方式
    if has_ssh_copy_id():
        print(f"   使用 ssh-copy-id 复制公钥，需要输入远程服务器密码:")
        success, msg = copy_pubkey_with_ssh_copy_id(host, username, port, pubkey_path)
    else:
        print(f"   ssh-copy-id 不可用，使用手动方式复制公钥")
        success, msg = copy_pubkey_manual(host, username, port, pubkey, timeout)

    if not success:
        return False, f"✗ {username}@{host}:{port} 复制公钥失败: {msg}"

    # 验证是否成功
    if check_ssh_connection(host, username, port, timeout):
        return True, f"✓ {username}@{host}:{port} 免密登录配置成功"
    else:
        return False, f"✗ {username}@{host}:{port} 配置后仍无法免密登录"


def run_ssh_setup(args) -> int:
    """执行SSH免密登录配置

    Args:
        args: CLI参数，包含 config_file

    Returns:
        退出码
    """
    from core.config import load_config

    config_file = args.config_file

    # 加载配置
    try:
        config = load_config(config_file)
    except Exception as e:
        print(f"❌ 加载配置文件失败: {e}")
        return 1

    # 收集需要配置的远程机器
    remote_machines = []
    for name, machine in config.machines.items():
        if not machine.is_local:
            if not machine.username:
                print(f"⚠️  机器 {name} 是远程机器但缺少 username 配置，跳过")
                continue
            remote_machines.append({
                'name': name,
                'host': machine.host,
                'port': machine.port,
                'username': machine.username
            })

    if not remote_machines:
        print("⚠️  配置中没有需要配置的远程服务器（所有机器都是 local）")
        return 0

    print(f"📋 发现 {len(remote_machines)} 台远程服务器:")
    for m in remote_machines:
        print(f"   - {m['name']}: {m['username']}@{m['host']}:{m['port']}")
    print()

    # 先检查是否所有服务器都已经可以免密登录
    print("🔍 检查当前免密登录状态...")
    already_configured = []
    need_configure = []

    for m in remote_machines:
        if check_ssh_connection(m['host'], m['username'], m['port'], config.runtime.ssh_timeout):
            already_configured.append(m['name'])
            print(f"   ✓ {m['name']}: 已支持免密登录")
        else:
            need_configure.append(m)
            print(f"   ✗ {m['name']}: 需要配置")

    print()

    if not need_configure:
        print("✅ 所有服务器都已经支持免密登录，无需配置!")
        return 0

    # 检查本地SSH密钥
    pubkey_path = get_default_ssh_pubkey()

    if pubkey_path:
        print(f"🔑 找到SSH公钥: {pubkey_path}")
    else:
        print("🔑 未找到SSH公钥，将生成新密钥...")

        # 生成新的SSH密钥
        key_type = "ed25519" if args.key_type == "ed25519" else "rsa"
        success, message = generate_ssh_key(key_type)

        if success:
            print(f"   {message}")
            pubkey_path = get_default_ssh_pubkey()
            if not pubkey_path:
                print(f"❌ 生成了密钥但找不到公钥文件")
                return 1
        else:
            print(f"❌ {message}")
            return 1

    # 显示公钥信息
    pubkey_content = read_pubkey(pubkey_path)
    if pubkey_content:
        print(f"   公钥: {pubkey_content[:50]}...")

    # 检查 ssh-copy-id 是否可用
    if has_ssh_copy_id():
        print(f"📦 ssh-copy-id 工具可用")
    else:
        print(f"⚠️  ssh-copy-id 工具不可用，将使用手动方式复制公钥")

    print()
    print(f"🔧 需要配置 {len(need_configure)} 台服务器:")
    for m in need_configure:
        print(f"   - {m['name']}")
    print()

    # 配置需要的服务器
    results = []
    for machine in need_configure:
        success, message = setup_passwordless_ssh(
            host=machine['host'],
            username=machine['username'],
            port=machine['port'],
            pubkey_path=pubkey_path,
            timeout=config.runtime.ssh_timeout
        )
        results.append((machine['name'], success, message))
        print(f"   {message}")

    # 汇总结果
    print("\n" + "="*50)
    print("📊 配置结果汇总:")
    print("="*50)

    # 显示已配置的服务器
    if already_configured:
        print(f"\n已有免密登录 ({len(already_configured)} 台):")
        for name in already_configured:
            print(f"   ✓ {name}: 无需配置")

    # 显示本次配置的服务器
    if results:
        print(f"\n本次配置 ({len(results)} 台):")
        success_count = sum(1 for _, success, _ in results if success)
        for name, success, message in results:
            status = "✓" if success else "✗"
            print(f"   {status} {name}: {message}")

    print()
    total_success = len(already_configured) + sum(1 for _, success, _ in results if success)
    total_count = len(remote_machines)

    if total_success == total_count:
        print(f"✅ 全部 {total_count} 台服务器可免密登录!")
        return 0
    else:
        print(f"⚠️  {total_success}/{total_count} 台服务器可免密登录")
        return 1