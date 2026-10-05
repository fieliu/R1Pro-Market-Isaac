"""CPU-only validation helpers for the InternDataEngine R1 Pro adapter."""

from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


class AdapterValidationError(ValueError):
    """The adapter contract is incomplete or inconsistent."""


@dataclass(frozen=True)
class JointResolution:
    left_arm: tuple[int, ...]
    right_arm: tuple[int, ...]
    left_gripper: tuple[int, ...]
    right_gripper: tuple[int, ...]

    def as_dict(self) -> dict[str, list[int]]:
        return {
            "left_joint_indices": list(self.left_arm),
            "right_joint_indices": list(self.right_arm),
            "left_gripper_indices": list(self.left_gripper),
            "right_gripper_indices": list(self.right_gripper),
        }


def load_manifest(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != 1:
        raise AdapterValidationError("Unsupported adapter manifest schema")
    for key in ("target_class", "asset", "arms", "gripper", "calibration"):
        if key not in manifest:
            raise AdapterValidationError(f"Missing manifest key: {key}")
    all_names: list[str] = []
    for side in ("left", "right"):
        arm = manifest["arms"].get(side)
        if not arm:
            raise AdapterValidationError(f"Missing {side} arm definition")
        if len(arm.get("joint_names", [])) != 7:
            raise AdapterValidationError(f"{side} arm must contain seven joints")
        if len(arm.get("gripper_joint_names", [])) != 2:
            raise AdapterValidationError(f"{side} gripper must contain two joints")
        all_names += arm["joint_names"] + arm["gripper_joint_names"]
        for key in ("base_link", "ee_link", "camera_link"):
            if not arm.get(key):
                raise AdapterValidationError(f"Missing {side} arm path: {key}")
    if len(all_names) != len(set(all_names)):
        raise AdapterValidationError("Joint names must be unique across both arms")
    if manifest["gripper"].get("open_joint_targets_m") != [0.05, -0.05]:
        raise AdapterValidationError("Open gripper targets differ from the official URDF")
    if manifest["gripper"].get("closed_joint_targets_m") != [0.0, 0.0]:
        raise AdapterValidationError("Closed gripper targets differ from the official URDF")


def resolve_joint_indices(dof_names: Iterable[str], manifest: Mapping[str, Any]) -> JointResolution:
    """Resolve Isaac-reported names; numeric indices must never be guessed."""
    validate_manifest(manifest)
    names = list(dof_names)
    seen: set[str] = set()
    duplicates: set[str] = set()
    for name in names:
        if name in seen:
            duplicates.add(name)
        seen.add(name)
    if duplicates:
        raise AdapterValidationError(f"Duplicate articulation DOF names: {sorted(duplicates)}")
    index = {name: i for i, name in enumerate(names)}

    def one(side: str, key: str) -> tuple[int, ...]:
        expected = manifest["arms"][side][key]
        missing = [name for name in expected if name not in index]
        if missing:
            raise AdapterValidationError(f"Isaac articulation is missing {side} {key}: {missing}")
        return tuple(index[name] for name in expected)

    return JointResolution(
        one("left", "joint_names"),
        one("right", "joint_names"),
        one("left", "gripper_joint_names"),
        one("right", "gripper_joint_names"),
    )


def read_urdf_joints(path: str | Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for joint in ET.parse(path).getroot().findall("joint"):
        limit = joint.find("limit")
        result[joint.attrib["name"]] = {
            "type": joint.get("type"),
            "lower": float(limit.get("lower")) if limit is not None and limit.get("lower") else None,
            "upper": float(limit.get("upper")) if limit is not None and limit.get("upper") else None,
        }
    return result


def validate_against_urdf(manifest: Mapping[str, Any], urdf_path: str | Path) -> list[str]:
    validate_manifest(manifest)
    joints = read_urdf_joints(urdf_path)
    issues: list[str] = []
    for side in ("left", "right"):
        arm = manifest["arms"][side]
        for name in arm["joint_names"]:
            if name not in joints or joints[name]["type"] != "revolute":
                issues.append(f"URDF missing revolute arm joint {name}")
        for name, limits in zip(arm["gripper_joint_names"], ((0.0, 0.05), (-0.05, 0.0))):
            info = joints.get(name)
            if info is None or info["type"] != "prismatic" or (info["lower"], info["upper"]) != limits:
                issues.append(f"URDF gripper joint {name} has unexpected type or limits")
    return issues


def validate_usd_paths(manifest: Mapping[str, Any], usd_path: str | Path) -> list[str]:
    try:
        from pxr import Usd  # type: ignore
    except ImportError:
        return ["usd-core is unavailable; USD path validation was skipped"]
    stage = Usd.Stage.Open(str(usd_path))
    if stage is None:
        return [f"Could not open USD: {usd_path}"]
    default = stage.GetDefaultPrim()
    paths = [manifest["asset"]["articulation_relative_path"]]
    for side in ("left", "right"):
        arm = manifest["arms"][side]
        paths += [arm["base_link"], arm["ee_link"], arm["camera_link"]]
    return [
        f"USD missing prim relative to default prim: {path}"
        for path in paths
        if not stage.GetPrimAtPath(default.GetPath().AppendPath(path)).IsValid()
    ]


def unresolved_calibrations(manifest: Mapping[str, Any]) -> list[str]:
    return sorted(key for key, value in manifest["calibration"].items() if value is None)


def build_interndata_robot_config(
    manifest: Mapping[str, Any], resolution: JointResolution, *, asset_path: str
) -> dict[str, Any]:
    """Build engine YAML data only after grasp/collision calibration exists."""
    missing = unresolved_calibrations(manifest)
    if missing:
        raise AdapterValidationError("Calibration is incomplete: " + ", ".join(missing))
    c = manifest["calibration"]
    left, right = manifest["arms"]["left"], manifest["arms"]["right"]
    return {
        "target_class": manifest["target_class"],
        "path": asset_path,
        "robot_file": [c["left_curobo_config"], c["right_curobo_config"]],
        "gripper_max_width": manifest["gripper"]["max_width_m"],
        "gripper_min_width": manifest["gripper"]["min_width_m"],
        "tcp_offset": c["tcp_offset_m"],
        "solver_position_iteration_count": 128,
        "solver_velocity_iteration_count": 4,
        "stabilization_threshold": 0.005,
        "articulation_relative_path": manifest["asset"]["articulation_relative_path"],
        **resolution.as_dict(),
        "fl_ee_path": left["ee_link"],
        "fr_ee_path": right["ee_link"],
        "fl_base_path": left["base_link"],
        "fr_base_path": right["base_link"],
        "fl_gripper_keypoints": c["left_gripper_keypoints"],
        "fr_gripper_keypoints": c["right_gripper_keypoints"],
        "fl_filter_paths": c["left_filter_paths"],
        "fr_filter_paths": c["right_filter_paths"],
        "fl_forbid_collision_paths": c["left_forbid_collision_paths"],
        "fr_forbid_collision_paths": c["right_forbid_collision_paths"],
        "R_ee_graspnet": c["R_ee_graspnet"],
        "ee_axis": c["ee_axis"],
        "left_joint_home": c["left_joint_home"],
        "right_joint_home": c["right_joint_home"],
        "left_joint_home_std": [0.0] * 7,
        "right_joint_home_std": [0.0] * 7,
        "left_gripper_home": manifest["gripper"]["open_joint_targets_m"],
        "right_gripper_home": manifest["gripper"]["open_joint_targets_m"],
    }


def git_head(path: str | Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
