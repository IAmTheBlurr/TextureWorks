"""Versioned, deterministic material bundles and batch CLI.

Run ``python -m textureworks.bundle --help``. See the material-bundles reference
for the recipe, authored input contracts and reusable Unity profile.
"""

from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import re
import shutil
import struct
import tempfile

import click
import cupy as cp
import numpy as np
from PIL import Image

from textureworks import __version__
from textureworks.core.io import load_texture, save_map, to_grayscale
from textureworks.core.material_fields import number

SCHEMA_VERSION = 1
PROFILE = "textureworks-urp-two-material-v1"
PRESETS = {
    "masonry": {"relief_depth": .04, "roughness": .78, "metallic": 0, "curvature_range": 40,
                "detail_depth": .0008, "edge_amount": .4, "cavity_amount": .85},
    "wood": {"relief_depth": .025, "roughness": .65, "metallic": 0, "curvature_range": 30,
             "detail_depth": .0004, "edge_amount": .35, "cavity_amount": .45},
    "painted-metal": {"relief_depth": .012, "roughness": .4, "metallic": 0, "curvature_range": 50,
                      "detail_depth": .0002, "edge_amount": .8, "cavity_amount": .25},
    "fine-detail": {"relief_depth": .003, "roughness": .7, "metallic": 0, "curvature_range": 80,
                    "detail_depth": .0003, "edge_amount": .25, "cavity_amount": .35},
}
_ROLES = {"albedo", "height", "normal", "roughness", "metallic", "ao", "curvature",
          "edge", "cavity", "wear", "mask", "detail_color", "detail_normal", "preview_height", "preview_weight"}
