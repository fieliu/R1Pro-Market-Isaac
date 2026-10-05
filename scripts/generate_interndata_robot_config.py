#!/usr/bin/env python3
"""Generate JSON-as-YAML robot config from a successful Isaac report."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r1pro_market.interndata import (  # noqa: E402
    AdapterValidationError,
    build_interndata_robot_config,
    load_manifest,
    resolve_joint_indices,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "configs/interndata/r1pro_manifest.json")
    parser.add_argument("--runtime-report", type=Path, default=ROOT / "reports/isaac_smoke.json")
    parser.add_argument("--output", type=Path, default=ROOT / "generated/interndata/r1pro_robot.yaml")
    parser.add_argument("--asset-path", default="r1pro_with_basket.usda")
    args = parser.parse_args()
    runtime = json.loads(args.runtime_report.read_text(encoding="utf-8"))
    if not runtime.get("physics_simulated") or not runtime.get("dof_names"):
        parser.error("a successful Isaac report with dof_names is required")
    manifest = load_manifest(args.manifest)
    resolution = resolve_joint_indices(runtime["dof_names"], manifest)
    try:
        config = build_interndata_robot_config(manifest, resolution, asset_path=args.asset_path)
    except AdapterValidationError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
