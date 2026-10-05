"""Run with Isaac Sim 4.5 python.sh, not the asset-development venv.

A physics smoke check (hold robot, drop cube into basket), NOT a grasp expert.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--asset",type=Path,default=ROOT/"assets/generated/r1pro_with_basket.usda")
    p.add_argument("--report",type=Path,default=ROOT/"reports/isaac_smoke.json")
    p.add_argument("--basket-config",type=Path,default=ROOT/"configs/basket.json")
    p.add_argument("--gui",action="store_true")
    p.add_argument("--steps",type=int,default=600)
    args=p.parse_args()
    if args.steps < 120:
        p.error("--steps must be at least 120 to allow settling")
    args.report.parent.mkdir(parents=True,exist_ok=True)
    if importlib.util.find_spec("isaacsim") is None:
        report={"status":"blocked","reason":"Isaac Sim is not installed in this interpreter",
                "python":sys.executable,"physics_simulated":False}
        args.report.write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
        return 2
    if not args.asset.is_file():
        p.error("Build assets first using scripts/build_assets.py")
    from isaacsim import SimulationApp
    app=SimulationApp({"headless":not args.gui,"width":640,"height":480})
    report={"status":"failed","physics_simulated":False,"asset":str(args.asset)}
    try:
        import numpy as np
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdLux
        from isaacsim.core.api import World
        from isaacsim.core.api.robots import Robot
        from isaacsim.core.api.objects import DynamicCuboid
        from isaacsim.core.prims import SingleRigidPrim
        from isaacsim.core.utils.stage import add_reference_to_stage
        from isaacsim.core.utils.types import ArticulationAction
        import omni.usd
        from r1pro_market.basket import BasketConfig
        cfg=BasketConfig.load(args.basket_config)
        robot_cfg=json.loads((ROOT/"configs/robot.json").read_text())
        world=World(stage_units_in_meters=1.0,physics_dt=1/120,rendering_dt=1/30)
        add_reference_to_stage(str(args.asset.resolve()),"/World/Assembly")
        world.scene.add_default_ground_plane()
        stage=omni.usd.get_context().get_stage()
        light=UsdLux.DomeLight.Define(stage,"/World/SmokeLight")
        light.CreateIntensityAttr(800)
        prefix="/World/Assembly"
        base=prefix+"/R1Pro/"+cfg.mount_link
        basket_path=prefix+"/Basket"
        # Anchor only in this local-manipulation test. The exported robot stays mobile.
        anchor=UsdPhysics.FixedJoint.Define(stage,"/World/LocalTaskBaseAnchor")
        anchor.CreateBody1Rel().SetTargets([Sdf.Path(base)])
        base_world=UsdGeom.Xformable(stage.GetPrimAtPath(base)).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default())
        anchor.CreateLocalPos0Attr(Gf.Vec3f(*base_world.ExtractTranslation()))
        rotation=base_world.ExtractRotationQuat()
        anchor.CreateLocalRot0Attr(Gf.Quatf(rotation.GetReal(),Gf.Vec3f(*rotation.GetImaginary())))
        anchor.CreateLocalPos1Attr(Gf.Vec3f(0))
        anchor.CreateLocalRot1Attr(Gf.Quatf(1))
        robot=world.scene.add(Robot(
            prim_path=prefix+"/R1Pro/"+robot_cfg["articulation_relative_path"],name="r1pro"))
        basket=world.scene.add(SingleRigidPrim(prim_path=basket_path,name="basket"))
        basket_matrix=UsdGeom.Xformable(stage.GetPrimAtPath(basket_path)).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default())
        edge=0.04
        start=basket_matrix.Transform(Gf.Vec3d(0,0,cfg.inner_size_xyz_m[2]+0.08))
        probe=world.scene.add(DynamicCuboid("/World/Probe",name="probe",
            position=np.array(start),size=edge,mass=0.05,color=np.array([1.,0.3,0.1])))
        world.reset()
        initial_q=np.asarray(robot.get_joint_positions()).copy()
        if not np.isfinite(initial_q).all() or len(initial_q)==0:
            raise RuntimeError("Invalid robot joint feedback")
        basket_start=np.asarray(basket.get_world_pose()[0]).copy()
        max_drift=0.0
        completed=0
        for _ in range(args.steps):
            if not app.is_running():
                raise RuntimeError("Simulation closed before smoke check completed")
            robot.apply_action(ArticulationAction(joint_positions=initial_q))
            world.step(render=bool(args.gui))
            completed+=1
            if not np.isfinite(robot.get_joint_positions()).all():
                raise RuntimeError("Non-finite articulation state")
            max_drift=max(max_drift,float(np.linalg.norm(
                np.asarray(basket.get_world_pose()[0])-basket_start)))
        position,orientation=basket.get_world_pose()
        # Convert world probe position to the actual basket frame after physics.
        rotation=Gf.Quatd(float(orientation[0]),Gf.Vec3d(*map(float,orientation[1:])))
        matrix=Gf.Matrix4d(1).SetRotate(rotation)
        matrix.SetTranslateOnly(Gf.Vec3d(*map(float,position)))
        local=np.array(matrix.GetInverse().Transform(Gf.Vec3d(*map(float,probe.get_world_pose()[0]))))
        half=np.array(cfg.inner_size_xyz_m[:2])/2
        inside=bool(np.all(np.abs(local[:2])+edge/2 < half)
                    and -0.005 <= local[2]-edge/2 <= 0.02)
        speed=float(np.linalg.norm(probe.get_linear_velocity()))
        stable=inside and speed < 0.05 and max_drift < 0.01
        report.update(status="passed" if stable else "failed",physics_simulated=True,
                      completed_steps=completed,dof_names=list(robot.dof_names),
                      basket_max_drift_m=max_drift,probe_local_position_m=local.tolist(),
                      probe_speed_m_s=speed,probe_inside=inside,
                      grasp_validated=False,reachability_validated=False)
        return 0 if stable else 1
    except Exception as exc:
        report["error"]=f"{type(exc).__name__}: {exc}"
        return 1
    finally:
        args.report.write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
        app.close()

if __name__=="__main__":
    raise SystemExit(main())
