"""Train an outcome-supervised selector after freezing the profile proposal."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import roc_auc_score
from torch import nn


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "staged_profile_selector"
REPORT = ROOT / "reports" / "07B_STAGED_PROFILE_SELECTOR.md"
RESULT.mkdir(parents=True, exist_ok=True)
REPORT.parent.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("profile_probe", ROOT / "scripts" / "07_local_profile_observability.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load profile probe")
probe = importlib.util.module_from_spec(spec); sys.modules[spec.name] = probe; spec.loader.exec_module(probe)
DEVICE = probe.DEVICE


class Selector(nn.Module):
    def __init__(self):
        super().__init__()
        self.body = nn.Sequential(nn.Conv1d(4, 40, 7, padding=3), nn.SiLU(), probe.Res1D(40), probe.Res1D(40), probe.Res1D(40), nn.Conv1d(40, 48, 5, padding=2), nn.SiLU())
        self.head = nn.Sequential(nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(48, 32), nn.SiLU(), nn.Linear(32, 1))
    def forward(self, source: torch.Tensor, rendered: torch.Tensor) -> torch.Tensor:
        base = probe.feature_tensor(source)
        value = torch.cat([base, (rendered-source)[:, None]], dim=1)
        return torch.sigmoid(self.head(self.body(value))[:, 0])


@torch.inference_mode()
def proposal_outputs(model, source: np.ndarray) -> np.ndarray:
    tensor = torch.from_numpy(source).to(DEVICE); rows=[]
    for start in range(0,len(tensor),1024): rows.append(model(tensor[start:start+1024])[0].cpu().numpy())
    return np.concatenate(rows)


def oracle_alpha(source: np.ndarray, target: np.ndarray, rendered: np.ndarray) -> np.ndarray:
    delta = rendered-source; desired = target-source
    numerator = np.sum(delta*desired,axis=1); denominator = np.sum(delta*delta,axis=1)+1e-8
    return np.clip(numerator/denominator,0.0,1.0).astype(np.float32)


def stratified_indices(alpha: np.ndarray) -> list[np.ndarray]:
    edges=[-1e-6,0.02,0.20,0.45,0.70,0.90,1.000001]
    bins=[]
    for lo,hi in zip(edges[:-1],edges[1:]):
        index=np.flatnonzero((alpha>lo)&(alpha<=hi))
        if len(index):bins.append(index)
    return bins


def train_selector(source: np.ndarray, rendered: np.ndarray, alpha: np.ndarray, steps: int=1200):
    probe.seed_all(108750);model=Selector().to(DEVICE);optimizer=torch.optim.AdamW(model.parameters(),lr=4e-4,weight_decay=1e-5)
    source_t=torch.from_numpy(source).to(DEVICE);rendered_t=torch.from_numpy(rendered).to(DEVICE);alpha_t=torch.from_numpy(alpha).to(DEVICE);bins=stratified_indices(alpha);rng=np.random.default_rng(108751);trace=[];batch=384
    for step in range(1,steps+1):
        per=max(1,batch//len(bins));indices=np.concatenate([rng.choice(values,size=per,replace=True) for values in bins]);rng.shuffle(indices);index=torch.from_numpy(indices[:batch]).to(DEVICE)
        prediction=model(source_t[index],rendered_t[index]);loss=F.smooth_l1_loss(prediction,alpha_t[index],beta=0.05)
        optimizer.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5.0);optimizer.step()
        if step==1 or step%100==0:
            row={"step":step,"loss":float(loss.detach()),"predicted_mean":float(prediction.mean().detach()),"target_mean":float(alpha_t[index].mean().detach())};trace.append(row);print(json.dumps(row),flush=True)
    torch.save({"model":model.state_dict(),"steps":steps,"proposal":"direct_parameter_frozen"},RESULT/'selector.pth');return model.eval(),trace


@torch.inference_mode()
def evaluate(selector, data, proposal_output):
    source=data['source'];target=data['target'];oracle=oracle_alpha(source,target,proposal_output);source_t=torch.from_numpy(source).to(DEVICE);proposal_t=torch.from_numpy(proposal_output).to(DEVICE);pred=[]
    for start in range(0,len(source),1024):pred.append(selector(source_t[start:start+1024],proposal_t[start:start+1024]).cpu().numpy())
    alpha=np.concatenate(pred);pred_output=source+alpha[:,None]*(proposal_output-source);oracle_output=source+oracle[:,None]*(proposal_output-source)
    def metrics(output):
        sc,sw,sv=probe.derivative_geometry(source);tc,tw,tv=probe.derivative_geometry(target);oc,ow,ov=probe.derivative_geometry(output);valid=sv&tv&ov
        return {"profile_mae_gray":float(np.mean(np.abs(output-target))*255),"profile_improved_fraction":float(np.mean(np.mean(np.abs(output-target),axis=1)<np.mean(np.abs(source-target),axis=1))),"center_abs_error_px":float(np.median(np.abs(oc[valid]-tc[valid]))),"width_abs_error_px":float(np.median(np.abs(ow[valid]-tw[valid])))}
    return {"profiles":len(source),"raw":metrics(source),"proposal":metrics(proposal_output),"oracle_selector":metrics(oracle_output),"learned_selector":metrics(pred_output),"alpha":{"oracle_mean":float(oracle.mean()),"predicted_mean":float(alpha.mean()),"oracle_identity_mean":float(oracle[data['role']==0].mean()),"oracle_degraded_mean":float(oracle[data['role']!=0].mean()),"predicted_identity_mean":float(alpha[data['role']==0].mean()),"predicted_degraded_mean":float(alpha[data['role']!=0].mean()),"prediction_mae":float(np.mean(np.abs(alpha-oracle))),"identity_vs_degraded_auc":float(roc_auc_score(data['role']!=0,alpha)),"correlation":float(np.corrcoef(alpha,oracle)[0,1])}}


def main():
    probe.seed_all(108700);train=probe.generate_profiles(60000,108701,False);test=probe.generate_profiles(12000,108702,False);severe=probe.generate_profiles(12000,108703,True)
    proposal=probe.ProfileEstimator(False).to(DEVICE);state=torch.load(ROOT/'results/local_profile_observability/direct_parameter.pth',map_location=DEVICE,weights_only=False);proposal.load_state_dict(state['model']);proposal.eval()
    for parameter in proposal.parameters():parameter.requires_grad_(False)
    train_rendered=proposal_outputs(proposal,train['source']);train_alpha=oracle_alpha(train['source'],train['target'],train_rendered)
    selector,trace=train_selector(train['source'],train_rendered,train_alpha)
    summary={"status":"complete","device":str(DEVICE),"training":{"profiles":len(train['source']),"steps":1200,"oracle_alpha_distribution":{"mean":float(train_alpha.mean()),"p10":float(np.quantile(train_alpha,.1)),"median":float(np.median(train_alpha)),"p90":float(np.quantile(train_alpha,.9)),"zero_fraction":float((train_alpha<=.02).mean()),"high_fraction":float((train_alpha>=.9).mean())},"trace":trace},"in_distribution":evaluate(selector,test,proposal_outputs(proposal,test['source'])),"severe_heldout":evaluate(selector,severe,proposal_outputs(proposal,severe['source'])),"interpretation_boundary":"The proposal is frozen and the selector receives a direct counterfactual adoption target. This remains a 1-D mechanism probe, not a full image model."}
    (RESULT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');s=summary['severe_heldout']
    REPORT.write_text('\n'.join(['# Staged Outcome-Supervised Profile Selector','',f"- Severe Raw MAE: {s['raw']['profile_mae_gray']:.3f} gray.",f"- Frozen proposal MAE: {s['proposal']['profile_mae_gray']:.3f} gray.",f"- Oracle adoption MAE: {s['oracle_selector']['profile_mae_gray']:.3f} gray.",f"- Learned adoption MAE: {s['learned_selector']['profile_mae_gray']:.3f} gray.",f"- Learned alpha MAE/correlation: {s['alpha']['prediction_mae']:.3f} / {s['alpha']['correlation']:.3f}.",f"- Identity/degraded predicted alpha: {s['alpha']['predicted_identity_mean']:.3f}/{s['alpha']['predicted_degraded_mean']:.3f}.",'','This directly tests whether proposal-first, outcome-supervised selection avoids the joint-gate identity shortcut.','']),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())

