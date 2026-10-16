"""Read-only source aggregation and figures for the self-contained R140v2 report."""
from __future__ import annotations

import json
from pathlib import Path
from collections import Counter

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.facecolor": "white"})

def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8-sig"))

def rounded_rows(frame):
    rows=[]
    for item in frame.to_dict(orient="records"):
        rows.append({k:(None if pd.isna(v) else v.item() if isinstance(v,np.generic) else v)
                     for k,v in item.items()})
    return rows

train = read("runs/formal_8192/training_complete.json")
audit = read("results/final_audit.json")
complete = read("results/complete.json")
assert train["unique_updates"] == 8192 and audit["output_sha256_verified"] == 930
assert complete["images"] == 930 and complete["circles"] == 8370
source_manifest=read("data/manifest.json")
cfg=read("config/TRAIN.json")
model=read("config/model.json")
plan=read("evaluation/capture_plan.json")
summary=pd.read_csv(ROOT / "results/comparison/displacement_summary.csv")
geometry=pd.read_csv(ROOT / "results/comparison/shape_size_summary.csv")
sem=pd.read_csv(ROOT / "results/comparison/SEM_comparison.csv")
paired=pd.read_csv(ROOT / "results/comparison/paired_scan_intervals.csv")
position=pd.read_csv(ROOT / "results/comparison/position_statistics.csv")
scans=pd.read_csv(ROOT / "results/comparison/scan_statistics.csv")
displacements=pd.read_csv(ROOT / "results/comparison/all_displacements.csv")
weights=pd.read_csv(ROOT / "results/PSF_all930_weights.csv")
psf_test=pd.read_csv(ROOT / "results/PSF_on_off_generated32.csv")
timing=pd.read_csv(ROOT / "results/reconstruction_runtime.csv")
gates=[read(str(p.relative_to(ROOT))) for p in sorted((ROOT / "runs/formal_8192").glob("stability_step*.json"))]
dev=[read(str(p.relative_to(ROOT))) for p in sorted((ROOT / "runs/formal_8192/evaluations").glob("dev_*.json"))]
test=read("runs/formal_8192/evaluations/test_08192.json")
categories=Counter((x["split"],x["category"]) for x in source_manifest["entries"])

late=[]
for (name,kind),g in displacements[displacements.run_index>6].groupby(["model","kind"]):
    late.append(dict(model=name,kind=kind,mae_nm=float(g.error_nm.abs().mean()),
                     repeatability_nm=float(g.groupby("j").error_nm.std(ddof=1).mean()),
                     maximum_error_nm=float(g.error_nm.abs().max())))
late=pd.DataFrame(late)
order=[r["run"] for r in plan["runs"]]
scan_rows=[]
for ix,run in enumerate(order,1):
    a=scans[(scans.run==run)&(scans.kind=="adjacent")].set_index("model").mae_nm
    b=scans[(scans.run==run)&(scans.kind=="start")].set_index("model").mae_nm
    scan_rows.append(dict(scan=ix,run=run,new_adj=float(a["R140v2-StableUNet"]),
                          r137_adj=float(a["R137-WeakPSF"]),new_start=float(b["R140v2-StableUNet"]),
                          r137_start=float(b["R137-WeakPSF"])))
position_rows=[]
for j in range(1,31):
    n=position[(position.model=="R140v2-StableUNet")&(position.kind=="adjacent")&(position.position==j)].iloc[0]
    r=position[(position.model=="R137-WeakPSF")&(position.kind=="adjacent")&(position.position==j)].iloc[0]
    s=position[(position.model=="R140v2-StableUNet")&(position.kind=="start")&(position.position==j)].iloc[0]
    position_rows.append(dict(position=j,pi_um=float(n.mean_PI_um),new_adj_bias=float(n.mean_error_nm),
                              new_adj_repeat=float(n.repeat_sd_nm),r137_adj_repeat=float(r.repeat_sd_nm),
                              new_start_bias=float(s.mean_error_nm)))

