"""Short learned probe for single-image local edge-profile observability.

Two tiny models start from independent random initialization on the same
phase-matched 1-D optical profiles.  Both predict explicit foreground,
background, center and width parameters.  One applies the rendered profile
directly; the other has an unsupervised output gate.  This is a mechanism test,
not an image model or deployable checkpoint.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F
from scipy.ndimage import gaussian_filter1d, shift as ndi_shift
from sklearn.metrics import roc_auc_score
from torch import nn


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "local_profile_observability"
REPORT = ROOT / "reports" / "07_LOCAL_PROFILE_OBSERVABILITY.md"
RESULT.mkdir(parents=True, exist_ok=True)
REPORT.parent.mkdir(parents=True, exist_ok=True)
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
LENGTH = 65
CENTER_INDEX = 32.0


def seed_all(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)


def sigmoid(value: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(value, -40.0, 40.0)))


def generate_profiles(count: int, seed: int, severe: bool = False) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = np.arange(LENGTH, dtype=np.float32)
    sources, targets, parameters, roles = [], [], [], []
    role_names = ["identity", "gaussian", "asymmetric", "low_contrast"]
    for index in range(count):
        role = role_names[index % len(role_names)]
        center = float(rng.uniform(CENTER_INDEX - 1.8, CENTER_INDEX + 1.8))
        target_scale = float(rng.uniform(0.30, 1.35))
        background = float(rng.uniform(20, 235))
        sign = 1.0 if rng.random() < 0.5 else -1.0
        maximum = (250.0 - background) if sign > 0 else (background - 5.0)
        minimum = 8.0 if (severe or role == "low_contrast") else 30.0
        if maximum < minimum:
            sign = -sign
            maximum = (250.0 - background) if sign > 0 else (background - 5.0)
        if severe or role == "low_contrast":
            contrast = float(rng.uniform(8, max(9, min(65, maximum))))
        else:
            contrast = float(rng.uniform(30, max(31, min(150, maximum))))
        outside = background
        inside = background + sign * contrast
        target = np.clip(outside + (inside - outside) * sigmoid((x - center) / target_scale), 0, 255)

        if role == "identity":
            blur_sigma = float(rng.uniform(0.0, 0.25)); noise = float(rng.uniform(0.0, 0.8)); ghost = halo = slope = 0.0
        elif role == "gaussian":
            blur_sigma = float(rng.uniform(0.7, 3.4 if not severe else 4.8)); noise = float(rng.uniform(0.5, 5.0 if not severe else 10.0)); ghost = halo = 0.0; slope = float(rng.uniform(-8, 8))
        elif role == "asymmetric":
            blur_sigma = float(rng.uniform(0.8, 3.0 if not severe else 4.5)); noise = float(rng.uniform(0.5, 5.0 if not severe else 9.0)); ghost = float(rng.uniform(0.02, 0.12 if not severe else 0.25)); halo = float(rng.uniform(-0.12, 0.12) if not severe else rng.uniform(-0.24, 0.24)); slope = float(rng.uniform(-10, 10))
        else:
            blur_sigma = float(rng.uniform(1.0, 3.8 if not severe else 5.0)); noise = float(rng.uniform(1.0, 7.0 if not severe else 12.0)); ghost = float(rng.uniform(0.0, 0.08)); halo = float(rng.uniform(-0.08, 0.08)); slope = float(rng.uniform(-25, 25) if not severe else rng.uniform(-55, 55))
        source = gaussian_filter1d(target, blur_sigma, mode="reflect") if blur_sigma > 0 else target.copy()
        if ghost:
            shifted = ndi_shift(source, float(rng.uniform(-2.5, 2.5)), order=1, mode="reflect")
            source = (1.0 - ghost) * source + ghost * shifted
        if halo:
            broad = gaussian_filter1d(source, 4.0, mode="reflect")
            source = source + halo * (broad - source)
        source = source + slope * (x - CENTER_INDEX) / LENGTH
        source = source + rng.normal(0.0, noise, LENGTH)
        source = np.clip(source, 0, 255)
        sources.append(source.astype(np.float32) / 255.0)
        targets.append(target.astype(np.float32) / 255.0)
        parameters.append([outside / 255.0, inside / 255.0, (center - CENTER_INDEX) / 6.0, math.log(target_scale)])
        roles.append(role_names.index(role))
    return {
        "source": np.stack(sources), "target": np.stack(targets), "parameters": np.asarray(parameters, np.float32), "role": np.asarray(roles, np.int64),
    }


def feature_tensor(source: torch.Tensor) -> torch.Tensor:
    mean = source.mean(dim=-1, keepdim=True); std = source.std(dim=-1, keepdim=True).clamp_min(2.0 / 255.0)
    normalized = (source - mean) / (3.0 * std)
    gradient = F.pad(source[:, 1:] - source[:, :-1], (0, 1))
    return torch.stack([source, normalized, gradient], dim=1)


class Res1D(nn.Module):
    def __init__(self, channels: int):
        super().__init__(); self.a = nn.Conv1d(channels, channels, 5, padding=2); self.b = nn.Conv1d(channels, channels, 5, padding=2)
    def forward(self, x):
        return F.silu(x + 0.2 * self.b(F.silu(self.a(x))))


class ProfileEstimator(nn.Module):
    def __init__(self, gated: bool):
        super().__init__(); self.gated = gated
        self.body = nn.Sequential(nn.Conv1d(3, 40, 7, padding=3), nn.SiLU(), Res1D(40), Res1D(40), Res1D(40), nn.Conv1d(40, 56, 5, padding=2), nn.SiLU())
        self.head = nn.Sequential(nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(56, 48), nn.SiLU(), nn.Linear(48, 5 if gated else 4))
    def forward(self, source: torch.Tensor):
        raw = self.head(self.body(feature_tensor(source)))
        outside = torch.sigmoid(raw[:, 0]); inside = torch.sigmoid(raw[:, 1]); center = CENTER_INDEX + 6.0 * torch.tanh(raw[:, 2]); scale = 0.22 + 2.8 * torch.sigmoid(raw[:, 3])
        coordinate = torch.arange(LENGTH, device=source.device, dtype=source.dtype)[None]
        rendered = outside[:, None] + (inside - outside)[:, None] * torch.sigmoid((coordinate - center[:, None]) / scale[:, None])
        if self.gated:
            gate = torch.sigmoid(raw[:, 4]); output = source + gate[:, None] * (rendered - source)
        else:
            gate = torch.ones_like(center); output = rendered
        return output, torch.stack([outside, inside, (center-CENTER_INDEX)/6.0, torch.log(scale)], dim=1), gate


def derivative_geometry(profiles: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    outside = np.median(profiles[:, :8], axis=1, keepdims=True); inside = np.median(profiles[:, -8:], axis=1, keepdims=True)
    normalized = (profiles - outside) / np.where(np.abs(inside-outside) > 1e-5, inside-outside, 1.0)
    derivative = np.maximum(np.diff(normalized, axis=1), 0.0); mass = derivative.sum(axis=1)
    cdf = np.cumsum(derivative, axis=1) / np.maximum(mass[:, None], 1e-8); mid = np.arange(LENGTH-1, dtype=np.float32)+0.5
    q10 = mid[np.argmax(cdf >= 0.10, axis=1)]; q50 = mid[np.argmax(cdf >= 0.50, axis=1)]; q90 = mid[np.argmax(cdf >= 0.90, axis=1)]
    return q50, q90-q10, mass > 0.15


def train_arm(name: str, gated: bool, train: dict[str, np.ndarray], steps: int = 1400) -> tuple[ProfileEstimator, list[dict[str, float]]]:
    seed_all(108700 + int(gated))
    model = ProfileEstimator(gated).to(DEVICE); optimizer = torch.optim.AdamW(model.parameters(), lr=4e-4, weight_decay=1e-5)
    source = torch.from_numpy(train["source"]).to(DEVICE); target = torch.from_numpy(train["target"]).to(DEVICE); params = torch.from_numpy(train["parameters"]).to(DEVICE)
    generator = torch.Generator(device=DEVICE).manual_seed(108710 + int(gated)); trace=[]; batch=384
    for step in range(1, steps+1):
        index = torch.randint(0, len(source), (batch,), device=DEVICE, generator=generator)
        prediction, pred_params, gate = model(source[index])
        profile_loss = F.smooth_l1_loss(prediction, target[index], beta=1.0/255.0)
        parameter_loss = F.smooth_l1_loss(pred_params[:, :3], params[index, :3], beta=0.01) + 0.25*F.smooth_l1_loss(pred_params[:, 3], params[index, 3], beta=0.05)
        loss = profile_loss + 0.18 * parameter_loss
        optimizer.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0); optimizer.step()
        if step == 1 or step % 100 == 0:
            row={"step":step,"total":float(loss.detach()),"profile":float(profile_loss.detach()),"parameter":float(parameter_loss.detach()),"gate":float(gate.mean().detach())}
            trace.append(row); print(json.dumps({"arm":name,**row}),flush=True)
    torch.save({"model":model.state_dict(),"gated":gated,"steps":steps,"seed":108700+int(gated)}, RESULT/f"{name}.pth")
    return model, trace


@torch.inference_mode()
def evaluate(model: ProfileEstimator, data: dict[str, np.ndarray]) -> dict[str, object]:
    source_t=torch.from_numpy(data["source"]).to(DEVICE); outputs=[]; params=[]; gates=[]
    for start in range(0,len(source_t),1024):
        out,p,g=model(source_t[start:start+1024]);outputs.append(out.cpu().numpy());params.append(p.cpu().numpy());gates.append(g.cpu().numpy())
    output=np.concatenate(outputs); predicted_params=np.concatenate(params); gate=np.concatenate(gates); source=data["source"];target=data["target"]
    source_center,source_width,source_valid=derivative_geometry(source);target_center,target_width,target_valid=derivative_geometry(target);out_center,out_width,out_valid=derivative_geometry(output);valid=source_valid&target_valid&out_valid
    result={
        "profiles":len(source),
        "profile_mae_gray":{"raw":float(np.mean(np.abs(source-target))*255),"model":float(np.mean(np.abs(output-target))*255)},
        "center_abs_error_px":{"raw":float(np.median(np.abs(source_center[valid]-target_center[valid]))),"model":float(np.median(np.abs(out_center[valid]-target_center[valid])))},
        "width_abs_error_px":{"raw":float(np.median(np.abs(source_width[valid]-target_width[valid]))),"model":float(np.median(np.abs(out_width[valid]-target_width[valid])))},
        "profile_improved_fraction":float(np.mean(np.mean(np.abs(output-target),axis=1)<np.mean(np.abs(source-target),axis=1))),
        "predicted_parameter_mae":{"outside_gray":float(np.mean(np.abs(predicted_params[:,0]-data['parameters'][:,0]))*255),"inside_gray":float(np.mean(np.abs(predicted_params[:,1]-data['parameters'][:,1]))*255),"center_px":float(np.mean(np.abs(predicted_params[:,2]-data['parameters'][:,2]))*6),"log_scale":float(np.mean(np.abs(predicted_params[:,3]-data['parameters'][:,3])))},
        "gate":{"overall_mean":float(gate.mean()),"identity_mean":float(gate[data['role']==0].mean()),"degraded_mean":float(gate[data['role']!=0].mean()),"identity_vs_degraded_auc":float(roc_auc_score(data['role']!=0,gate))},
    }
    return result


def plot_examples(models: dict[str,ProfileEstimator], data: dict[str,np.ndarray]) -> None:
    indices=[0,1,2,3,8,9,10,11];x=np.arange(LENGTH);fig,axes=plt.subplots(len(indices),1,figsize=(10,18),constrained_layout=True)
    source_t=torch.from_numpy(data['source'][indices]).to(DEVICE)
    predictions={name:model(source_t)[0].detach().cpu().numpy() for name,model in models.items()}
    for ax,idx,local in zip(axes,indices,range(len(indices))):
        ax.plot(x,data['source'][idx]*255,label='source',color='#777',alpha=.8);ax.plot(x,data['target'][idx]*255,label='target',color='black',linewidth=2)
        for name,value in predictions.items():ax.plot(x,value[local]*255,label=name,linewidth=1.2)
        ax.set_title(f"role={idx%4}");ax.set_xlim(8,56)
    axes[0].legend(ncol=4);fig.savefig(RESULT/'heldout_profiles.png',dpi=170);plt.close(fig)


def main() -> int:
    seed_all(108700);train=generate_profiles(60000,108701,False);test=generate_profiles(12000,108702,False);severe=generate_profiles(12000,108703,True)
    models={};traces={}
    for name,gated in (("direct_parameter",False),("gated_parameter",True)):
        model,trace=train_arm(name,gated,train);models[name]=model.eval();traces[name]=trace
    summary={"status":"complete","device":str(DEVICE),"train_profiles":len(train['source']),"steps_per_arm":1400,"arms":{},"interpretation_boundary":"This 1-D phase-matched probe tests local observability only; it does not establish full-image topology, texture, tile, SEM, or GMF performance."}
    for name,model in models.items():summary['arms'][name]={"in_distribution":evaluate(model,test),"severe_heldout":evaluate(model,severe),"trace":traces[name]}
    (RESULT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');plot_examples(models,severe)
    direct=summary['arms']['direct_parameter']['severe_heldout'];gated=summary['arms']['gated_parameter']['severe_heldout']
    REPORT.write_text('\n'.join([
        '# R108A Local Profile Observability', '',
        f"- Severe held-out Raw/profile MAE: {direct['profile_mae_gray']['raw']:.3f} gray.",
        f"- Direct explicit-parameter model: {direct['profile_mae_gray']['model']:.3f} gray; center {direct['center_abs_error_px']['model']:.3f} px; width {direct['width_abs_error_px']['model']:.3f} px.",
        f"- Gated model: {gated['profile_mae_gray']['model']:.3f} gray; center {gated['center_abs_error_px']['model']:.3f} px; width {gated['width_abs_error_px']['model']:.3f} px.",
        f"- Gated identity/degraded means: {gated['gate']['identity_mean']:.3f}/{gated['gate']['degraded_mean']:.3f}; AUC {gated['gate']['identity_vs_degraded_auc']:.3f}.",
        '', 'This probe decides whether local center/width/radiometry estimation is observable before constructing a full image model.', ''
    ]),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
