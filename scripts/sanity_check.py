#!/usr/bin/env python3
"""Sanity-check competitor store refresh output before monthly maintenance.

The check is intentionally conservative: a cron should only publish/commit when
existing competitors return plausible store counts and no hard exceptions such
as zero stores or significant drops appear.
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "registry" / "source_registry.yaml"
CACHE_DIR = ROOT / "cache"
OUTPUT_CSV = ROOT / "output" / "dim_competitor_stores.csv"
REPORTS_DIR = ROOT / "reports"


@dataclass
class CheckResult:
    key: str
    label: str
    status: str
    count: int
    min_expected: int | None = None
    max_expected: int | None = None
    previous_count: int | None = None
    drop_pct: float | None = None
    missing_address_count: int = 0
    missing_geo_count: int | None = None
    messages: list[str] | None = None

    def severity_rank(self) -> int:
        return {"fail": 3, "warn": 2, "pass": 1}.get(self.status, 0)


def load_registry(path: Path = REGISTRY_PATH) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [e for e in raw.get("entries", []) if e.get("enabled", False)]


def prefix(entry: dict[str, Any]) -> str:
    return f"{entry['market_code']}{entry['competitor_initial']}"


def cache_path_for(key: str, month: str, cache_dir: Path = CACHE_DIR) -> Path:
    return cache_dir / f"{key}_{month}.json"


def load_cache_records(key: str, month: str, cache_dir: Path = CACHE_DIR) -> list[dict[str, Any]]:
    path = cache_path_for(key, month, cache_dir)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def previous_months_for(key: str, month: str, cache_dir: Path = CACHE_DIR) -> list[str]:
    months = []
    for path in cache_dir.glob(f"{key}_*.json"):
        m = path.stem.rsplit("_", 1)[-1]
        if m.isdigit() and len(m) == 6 and m < month:
            months.append(m)
    return sorted(months, reverse=True)


def load_output_geo_missing(key: str, csv_path: Path = OUTPUT_CSV) -> int | None:
    """Return missing lat/lon count for this key if output CSV exists."""
    if not csv_path.exists():
        return None
    missing = 0
    matched = 0
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_key = (row.get("market_code") or "") + (row.get("competitor_initial") or "")
            if row_key != key:
                continue
            matched += 1
            if not row.get("lat") or not row.get("lon"):
                missing += 1
    return missing if matched else None


def check_entry(
    entry: dict[str, Any],
    month: str,
    cache_dir: Path = CACHE_DIR,
    output_csv: Path = OUTPUT_CSV,
) -> CheckResult:
    key = prefix(entry)
    label = f"{entry['competitor_name']} {entry['market_code']}"
    records = load_cache_records(key, month, cache_dir)
    count = len(records)
    expected = entry.get("expected_store_count") or {}
    min_expected = expected.get("min")
    max_expected = expected.get("max")
    messages: list[str] = []
    status = "pass"

    if count == 0:
        status = "fail"
        messages.append("returned zero stores")
    if min_expected is not None and count < int(min_expected):
        status = "fail"
        messages.append(f"below minimum expected count ({count} < {min_expected})")
    if max_expected is not None and count > int(max_expected):
        status = "warn" if status != "fail" else status
        messages.append(f"above maximum expected count ({count} > {max_expected})")

    missing_address = sum(
        1 for r in records
        if not str(r.get("address") or "").strip()
    )
    if count and missing_address / count > 0.10:
        status = "fail"
        messages.append(f"too many missing addresses ({missing_address}/{count})")
    elif missing_address:
        status = "warn" if status != "fail" else status
        messages.append(f"some missing addresses ({missing_address}/{count})")

    previous_count = None
    drop_pct = None
    months = previous_months_for(key, month, cache_dir)
    if months:
        previous_records = load_cache_records(key, months[0], cache_dir)
        previous_count = len(previous_records)
        if previous_count > 0:
            drop_pct = max(0.0, (previous_count - count) / previous_count)
            threshold = float(entry.get("significant_drop_pct", 0.35))
            if drop_pct > threshold:
                status = "fail"
                messages.append(
                    f"significant drop vs {months[0]} ({previous_count} -> {count}, {drop_pct:.0%})"
                )

    missing_geo = load_output_geo_missing(key, output_csv)
    if missing_geo is not None and count and missing_geo / count > 0.25:
        status = "fail"
        messages.append(f"too many missing lat/lon values ({missing_geo}/{count})")

    if not messages:
        messages.append("ok")

    return CheckResult(
        key=key,
        label=label,
        status=status,
        count=count,
        min_expected=min_expected,
        max_expected=max_expected,
        previous_count=previous_count,
        drop_pct=drop_pct,
        missing_address_count=missing_address,
        missing_geo_count=missing_geo,
        messages=messages,
    )


def entry_matches_filter(entry: dict[str, Any], filter_term: str) -> bool:
    if not filter_term:
        return True
    term = filter_term.lower()
    return (
        term in prefix(entry).lower()
        or term in str(entry.get("competitor_name", "")).lower()
        or term in str(entry.get("market_code", "")).lower()
    )


def run_checks(
    month: str,
    registry_path: Path = REGISTRY_PATH,
    cache_dir: Path = CACHE_DIR,
    output_csv: Path = OUTPUT_CSV,
    filter_term: str = "",
) -> list[CheckResult]:
    entries = [
        e for e in load_registry(registry_path)
        if entry_matches_filter(e, filter_term)
    ]
    return [check_entry(e, month, cache_dir, output_csv) for e in entries]


def render_markdown(month: str, results: list[CheckResult]) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    overall = "PASS" if all(r.status != "fail" for r in results) else "FAIL"
    lines = [
        f"# Competitor store sanity report — {month}",
        "",
        f"Generated: `{generated_at}`",
        f"Overall: **{overall}**",
        "",
        "| Status | Key | Competitor / market | Count | Expected | Notes |",
        "|---|---:|---|---:|---:|---|",
    ]
    for r in sorted(results, key=lambda x: (-x.severity_rank(), x.key)):
        expected = ""
        if r.min_expected is not None or r.max_expected is not None:
            expected = f"{r.min_expected or ''}-{r.max_expected or ''}"
        notes = "; ".join(r.messages or [])
        lines.append(f"| {r.status.upper()} | `{r.key}` | {r.label} | {r.count} | {expected} | {notes} |")
    lines.extend([
        "",
        "## Rule",
        "",
        "Monthly maintenance may proceed only when there are no `FAIL` rows. Zero-store results, significant drops, too many missing addresses, or too many missing coordinates require human review or source fallback updates.",
    ])
    return "\n".join(lines) + "\n"


def write_reports(month: str, results: list[CheckResult], reports_dir: Path = REPORTS_DIR) -> tuple[Path, Path]:
    reports_dir.mkdir(exist_ok=True)
    md_path = reports_dir / f"{month}_sanity_report.md"
    json_path = reports_dir / f"{month}_sanity_report.json"
    md_path.write_text(render_markdown(month, results), encoding="utf-8")
    json_path.write_text(
        json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return md_path, json_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sanity-check competitor store refresh output")
    parser.add_argument("--month", required=True, help="Month to check in YYYYMM format")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--filter", default="", help="Only check registry entries matching this term")
    parser.add_argument("--write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = run_checks(args.month, args.registry, args.cache_dir, args.output_csv, args.filter)
    if args.write_report:
        md_path, json_path = write_reports(args.month, results, args.reports_dir)
        print(f"Wrote {md_path}")
        print(f"Wrote {json_path}")
    print(render_markdown(args.month, results))
    return 1 if any(r.status == "fail" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
