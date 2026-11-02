#!/usr/bin/env python3
"""Hackomon Pager entry point."""

import argparse
import sys
import traceback

from hackomon.app import run_on_pager
from hackomon.pager_backend import PagerDependencyError


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hackomon — Pager Edition")
    parser.add_argument("--pagerctl-lib", help="explicit path to libpagerctl.so")
    parser.add_argument("--data-dir", help="override persistent data directory")
    args = parser.parse_args(argv)
    try:
        run_on_pager(args.pagerctl_lib, args.data_dir)
        return 0
    except PagerDependencyError as error:
        print("DEPENDENCY ERROR: %s" % error, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

