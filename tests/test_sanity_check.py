from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def load_sanity_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "sanity_check.py"
    spec = importlib.util.spec_from_file_location("sanity_check", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_registry(path: Path) -> None:
    path.write_text(
        """
entries:
  - market_code: HK
    competitor_name: Test Brand
    competitor_initial: T
    enabled: true
    expected_store_count:
      min: 2
      max: 10
    significant_drop_pct: 0.25
    source_priority:
      - type: official
        url: https://example.com/stores
        status: active
        confidence: high
""".strip(),
        encoding="utf-8",
    )


def write_cache(cache_dir: Path, key: str, month: str, count: int) -> None:
    cache_dir.mkdir()
    rows = [
        {"shop_name": f"Store {i}", "address": f"Address {i}"}
        for i in range(count)
    ]
    (cache_dir / f"{key}_{month}.json").write_text(json.dumps(rows), encoding="utf-8")


def test_zero_store_result_fails(tmp_path: Path) -> None:
    sanity = load_sanity_module()
    registry = tmp_path / "registry.yaml"
    cache = tmp_path / "cache"
    cache.mkdir()
    write_registry(registry)
    (cache / "HKT_202607.json").write_text("[]", encoding="utf-8")

    results = sanity.run_checks("202607", registry, cache, tmp_path / "missing.csv")

    assert len(results) == 1
    assert results[0].status == "fail"
    assert "returned zero stores" in "; ".join(results[0].messages)


def test_plausible_result_passes(tmp_path: Path) -> None:
    sanity = load_sanity_module()
    registry = tmp_path / "registry.yaml"
    cache = tmp_path / "cache"
    write_registry(registry)
    write_cache(cache, "HKT", "202607", 3)

    results = sanity.run_checks("202607", registry, cache, tmp_path / "missing.csv")

    assert results[0].status == "pass"
    assert results[0].count == 3


def test_significant_drop_fails(tmp_path: Path) -> None:
    sanity = load_sanity_module()
    registry = tmp_path / "registry.yaml"
    cache = tmp_path / "cache"
    write_registry(registry)
    write_cache(cache, "HKT", "202606", 8)
    rows = [{"shop_name": "Only Store", "address": "Address"}]
    (cache / "HKT_202607.json").write_text(json.dumps(rows), encoding="utf-8")

    results = sanity.run_checks("202607", registry, cache, tmp_path / "missing.csv")

    assert results[0].status == "fail"
    assert "significant drop" in "; ".join(results[0].messages)
