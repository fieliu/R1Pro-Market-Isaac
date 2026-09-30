"""Reproduce locked source checkouts without overwriting existing work."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def run(args,env):
    subprocess.run(args,check=True,env=env,timeout=600)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,default=ROOT.parent)
    args=parser.parse_args()
    env=dict(os.environ,GIT_LFS_SKIP_SMUDGE="1",GIT_TERMINAL_PROMPT="0")
    for item in json.loads((ROOT/"dependencies.lock.json").read_text())["repositories"]:
        dest=args.root.resolve()/item["name"]
        if dest.exists():
            actual=subprocess.check_output(["git","-C",str(dest),"rev-parse","HEAD"],text=True).strip()
            if actual!=item["commit"]:
                raise RuntimeError(f"{dest} differs from lock; refusing to overwrite existing checkout")
            print(f"OK {item['name']} {actual}")
            continue
        run(["git","init",str(dest)],env)
        run(["git","-C",str(dest),"remote","add","origin",item["url"]],env)
        run(["git","-C",str(dest),"fetch","--depth","1","origin",item["commit"]],env)
        run(["git","-C",str(dest),"-c","filter.lfs.smudge=",
             "-c","filter.lfs.required=false","checkout","--detach","FETCH_HEAD"],env)

if __name__=="__main__":
    main()
