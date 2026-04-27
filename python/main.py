#!/usr/bin/env python3
"""
ASV Benchmark Tools - CLI Entry Point

Usage:
    python main.py cmp <config_file> [options]
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
    cmp_parser = subparsers.add_parser('cmp', help='Compare ASV benchmark results')
    cmp_parser.add_argument('config_file', help='Configuration file (YAML)')
    cmp_parser.add_argument('--skip-run', '-s', action='store_true',
                           help='Skip ASV run, use existing results')
    cmp_parser.add_argument('--dry-run', '-n', action='store_true',
                           help='Show commands without executing')
    cmp_parser.add_argument('--verbose', '-v', action='store_true',
                           help='Verbose output')
    cmp_parser.add_argument('--output-dir', '-o', help='Output directory')
    cmp_parser.add_argument('--info', '-i', help='Custom info for output filename')

    args = parser.parse_args()

    if args.command == 'cmp':
        from cli.cmp_cmd import run_compare
        sys.exit(run_compare(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()