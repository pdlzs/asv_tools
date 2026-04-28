#!/usr/bin/env python3
"""
ASV Benchmark Tools - CLI Entry Point

Usage:
    python main.py cmp <config_file> [options]
    python main.py cont <config_file> [options]
    python main.py ssh-setup <config_file> [options]
"""

import argparse
import re
import sys
import time


def parse_delay(delay_str: str) -> float:
    """
    Parse delay string like '10s', '30m', '6h' to seconds.

    Args:
        delay_str: Delay string with unit (s/m/h)

    Returns:
        Delay in seconds

    Raises:
        ValueError: If format is invalid
    """
    if not delay_str:
        return 0.0

    match = re.match(r'^(\d+)(s|m|h)$', delay_str.lower())
    if not match:
        raise ValueError(f"Invalid delay format '{delay_str}'. Use format like '10s', '30m', '6h'")

    value = int(match.group(1))
    unit = match.group(2)

    multipliers = {'s': 1, 'm': 60, 'h': 3600}
    return value * multipliers[unit]


def main():
    parser = argparse.ArgumentParser(
        prog='asv_tools',
        description='ASV Benchmark Tools'
    )
    parser.add_argument('-d', '--delay', metavar='TIME',
                       help='Delay before execution (e.g., 10s, 30m, 6h)')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # cmp 子命令
    cmp_parser = subparsers.add_parser('cmp', help='Compare ASV benchmark results across machines')
    cmp_parser.add_argument('config_file', help='Configuration file (YAML)')
    cmp_parser.add_argument('--skip-run', '-s', action='store_true',
                           help='Skip ASV run, use existing results')
    cmp_parser.add_argument('--dry-run', '-n', action='store_true',
                           help='Show commands without executing')
    cmp_parser.add_argument('--verbose', '-v', action='store_true',
                           help='Verbose output')
    cmp_parser.add_argument('--output-dir', '-o', help='Output directory')
    cmp_parser.add_argument('--info', '-i', help='Custom info for output filename')

    # cont 子命令
    cont_parser = subparsers.add_parser('cont', help='Compare two commits on single machine (asv continuous)')
    cont_parser.add_argument('config_file', help='Configuration file (YAML)')
    cont_parser.add_argument('--dry-run', '-n', action='store_true',
                            help='Show commands without executing')
    cont_parser.add_argument('--verbose', '-v', action='store_true',
                            help='Verbose output')

    # ssh-setup 子命令
    ssh_parser = subparsers.add_parser('ssh-setup', help='Setup SSH passwordless login')
    ssh_parser.add_argument('config_file', help='Configuration file (YAML)')
    ssh_parser.add_argument('--key-type', choices=['ed25519', 'rsa'], default='ed25519',
                           help='SSH key type to generate (default: ed25519)')

    # collect 子命令
    collect_parser = subparsers.add_parser('collect', help='Collect performance configuration from machines')
    collect_parser.add_argument('config_file', help='Configuration file (YAML)')
    collect_parser.add_argument('--dry-run', '-n', action='store_true',
                               help='Show commands without executing')
    collect_parser.add_argument('--verbose', '-v', action='store_true',
                               help='Verbose output')
    collect_parser.add_argument('--force', '-f', action='store_true',
                               help='Force execution, skip tool availability check')
    collect_parser.add_argument('--output-dir', '-o', help='Output directory')
    collect_parser.add_argument('--info', '-i', help='Custom info for output filename')

    args = parser.parse_args()

    # 处理延迟执行
    if args.delay:
        delay_seconds = parse_delay(args.delay)
        print(f"Waiting {args.delay} ({delay_seconds}s) before execution...")
        time.sleep(delay_seconds)

    if args.command == 'cmp':
        from cli.cmp_cmd import run_compare
        sys.exit(run_compare(args))
    elif args.command == 'cont':
        from cli.cont_cmd import run_continuous
        sys.exit(run_continuous(args))
    elif args.command == 'ssh-setup':
        from cli.ssh_setup_cmd import run_ssh_setup
        sys.exit(run_ssh_setup(args))
    elif args.command == 'collect':
        from cli.collect_cmd import run_collect
        sys.exit(run_collect(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()