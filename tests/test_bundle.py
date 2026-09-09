"""Complete API/CLI generation and lossless authored input contracts."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import cupy as cp
import numpy as np
import pytest
from click.testing import CliRunner
from PIL import Image

from textureworks.bundle import generate_batch, generate_bundle, load_bundle, main
from textureworks.pipeline import main as legacy_cli


@pytest.fixture
def recipe(tmp_path):
    x,y = np.meshgrid(np.arange(19),np.arange(13))
    color = np.stack((80+x*5,50+y*9,100+((x+y)%4)*25),axis=2).astype(np.uint8)
    Image.fromarray(color).save(tmp_path/"color.png")
    Image.fromarray((10000+x*611+y*177).astype(np.uint16)).save(tmp_path/"height.png")
    Image.fromarray(np.full((13,19),23456,np.uint16)).save(tmp_path/"roughness.png")
    normal = np.broadcast_to(np.array([128,140,254],np.uint8),(13,19,3)).copy()
    Image.fromarray(normal).save(tmp_path/"normal.png")
    Image.fromarray((x/18*255).astype(np.uint8)).save(tmp_path/"mask.png")
    return {"name":"test-material","preset":"painted-metal","physical_size":[.7,.4],"relief_depth":.02,
            "layers":[{"albedo":"color.png","height":"height.png","roughness":"roughness.png",
                       "normal":{"path":"normal.png","normal_convention":"directx"},"ao":.9},
                      {"albedo":"color.png","height":"height.png","metallic":1,"ao":1}],
            "mask":"mask.png","seed":912}


@pytest.mark.parametrize("backend",["ptx","cupy"])
def test_round_trip_precision_provenance_and_determinism(tmp_path,recipe,backend):
    out = tmp_path/"bundle"
    manifest = generate_bundle(recipe,out,base_dir=tmp_path,backend=backend)
    first = manifest.read_bytes()
    result = load_bundle(manifest)
    assert len(result["layers"]) == 2
    assert result["physical_size"] == [.7,.4] and result["height_reference"] == 1
    for source,dest in (("height.png","layer0_height.png"),("roughness.png","layer0_roughness.png"),
                        ("normal.png","layer0_normal.png"),("mask.png","mask.png")):
        assert (tmp_path/source).read_bytes() == (out/dest).read_bytes()
    authored = next(x for x in result["textures"] if x["path"] == "layer0_normal.png")
    assert authored["normal_convention"] == "directx" and authored["encoding"] == "xyz-unorm"
    assert all(x["bits"] == 16 for x in result["textures"] if x["role"] in ("height","roughness"))
    generate_bundle(recipe,out,base_dir=tmp_path,backend=backend)
    assert manifest.read_bytes() == first
    assert {s["role"] for s in result["sources"]} >= {"albedo","height","normal","mask","detail_source"}


def test_shared_height_once_and_external_detail(tmp_path,recipe,monkeypatch):
    from textureworks.ptx import height as height_module
    original = height_module.generate_height
    count = 0
    def generate(*args,**kwargs):
        nonlocal count
        count += 1
        return original(*args,**kwargs)
    monkeypatch.setattr(height_module,"generate_height",generate)
    recipe["layers"] = [{"albedo":"color.png","ao":1}]
    Image.fromarray(np.full((7,31,3),128,np.uint8)).save(tmp_path/"detail.png")
    recipe["detail"] = {"source":"detail.png","physical_size":[.1,.2]}
    manifest = generate_bundle(recipe,tmp_path/"bundle",base_dir=tmp_path)
    assert count == 1
    result = load_bundle(manifest)
    detail = next(t for t in result["textures"] if t["role"] == "detail_color")
    assert (detail["width"],detail["height"]) == (31,7)
    np.testing.assert_array_equal(np.asarray(Image.open(manifest.parent/detail["path"])),128)
    normal = np.asarray(Image.open(manifest.parent/"detail_normal.png"))
    np.testing.assert_array_equal(normal,np.broadcast_to([128,128,255],normal.shape))


def test_cli_generation_batch_and_legacy_compatibility(tmp_path,recipe):
    recipe_path = tmp_path/"recipe.json"; recipe_path.write_text(json.dumps(recipe))
    runner = CliRunner()
    generated = runner.invoke(main,["generate",str(recipe_path),"-o",str(tmp_path/"cli")])
    assert generated.exit_code == 0, generated.output
    verified = runner.invoke(main,["verify",str(tmp_path/"cli")])
    assert verified.exit_code == 0 and "Verified test-material" in verified.output
    batch = tmp_path/"batch.json"; batch.write_text(json.dumps({"schema_version":1,"recipes":["recipe.json"]}))
    result = runner.invoke(main,["batch",str(batch),"-o",str(tmp_path/"batch")])
    assert result.exit_code == 0, result.output
    bundled = runner.invoke(legacy_cli,[str(tmp_path/"color.png"),"--bundle-preset","wood","-o",str(tmp_path/"quick")])
    assert bundled.exit_code == 0, bundled.output
    old = runner.invoke(legacy_cli,[str(tmp_path/"color.png"),"--map","height","--height-bits","16","-o",str(tmp_path/"old")])
    assert old.exit_code == 0 and (tmp_path/"old/color_height.png").is_file()


@pytest.mark.parametrize("change", ["dimension","color_space","reference","normal","encoding","negative","unknown","profile"])
def test_reject_incompatible_recipes(tmp_path,recipe,change):
    r = deepcopy(recipe)
    if change == "dimension":
        Image.fromarray(np.zeros((3,7),np.uint8)).save(tmp_path/"short.png"); r["mask"]="short.png"
    elif change == "color_space": r["layers"][0]["height"]={"path":"height.png","color_space":"srgb"}
    elif change == "reference": r["layers"][0]["height"]={"path":"height.png","height_reference":.5}
    elif change == "normal": r["layers"][0]["normal"]={"path":"normal.png","normal_convention":"guess"}
    elif change == "encoding": r["layers"][0]["height"]={"path":"height.png","encoding":"black-top"}
    elif change == "negative": r["relief_depth"]=-1
    elif change == "unknown": r["detial"]={}
    elif change == "profile": r["schema_version"]=7
    with pytest.raises(ValueError): generate_bundle(r,tmp_path/"bad",base_dir=tmp_path)
    assert not (tmp_path/"bad").exists()


def test_changed_hash_and_metadata_cannot_pass_or_be_overwritten(tmp_path,recipe):
    path = generate_bundle(recipe,tmp_path/"bundle",base_dir=tmp_path)
    original = path.read_text()
    result = json.loads(original); result["textures"][0]["color_space"]="srgb"
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError): load_bundle(path)
    path.write_text(original)
    result = json.loads(original); result["detail"]["fade_end"] = -10
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError,match="disagrees"): load_bundle(path)
    path.write_text(original)
    mask = path.parent/"mask.png"
    mask.write_bytes((tmp_path/"height.png").read_bytes())
    with pytest.raises(ValueError,match="Missing or changed"): load_bundle(path)
    with pytest.raises(ValueError): generate_bundle(recipe,path.parent,base_dir=tmp_path)
    assert mask.read_bytes() == (tmp_path/"height.png").read_bytes()


def test_collision_and_directory_preservation(tmp_path,recipe):
    p = tmp_path/"one.json"; p.write_text(json.dumps(recipe))
    b = tmp_path/"batch.json"; b.write_text(json.dumps({"schema_version":1,"recipes":[p.name,p.name]}))
    with pytest.raises(ValueError,match="collide"): generate_batch(b,tmp_path/"output")
    out = tmp_path/"unrelated"; out.mkdir(); (out/"mine.txt").write_text("Keep me")
    with pytest.raises(ValueError,match="nonempty"): generate_bundle(recipe,out,base_dir=tmp_path)
    assert (out/"mine.txt").read_text() == "Keep me"


def test_reject_ambiguous_image_and_traversal(tmp_path,recipe):
    Image.fromarray(np.zeros((13,19,4),np.uint8)).save(tmp_path/"rgba.png")
    r = deepcopy(recipe); r["layers"][0]["albedo"]="rgba.png"
    with pytest.raises(ValueError,match="no alpha"): generate_bundle(r,tmp_path/"bad",base_dir=tmp_path)
    path = generate_bundle(recipe,tmp_path/"bundle",base_dir=tmp_path)
    manifest = json.loads(path.read_text()); manifest["textures"][0]["path"]="../color.png"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match="filenames"): load_bundle(path)


@pytest.mark.parametrize("change", ["textures_null","entry_null","path_object","role_object","normal_authored","detail_boundary"])
def test_malformed_manifest_has_clear_errors(tmp_path,recipe,change):
    path = generate_bundle(recipe,tmp_path/"bundle",base_dir=tmp_path)
    manifest = json.loads(path.read_text())
    if change == "textures_null": manifest["textures"] = None
    elif change == "entry_null": manifest["textures"][0] = None
    elif change == "path_object": manifest["textures"][0]["path"] = {}
    elif change == "role_object": manifest["textures"][0]["role"] = {}
    elif change == "normal_authored": manifest["layers"][0]["normal_authored"] = not manifest["layers"][0]["normal_authored"]
    elif change == "detail_boundary": del manifest["detail"]["boundary"]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError): load_bundle(path)
