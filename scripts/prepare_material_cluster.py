"""Build small, reproducible authored cluster fixtures and their material bundles.

The geometric height/mask fields here are deliberate authored construction,
not reconstruction from albedo. Existing image-generation provenance remains
in textures/pom-validation/README.md. No LLM runs during regeneration.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from textureworks.bundle import generate_batch


def _smooth(edge0: float,edge1: float,value: np.ndarray) -> np.ndarray:
    t = np.clip((value-edge0)/(edge1-edge0),0,1)
    return t*t*(3-2*t)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root/"textures/material-cluster"
    destination = root/"demo/TextureWorksMaterialLab/Assets/TextureWorks/Bundles"
    source.mkdir(parents=True,exist_ok=True)
    n = 128
    u,v = np.meshgrid((np.arange(n)+.5)/n,(np.arange(n)+.5)/n)
    rng = np.random.default_rng(731)
    noise = rng.random((n,n))

    def image(name: str,data: np.ndarray,scalar: bool = False) -> str:
        path = source/(name+".png")
        encoded = np.rint(np.clip(data,0,1)*(65535 if scalar else 255)).astype(np.uint16 if scalar else np.uint8)
        Image.fromarray(encoded).save(path)
        return path.name

    source_names = {"masonry":"limestone-blocks","wood":"oak-planks","painted-metal":"machined-metal"}
    inherited = {}
    for name,original in source_names.items():
        path = root/"textures/pom-validation"/(original+".png")
        with Image.open(path) as im:
            inherited[name] = np.asarray(im.convert("RGB").resize((n,n),Image.Resampling.LANCZOS),dtype=np.float32)/255
            if name == "masonry":
                # A verified interior crop removes the original mortar layout before
                # applying the new authored courses. Crop is recorded below.
                crop = im.convert("RGB").crop((int(im.width*.36),int(im.height*.035),int(im.width*.63),int(im.height*.15)))
                inherited[name] = np.asarray(crop.resize((n,n),Image.Resampling.LANCZOS),dtype=np.float32)/255
            # Author periodic microdetail explicitly. This fixture construction is
            # not a claim that wrapping a convolution makes an arbitrary input tile.
            du,dv = np.meshgrid((np.arange(256)+.5)/256,(np.arange(256)+.5)/256)
            micro = np.full_like(du,.5)
            micro_rng = np.random.default_rng({"masonry":741,"wood":742,"painted-metal":743}[name])
            for harmonic in range(12):
                fx = int(micro_rng.integers(12,60)); fy = int(micro_rng.integers(12,60))
                if name == "wood": fy = int(micro_rng.integers(1,5))
                micro += .024*np.sin(2*np.pi*(fx*du+fy*dv)+micro_rng.uniform(0,2*np.pi))
            image(name+"-detail",np.repeat(micro[:,:,None],3,axis=2))
    records = []
    for name in ("masonry","wood","painted-metal","fine-detail"):
        if name == "masonry":
            # Authored staggered courses; mortar is recessed in both albedo/height.
            row = np.floor(v*3)
            cell = (u*3+.5*(row%2))%1
            edge = np.minimum(np.minimum(cell,1-cell),np.minimum((v*3)%1,1-(v*3)%1))
            block = _smooth(.055,.15,edge)
            ha = .23+.67*block+.025*(noise-.5)*block
            hb = np.minimum(ha+.10, .96)
            a = inherited[name]*(.42+.43*block[:,:,None])
            b = np.broadcast_to([.18,.145,.095],a.shape)*( .85+.15*noise[:,:,None])
            mask = (1-block)*.95
            mask_provenance = "Authored mortar recess mask from the same staggered-course construction as height."
            depth,rough_a,rough_b,metal_a,metal_b = .035,.8,.94,0,0
        elif name == "wood":
            seams = _smooth(.015,.065,np.minimum((u*4)%1,1-(u*4)%1))
            grain = .5+.5*np.sin(2*np.pi*(v*8+.12*np.sin(u*25)))
            ha = .35+.52*seams+.05*grain
            hb = np.maximum(ha-.025,0)
            a = inherited[name]
            b = np.clip(a*1.17+.025,0,1)
            # Broad use areas away from face boundaries, without implying mesh wear.
            mask = _smooth(.25,.7,.5+.5*np.sin(u*17)*np.cos(v*7))*.85*seams
            mask_provenance = "Authored surface finish removal; this mask does not describe crate silhouette wear."
            depth,rough_a,rough_b,metal_a,metal_b = .018,.55,.8,0,0
        elif name == "painted-metal":
            border = np.minimum.reduce([u,1-u,v,1-v])
            inset = _smooth(.06,.10,border)
            panel = .12*np.sin(np.pi*u)**8*np.sin(np.pi*v)**8
            ha = .86-panel+.035*(1-inset)
            hb = ha-.15
            a = np.broadcast_to([.105,.31,.29],(n,n,3))*(.94+.06*noise[:,:,None])
            b = inherited[name]*.6+.13
            # Face UVs are [0,1] on each cabinet cube face. This is a real authored
            # face-edge mask, independent of albedo, for those known mesh borders.
            chip = 1-_smooth(.018,.07,border)
            scratch = _smooth(.992,.999,np.sin(u*63+v*12))*_smooth(.1,.25,border)*_smooth(.35,.75,noise)
            mask = np.clip(chip*(.8+.2*noise)+scratch*.9,0,1)
            mask_provenance = "Authored mask for cabinet cube face UV borders plus surface scratches; mesh-layout knowledge, not albedo inference."
            depth,rough_a,rough_b,metal_a,metal_b = .012,.43,.32,0,1
        else:
            # Analytic woven textile: independently authored height and albedo.
            wave = .5+.25*np.cos(2*np.pi*u*16)+.25*np.cos(2*np.pi*v*16)
            ha = .32+.5*wave
            hb = np.minimum(ha+.06,.95)
            a = np.array([.29,.34,.40])[None,None,:]*(.6+.4*wave[:,:,None])
            b = np.broadcast_to([.34,.29,.21],a.shape)*(.85+.15*wave[:,:,None])
            mask = (1-wave)*.8
            du,dv = np.meshgrid((np.arange(256)+.5)/256,(np.arange(256)+.5)/256)
            fine = .5+.2*np.sin(du*np.pi*96)+.2*np.sin(dv*np.pi*96)
            image(name+"-detail",np.repeat(fine[:,:,None],3,axis=2))
            mask_provenance = "Analytic weave recess mask; known synthetic ground truth, not a reconstruction claim."
            depth,rough_a,rough_b,metal_a,metal_b = .003,.72,.92,0,0
        a_path,b_path = image(name+"-a",a),image(name+"-b",b)
        ha_path,hb_path = image(name+"-height-a",ha,True),image(name+"-height-b",hb,True)
        mask_path = image(name+"-mask",mask,True)
        edge_path = image(name+"-edge",mask if name == "painted-metal" else np.zeros_like(mask),True)
        recipe = {"schema_version":1,"name":name,"preset":name,"physical_size":[1,1],"relief_depth":depth,
            "boundary":"clamp" if name == "painted-metal" else "wrap","seed":731,
            "layers":[{"name":{"masonry":"Limestone","wood":"Finished oak","painted-metal":"Paint","fine-detail":"Weave"}[name],
                        "albedo":a_path,"height":ha_path,"roughness":rough_a,"metallic":metal_a,"edge":edge_path},
                       {"name":{"masonry":"Recess grime","wood":"Raw oak","painted-metal":"Steel","fine-detail":"Settled dirt"}[name],
                        "albedo":b_path,"height":hb_path,"roughness":rough_b,"metallic":metal_b}],
            "mask":{"path":mask_path,"provenance":mask_provenance},
            "detail":{"source":{"path":name+"-detail.png","provenance":"Authored periodic Fourier microdetail generated by prepare_material_cluster.py."
                                    if name != "fine-detail" else "Analytic sine weave generated by prepare_material_cluster.py."},
                      "physical_size":[.25,.25],"radius":4,"tiling":4,"normal_strength":.22,
                      "color_strength":.3,"roughness_strength":.1,"fade_start":2,"fade_end":6,"boundary":"wrap"},
            "composition":{"coverage":.5,"blend_width":.25,"height_bias":.5,"quality":"balanced"},
            "provenance":"Authored geometric fixture from scripts/prepare_material_cluster.py. "+mask_provenance}
        path = source/(name+".json")
        path.write_text(json.dumps(recipe,indent=2)+"\n",encoding="utf-8")
        records.append(path.name)
    (source/"batch.json").write_text(json.dumps({"schema_version":1,"recipes":records},indent=2)+"\n",encoding="utf-8")
    provenance = {"script":"scripts/prepare_material_cluster.py","seed":731,"size":128,"detail_size":256,
                  "masonry_crop_normalized":[.36,.035,.63,.15],"detail_seeds":{"masonry":741,"wood":742,"painted-metal":743},
                  "originals":{name:{"path":"textures/pom-validation/"+original+".png",
                    "sha256":hashlib.sha256((root/"textures/pom-validation"/(original+".png")).read_bytes()).hexdigest()}
                               for name,original in source_names.items()},
                  "limitation":"Authored synthetic geometric construction with generated image color; not physical reconstruction accuracy."}
    (source/"provenance.json").write_text(json.dumps(provenance,indent=2)+"\n",encoding="utf-8")
    for path in generate_batch(source/"batch.json",destination): print(path)


if __name__ == "__main__":
    main()
