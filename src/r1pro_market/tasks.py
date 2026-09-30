"""Candidate task specifications. Generation is not planning or execution."""
import hashlib
import json
import random

SKILLS=("shelf_to_basket","basket_to_shelf","basket_to_freezer","basket_to_receiving")

def validate_split(scenes):
    groups={}
    ids=set()
    for s in scenes:
        if s["scene_id"] in ids:
            raise ValueError("Duplicate scene_id")
        ids.add(s["scene_id"])
        if s["split"] not in ("train","validation","test"):
            raise ValueError("Unknown split")
        group=s["layout_family"]
        if group in groups and groups[group]!=s["split"]:
            raise ValueError(f"Layout family {group} leaks across splits")
        groups[group]=s["split"]

def generate_candidates(scene, count, seed):
    if count < 1:
        raise ValueError("count must be positive")
    if not scene.get("objects") or not scene.get("skills"):
        raise ValueError("Scene must supply objects and supported skills")
    rng=random.Random(seed)
    for i in range(count):
        skill=scene["skills"][i % len(scene["skills"])]
        if skill not in SKILLS:
            raise ValueError(f"Unsupported skill {skill}")
        source,dest=skill.split("_to_")
        if source not in scene["regions"] or dest not in scene["regions"]:
            raise ValueError(f"Missing source/destination region for {skill}")
        obj=rng.choice(scene["objects"])
        placement={}
        for role,region_id in (("source",source),("destination",dest)):
            region=scene["regions"][region_id]
            # Axis-aligned, upright objects only in this initial task spec.
            half=[v/2 for v in obj["size_xyz_m"]]
            low=[region["min_xyz_m"][j]+half[j]+0.005 for j in (0,1)]
            high=[region["max_xyz_m"][j]-half[j]-0.005 for j in (0,1)]
            if any(a>b for a,b in zip(low,high)) or obj["size_xyz_m"][2] > (
                    region["max_xyz_m"][2]-region["min_xyz_m"][2]):
                raise ValueError(f"Object {obj['id']} does not fit in {region_id}")
            placement[role]={"region":region_id,"frame":region["frame"],
                "object_center_xyz_m":[rng.uniform(low[0],high[0]),rng.uniform(low[1],high[1]),
                                       region["min_xyz_m"][2]+half[2]],
                "object_orientation_wxyz":[1,0,0,0]}
        task={"schema_version":1,"scene_id":scene["scene_id"],"layout_family":scene["layout_family"],
              "split":scene["split"],"seed":seed,"index":i,"skill":skill,
              "object_id":obj["id"],"object_size_xyz_m":obj["size_xyz_m"],
              "placement":placement,"robot_reset":scene["robot_reset"],
              "initial_scene_snapshot":scene["initial_scene_snapshot"],
              "instruction":f"Move the {obj['description']} from the {source} to the {dest}.",
              "status":"candidate_unvalidated",
              "validation_required":["asset_load","collision_free_reset","visibility",
                                     "reachable_grasp","expert_execution","stable_success"]}
        task["task_id"]=hashlib.sha256(json.dumps(task,sort_keys=True).encode()).hexdigest()[:20]
        yield task
