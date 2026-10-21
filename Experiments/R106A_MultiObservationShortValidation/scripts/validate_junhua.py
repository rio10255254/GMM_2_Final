from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
RUN_SHORT = ROOT / "scripts" / "run_short.py"
R105C = ROOT.parent / "R105C_JunHuaMultiObservationFeasibility"
SOURCE = Path(r"D:\NTU_ImageDataset\Pitch1um_Y_100\Raw")
RESULTS = ROOT / "results"
REPORTS = ROOT / "reports"
SCALE = 5


def load_short_module():
    spec = importlib.util.spec_from_file_location("r106a_short_for_real", RUN_SHORT)
    if spec is None or spec.loader is None:
        raise RuntimeError(RUN_SHORT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_model(module, device):
    checkpoint = torch.load(ROOT / "weights" / "r106a_step1500.pth", map_location=device, weights_only=False)
    model = module.ReferenceEvidenceNet().to(device)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval()
    return model


def read_small(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return cv2.resize(image, (1024, 1024), interpolation=cv2.INTER_AREA).astype(np.float32)


def rough_center(image):
    background = cv2.GaussianBlur(image, (0, 0), 35.0, borderType=cv2.BORDER_REFLECT_101)
    positive = np.maximum(image - background - 2.0, 0.0)
    threshold = float(np.percentile(positive[positive > 0], 70))
    weights = np.where(positive >= threshold, positive, 0.0)
    yy, xx = np.mgrid[: image.shape[0], : image.shape[1]].astype(np.float32)
    total = max(float(weights.sum()), 1e-9)
    return float((xx * weights).sum() / total), float((yy * weights).sum() / total)


def crop_model(image, center):
    crop = cv2.getRectSubPix(image, (400, 400), center)
    return (cv2.resize(crop, (96, 96), interpolation=cv2.INTER_AREA) / 255.0).astype(np.float32)


def circle_fit(image):
    smooth = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 0.8, borderType=cv2.BORDER_REFLECT_101)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3); gradient = np.sqrt(gx * gx + gy * gy)
    yy, xx = np.mgrid[:96, :96].astype(np.float64); distance = np.sqrt((xx - 48.0) ** 2 + (yy - 48.0) ** 2); annulus = (distance >= 17) & (distance <= 36)
    selected = annulus & (gradient >= np.percentile(gradient[annulus], 65)); x, y = xx[selected], yy[selected]
    radius = 26.0
    for _ in range(4):
        design = np.stack([2*x, 2*y, np.ones_like(x)], 1); target = x*x+y*y; cx, cy, constant = np.linalg.lstsq(design, target, rcond=None)[0]; radius = float(np.sqrt(max(constant+cx*cx+cy*cy, 0))); residual = np.abs(np.sqrt((x-cx)**2+(y-cy)**2)-radius); keep = residual < np.percentile(residual,80); x,y=x[keep],y[keep]
    return {"cx":float(cx),"cy":float(cy),"radius":radius}


def edge_energy(image):
    smooth=cv2.GaussianBlur(image.astype(np.float32),(0,0),0.8,borderType=cv2.BORDER_REFLECT_101); gx=cv2.Sobel(smooth,cv2.CV_32F,1,0,ksize=3); gy=cv2.Sobel(smooth,cv2.CV_32F,0,1,ksize=3); return float(np.mean(np.sqrt(gx*gx+gy*gy)))


@torch.inference_mode()
def infer(module, model, frames, used, device):
    tensor=torch.from_numpy(frames[None]).to(device); details=model(tensor,module.make_valid(1,used,device)); return details["output"][0,0].cpu().numpy(),details["weights"].mean(dim=(2,3))[0].cpu().numpy()


def preview(rows, images):
    indices=[0,25,50,75,99]; columns=["Reference","R106A N=1","R106A N=2","R106A cross N=4","N4-N2 x8","Wrong-bundle N4"]
    panel=175;gap=10;canvas=Image.new("RGB",(gap+len(columns)*(panel+gap),34+len(indices)*214+gap),"white");draw=ImageDraw.Draw(canvas);font=ImageFont.load_default()
    for c,label in enumerate(columns):draw.text((gap+c*(panel+gap),10),label,fill="black",font=font)
    for r,i in enumerate(indices):
        item=images[i];values=[item["ref"],item["n1"],item["n2"],item["n4"],np.abs(item["n4"]-item["n2"])*8,item["wrong"]];top=34+r*214
        for c,value in enumerate(values):
            clipped=np.clip(value,0,1);rgb=np.stack([clipped,clipped*.18,np.zeros_like(clipped)],-1) if c==4 else np.repeat(clipped[...,None],3,-1);im=Image.fromarray(np.round(rgb*255).astype(np.uint8),"RGB").resize((panel,panel),Image.Resampling.BICUBIC);canvas.paste(im,(gap+c*(panel+gap),top))
        row=rows[i];draw.text((gap,top+panel+7),f"bundle {i:03d} | N2 center {row['n2_center_shift_px']:.3f}px | N4 {row['n4_center_shift_px']:.3f}px | N4-N2 {row['n4_minus_n2_mae_gray']:.3f} gray",fill="black",font=font)
    canvas.save(REPORTS/"R106A_JUNHUA_QA.png",optimize=True)


