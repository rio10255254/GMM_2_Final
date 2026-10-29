"""Score frozen parameter choices on untouched frames and different pillars."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.io import loadmat
from scipy.ndimage import gaussian_filter
from scipy.signal import fftconvolve
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parent
RUN = ROOT.parent
IDS = [36, 35, 34, 30, 29, 28, 24, 23, 22]
TILE = [69, 150, 231]
CASES = ["confirm_original", "confirm_weight_0", "confirm_weight_0p1", "confirm_bads_restarts", "confirm_amp_fixed", "confirm_profile_gain_0", "confirm_profile_gain_0p1"]
JULY = Path(str(PROJECT_ROOT / 'PSF_Fitting/output/pillar_via_junction_psf_20260713/20x/fit_result/PSF_fitted_2D_FOVstack.mat'))


def records(path):
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def metrics(observed, prediction, train, hold):
    gain = float(np.dot(observed[train], prediction[train]) / np.dot(prediction[train], prediction[train]))
    y, p = observed[hold], gain * prediction[hold]
    return gain, float(np.mean((y-p)**2)), float(np.mean(np.abs(y-p))), float(np.corrcoef(y,p)[0,1])


def gradient_mae(observed, prediction, hold):
    def normalized_gradient(image):
        gx = cv2.Sobel(image, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(image, cv2.CV_64F, 0, 1, ksize=3)
        magnitude = np.hypot(gx, gy)
        return (magnitude - magnitude.min()) / max(magnitude.max() - magnitude.min(), 1e-12)
    return float(np.mean(np.abs(normalized_gradient(observed)[hold] - normalized_gradient(prediction)[hold])))


def main():
    split = json.loads((ROOT / "confirmation_split.json").read_text(encoding="utf-8"))
    assert split["selection_frozen_before_confirmation"] is True
    frames = split["confirmation_frames"]
    hold_ids = split["heldout_sem_ids"]
    hold_indices = [IDS.index(i) for i in hold_ids]
    truth = np.load(RUN / "sem_shape_forward_validation" / "gt_sem_contour_20x_float.npz")["image"]
    train = cv2.imread(str(RUN / "fit_input" / "loss_mask_train6_B.bmp"), 0) > 0
    hold = cv2.imread(str(RUN / "fit_input" / "loss_mask_hold3_B.bmp"), 0) > 0
    assert train.sum() == 6 * 317 and hold.sum() == 3 * 317

    kernels = {}
    batch = {}
    for case in CASES:
        data = loadmat(ROOT / case / "PSF_fitted_2D_FOVstack.mat")
        kernels[case] = data["psf_grid"].reshape(101,101,len(frames))
        batch[case] = records(ROOT / case / "batch_results.csv")
        assert [int(r["file_index"]) for r in batch[case]] == frames
        config = json.loads((ROOT / case / "reasonable_config.json").read_text(encoding="utf-8"))
        assert config["loss_mask_path"] == str(RUN / "fit_input" / "loss_mask_train6_B.bmp")
        assert config["gt_path"] == str(RUN / "fit_input" / "GT" / "gt_sem_cd.bmp")
    old = loadmat(JULY,variable_names=["psf_grid"])["psf_grid"]
    old /= old.sum()

    rows = []
    per_pillar = []
    for index, frame in enumerate(frames):
        observed = cv2.imread(str(RUN / "fit_input" / f"fit_input_{frame:02d}.bmp"),0).astype(float)/255
        preds = {}
        for case in CASES:
            psf = kernels[case][:,:,index]
            psf = psf / psf.sum()
            preds[case] = (fftconvolve(truth,psf,mode="same"),psf)
        preds["july"] = (fftconvolve(truth,old,mode="same"),old)
        gaussian_candidates=[]
        for sigma in np.arange(1,10.01,.1):
            pred=gaussian_filter(truth,float(sigma),mode="constant")
            _,mse,_,_=metrics(observed,pred,train,train)
            gaussian_candidates.append((mse,float(sigma),pred))
        _,sigma,gaussian=min(gaussian_candidates,key=lambda r:r[0])
        preds["gaussian"]=(gaussian,None)
        for model,(prediction,psf) in preds.items():
            gain,mse,mae,corr=metrics(observed,prediction,train,hold)
            edge_error = gradient_mae(observed, gain * prediction, hold)
            if psf is None:
                peak_offset=centroid_offset=0
                calls=0
            else:
                py,px=np.unravel_index(np.argmax(psf),psf.shape)
                yy,xx=np.mgrid[:101,:101]
                peak_offset=float(np.hypot(px-50,py-50))
                centroid_offset=float(np.hypot(np.sum((xx-50)*psf),np.sum((yy-50)*psf)))
                calls=int(batch[model][index]["iterations"]) if model in CASES else 0
            rows.append({"frame":frame,"model":model,"gain_from_train6":gain,
                         "gaussian_sigma_px":sigma if model=="gaussian" else "",
                         "heldout_mse":mse,"heldout_mae":mae,"heldout_correlation":corr,
                         "heldout_gradient_mae":edge_error,
                         "peak_offset_px":peak_offset,"centroid_offset_px":centroid_offset,
                         "BADS_calls":calls})
            for pillar_index in hold_indices:
                row,col=divmod(pillar_index,3)
                x,y=TILE[col],TILE[row]
                region=np.s_[y-10:y+11,x-10:x+11]
                actual=observed[region]
                predicted=gain*prediction[region]
                per_pillar.append({"frame":frame,"sem_id":IDS[pillar_index],"model":model,
                                   "mse":float(np.mean((actual-predicted)**2)),
                                   "correlation":float(np.corrcoef(actual.ravel(),predicted.ravel())[0,1])})

    with (ROOT / "confirmation_metrics.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with (ROOT / "confirmation_per_pillar.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(per_pillar[0]));writer.writeheader();writer.writerows(per_pillar)
    summary=[]
    for model in CASES+["july","gaussian"]:
        subset=[r for r in rows if r["model"]==model]
        summary.append({"model":model,"mean_heldout_mse":float(np.mean([r["heldout_mse"] for r in subset])),
                        "mean_heldout_correlation":float(np.mean([r["heldout_correlation"] for r in subset])),
                        "mean_heldout_gradient_mae":float(np.mean([r["heldout_gradient_mae"] for r in subset])),
                        "max_peak_offset_px":max(r["peak_offset_px"] for r in subset),
                        "max_centroid_offset_px":max(r["centroid_offset_px"] for r in subset),
                        "mean_BADS_calls":float(np.mean([r["BADS_calls"] for r in subset]))})
    (ROOT / "confirmation_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__": main()
