#!/usr/bin/env python3
"""Register the external R1 Pro plugin, then run InternDataEngine."""

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-root", type=Path, default=Path("../InternDataEngine"))
    parser.add_argument("--config", required=True)
    args, extras = parser.parse_known_args()
    project_root = Path(__file__).resolve().parents[1]
    engine_root = args.engine_root.resolve()
    config_path = Path(args.config).resolve()
    if not (engine_root / "launcher.py").is_file():
        parser.error(f"InternDataEngine launcher not found: {engine_root / 'launcher.py'}")
    if not config_path.is_file():
        parser.error(f"Workflow config not found: {config_path}")

    os.chdir(engine_root)
    sys.path.insert(0, str(project_root / "src"))
    sys.path.insert(0, str(engine_root))
    sys.argv = ["launcher.py", "--config", str(config_path), *extras]
    import launcher  # type: ignore  # pylint: disable=import-outside-toplevel
    import r1pro_market.interndata_plugin  # noqa: F401  # pylint: disable=import-outside-toplevel
    from core.controllers import get_controller_dict  # type: ignore
    from core.robots.base_robot import ROBOT_DICT  # type: ignore

    if "R1ProMarket" not in ROBOT_DICT or "R1ProMarket" not in get_controller_dict():
        raise RuntimeError("R1 Pro InternDataEngine plugin registration failed")
    result = launcher.main()
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
