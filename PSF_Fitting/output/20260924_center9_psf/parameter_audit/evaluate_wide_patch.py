"""Compare longer-tail crop against the same narrow-crop fitter on two splits."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.io import loadmat
from scipy.signal import fftconvolve


ROOT = Path(__file__).resolve().parent
RUN = ROOT.parent
SPLITS = {
    "A": ([1,13,25], "profile_gain_0p1", "loss_mask_hold3.bmp"),
    "B": ([4,7,12,18,23], "confirm_profile_gain_0p1", "loss_mask_hold3_B.bmp"),
}


def main():
    truth = np.load(RUN / "sem_shape_forward_validation" / "gt_sem_contour_20x_float.npz")["image"]
    rows=[]
    for split,(frames,narrow_name,hold10_name) in SPLITS.items():
        wide=loadmat(ROOT / f"wide_profile_gain_{split}" / "PSF_fitted_2D_FOVstack.mat")["psf_grid"].reshape(101,101,len(frames))
        narrow=loadmat(ROOT / narrow_name / "PSF_fitted_2D_FOVstack.mat")["psf_grid"].reshape(101,101,len(frames))
        train=cv2.imread(str(ROOT / "wide_input" / f"loss_mask_train6_{split}.bmp"),0)>0
        hold12=cv2.imread(str(ROOT / "wide_input" / f"loss_mask_hold3_{split}.bmp"),0)>0
        hold10=cv2.imread(str(RUN / "fit_input" / hold10_name),0)>0
        yy,xx=np.mgrid[:101,:101]
        for index,frame in enumerate(frames):
            observed=cv2.imread(str(ROOT / "wide_input" / f"fit_input_{frame:02d}.bmp"),0).astype(float)/255
            for case,kernel in (("wide",wide[:,:,index]),("narrow",narrow[:,:,index])):
                psf=kernel/kernel.sum()
                prediction=fftconvolve(truth,psf,mode="same")
                gain=float(np.dot(observed[train],prediction[train])/np.dot(prediction[train],prediction[train]))
                rows.append({"split":split,"frame":frame,"case":case,
                             "heldout_radius10_mse":float(np.mean((observed[hold10]-gain*prediction[hold10])**2)),
                             "heldout_radius12_mse":float(np.mean((observed[hold12]-gain*prediction[hold12])**2)),
                             "centroid_radial_offset_px":float(np.hypot(np.sum((xx-50)*psf),np.sum((yy-50)*psf)))})
    with (ROOT / "wide_patch_metrics.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=[]
    for split in SPLITS:
        for case in ("wide","narrow"):
            subset=[r for r in rows if r["split"]==split and r["case"]==case]
            summary.append({"split":split,"case":case,
                            "mean_heldout_radius10_mse":float(np.mean([r["heldout_radius10_mse"] for r in subset])),
                            "mean_heldout_radius12_mse":float(np.mean([r["heldout_radius12_mse"] for r in subset])),
                            "max_centroid_radial_offset_px":max(r["centroid_radial_offset_px"] for r in subset)})
    (ROOT / "wide_patch_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":main()
