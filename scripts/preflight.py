"""Read-only runtime/dependency probe. Run with development OR Isaac Python."""
import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def command(argv):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=15)
        return {"returncode":r.returncode,"stdout":r.stdout.strip(),"stderr":r.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error":str(exc)}

def check():
    report = {"python":sys.executable,"version":platform.python_version(),
              "platform":platform.platform(),"modules":{},
              "gpu":command(["nvidia-smi","--query-gpu=name,memory.total,driver_version",
                             "--format=csv,noheader"]),
              "repositories":{}}
    for name in ("pxr","isaacsim","numpy","curobo","isaaclab"):
        report["modules"][name] = importlib.util.find_spec(name) is not None
    lock = ROOT/"dependencies.lock.json"
    if lock.exists():
        for item in json.loads(lock.read_text())["repositories"]:
            dest = (ROOT/item["relative_path"]).resolve()
            result = command(["git","-C",str(dest),"rev-parse","HEAD"])
            report["repositories"][item["name"]] = {
                "path":str(dest),"expected_commit":item["commit"],
                "actual_commit":result.get("stdout"),
                "matches_lock":result.get("stdout")==item["commit"]}
    report["isaac_python_env"] = os.environ.get("ISAAC_PYTHON")
    report["runtime_ready"] = report["modules"]["isaacsim"]
    report["next_gate"] = "run smoke_isaac.py using Isaac Python" if report["runtime_ready"] else (
        "Isaac runtime not found in this interpreter; set ISAAC_PYTHON to its python.sh")
    return report

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--report",type=Path,default=ROOT/"reports/preflight.json")
    p.add_argument("--require-isaac",action="store_true")
    args=p.parse_args()
    report=check()
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    raise SystemExit(2 if args.require_isaac and not report["runtime_ready"] else 0)
