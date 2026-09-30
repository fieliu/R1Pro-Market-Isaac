"""Generate candidate metadata, not trajectories or training samples."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from r1pro_market.tasks import generate_candidates,validate_split

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--scene",type=Path,default=ROOT/"configs/example_scene.json")
    p.add_argument("--count",type=int,default=10)
    p.add_argument("--seed",type=int,default=42)
    p.add_argument("--output",type=Path,default=ROOT/"datasets/candidates/example.jsonl")
    args=p.parse_args()
    scene=json.loads(args.scene.read_text())
    validate_split([scene])
    tasks=list(generate_candidates(scene,args.count,args.seed))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x") as f:
        for task in tasks:
            f.write(json.dumps(task,ensure_ascii=False)+"\n")
    print(f"Saved {len(tasks)} UNVALIDATED CANDIDATES to {args.output}; no trajectories collected")
