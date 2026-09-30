"""Build a hollow, compound-collider basket. No Isaac/PhysX import required."""
from dataclasses import dataclass
from pathlib import Path
import json
import math
import os
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

@dataclass(frozen=True)
class BasketConfig:
    inner_size_xyz_m: tuple
    wall_thickness_m: float
    mass_kg: float
    static_friction: float
    dynamic_friction: float
    mount_link: str
    position_in_mount_m: tuple
    orientation_wxyz: tuple
    support_height_m: float
    placement_margin_m: float
    calibration_status: str = "candidate_unverified"

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        data.pop("schema_version", None)
        cfg = cls(**data)
        cfg.validate()
        return cfg

    def validate(self):
        if len(self.inner_size_xyz_m) != 3 or len(self.position_in_mount_m) != 3:
            raise ValueError("Expected 3D dimensions and mount position")
        values = (*self.inner_size_xyz_m, self.wall_thickness_m, self.mass_kg,
                  self.static_friction, self.dynamic_friction, self.support_height_m,
                  self.placement_margin_m, *self.position_in_mount_m, *self.orientation_wxyz)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Parameters must be finite")
        if min(*self.inner_size_xyz_m, self.wall_thickness_m, self.mass_kg) <= 0:
            raise ValueError("Basket dimensions, wall thickness and mass must be positive")
        if min(self.static_friction, self.dynamic_friction, self.support_height_m,
               self.placement_margin_m) < 0:
            raise ValueError("Friction, support height and margin must be nonnegative")
        if self.dynamic_friction > self.static_friction:
            raise ValueError("Dynamic friction must not exceed static friction")
        if 2 * self.placement_margin_m >= min(self.inner_size_xyz_m[:2]):
            raise ValueError("Placement margin leaves no usable basket floor")
        if len(self.orientation_wxyz) != 4 or not math.isclose(
                sum(v*v for v in self.orientation_wxyz), 1.0, abs_tol=1e-6):
            raise ValueError("Mount quaternion must be normalized, in wxyz order")
        if not self.mount_link or self.mount_link.startswith("/") or ".." in self.mount_link:
            raise ValueError("mount_link must be relative to the referenced robot root")

def box(stage, path, size, center, color=(0.15, 0.45, 0.65)):
    cube = UsdGeom.Cube.Define(stage, path)
    cube.CreateSizeAttr(1.0)
    cube.AddTranslateOp().Set(Gf.Vec3d(*center))
    cube.AddScaleOp().Set(Gf.Vec3f(*size))
    cube.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    UsdPhysics.CollisionAPI.Apply(cube.GetPrim())
    return cube.GetPrim()

def make_stage(path):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing asset: {path}")
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdPhysics.SetStageKilogramsPerUnit(stage, 1.0)
    return stage

def add_basket(stage, path, cfg):
    cfg.validate()
    root = UsdGeom.Xform.Define(stage, path)
    UsdPhysics.RigidBodyAPI.Apply(root.GetPrim())
    UsdPhysics.MassAPI.Apply(root.GetPrim()).CreateMassAttr(cfg.mass_kg)
    root.GetPrim().CreateAttribute("market:calibrationStatus", Sdf.ValueTypeNames.String).Set(
        cfg.calibration_status)
    x, y, h = cfg.inner_size_xyz_m
    t = cfg.wall_thickness_m
    # Basket frame origin: center of the interior floor, z=0 at its upper surface.
    shapes = [
        ("floor", (x+2*t, y+2*t, t), (0, 0, -t/2)),
        ("wall_x_neg", (t, y+2*t, h), (-(x+t)/2, 0, h/2)),
        ("wall_x_pos", (t, y+2*t, h), ((x+t)/2, 0, h/2)),
        ("wall_y_neg", (x, t, h), (0, -(y+t)/2, h/2)),
        ("wall_y_pos", (x, t, h), (0, (y+t)/2, h/2)),
    ]
    if cfg.support_height_m:
        for side in (-1, 1):
            shapes.append((f"support_{'left' if side>0 else 'right'}",
                           (0.025, 0.025, cfg.support_height_m),
                           (-x/3, side*y/3, -t-cfg.support_height_m/2)))
    material = UsdShade.Material.Define(stage, path + "/Material")
    physics = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    physics.CreateStaticFrictionAttr(cfg.static_friction)
    physics.CreateDynamicFrictionAttr(cfg.dynamic_friction)
    physics.CreateRestitutionAttr(0.0)
    for name, size, center in shapes:
        prim = box(stage, path + "/" + name, size, center)
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(material, materialPurpose="physics")
    m = cfg.placement_margin_m
    root.GetPrim().CreateAttribute("market:interiorMin", Sdf.ValueTypeNames.Double3).Set(
        Gf.Vec3d(-x/2+m, -y/2+m, 0))
    root.GetPrim().CreateAttribute("market:interiorMax", Sdf.ValueTypeNames.Double3).Set(
        Gf.Vec3d(x/2-m, y/2-m, h))
    return root

def build_basket(output, cfg):
    stage = make_stage(output)
    root = add_basket(stage, "/Basket", cfg)
    stage.SetDefaultPrim(root.GetPrim())
    stage.GetRootLayer().Save()
    return Path(output)

def assemble_robot(source, output, cfg):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    source_stage = Usd.Stage.Open(str(source))
    if not source_stage or not source_stage.GetDefaultPrim():
        raise ValueError("Robot source must have a valid defaultPrim")
    relative_source_link = str(source_stage.GetDefaultPrim().GetPath()) + "/" + cfg.mount_link
    source_link = source_stage.GetPrimAtPath(relative_source_link)
    if not source_link or not source_link.HasAPI(UsdPhysics.RigidBodyAPI):
        raise ValueError(f"Mount target is not a rigid body: {relative_source_link}")
    stage = make_stage(output)
    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())
    robot = UsdGeom.Xform.Define(stage, "/World/R1Pro")
    robot.GetPrim().GetReferences().AddReference(
        os.path.relpath(source, output.parent).replace(os.sep, "/"))
    mount_path = "/World/R1Pro/" + cfg.mount_link
    mount = stage.GetPrimAtPath(mount_path)
    basket = add_basket(stage, "/World/Basket", cfg)
    q = cfg.orientation_wxyz
    rotation = Gf.Quatd(q[0], Gf.Vec3d(*q[1:]))
    local = Gf.Matrix4d(1.0)
    local.SetRotate(rotation)
    local.SetTranslateOnly(Gf.Vec3d(*cfg.position_in_mount_m))
    mount_world = UsdGeom.Xformable(mount).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    basket.AddTransformOp().Set(local * mount_world)
    joint = UsdPhysics.FixedJoint.Define(stage, "/World/BasketMount")
    joint.CreateBody0Rel().SetTargets([Sdf.Path(mount_path)])
    joint.CreateBody1Rel().SetTargets([Sdf.Path("/World/Basket")])
    joint.CreateLocalPos0Attr(Gf.Vec3f(*cfg.position_in_mount_m))
    joint.CreateLocalRot0Attr(Gf.Quatf(q[0], Gf.Vec3f(*q[1:])))
    joint.CreateLocalPos1Attr(Gf.Vec3f(0))
    joint.CreateLocalRot1Attr(Gf.Quatf(1))
    joint.CreateCollisionEnabledAttr(False)  # Only the two directly connected bodies.
    # Do not mask arm-basket collisions or add a second articulation root.
    stage.GetRootLayer().Save()
    return output
