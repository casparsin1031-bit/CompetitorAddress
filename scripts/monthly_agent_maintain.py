#!/usr/bin/env python3
"""Monthly agent-maintenance entrypoint for CompetitorAddress.

Runs the scraper pipeline, writes a sanity report, and exits non-zero when the
result should NOT be automatically maintained. This is the command Hermes cron
or GitHub Actions should call before publishing/committing refreshed data.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> int:
    print("$", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, text=True)
    return proc.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run monthly competitor-store maintenance")
    parser.add_argument("--force", action="store_true", help="Force re-scrape, ignoring cache")
    parser.add_argument("--filter", default="", help="Pipeline filter, e.g. HKM or Sushiro")
    parser.add_argument("--no-enrich", action="store_true", help="Skip geocoding enrichment")
    parser.add_argument("--month", default="", help="Month to check in YYYYMM; defaults to current UTC month")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    month = args.month or datetime.now(timezone.utc).strftime("%Y%m")

    pipeline_cmd = [sys.executable, "pipeline.py"]
    if args.force:
        pipeline_cmd.append("--force")
    if args.filter:
        pipeline_cmd.extend(["--filter", args.filter])
    if args.no_enrich:
        pipeline_cmd.append("--no-enrich")

    pipeline_rc = run(pipeline_cmd)
    if pipeline_rc != 0:
        print(f"Pipeline failed with exit code {pipeline_rc}; not maintaining output.")
        return pipeline_rc

    sanity_cmd = [
        sys.executable,
        "scripts/sanity_check.py",
        "--month",
        month,
        "--write-report",
    ]
    if args.filter:
        sanity_cmd.extend(["--filter", args.filter])
    if args.no_enrich:
        sanity_cmd.append("--skip-geo-check")
    sanity_rc = run(sanity_cmd)
    if sanity_rc != 0:
        print("Sanity check failed; monthly maintenance requires human review.")
        return sanity_rc

    print("Sanity check passed; monthly maintenance output is eligible for publish/commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
