"""Optional, reversible optical input; native 25-PSF behavior remains the default."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
import torch
from scipy.io import loadmat
from optical.fullres_psf import FullResPSF
from optical.adaptive_fourier_psf import AdaptiveFourierPSFFusion

ROOT=Path(__file__).resolve().parents[1]
SWEEP=Path('D:/GMM_2_Final/PSF_Fitting/tests/artifacts/cd_verification_20260714/50x_deconvolution_sweep.mat')
FIT=Path('D:/GMM_2_Final/PSF_Fitting/output/pillar_via_junction_psf_20260713/50x/fit_result/PSF_fitted_2D_FOVstack.mat')
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def load_original_kernel():
    manifest=json.loads((ROOT/'results/source_manifest.json').read_text(encoding='utf-8'))
    for p in [SWEEP,FIT]:
        rec=next(r for r in manifest if Path(r['path'])==p);assert sha(p)==rec['sha256']
    kernel=np.asarray(loadmat(SWEEP,variable_names=['psf'])['psf'],dtype=np.float64)
    fit=np.squeeze(loadmat(FIT,variable_names=['psf_grid'])['psf_grid']).astype(np.float64);fit/=fit.sum()
    if kernel.shape!=(101,101) or not np.isfinite(kernel).all() or (kernel<0).any() or kernel.sum()<=0:raise ValueError('Invalid objective calibration')
    kernel/=kernel.sum();assert np.allclose(kernel,fit,rtol=0,atol=1e-14)
    return kernel

class ObjectiveSinglePSF(FullResPSF):
    def __init__(self,kernel):
        torch.nn.Module.__init__(self)
        # Keep the measured asymmetry and index-50 origin. Do not recenter or symmetrize.
        value=torch.from_numpy(np.array(kernel,dtype=np.float32,copy=True))[None,None]
        self.register_buffer('bank',value.clone());self.register_buffer('mean_kernel',value.clone());self._cache={}
    def blur(self,image,indices=None):
        if indices is not None and ((indices < -2)|(indices>=1)).any():raise ValueError('Single objective kernel only permits index 0, mean, or identity')
        return super().blur(image,indices)

class SingleObjectiveFusion(AdaptiveFourierPSFFusion):
    def select(self,features,image=None):
        # With exactly one measured kernel, there is no selection task. Keep estimator weights intact but dormant.
        n=features.shape[0];weights=torch.ones((n,1),device=features.device,dtype=features.dtype)
        logits=torch.zeros_like(weights);self.last_logits=logits;self.last_weights=weights.detach();self.last_entropy=torch.zeros((),device=features.device)
        return logits,weights
    def train(self,mode=True):
        if mode:raise RuntimeError('Objective adapter is inference-only; no training is authorized')
        return super().train(False)

def restore_native_optics(model):
    """Undo a temporary single-PSF input, preserving the native selector and learned state."""
    original=model.__dict__.pop('_temporary_optical_modules',None)
    if original is not None:
        device=next(model.parameters()).device
        model.base.optics,model.psf_fusion=original
        model.base.optics.to(device);model.psf_fusion.to(device)
        model.base.optics._cache.clear();model.psf_fusion._transfer_cache.clear();model.eval()

def configure_optical_input(model,cfg,model_root,kernel=None):
    """None restores native 25 PSFs; a calibrated 2-D kernel temporarily selects single-PSF mode.

    This interface has no magnification, source path, scale conversion, resizing, or training logic.
    A different multi-PSF bank needs a verified index mapping and is deliberately not fabricated here.
    """
    if kernel is None:
        restore_native_optics(model)
        return dict(mode='native',effective_kernel_count=25)
    kernel=np.asarray(kernel,dtype=np.float64)
    if kernel.shape!=(101,101) or not np.isfinite(kernel).all() or (kernel<0).any() or not np.isclose(kernel.sum(),1,rtol=0,atol=1e-10):
        raise ValueError('Supply a normalized finite nonnegative 101x101 measured kernel, or None for native optics')
    restore_native_optics(model)
    before={k:v.detach().cpu().clone() for k,v in model.named_parameters()}
    oldstate={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    device=next(model.parameters()).device
    original=(model.base.optics,model.psf_fusion)
    # A tuple kept outside registered submodules is only the reversible runtime handle.
    model.__dict__['_temporary_optical_modules']=original
    model.base.optics=ObjectiveSinglePSF(kernel).to(device)
    fusion=SingleObjectiveFusion(cfg,Path(model_root)/cfg['psf_bank'])
    fusion.load_state_dict(model.psf_fusion.state_dict(),strict=True)
    fusion.bank=torch.from_numpy(kernel.astype(np.float32))[None,None]
    fusion.count=1;fusion._transfer_cache.clear();model.psf_fusion=fusion.to(device).eval();model.eval()
    assert all(torch.equal(before[k],v.cpu()) for k,v in model.named_parameters())
    changed=[k for k,v in model.state_dict().items() if not torch.equal(oldstate[k],v.cpu())]
    assert set(changed)=={'base.optics.bank','base.optics.mean_kernel','psf_fusion.bank'},changed
    return dict(mode='temporary_single_calibrated_psf',effective_kernel_count=1,learned_parameters_unchanged=True,changed_buffers=changed,reversible=True)

def install_50x(model,cfg,model_root):
    """Experiment-specific provenance wrapper; not a permanent change to the model interface."""
    auth=json.loads((ROOT/'config/objective_optics_authorization.json').read_text(encoding='utf-8'))
    assert auth['use_original_50x_calibration'] and auth['allow_inference_optical_input_adapter']
    kernel=load_original_kernel()
    installed=configure_optical_input(model,cfg,model_root,kernel)
    path=ROOT/'config/50x_calibrated_psf.npz'
    if path.exists():
        with np.load(path) as z:assert np.array_equal(z['all_kernels'],kernel[None])
    else:
        with path.open('xb') as f:np.savez_compressed(f,all_kernels=kernel[None])
    y,x=np.mgrid[-50:51,-50:51]
    result=dict(mode='50x original single calibrated kernel',source_path=str(SWEEP),source_sha256=sha(SWEEP),source_key='psf',fit_path=str(FIT),fit_sha256=sha(FIT),effective_bank_path=str(path),effective_bank_sha256=sha(path),effective_kernel_count=1,object_um_per_px=.069,kernel_centroid_xy_px=[float((kernel*x).sum()),float((kernel*y).sum())],kernel_origin='original central sample index 50; not recentered',max_centrosymmetry_difference=float(abs(kernel-kernel[::-1,::-1]).max()),learned_parameters_unchanged=True,changed_buffers=installed['changed_buffers'],selector_mode='single calibrated kernel, weight exactly 1; original selector parameters retained but unused',adapter_sha256=sha(Path(__file__)),temporary_and_reversible=True,native_25_psf_default_preserved=True)
    return result
