"""Runtime plugin registered by scripts/run_interndata.py inside Isaac Python.

Do not import this module in the CPU asset environment: it intentionally
depends on Isaac Sim, cuRobo, and InternDataEngine.
"""

import os

import numpy as np
from core.controllers.base_controller import register_controller
from core.controllers.template_controller import TemplateController
from core.robots.base_robot import register_robot
from core.robots.template_robot import TemplateRobot
from omni.isaac.core.prims import XFormPrim
from omni.isaac.core.robots.robot import Robot
from omni.isaac.core.utils.prims import create_prim


@register_robot
class R1ProMarket(TemplateRobot):
    """R1 Pro whose articulation root is nested inside the composed USD."""

    def __init__(self, asset_root: str, root_prim_path: str, cfg: dict, *args, **kwargs):
        self.asset_root = asset_root
        self.cfg = cfg
        usd_path = os.path.join(asset_root, cfg["path"])
        container_path = f"{root_prim_path}/{cfg['name']}"
        create_prim(usd_path=usd_path, prim_path=container_path)
        articulation_path = f"{container_path}/{cfg['articulation_relative_path']}"
        Robot.__init__(self, articulation_path, cfg["name"], *args, **kwargs)
        self._assembly_xform = XFormPrim(prim_path=container_path)
        self.robot_prim_path = container_path
        self.gripper_max_width = cfg["gripper_max_width"]
        self.gripper_min_width = cfg["gripper_min_width"]
        self.set_solver_position_iteration_count(cfg["solver_position_iteration_count"])
        self.set_stabilization_threshold(cfg["stabilization_threshold"])
        self.set_solver_velocity_iteration_count(cfg["solver_velocity_iteration_count"])
        self._setup_joint_indices()
        self._setup_paths()
        self._setup_gripper_keypoints()
        self._setup_collision_paths()
        self._load_extra_depth(usd_path)

    def _get_gripper_state(self, gripper_home):
        return 1.0 if len(gripper_home) == 2 and gripper_home[0] > 0 and gripper_home[1] < 0 else -1.0

    def set_local_pose(self, translation=None, orientation=None):
        if hasattr(self, "_assembly_xform"):
            return self._assembly_xform.set_local_pose(translation=translation, orientation=orientation)
        return super().set_local_pose(translation=translation, orientation=orientation)

    def get_local_pose(self):
        if hasattr(self, "_assembly_xform"):
            return self._assembly_xform.get_local_pose()
        return super().get_local_pose()

    def set_local_scale(self, scale):
        if hasattr(self, "_assembly_xform"):
            return self._assembly_xform.set_local_scale(scale)
        return super().set_local_scale(scale)


@register_controller
class R1ProMarketController(TemplateController):
    """Map separate signed R1 Pro finger joints to one logical open/close state."""

    def _get_default_ignore_substring(self):
        return ["material", "Plane", "scene", "table"]

    def _configure_joint_indices(self, robot_file: str) -> None:
        basename = os.path.basename(robot_file).lower()
        if "left" in basename:
            side = "left"
        elif "right" in basename:
            side = "right"
        else:
            raise ValueError("R1 Pro cuRobo config filename must include 'left' or 'right'")
        self.raw_js_names = [f"{side}_arm_joint{i}" for i in range(1, 8)]
        self.cmd_js_names = list(self.raw_js_names)
        self.arm_indices = np.array(self.robot.cfg[f"{side}_joint_indices"])
        self.gripper_indices = np.array(self.robot.cfg[f"{side}_gripper_indices"])
        base_path_attribute = "fl_base_path" if side == "left" else "fr_base_path"
        self.reference_prim_path = getattr(self.task.robots[self.name], base_path_attribute)
        self.lr_name = side
        state = getattr(self.robot, f"{side}_gripper_state")
        self._gripper_state = 1.0 if state == 1.0 else -1.0
        self._gripper_joint_position = np.array([0.05, -0.05])

    def get_gripper_action(self):
        if self._gripper_state == 1.0:
            return np.array([0.05, -0.05])
        return np.array([0.0, 0.0])
