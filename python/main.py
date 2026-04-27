#!/usr/bin/env python3
"""
ASV Benchmark Tools - CLI Entry Point

Usage:
    python main.py cmp <config_file> [options]
    python main.py cont <config_file> [options]
    python main.py ssh-setup <config_file> [options]
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog='asv_tools',
        description='ASV Benchmark Tools'
    )
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

    args = parser.parse_args()

    if args.command == 'cmp':
        from cli.cmp_cmd import run_compare
        sys.exit(run_compare(args))
    elif args.command == 'cont':
        from cli.cont_cmd import run_continuous
        sys.exit(run_continuous(args))
    elif args.command == 'ssh-setup':
        from cli.ssh_setup_cmd import run_ssh_setup
        sys.exit(run_ssh_setup(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()