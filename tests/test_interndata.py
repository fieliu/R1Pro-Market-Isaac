import copy
import json
from pathlib import Path

import pytest

from r1pro_market.interndata import (
    AdapterValidationError,
    build_interndata_robot_config,
    load_manifest,
    resolve_joint_indices,
    unresolved_calibrations,
    validate_against_urdf,
    validate_usd_paths,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "configs/interndata/r1pro_manifest.json"


def test_manifest_matches_official_urdf_and_composed_usd():
    manifest = load_manifest(MANIFEST_PATH)
    urdf = (ROOT / manifest["asset"]["official_urdf"]).resolve()
    usd = (ROOT / manifest["asset"]["project_usd"]).resolve()
    assert validate_against_urdf(manifest, urdf) == []
    assert validate_usd_paths(manifest, usd) == []


def test_joint_indices_are_resolved_by_name_not_position_assumptions():
    manifest = load_manifest(MANIFEST_PATH)
    expected = (
        manifest["arms"]["right"]["gripper_joint_names"]
        + ["uncontrolled_joint"]
        + manifest["arms"]["left"]["joint_names"]
        + manifest["arms"]["right"]["joint_names"]
        + manifest["arms"]["left"]["gripper_joint_names"]
    )
    resolution = resolve_joint_indices(expected, manifest)
    assert resolution.left_arm == tuple(range(3, 10))
    assert resolution.right_arm == tuple(range(10, 17))
    assert resolution.left_gripper == (17, 18)
    assert resolution.right_gripper == (0, 1)


def test_missing_or_duplicate_dof_names_are_rejected():
    manifest = load_manifest(MANIFEST_PATH)
    with pytest.raises(AdapterValidationError, match="missing"):
        resolve_joint_indices(manifest["arms"]["left"]["joint_names"], manifest)
    all_names = []
    for side in ("left", "right"):
        all_names += manifest["arms"][side]["joint_names"]
        all_names += manifest["arms"][side]["gripper_joint_names"]
    with pytest.raises(AdapterValidationError, match="Duplicate"):
        resolve_joint_indices(all_names + [all_names[0]], manifest)


def test_config_generation_refuses_unknown_calibration():
    manifest = load_manifest(MANIFEST_PATH)
    assert "tcp_offset_m" in unresolved_calibrations(manifest)
    names = []
    for side in ("left", "right"):
        names += manifest["arms"][side]["joint_names"]
        names += manifest["arms"][side]["gripper_joint_names"]
    resolution = resolve_joint_indices(names, manifest)
    with pytest.raises(AdapterValidationError, match="Calibration is incomplete"):
        build_interndata_robot_config(manifest, resolution, asset_path="r1pro_with_basket.usda")


def test_locked_engine_repositories_are_recorded():
    lock = json.loads((ROOT / "dependencies.lock.json").read_text(encoding="utf-8"))
    commits = {item["name"]: item["commit"] for item in lock["repositories"]}
    assert commits["InternDataEngine"] == "2a0a21f2c836df97c925729084e13d68950b4deb"
    assert commits["GenManip"] == "1958e3781e4fb1921d1834b658b295e3660899ab"
    assert commits["InternUtopia"] == "b0a9520c586317c2743023c153cbf7c4f04f4732"


def test_manifest_rejects_invented_gripper_targets():
    manifest = copy.deepcopy(load_manifest(MANIFEST_PATH))
    manifest["gripper"]["open_joint_targets_m"] = [0.04, 0.04]
    names = []
    for side in ("left", "right"):
        names += manifest["arms"][side]["joint_names"]
        names += manifest["arms"][side]["gripper_joint_names"]
    with pytest.raises(AdapterValidationError, match="official URDF"):
        resolve_joint_indices(names, manifest)