def main():
    module=load_short_module();device=torch.device("cuda:0" if torch.cuda.is_available() else "cpu");model=load_model(module,device)
    synthetic=json.loads((RESULTS/"synthetic_summary.json").read_text(encoding="utf-8")); files=sorted(SOURCE.glob("*.bmp")); registration=json.loads((R105C/"results"/"cross_position_manifest.json").read_text(encoding="utf-8"))
    rows=[];images={}
    for position in range(100):
        first=read_small(files[2*position]);second=read_small(files[2*position+1]);next_first=read_small(files[2*(position+1)]);next_second=read_small(files[2*(position+1)+1]);record=registration[position]
        warp=np.asarray([[1,0,record["content_shift_dx_px"]/SCALE],[0,1,record["content_shift_dy_px"]/SCALE]],np.float32)
        next_first=cv2.warpAffine(next_first,warp,(1024,1024),flags=cv2.INTER_LINEAR|cv2.WARP_INVERSE_MAP,borderMode=cv2.BORDER_REFLECT_101);next_second=cv2.warpAffine(next_second,warp,(1024,1024),flags=cv2.INTER_LINEAR|cv2.WARP_INVERSE_MAP,borderMode=cv2.BORDER_REFLECT_101)
        center=rough_center(.5*(first+second));frames=np.stack([crop_model(first,center),crop_model(second,center),crop_model(next_first,center),crop_model(next_second,center)])
        far=(position+37)%101;far_first=read_small(files[2*far]);far_second=read_small(files[2*far+1]);wrong_frames=np.stack([frames[0],frames[1],crop_model(far_first,center),crop_model(far_second,center)])
        n1,w1=infer(module,model,frames,1,device);n2,w2=infer(module,model,frames,2,device);n4,w4=infer(module,model,frames,4,device);wrong,ww=infer(module,model,wrong_frames,4,device)
        singles=[]
        for j in range(4):
            reordered=frames.copy();reordered[[0,j]]=reordered[[j,0]];value,_=infer(module,model,reordered,1,device);singles.append(value)
        jack=np.std(np.stack(singles),axis=0);ref=frames[0];gref=circle_fit(ref);gn1,gn2,gn4,gwrong=map(circle_fit,[n1,n2,n4,wrong])
        shift=lambda g:float(np.hypot(g["cx"]-gref["cx"],g["cy"]-gref["cy"]))
        row={"bundle_index":position,"n1_center_shift_px":shift(gn1),"n2_center_shift_px":shift(gn2),"n4_center_shift_px":shift(gn4),"wrong_center_shift_px":shift(gwrong),"n1_radius_change_px":gn1["radius"]-gref["radius"],"n2_radius_change_px":gn2["radius"]-gref["radius"],"n4_radius_change_px":gn4["radius"]-gref["radius"],"n1_edge_ratio":edge_energy(n1)/edge_energy(ref),"n2_edge_ratio":edge_energy(n2)/edge_energy(ref),"n4_edge_ratio":edge_energy(n4)/edge_energy(ref),"n2_minus_n1_mae_gray":float(np.mean(np.abs(n2-n1))*255),"n4_minus_n2_mae_gray":float(np.mean(np.abs(n4-n2))*255),"wrong_minus_n1_mae_gray":float(np.mean(np.abs(wrong-n1))*255),"n2_second_weight":float(w2[1]),"n4_neighbor_weight_median":float(np.median(w4[2:])),"wrong_neighbor_weight_median":float(np.median(ww[2:])),"jackknife_gray":float(jack.mean()*255)};rows.append(row)
        if position in {0,25,50,75,99}:images[position]={"ref":ref,"n1":n1,"n2":n2,"n4":n4,"wrong":wrong}
        if position%10==0 or position==99:print(json.dumps({"stage":"junhua_locked","bundle":position}),flush=True)
    metrics=[k for k in rows[0] if k!="bundle_index"];median={k:float(np.median([r[k] for r in rows])) for k in metrics};p95={k:float(np.percentile([r[k] for r in rows],95)) for k in metrics}
    directions={"n2_center_not_worse":median["n2_center_shift_px"]<=median["n1_center_shift_px"]+0.05,"n4_center_not_worse":median["n4_center_shift_px"]<=median["n2_center_shift_px"]+0.05,"n2_uses_observation":median["n2_minus_n1_mae_gray"]>0.02,"n4_uses_cross_observation":median["n4_minus_n2_mae_gray"]>0.02,"n4_edge_not_worse":median["n4_edge_ratio"]>=median["n2_edge_ratio"]*.98,"wrong_weight_rejected":median["wrong_neighbor_weight_median"]<median["n4_neighbor_weight_median"]*.75,"wrong_falls_back":median["wrong_minus_n1_mae_gray"]<=median["n4_minus_n2_mae_gray"]*1.5}
    decision={"directions":directions,"real_gate_passed":all(directions.values()),"synthetic_gate_passed":bool(synthetic["decision"]["synthetic_gate_passed"]),"full_r106_authorized":bool(all(directions.values()) and synthetic["decision"]["synthetic_gate_passed"]),"interpretation":"Real JunHua gate passed, but full R106 still requires the synthetic gate." if all(directions.values()) else "Real JunHua gate also failed; do not start full R106."}
    summary={"status":"complete","bundles":len(rows),"median":median,"p95":p95,"decision":decision};(RESULTS/"junhua_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8");(RESULTS/"junhua_manifest.json").write_text(json.dumps(rows,indent=2),encoding="utf-8");preview(rows,images)
    (REPORTS/"R106A_JUNHUA_RESULTS.md").write_text("# R106A Locked JunHua Short Gate\n\n```json\n"+json.dumps(summary,indent=2)+"\n```\n",encoding="utf-8");print(json.dumps({"status":"complete","decision":decision,"median":median}),flush=True);return 0


if __name__=="__main__":raise SystemExit(main())