data=dict(config=cfg,model=model,training=train,audit=audit,complete=complete,
          categories=[dict(split=a,category=b,count=c) for (a,b),c in sorted(categories.items())],
          unique_parents=len({x["parent_id"] for x in source_manifest["entries"]}),
          unique_geometries=len({x["geometry_sha256"] for x in source_manifest["entries"]}),
          displacement=rounded_rows(summary),late24=rounded_rows(late),geometry=rounded_rows(geometry),
          sem=rounded_rows(sem),paired=rounded_rows(paired),scan_rows=scan_rows,position_rows=position_rows,
          gates=gates,dev=[dict(step=x["step"],total=x["means"]["total"]) for x in dev],
          test=test["means"],
          psf=dict(weights_mean={k:float(v) for k,v in weights.filter(regex="^w").mean().items()},
                   weights_min={k:float(v) for k,v in weights.filter(regex="^w").min().items()},
                   weights_max={k:float(v) for k,v in weights.filter(regex="^w").max().items()},
                   generated32_on_mean=float(psf_test.loss_on.mean()),
                   generated32_off_mean=float(psf_test.loss_off.mean()),
                   generated32_rms_gray_mean=float(psf_test.output_rms_gray.mean())),
          runtime={key:{metric:float(getattr(timing[key],metric)()) for metric in ("mean","median","min","max")}
                   for key in ("total_reconstruction_seconds","end_to_end_load_infer_save_seconds")},
          measurement_runtime=read("results/comparison/measurement_timing.json"),
          calibration=read("evaluation/calibration.json"),
          measure_config={key:read("evaluation/measurement_config.json")[key] for key in
                          ("sample_count","acm_iterations","normal_half_width_px","profile_step_px","profile_sigma_px","patch_half","object_um_per_px","pillars","aggregation")},
          psf_lineage={key:read("config/INHERITED_PSF_PROVENANCE.json")[key] for key in
                       ("only_calibration_buffers_transferred","learned_V42_weights_transferred","independent_physical_calibration_qualified","calibration_vs_training")})
(OUT/"doc_data.json").write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")

COL={"Raw":"#888888","R129":"#4184ac","R130-Clean":"#d98b3b","R137-WeakPSF":"#2e8b74",
     "R138-V42PSF8":"#9273b8","R139-UNetRecurrent":"#8a6380","R140v2-StableUNet":"#b93449"}

fig,ax=plt.subplots(figsize=(12.5,4.3))
ax.set_xlim(0,12.5);ax.set_ylim(0,4.3);ax.axis("off")
def box(x,y,w,h,title,detail,color="#e8f0f5"):
    p=FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.08,rounding_size=0.1",facecolor=color,
                     edgecolor="#63717d",linewidth=1.1)
    ax.add_patch(p);ax.text(x+w/2,y+h*.67,title,ha="center",va="center",fontsize=10.4,fontweight="bold")
    ax.text(x+w/2,y+h*.30,detail,ha="center",va="center",fontsize=8.3,color="#28343d")
def arrow(x1,y1,x2,y2):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle="-|>",mutation_scale=13,
                                 linewidth=1.2,color="#596775"))
box(.1,2.55,1.55,1.0,"Raw image","native size", "#edf1f4")
box(2.0,2.55,1.65,1.0,"Inputs","7 local channels")
box(4.0,2.55,2.0,1.0,"Encoder","32 > 64 > 96 > 128")
box(6.4,2.55,2.0,1.0,"Decoder","skips + anti-alias")
box(8.8,2.55,1.6,1.0,"Optical cue","half scale, pass 4", "#fff1d7")
box(10.8,2.55,1.55,1.0,"Update head","0.1 logit gain", "#f6e4e7")
for a,b in [(1.65,2),(3.65,4),(6,6.4),(8.4,8.8),(10.4,10.8)]:arrow(a,3.05,b,3.05)
box(4.15,.55,4.25,.95,"Shared recurrent correction","4 passes; raw anchor + bounded residual", "#e7f3ed")
arrow(11.55,2.55,11.55,1.45);arrow(11.55,1.45,8.55,1.45);arrow(8.55,1.45,8.55,1.03)
arrow(4.15,1.03,2.9,1.03);arrow(2.9,1.03,2.9,2.55)
ax.text(6.2,.17,"One shared network; PSF is inserted only on the fourth pass",ha="center",fontsize=8.5,color="#4d5964")
fig.tight_layout();fig.savefig(FIG/"architecture.png",dpi=190);plt.close(fig)

models=["Raw","R129","R130-Clean","R137-WeakPSF","R138-V42PSF8","R140v2-StableUNet"]
labels=["Raw","R129","R130","R137","R138","R140v2"]
fig,axes=plt.subplots(1,2,figsize=(11,4),layout="constrained")
for ax,key,title in zip(axes,("mae_nm","repeatability_nm"),("Adjacent PI error","Adjacent repeat SD")):
    vals=[float(summary[(summary.model==m)&(summary.kind=="adjacent")][key].iloc[0]) for m in models]
    bars=ax.barh(labels,vals,color=[COL[m] for m in models]);ax.invert_yaxis()
    ax.set_xlim(0,max(vals)*1.19);ax.set_xlabel("nm, lower is better");ax.set_title(title)
    for bar,v in zip(bars,vals):ax.text(v+.07,bar.get_y()+bar.get_height()/2,f"{v:.3f}",va="center",fontsize=8.5)
fig.savefig(FIG/"adjacent_comparison.png",dpi=190);plt.close(fig)

fig,ax=plt.subplots(figsize=(10.5,4),layout="constrained")
for m in ["Raw","R129","R137-WeakPSF","R140v2-StableUNet"]:
    p=position[(position.model==m)&(position.kind=="adjacent")].sort_values("position")
    ax.plot(p.position,p.repeat_sd_nm,label=m,color=COL[m],linewidth=2)
