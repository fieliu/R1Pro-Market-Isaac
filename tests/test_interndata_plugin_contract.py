import runpy
import sys
import types
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _module(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def test_runtime_plugin_paths_and_signed_gripper_mapping(monkeypatch):
    created = []

    def register(cls):
        return cls

    class FakeRobot:
        def __init__(self, prim_path, name, *args, **kwargs):
            self.prim_path = prim_path
            self.name = name

        def set_solver_position_iteration_count(self, value):
            self.position_iterations = value

        def set_stabilization_threshold(self, value):
            self.stabilization_threshold = value

        def set_solver_velocity_iteration_count(self, value):
            self.velocity_iterations = value

        def set_local_pose(self, translation=None, orientation=None):
            self.robot_pose = (translation, orientation)

        def get_local_pose(self):
            return ("robot-position", "robot-orientation")

        def set_local_scale(self, scale):
            self.robot_scale = scale

    class FakeTemplateRobot(FakeRobot):
        def _setup_joint_indices(self):
            pass

        def _setup_paths(self):
            self.fl_base_path = "/left-base"
            self.fr_base_path = "/right-base"

        def _setup_gripper_keypoints(self):
            pass

        def _setup_collision_paths(self):
            pass

        def _load_extra_depth(self, path):
            self.extra_depth_source = path

    class FakeTemplateController:
        pass

    class FakeXFormPrim:
        def __init__(self, prim_path):
            self.prim_path = prim_path

        def set_local_pose(self, translation=None, orientation=None):
            self.pose = (translation, orientation)

        def get_local_pose(self):
            return getattr(self, "pose", ("assembly-position", "assembly-orientation"))

        def set_local_scale(self, scale):
            self.scale = scale

    def create_prim(*, usd_path, prim_path):
        created.append((usd_path, prim_path))

    stubs = {
        "core": _module("core"),
        "core.controllers": _module("core.controllers"),
        "core.controllers.base_controller": _module(
            "core.controllers.base_controller", register_controller=register
        ),
        "core.controllers.template_controller": _module(
            "core.controllers.template_controller", TemplateController=FakeTemplateController
        ),
        "core.robots": _module("core.robots"),
        "core.robots.base_robot": _module("core.robots.base_robot", register_robot=register),
        "core.robots.template_robot": _module(
            "core.robots.template_robot", TemplateRobot=FakeTemplateRobot
        ),
        "omni": _module("omni"),
        "omni.isaac": _module("omni.isaac"),
        "omni.isaac.core": _module("omni.isaac.core"),
        "omni.isaac.core.prims": _module("omni.isaac.core.prims", XFormPrim=FakeXFormPrim),
        "omni.isaac.core.robots": _module("omni.isaac.core.robots"),
        "omni.isaac.core.robots.robot": _module("omni.isaac.core.robots.robot", Robot=FakeRobot),
        "omni.isaac.core.utils": _module("omni.isaac.core.utils"),
        "omni.isaac.core.utils.prims": _module(
            "omni.isaac.core.utils.prims", create_prim=create_prim
        ),
    }
    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)

    symbols = runpy.run_path(str(ROOT / "src/r1pro_market/interndata_plugin.py"))
    robot_class = symbols["R1ProMarket"]
    cfg = {
        "path": "r1pro_with_basket.usda",
        "name": "r1pro",
        "articulation_relative_path": "R1Pro/r1_pro_with_gripper/base_link",
        "gripper_max_width": 0.1,
        "gripper_min_width": 0.0,
        "solver_position_iteration_count": 128,
        "stabilization_threshold": 0.005,
        "solver_velocity_iteration_count": 4,
    }
    robot = robot_class("/assets", "/World/env", cfg)
    assert created == [("/assets/r1pro_with_basket.usda", "/World/env/r1pro")]
    assert robot.prim_path == "/World/env/r1pro/R1Pro/r1_pro_with_gripper/base_link"
    robot.set_local_pose([1, 2, 3], [1, 0, 0, 0])
    assert robot._assembly_xform.pose == ([1, 2, 3], [1, 0, 0, 0])

    controller_class = symbols["R1ProMarketController"]
    controller = controller_class()
    controller.name = "r1pro"
    controller.robot = types.SimpleNamespace(
        cfg={
            "left_joint_indices": list(range(7)),
            "left_gripper_indices": [14, 15],
            "right_joint_indices": list(range(7, 14)),
            "right_gripper_indices": [16, 17],
        },
        left_gripper_state=1.0,
        right_gripper_state=-1.0,
    )
    controller.task = types.SimpleNamespace(
        robots={"r1pro": types.SimpleNamespace(fl_base_path="/left", fr_base_path="/right")}
    )
    controller._configure_joint_indices("/configs/r1pro_left.yml")
    assert controller.raw_js_names == [f"left_arm_joint{i}" for i in range(1, 8)]
    assert controller.reference_prim_path == "/left"
    np.testing.assert_allclose(controller.get_gripper_action(), [0.05, -0.05])
    controller._gripper_state = -1.0
    np.testing.assert_allclose(controller.get_gripper_action(), [0.0, 0.0])
