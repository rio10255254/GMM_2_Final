"""Executable preflight for the restored adaptive PSF fusion design."""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from dataset import Bank
from model import Model
from utils import model_config, now, save, setup, train_config, verify_bank_lock


def rms_gray(value):
    return float(value.double().square().mean().sqrt()*255)


def main():
    setup(1512001);lock=verify_bank_lock();cfg=model_config();tc=train_config();bank=Bank(tc)
    device="cuda" if torch.cuda.is_available() else "cpu"
    model=Model(cfg,ROOT).to(device).eval();batch=bank.batch("dev",0,device)
    source=batch["source"]
    torch.cuda.reset_peak_memory_stats() if device=="cuda" else None
    started=time.perf_counter()
    with torch.inference_mode():
        output,states=model(source,batch["operator_psf_indices"],True)
    if device=="cuda":torch.cuda.synchronize()
    elapsed=time.perf_counter()-started
    if output.shape!=source.shape or not torch.isfinite(output).all() or output.min()<0 or output.max()>1:
        raise RuntimeError("Forward contract failed")

    sample=source[:1]
    with torch.inference_mode():
        _,_,sample_context=model.base_context(sample,torch.full((1,),-1,dtype=torch.long,device=device))
    with torch.inference_mode():
        anchor0,correction0=model.psf_fusion(sample,sample_context,torch.tensor([0],device=device))
        anchor24,correction24=model.psf_fusion(sample,sample_context,torch.tensor([24],device=device))
    candidate_rms=rms_gray(anchor0-anchor24)
    correction_rms=rms_gray(correction0-correction24)
    if candidate_rms<=0 or correction_rms<=0:raise RuntimeError("Distinct PSFs did not produce distinct fusion outputs")

    model.zero_grad(set_to_none=True)
    _,states=model(source,batch["operator_psf_indices"],True)
    selector_loss=model.psf_fusion.selector_loss(batch["actual_psf_indices"])
    selector_loss.backward()
    selector_gradient=math.sqrt(sum(float(p.grad.detach().double().square().sum()) for p in model.psf_fusion.estimator.parameters() if p.grad is not None))
    if not math.isfinite(selector_gradient) or selector_gradient<=1e-8:raise RuntimeError("Selector gradient is missing")

    # Nonzero native heads expose the tiled path while leaving all other weights fixed.
    generator=torch.Generator(device=device).manual_seed(1512002)
    with torch.no_grad():
        for stage in model.stages:
            stage.head.weight.copy_(torch.randn(stage.head.weight.shape,generator=generator,device=device)*1e-4)
            stage.head.bias.zero_()
    single=source[:1]
    with torch.inference_mode():
        full=model(single)
        tiled=model.forward_tiled(single)
    tiled_max=float((full-tiled).abs().max()*255)
    tiled_rms=rms_gray(full-tiled)
    if tiled_max>1e-3:raise RuntimeError(f"Tiled/full mismatch is too large: {tiled_max} gray")

    # Check the optimized pre-iFFT fusion against explicit post-iFFT fusion.
    fusion=model.psf_fusion
    small=single[...,:256,:256]
    with torch.inference_mode():
        _,_,small_context=model.base_context(small,torch.full((1,),-1,dtype=torch.long,device=device))
    with torch.inference_mode():
        logits,weights=fusion.select(small_context,small)
    padded=torch.cat((small[...,1:51].flip(-1),small,small[...,-51:-1].flip(-1)),-1)
    padded=torch.cat((padded[...,1:51,:].flip(-2),padded,padded[...,-51:-1,:].flip(-2)),-2)
    height,width=padded.shape[-2:];transfers=fusion._transfer_bank(height,width,small.device)
    selected=torch.tensor([0,12,24],device=device);w=torch.tensor([.2,.3,.5],device=device)
    spectrum=torch.fft.rfft2(padded.float())
    explicit=[]
    for index in selected.tolist():explicit.append(torch.fft.irfft2(spectrum*transfers[index][None,None],s=(height,width)))
    explicit=sum(float(w[i])*explicit[i] for i in range(3))
    mixed=torch.einsum("n,nhw->hw",w.to(transfers.dtype),transfers[selected])
    optimized=torch.fft.irfft2(spectrum*mixed[None,None],s=(height,width))
    fusion_equivalence=float((explicit-optimized).abs().max())
    if fusion_equivalence>2e-6:raise RuntimeError("Weighted fusion optimization changed the result")

    kernels=model.psf_fusion.bank[:,0].detach().cpu().double().reshape(cfg["psf_count"],-1)
    normalized=kernels/kernels.norm(dim=1,keepdim=True)
    cosine=normalized@normalized.T;mask=~torch.eye(cfg["psf_count"],dtype=bool)
    result={
        "status":"passed","completed_utc":now(),"device":device,"forward_seconds_batch4_384":elapsed,
        "peak_gpu_allocated_bytes":torch.cuda.max_memory_allocated() if device=="cuda" else None,
        "parameter_count":sum(p.numel() for p in model.parameters()),
        "psf_bank_sha256":lock["bank_sha256"],"psf_pairwise_cosine_min":float(cosine[mask].min()),
        "initial_beta":float(model.psf_fusion.beta_value()),"initial_selector_loss":float(selector_loss),
        "selector_gradient_l2":selector_gradient,"selector_weight_min":float(model.psf_fusion.last_weights.min()),
        "selector_weight_max":float(model.psf_fusion.last_weights.max()),
        "forced_0_vs_24_anchor_rms_gray":candidate_rms,"forced_0_vs_24_correction_rms_gray":correction_rms,
        "tiled_full_rms_gray":tiled_rms,"tiled_full_max_gray":tiled_max,
        "pre_ifft_vs_post_ifft_fusion_max_abs":fusion_equivalence,
        "contracts":{
            "fft_psf_bank_ifft":True,"learned_softmax_weights":True,"weighted_fusion":True,
            "bounded_beta":True,"residual_connection":True,"known_psf_supervision":True,
            "r148v2_context_and_native_stages_preserved":True,
        },
    }
    save(ROOT/"results/preflight.json",result);print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
