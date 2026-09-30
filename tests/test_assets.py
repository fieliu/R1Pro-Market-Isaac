import hashlib
import json
from pathlib import Path
import pytest
from pxr import Gf, Usd, UsdGeom, UsdPhysics
from r1pro_market.basket import BasketConfig, assemble_robot, build_basket
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def cfg():
    return BasketConfig.load(ROOT/"configs/basket.json")

def test_open_cavity_single_body_and_units(tmp_path,cfg):
    path=build_basket(tmp_path/"basket.usda",cfg)
    stage=Usd.Stage.Open(str(path))
    assert UsdGeom.GetStageMetersPerUnit(stage)==1
    bodies=[p for p in stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)]
    assert len(bodies)==1
    colliders=[p for p in stage.Traverse() if p.HasAPI(UsdPhysics.CollisionAPI)]
    assert len(colliders)==7
    cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),[UsdGeom.Tokens.default_])
    # Every interior sample must be outside every collision box, including at the opening.
    for z in (0.02,0.06,0.119,0.16):
        for x,y in ((0,0),(.08,.1),(-.08,-.1)):
            point=Gf.Vec3d(x,y,z)
            for collider in colliders:
                bounds=cache.ComputeWorldBound(collider).ComputeAlignedRange()
                assert not bounds.Contains(point), (collider.GetPath(),point)
    floor=cache.ComputeWorldBound(stage.GetPrimAtPath("/Basket/floor")).ComputeAlignedRange()
    assert abs(floor.GetMax()[2])<1e-7

def test_attachment_local_frames_match_and_source_not_modified(tmp_path,cfg):
    source=tmp_path/"source.usda"
    s=Usd.Stage.CreateNew(str(source))
    root=UsdGeom.Xform.Define(s,"/Source")
    s.SetDefaultPrim(root.GetPrim())
    # Deliberately rotated and translated parent: catches world/local frame mistakes.
    root.AddTranslateOp().Set(Gf.Vec3d(1,2,3))
    root.AddRotateZOp().Set(35)
    body=UsdGeom.Xform.Define(s,"/Source/"+cfg.mount_link)
    UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
    body.AddTranslateOp().Set(Gf.Vec3d(.1,.2,.3))
    s.GetRootLayer().Save()
    before=source.read_bytes()
    output=assemble_robot(source,tmp_path/"assembly.usda",cfg)
    assert source.read_bytes()==before
    stage=Usd.Stage.Open(str(output))
    joint=UsdPhysics.FixedJoint.Get(stage,"/World/BasketMount")
    mount=stage.GetPrimAtPath(str(joint.GetBody0Rel().GetTargets()[0]))
    basket=stage.GetPrimAtPath(str(joint.GetBody1Rel().GetTargets()[0]))
    m=UsdGeom.Xformable(mount).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    b=UsdGeom.Xformable(basket).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    a0=m.Transform(Gf.Vec3d(joint.GetLocalPos0Attr().Get()))
    a1=b.Transform(Gf.Vec3d(joint.GetLocalPos1Attr().Get()))
    assert (a0-a1).GetLength()<1e-6
    assert joint.GetCollisionEnabledAttr().Get() is False
    assert not basket.HasAPI(UsdPhysics.ArticulationRootAPI)
    assert not stage.GetCompositionErrors()

def test_reject_bad_mount_and_overwrite(tmp_path,cfg):
    path=build_basket(tmp_path/"basket.usda",cfg)
    with pytest.raises(FileExistsError):
        build_basket(path,cfg)
    with pytest.raises(ValueError,match="Mount target"):
        assemble_robot(path,tmp_path/"bad.usda",cfg)

@pytest.mark.parametrize("field,value",[
    ("mass_kg",-1),("inner_size_xyz_m",[0,.2,.2]),
    ("orientation_wxyz",[2,0,0,0]),("placement_margin_m",1),
    ("wall_thickness_m",float("nan"))])
def test_invalid_config(tmp_path,field,value):
    data=json.loads((ROOT/"configs/basket.json").read_text())
    data[field]=value
    path=tmp_path/"config.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        BasketConfig.load(path)
