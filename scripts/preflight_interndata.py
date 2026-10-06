#!/usr/bin/env python3
"""Static readiness check; runs without Isaac Sim or a GPU."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r1pro_market.interndata import (  # noqa: E402
    git_head,
    load_manifest,
    resolve_joint_indices,
    unresolved_calibrations,
    validate_against_urdf,
    validate_usd_paths,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "configs/interndata/r1pro_manifest.json")
    parser.add_argument("--runtime-report", type=Path, default=ROOT / "reports/isaac_smoke.json")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/interndata_preflight.json")
    parser.add_argument("--require-runtime", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    usd_path = (ROOT / manifest["asset"]["project_usd"]).resolve()
    urdf_path = (ROOT / manifest["asset"]["official_urdf"]).resolve()
    errors: list[str] = []
    if not usd_path.is_file():
        errors.append(f"Missing composed robot USD: {usd_path}")
    if not urdf_path.is_file():
        errors.append(f"Missing official robot URDF: {urdf_path}")
    if urdf_path.is_file():
        errors += validate_against_urdf(manifest, urdf_path)
    if usd_path.is_file():
        errors += validate_usd_paths(manifest, usd_path)

    lock = json.loads((ROOT / "dependencies.lock.json").read_text(encoding="utf-8"))
    dependencies = []
    warnings: list[str] = []
    for repo in lock["repositories"]:
        path = (ROOT / repo["relative_path"]).resolve()
        actual = git_head(path)
        required = bool(repo.get("required_for_interndata", False))
        dependencies.append({
            "name": repo["name"],
            "path": str(path),
            "expected": repo["commit"],
            "actual": actual,
            "ok": actual == repo["commit"],
            "required": required,
        })
        if actual != repo["commit"]:
            message = f"{repo['name']} checkout differs from dependencies.lock.json"
            if required:
                errors.append(message)
            else:
                warnings.append(message)

    runtime = {"physics_simulated": False, "joint_indices": None}
    if args.runtime_report.is_file():
        runtime.update(json.loads(args.runtime_report.read_text(encoding="utf-8")))
        if "dof_names" not in runtime and runtime.get("joint_names"):
            runtime["dof_names"] = runtime["joint_names"]
        if runtime.get("physics_simulated") and runtime.get("dof_names"):
            runtime["joint_indices"] = resolve_joint_indices(runtime["dof_names"], manifest).as_dict()
    blockers = [f"calibration:{key}" for key in unresolved_calibrations(manifest)]
    if not runtime.get("physics_simulated"):
        blockers.append("Isaac physics smoke has not passed")
    if runtime.get("joint_indices") is None:
        blockers.append("Isaac articulation DOF order has not been captured")

    report = {
        "status": "error" if errors else ("ready" if not blockers else "blocked"),
        "errors": errors,
        "warnings": warnings,
        "blockers": blockers,
        "dependencies": dependencies,
        "runtime": runtime,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if errors:
        return 1
    return 2 if args.require_runtime and blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
