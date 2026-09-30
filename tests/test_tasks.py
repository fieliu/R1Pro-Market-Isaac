import copy
import json
from pathlib import Path
import pytest
from r1pro_market.tasks import generate_candidates, validate_split
ROOT=Path(__file__).resolve().parents[1]

def scene():
    return json.loads((ROOT/"configs/example_scene.json").read_text())

def test_reproducible_candidates_and_no_false_success():
    a=list(generate_candidates(scene(),50,13))
    assert a==list(generate_candidates(scene(),50,13))
    assert a!=list(generate_candidates(scene(),50,14))
    assert len({t["task_id"] for t in a})==50
    assert {t["status"] for t in a}=={"candidate_unvalidated"}
    assert {t["skill"] for t in a}=={"shelf_to_basket","basket_to_shelf"}

def test_no_layout_family_leakage():
    a=scene()
    b=copy.deepcopy(a)
    b["scene_id"]="variant_2"
    b["split"]="test"
    with pytest.raises(ValueError,match="leaks"):
        validate_split([a,b])

def test_object_must_fit():
    s=scene()
    s["objects"][0]["size_xyz_m"]=[1,1,1]
    with pytest.raises(ValueError,match="does not fit"):
        list(generate_candidates(s,1,0))