_SCALARS = {"height", "roughness", "metallic", "ao", "curvature", "edge", "cavity", "mask", "preview_height", "preview_weight"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"Cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _unknown(value: dict, allowed: set[str], context: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    extra = set(value)-allowed
    if extra:
        raise ValueError(f"Unsupported {context} keys: {', '.join(sorted(extra))}")


def _image_info(path: Path, role: str) -> dict:
    """Reject conversions Pillow would otherwise perform silently."""
    with Image.open(path) as img:
        if img.format != "PNG":
            raise ValueError(f"{role}: only explicit RGB8 or grayscale 8/16-bit PNG is supported: {path}")
        header = path.read_bytes()[:29]
        width,height,bits,color_type = struct.unpack(">IIBB",header[16:26])
        if min(width,height) < 2 or max(width,height) > 8192:
            raise ValueError(f"{role}: dimensions must be between 2 and 8192")
        scalar = role in _SCALARS
        if scalar and (color_type != 0 or bits not in (8,16)):
            raise ValueError(f"{role}: requires grayscale PNG with 8 or 16 bits")
        if not scalar and (color_type != 2 or bits != 8):
            raise ValueError(f"{role}: requires RGB PNG with 8 bits; no alpha, palette or implicit conversion")
        if "icc_profile" in img.info:
            raise ValueError(f"{role}: convert ICC-profiled imagery explicitly to sRGB before bundling")
        img.load()
    return {"width":width,"height":height,"bits":bits,"channels":"R" if scalar else "RGB"}


def _size(value: list[float], name: str) -> list[float]:
    if not isinstance(value, (list,tuple)) or len(value) != 2:
        raise ValueError(f"{name} must be [width,height] in meters")
    return [number(v,name,1e-4,10000) for v in value]


def _source(value: str | dict, role: str, base: Path, physical: list[float], depth: float) -> tuple[Path,dict]:
    spec = {"path":value} if isinstance(value,str) else deepcopy(value)
    _unknown(spec,{"path","color_space","encoding","normal_convention","physical_size","relief_depth","height_reference","provenance"},role)
    if not isinstance(spec.get("path"),str):
        raise ValueError(f"{role} needs a file path")
    path = (base/spec["path"]).resolve()
    if not path.is_file():
        raise ValueError(f"{role}: file does not exist: {path}")
    info = _image_info(path,role)
    color_space = spec.get("color_space","srgb" if role == "albedo" else "linear")
    if color_space not in (("srgb","linear") if role == "albedo" else ("linear",)):
        raise ValueError(f"{role}: incompatible color space {color_space}")
    encoding = {"normal":"xyz-unorm","height":"white-top"}.get(role,"unorm")
    if spec.get("encoding",encoding) != encoding:
        raise ValueError(f"{role}: unsupported encoding; expected {encoding}")
    convention = spec.get("normal_convention","opengl")
    if role == "normal" and convention not in ("opengl","directx"):
        raise ValueError("normal_convention must be opengl (+Y) or directx (-Y)")
    if "physical_size" in spec and _size(spec["physical_size"],role) != physical:
        raise ValueError(f"{role}: incompatible physical_size")
    if "relief_depth" in spec and spec["relief_depth"] != depth:
        raise ValueError(f"{role}: incompatible relief_depth")
    if spec.get("height_reference",1) != 1:
        raise ValueError(f"{role}: height_reference must be 1 (mesh plane)")
    return path,{**info,"color_space":color_space,"encoding":encoding,
                 "normal_convention":convention if role == "normal" else "",
                 "source":spec["path"],"source_sha256":_sha(path),
                 "provenance":spec.get("provenance","authored input supplied by caller")}


def _linear(color: cp.ndarray, color_space: str) -> cp.ndarray:
    if color_space == "linear":
        return color
    return cp.where(color <= .04045,color/12.92,((color+.055)/1.055)**2.4).astype(cp.float32)


def _backend(backend: str):
    if backend not in ("ptx","cupy"):
        raise ValueError("backend must be ptx or cupy")
    prefix = "textureworks."+("cupy_ref" if backend == "cupy" else "ptx")
    return importlib.import_module(prefix+".material_fields"),prefix


def _resolved(recipe: dict) -> dict:
    _unknown(recipe,{"schema_version","name","preset","physical_size","relief_depth","boundary","seed",
                     "layers","detail","wear","composition","mask","provenance"},"recipe")
    if recipe.get("schema_version",1) != SCHEMA_VERSION:
        raise ValueError("unsupported recipe schema_version")
    preset_name = recipe.get("preset","masonry")
    if not isinstance(preset_name,str) or preset_name not in PRESETS:
        raise ValueError(f"Unknown preset: {preset_name}")
    preset = PRESETS[preset_name]
    name = recipe.get("name","material")
    if not isinstance(name,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}",name):
        raise ValueError("name must be 1-64 letters, digits, underscores or hyphens")
    size = _size(recipe.get("physical_size",[1,1]),"physical_size")
    depth = number(recipe.get("relief_depth",preset["relief_depth"]),"relief_depth",0,100)
    boundary = recipe.get("boundary","wrap")
    if boundary not in ("clamp","wrap"):
        raise ValueError("boundary must be clamp or wrap")
    seed = recipe.get("seed",0)
    if isinstance(seed,bool) or not isinstance(seed,int) or not 0 <= seed <= 0xffffffff:
        raise ValueError("seed must be uint32")
    layers = recipe.get("layers")
    if not isinstance(layers,list) or not 1 <= len(layers) <= 2:
        raise ValueError("layers must contain one or two materials")
    for layer in layers:
        _unknown(layer,{"name","albedo","height","normal","roughness","metallic","ao","edge","cavity"},"layer")
        if "albedo" not in layer:
            raise ValueError("each layer requires albedo")
    for key in ("detail","wear","composition"):
        if key in recipe and not isinstance(recipe[key],dict):
            raise ValueError(f"{key} must be an object")
    detail = {"radius":4,"relief_depth":preset["detail_depth"],"physical_size":size,
              "tiling":4,"color_strength":.35,"normal_strength":.5,
              "roughness_strength":.1,"fade_start":3,"fade_end":8,"boundary":"wrap",**recipe.get("detail",{})}
    _unknown(detail,{"source","radius","relief_depth","physical_size","tiling","color_strength",
                     "normal_strength","roughness_strength","fade_start","fade_end","boundary"},"detail")
    if detail["boundary"] not in ("clamp","wrap"):
        raise ValueError("detail.boundary must be clamp or wrap")
    detail["physical_size"] = _size(detail["physical_size"],"detail.physical_size")
    if type(detail["radius"]) is not int or not 1 <= detail["radius"] <= 64:
        raise ValueError("detail.radius must be an integer in [1,64]")
    for key,low,high in (("relief_depth",0,50),("tiling",.01,128),("color_strength",0,2),
                          ("normal_strength",0,4),("roughness_strength",0,1),("fade_start",0,10000),("fade_end",0,10000)):
        detail[key] = number(detail[key],"detail."+key,low,high)
    wear = {"curvature_range":preset["curvature_range"],"edge_amount":preset["edge_amount"],
            "cavity_amount":preset["cavity_amount"],"threshold":.1,"variation":.35,**recipe.get("wear",{})}
    _unknown(wear,{"curvature_range","edge_amount","cavity_amount","threshold","variation"},"wear")
    for key in wear:
        wear[key] = number(wear[key],"wear."+key,1e-6 if key == "curvature_range" else 0,
                           1e6 if key == "curvature_range" else .999 if key == "threshold" else 1)
    composition = {"coverage":.5,"blend_width":.2,"height_bias":.5,"mask_source":"cavity","quality":"balanced",
                   **recipe.get("composition",{})}
    _unknown(composition,{"coverage","blend_width","height_bias","mask_source","quality"},"composition")
    for key in ("coverage","blend_width","height_bias"):
        composition[key] = number(composition[key],"composition."+key,0,1)
    if composition["mask_source"] not in ("edge","cavity","combined") or composition["quality"] not in ("balanced","low","high"):
        raise ValueError("composition mask_source or quality is unsupported")
    return {**deepcopy(recipe),"schema_version":1,"name":name,"preset":preset_name,"physical_size":size,
            "relief_depth":depth,"boundary":boundary,"seed":seed,"detail":detail,"wear":wear,"composition":composition}


def generate_bundle(recipe: dict, output: str | Path, *, base_dir: str | Path = ".", backend: str = "ptx") -> Path:
    """Validate a recipe, resolve shared fields once, and export a material bundle.

    Authored PNG bytes are copied intact. Existing bundles may be regenerated
    only while their recorded files still match their hashes. Unity .meta files
    survive. The manifest is replaced last after generation succeeds.
    """
    recipe = _resolved(recipe)
    fields,prefix = _backend(backend)
    base,output = Path(base_dir).resolve(),Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        if not (output/"material.json").is_file():
            raise ValueError(f"Output is nonempty and is not a material bundle: {output}")
        load_bundle(output/"material.json")
    physical,depth = recipe["physical_size"],recipe["relief_depth"]
    preset = PRESETS[recipe["preset"]]
    entries,sources,layers,inputs,height_fields = [],[],[],[],[]
    common_shape = None
    # Resolve all authored files before touching the output directory.
    for index,layer in enumerate(recipe["layers"]):
        loaded = {}
        for role,value in layer.items():
            if role == "name": continue
            if role in ("roughness","metallic","ao") and isinstance(value,(int,float)):
                loaded[role] = number(value,role,0,1)
                continue
            path,info = _source(value,role,base,physical,depth)
            shape = (info["height"],info["width"])
            if common_shape is None: common_shape = shape
            if shape != common_shape:
                raise ValueError(f"{role}: all material layers and authored maps must have identical dimensions")
            loaded[role] = (path,info)
            sources.append({"layer":index,"role":role,**info})
        inputs.append(loaded)
    mask_input = _source(recipe["mask"],"mask",base,physical,depth) if "mask" in recipe else None
    if mask_input and (mask_input[1]["height"],mask_input[1]["width"]) != common_shape:
        raise ValueError("mask dimensions must match the layers")
    detail_input = (_source(recipe["detail"]["source"],"albedo",base,recipe["detail"]["physical_size"],depth)
                    if "source" in recipe["detail"] else inputs[0]["albedo"])
    if mask_input: sources.append({"layer":-1,"role":"mask",**mask_input[1]})
    sources.append({"layer":-1,"role":"detail_source",**detail_input[1]})
    all_paths = [v[0] for l in inputs for v in l.values() if isinstance(v,tuple)]
    all_paths += [detail_input[0]]+([mask_input[0]] if mask_input else [])
    if any(path == output or output in path.parents for path in all_paths):
        raise ValueError("Bundle output must not contain its source inputs")
    h,w = common_shape
    spacing = (physical[0]/w,physical[1]/h)
    if min(spacing) < 1e-6:
        raise ValueError("physical_size gives texel spacing below 1e-6 meters")
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".textureworks-",dir=output.parent) as temporary:
        staging = Path(temporary)

        def export(role: str, data: cp.ndarray, layer: int = -1, authored: tuple | None = None) -> None:
            filename = (f"layer{layer}_" if layer >= 0 else "")+role+".png"
            path = staging/filename
            color_space,encoding,convention = "linear","unorm",""
            if authored is not None:
                shutil.copyfile(authored[0],path)
                color_space,encoding,convention = (authored[1][k] for k in ("color_space","encoding","normal_convention"))
            elif role in ("normal","detail_normal","detail_color"):
                # Centered UNORM8 gives exact flat normals/residuals at byte 128.
                arr = cp.asnumpy(data)*2-1
                Image.fromarray(np.clip(np.rint(128+127*arr),0,255).astype(np.uint8)).save(path)
                encoding = "xyz-centered-unorm8" if role != "detail_color" else "residual-centered-unorm8"
                convention = "opengl" if role != "detail_color" else ""
            else:
                save_map(data,path,bits=16 if data.ndim == 2 else 8)
                if role == "height": encoding = "white-top"
            info = _image_info(path,role)
            entries.append({"layer":layer,"role":role,"path":filename,"sha256":_sha(path),**info,
                            "color_space":color_space,"encoding":encoding,"normal_convention":convention,
                            "origin":"authored" if authored else "generated"})

        for index,loaded in enumerate(inputs):
            albedo = load_texture(loaded["albedo"][0])
            linear = _linear(albedo,loaded["albedo"][1]["color_space"])
            # One canonical height field for normals, AO, curvature and export.
            if "height" in loaded:
                height = load_texture(loaded["height"][0])
            else:
                height = importlib.import_module(prefix+".height").generate_height(linear,blur_sigma=1.5,contrast=1.2)
            # Quantize derived height once BEFORE dependencies, matching the exported field.
            if "height" not in loaded:
                height = cp.rint(height*65535)/65535
            height_fields.append(height)
            normal = fields.generate_surface_normal(height,spacing,depth,recipe["boundary"])
            curvature = fields.generate_curvature(height,spacing,depth,recipe["wear"]["curvature_range"],recipe["boundary"])
            maps = {"albedo":albedo,"height":height,"normal":normal,"curvature":curvature}
            for role in ("normal","roughness","metallic","ao","edge","cavity"):
                value = loaded.get(role)
                if isinstance(value,tuple): maps[role] = load_texture(value[0])
                elif isinstance(value,(float,int)): maps[role] = cp.full_like(height,value)
                elif role in ("roughness","metallic"): maps[role] = cp.full_like(height,preset[role])
            if "normal" in loaded and not bool(cp.all(maps["normal"][:,:,2] > .5)):
                raise ValueError("Authored normals must have positive tangent Z")
            if "ao" not in maps:
                maps["ao"] = importlib.import_module(prefix+".ao").generate_ao(linear,height_map=height)
            wear = fields.generate_wear(curvature,**{k:v for k,v in recipe["wear"].items() if k != "curvature_range"},
                                         seed=recipe["seed"],edge_mask=maps.get("edge"),cavity_mask=maps.get("cavity"))
            if index == 0:
                export("wear",wear)
                export("edge",wear[:,:,0])
                export("cavity",wear[:,:,1])
                channel = {"edge":0,"cavity":1,"combined":2}[recipe["composition"]["mask_source"]]
                mask = load_texture(mask_input[0]) if mask_input else wear[:,:,channel]
                export("mask",mask,authored=mask_input)
            for role,data in maps.items():
                export(role,data,index,loaded.get(role) if isinstance(loaded.get(role),tuple) else None)
            layers.append({"name":recipe["layers"][index].get("name",f"Material {'AB'[index]}"),
                           "normal_authored":"normal" in loaded})
        composition = recipe["composition"]
        weight = fields.generate_layer_weight(height_fields[0],height_fields[-1],mask,
            composition["coverage"],composition["blend_width"],composition["height_bias"])
        export("preview_weight",weight)
        export("preview_height",height_fields[0]+(height_fields[-1]-height_fields[0])*weight)
        detail_color = _linear(load_texture(detail_input[0]),detail_input[1]["color_space"])
        detail = fields.generate_detail(detail_color,recipe["detail"]["radius"],recipe["detail"]["boundary"])
        ds = recipe["detail"]["physical_size"]
        detail_normal = fields.generate_surface_normal(to_grayscale(detail),
            (ds[0]/detail.shape[1],ds[1]/detail.shape[0]),2*recipe["detail"]["relief_depth"],recipe["detail"]["boundary"])
        export("detail_color",detail); export("detail_normal",detail_normal)
        manifest = {"schema_version":1,"profile":PROFILE,"name":recipe["name"],"generator_version":__version__,
                    "backend":backend,"width":w,"height":h,"physical_size":physical,"relief_depth":depth,
                    "height_reference":1,"normal_convention":"per-texture; tangent +V is image-up",
                    "boundary":recipe["boundary"],"filter":"trilinear","anisotropy":4,
                    "layers":layers,"textures":entries,"sources":sources,"parameters":recipe,
                    "detail":recipe["detail"],"composition":recipe["composition"],
                    "limitations":["Estimated height is not physical reconstruction.",
                        "UV relief curvature does not describe mesh corners or silhouettes.",
                        "Frequency separation cannot recover absent detail.",
                        "Periodic sampling does not make source imagery seamless."]}
        (staging/"material.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        load_bundle(staging/"material.json")
        output.mkdir(parents=True,exist_ok=True)
        for path in sorted(staging.glob("*.png")): shutil.copyfile(path,output/path.name)
        # Replace the authoritative manifest atomically only after all outputs exist.
        manifest_temp = output/".material.json.tmp"
        shutil.copyfile(staging/"material.json",manifest_temp)
        manifest_temp.replace(output/"material.json")
    return output/"material.json"


def load_bundle(path: str | Path) -> dict:
    """Read and verify version, metadata, required maps, dimensions and hashes."""
    path = Path(path).resolve()
    if path.is_dir(): path /= "material.json"
    manifest = _json(path)
    if manifest.get("schema_version") != 1 or manifest.get("profile") != PROFILE:
        raise ValueError("Unsupported bundle version or profile")
    if manifest.get("height_reference") != 1:
        raise ValueError("Bundle height_reference must be 1")
    _size(manifest.get("physical_size"),"physical_size")
    number(manifest.get("relief_depth"),"relief_depth",0,100)
    if manifest.get("boundary") not in ("clamp","wrap") or manifest.get("filter") != "trilinear":
        raise ValueError("Unsupported bundle sampling settings")
    resolved = _resolved(manifest.get("parameters",{}))
    for key in ("name","physical_size","relief_depth","boundary","detail","composition"):
        if manifest.get(key) != resolved.get(key):
            raise ValueError(f"Bundle {key} disagrees with recorded parameters")
    if manifest.get("anisotropy") != 4:
        raise ValueError("Bundle requires anisotropy 4")
    layers = manifest.get("layers",[])
    if not isinstance(layers,list) or not 1 <= len(layers) <= 2:
        raise ValueError("Bundle must have one or two layers")
    if len(layers) != len(resolved["layers"]):
        raise ValueError("Bundle layers disagree with recorded parameters")
    for index,layer in enumerate(layers):
        if not isinstance(layer,dict) or type(layer.get("normal_authored")) is not bool:
            raise ValueError("Each bundle layer needs an explicit normal_authored boolean")
        if layer["normal_authored"] != ("normal" in resolved["layers"][index]):
            raise ValueError("Bundle normal_authored disagrees with recorded inputs")
    entries = manifest.get("textures")
    if not isinstance(entries,list) or not all(isinstance(entry,dict) for entry in entries):
        raise ValueError("Bundle textures must be a list of objects")
    seen,paths = set(),set()
    for entry in entries:
        role,index = entry.get("role"),entry.get("layer")
        if not isinstance(role,str) or role not in _ROLES or type(index) is not int or index not in range(-1,len(layers)):
            raise ValueError("Invalid texture role or layer")
        relative = entry.get("path")
        if not isinstance(relative,str) or Path(relative).name != relative or "\\" in relative:
            raise ValueError("Texture paths must be plain filenames inside the bundle")
        key = (index,role)
        if key in seen or relative.casefold() in paths:
            raise ValueError("Duplicate texture role or path")
        seen.add(key); paths.add(relative.casefold())
        texture = (path.parent/relative).resolve()
        if texture.parent != path.parent or not texture.is_file() or _sha(texture) != entry.get("sha256"):
            raise ValueError(f"Missing or changed texture: {relative}")
        actual = _image_info(texture,role)
        if any(entry.get(k) != v for k,v in actual.items()):
            raise ValueError(f"Texture metadata differs from file: {relative}")
        if role not in ("detail_color","detail_normal") and (actual["width"],actual["height"]) != (manifest.get("width"),manifest.get("height")):
            raise ValueError(f"Incompatible texture dimensions: {relative}")
        if entry.get("color_space") not in (("srgb","linear") if role == "albedo" else ("linear",)):
            raise ValueError(f"Incompatible color space: {relative}")
        allowed = ("xyz-unorm","xyz-centered-unorm8") if role in ("normal","detail_normal") else ("white-top",) if role == "height" else ("residual-centered-unorm8",) if role == "detail_color" else ("unorm",)
        if entry.get("encoding") not in allowed:
            raise ValueError(f"Incompatible encoding: {relative}")
        if role in ("normal","detail_normal") and entry.get("normal_convention") not in ("opengl","directx"):
            raise ValueError(f"Invalid normal convention: {relative}")
    for index in range(len(layers)):
        for role in ("albedo","height","normal","roughness","metallic","ao","curvature"):
            if (index,role) not in seen: raise ValueError(f"Missing layer {index} {role}")
    for role in ("mask","edge","cavity","wear","detail_color","detail_normal"):
        if (-1,role) not in seen: raise ValueError(f"Missing {role}")
    detail_sizes = {(entry["width"],entry["height"]) for entry in entries if entry["role"] in ("detail_color","detail_normal")}
    if len(detail_sizes) != 1:
        raise ValueError("Detail color and normal dimensions must match")
    return manifest


def generate_batch(path: str | Path, output: str | Path, *, backend: str = "ptx") -> list[Path]:
    """Generate named recipe files in deterministic order, rejecting collisions."""
    path = Path(path).resolve()
    batch = _json(path)
    _unknown(batch,{"schema_version","recipes"},"batch")
    if batch.get("schema_version") != 1 or not isinstance(batch.get("recipes"),list) or not batch["recipes"]:
        raise ValueError("Batch needs schema_version 1 and a nonempty recipes list")
    if not all(isinstance(relative,str) and relative for relative in batch["recipes"]):
        raise ValueError("Batch recipes must be nonempty path strings")
    recipes = [(path.parent/relative).resolve() for relative in batch["recipes"]]
    resolved = [(p,_resolved(_json(p))) for p in recipes]
    names = [r["name"] for _,r in resolved]
    if len(set(n.casefold() for n in names)) != len(names):
        raise ValueError("Batch names collide")
    return [generate_bundle(r,Path(output)/r["name"],base_dir=p.parent,backend=backend)
            for p,r in sorted(resolved,key=lambda item:item[1]["name"])]


@click.group()
def main() -> None:
    """Generate and verify version 1 material bundles for the Unity URP profile."""


@main.command("generate")
@click.argument("recipe",type=click.Path(exists=True,dir_okay=False,path_type=Path))
@click.option("--output","-o",required=True,type=click.Path(path_type=Path))
@click.option("--backend",type=click.Choice(["ptx","cupy"]),default="ptx",show_default=True)
def generate_command(recipe: Path,output: Path,backend: str) -> None:
    """Generate a complete material from a JSON RECIPE."""
    try: click.echo(generate_bundle(_json(recipe),output,base_dir=recipe.parent,backend=backend))
    except (ValueError,OSError) as error: raise click.ClickException(str(error)) from error


@main.command("batch")
@click.argument("batch",type=click.Path(exists=True,dir_okay=False,path_type=Path))
@click.option("--output","-o",required=True,type=click.Path(path_type=Path))
@click.option("--backend",type=click.Choice(["ptx","cupy"]),default="ptx",show_default=True)
def batch_command(batch: Path,output: Path,backend: str) -> None:
    """Generate a collection of recipe files."""
    try:
        for path in generate_batch(batch,output,backend=backend): click.echo(path)
    except (ValueError,OSError) as error: raise click.ClickException(str(error)) from error


@main.command("verify")
@click.argument("bundle",type=click.Path(exists=True,path_type=Path))
def verify_command(bundle: Path) -> None:
    """Verify a bundle's metadata and every output hash."""
    try:
        result = load_bundle(bundle)
        click.echo(f"Verified {result['name']}: {len(result['textures'])} textures, schema 1")
    except (ValueError,OSError) as error: raise click.ClickException(str(error)) from error


if __name__ == "__main__":
    main()