ax.set(xlabel="Step position (1 to 30)",ylabel="Repeat SD across 30 scans (nm)",
       title="Adjacent displacement repeatability by position")
ax.grid(alpha=.18);ax.legend(ncol=4,fontsize=8)
fig.savefig(FIG/"position_repeatability.png",dpi=190);plt.close(fig)

fig,axes=plt.subplots(1,3,figsize=(11.5,3.8),layout="constrained")
for ax,key,title in zip(axes,("diameter_repeat_sd_nm","contour_repeat_sd_nm","shape_repeat_sd_nm"),
                        ("Diameter repeat SD","Contour repeat SD","Size removed shape SD")):
    vals=[float(geometry[geometry.model==m][key].iloc[0]) for m in models]
    ax.bar(range(len(models)),vals,color=[COL[m] for m in models]);ax.set_xticks(range(len(models)),labels,rotation=45,ha="right")
    ax.set_title(title,fontsize=10);ax.set_ylabel("nm, lower is better");ax.grid(axis="y",alpha=.15)
fig.savefig(FIG/"shape_repeatability.png",dpi=190);plt.close(fig)

fig,axes=plt.subplots(1,2,figsize=(11,4),layout="constrained")
for ax,key,title in zip(axes,("mean_diameter_difference_nm","de_size_shape_difference_nm"),
                        ("Mean diameter minus SEM","Size removed contour difference")):
    vals=[float(sem[(sem.model==m)&(sem.mapping_candidate==2)][key].iloc[0]) for m in models]
    bars=ax.barh(labels,vals,color=[COL[m] for m in models]);ax.invert_yaxis();ax.set_title(title)
    ax.set_xlabel("nm, lower magnitude is better");ax.set_xlim(0,max(vals)*1.25)
    for b,v in zip(bars,vals):ax.text(v+1,b.get_y()+b.get_height()/2,f"{v:.1f}",va="center",fontsize=8)
fig.savefig(FIG/"sem_comparison.png",dpi=190);plt.close(fig)

fig,axes=plt.subplots(1,2,figsize=(11,3.7),layout="constrained")
w=weights.filter(regex="^w")
axes[0].bar(w.columns,[float(w[c].mean()) for c in w],color="#c89549")
axes[0].set(ylim=(0,.16),ylabel="Mean mixture weight",title="Eight PSF candidate weights across 930 frames")
axes[0].axhline(.125,linestyle="--",color="#777",linewidth=1)
examples=audit["real_examples"]
axes[1].bar([str(x["global_index"]) for x in examples],
            [x["PSF_on_off_rms_gray"] for x in examples],color="#b93449")
axes[1].set(xlabel="Fixed real frame index",ylabel="RMS output change (8-bit gray)",
            title="PSF on versus off on four real frames")
fig.savefig(FIG/"psf_activity.png",dpi=190);plt.close(fig)

f=plan["frames"][0]
raw=cv2.imread(f["source"]["path"],cv2.IMREAD_GRAYSCALE).astype(np.float32)/255.0
with np.load(ROOT/"results/reconstruction"/f["run"]/"01.npz") as z:
    current=z["output"]
with np.load(ROOT.parent/"R137_WeakPSFFeature/results/reconstruction"/f["run"]/"01.npz") as z:
    old=z["output"]
with np.load(ROOT/"evaluation/baseline_centers/Raw"/(f["run"]+".npz")) as z:
    raw_points=z["points"][0,4]
with np.load(ROOT/"results/centers"/(f["run"]+".npz")) as z:
    current_points=z["points"][0,4]
with np.load(ROOT.parent/"R137_WeakPSFFeature/results/centers"/(f["run"]+".npz")) as z:
    old_points=z["points"][0,4]
x0,x1,y0,y1=1594,1648,728,782
vmin=float(np.quantile(np.r_[raw[y0:y1,x0:x1].ravel(),old[y0:y1,x0:x1].ravel(),
                             current[y0:y1,x0:x1].ravel()],.02))
vmax=float(np.quantile(np.r_[raw[y0:y1,x0:x1].ravel(),old[y0:y1,x0:x1].ravel(),
                             current[y0:y1,x0:x1].ravel()],.98))
fig,axes=plt.subplots(1,3,figsize=(10.4,3.8),layout="constrained")
for ax,img,points,title in zip(axes,(raw,old,current),(raw_points,old_points,current_points),
                               ("Raw","R137","R140v2")):
    ax.imshow(img[y0:y1,x0:x1],cmap="gray",vmin=vmin,vmax=vmax,interpolation="nearest")
    ax.plot(points[:,0]-x0,points[:,1]-y0,color="#29d9b2",linewidth=1.15)
    ax.set_title(title);ax.set_xlim(0,x1-x0);ax.set_ylim(y1-y0,0);ax.axis("off")
fig.savefig(FIG/"qualitative_crop.png",dpi=220);plt.close(fig)

print("ASSETS_READY",len(data["scan_rows"]),len(data["position_rows"]),len(list(FIG.glob("*.png"))))
