"""Generate basket + robot assembly; does not claim physics/reachability validation."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from r1pro_market.basket import BasketConfig, build_basket, assemble_robot

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT/"configs/basket.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT/"assets/generated")
    parser.add_argument("--robot-usd", type=Path)
    args = parser.parse_args()
    cfg = BasketConfig.load(args.config)
    robot_config = json.loads((ROOT/"configs/robot.json").read_text())
    source = args.robot_usd or (ROOT/robot_config["source_usd"]).resolve()
    if not source.is_file():
        parser.error(f"Robot USD not found: {source}")
    for name in ("basket.usda", "r1pro_with_basket.usda"):
        if (args.output_dir/name).exists():
            parser.error(f"Output exists: {args.output_dir/name}; use a new --output-dir")
    build_basket(args.output_dir/"basket.usda", cfg)
    assemble_robot(source, args.output_dir/"r1pro_with_basket.usda", cfg)
    print(json.dumps({"basket":str(args.output_dir/"basket.usda"),
                      "assembly":str(args.output_dir/"r1pro_with_basket.usda"),
                      "physics_validation":"pending", "reachability_validation":"pending"}, indent=2))

if __name__ == "__main__":
    main()
