#!/usr/bin/env python3
"""Hackomon Pager entry point."""

import argparse
import sys
import traceback

def main(argv=None):
    parser = argparse.ArgumentParser(description="Hackomon — Pager Edition")
    parser.add_argument("--pagerctl-lib", help="explicit path to libpagerctl.so")
    parser.add_argument("--data-dir", help="override persistent data directory")
    parser.add_argument("--doctor", action="store_true", help="check installation without opening screen or scanning")
    args = parser.parse_args(argv)
    if args.doctor:
        from hackomon.doctor import main as diagnose
        return diagnose(args.pagerctl_lib)
    from hackomon.app import run_on_pager
    from hackomon.pager_backend import PagerDependencyError
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

