"""Inspect composed USD references and physical topology, without simulating."""
import argparse
import json
from pathlib import Path
from pxr import Usd, UsdGeom, UsdPhysics

def inspect(path):
    stage = Usd.Stage.Open(str(path))
    if stage is None:
        raise ValueError(f"Cannot open USD: {path}")
    bodies, joints, roots = [], [], []
    errors = [str(e) for e in stage.GetCompositionErrors()]
    for p in stage.Traverse():
        if p.HasAPI(UsdPhysics.RigidBodyAPI):
            bodies.append(str(p.GetPath()))
        if p.HasAPI(UsdPhysics.ArticulationRootAPI):
            roots.append(str(p.GetPath()))
        if p.IsA(UsdPhysics.Joint):
            j = UsdPhysics.Joint(p)
            targets = list(j.GetBody0Rel().GetTargets()) + list(j.GetBody1Rel().GetTargets())
            for target in targets:
                t = stage.GetPrimAtPath(target)
                if not t or not t.HasAPI(UsdPhysics.RigidBodyAPI):
                    errors.append(f"Invalid joint body {target} in {p.GetPath()}")
            joints.append({"path":str(p.GetPath()), "type":p.GetTypeName(),
                           "targets":list(map(str, targets))})
    return {"file":str(Path(path).resolve()), "meters_per_unit":UsdGeom.GetStageMetersPerUnit(stage),
            "bodies":bodies, "joints":joints, "articulation_roots":roots,
            "errors":errors, "structural_check_passed":not errors,
            "physics_simulated":False}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("asset", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = inspect(args.asset)
    data = json.dumps(report, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(data)
    print(data)
    raise SystemExit(0 if report["structural_check_passed"] else 1)
