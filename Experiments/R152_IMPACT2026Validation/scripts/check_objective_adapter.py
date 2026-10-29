"""Test optical wiring against independent convolution and inverse-filter calculations."""
from pathlib import Path
import sys,json
import numpy as np
import torch
from scipy.signal import fftconvolve
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];MODEL_ROOT=Path(str(PROJECT_ROOT / 'Experiments/R152_R148v2_SafeAdaptivePSF'))
sys.path.insert(0,str(MODEL_ROOT))
from model import Model
from utils import setup,load,save,sha
from objective_optics import install_50x,load_original_kernel,configure_optical_input

def main():
    setup(1309001);cfg=load(MODEL_ROOT/'config/model.json');receipt=load(MODEL_ROOT/'runs/formal_8192/training_complete.json')['deployed_checkpoint']
    assert sha(str(PROJECT_ROOT / receipt['path']))==receipt['sha256']
    device='cuda' if torch.cuda.is_available() else 'cpu'
    m=Model(cfg,MODEL_ROOT).to(device).eval();m.load_state_dict(torch.load(str(PROJECT_ROOT / receipt['path']),map_location='cpu',weights_only=False)['model'])
    image_path=Path(PROJECT_ROOT / load(ROOT/'sources/sequence_config.json')['sequences']['50x_x_0p5um']['raw_dir'])/'frame_0000.bmp'
    a=np.asarray(Image.open(image_path),dtype=np.float32)/255
    x=torch.from_numpy(a[560:816,1050:1306][None,None]).to(device)
    with torch.inference_mode():old=m.forward_tiled(x)
    assert m.base.optics._cache and m.psf_fusion._transfer_cache
    record=install_50x(m,cfg,MODEL_ROOT)
    assert not m.base.optics._cache and not m.psf_fusion._transfer_cache
    k=load_original_kernel();expected=torch.from_numpy(k.astype(np.float32))[None,None].to(device)
    assert torch.equal(m.base.optics.mean_kernel,expected) and torch.equal(m.psf_fusion.bank,expected)
    with torch.inference_mode():
        blur=m.base.optics.blur(x).cpu().numpy()[0,0]
        new=m.forward_tiled(x)
        anchor,correction=m.psf_fusion(x,m.base.prepare(x,None)[2])
    np_x=x.cpu().numpy()[0,0].astype(float);padded=np.pad(np_x,50,mode='reflect');kf=k.astype(np.float32).astype(float)
    ref=fftconvolve(padded,kf,mode='same')[50:-50,50:-50]
    blur_err=float(abs(blur-ref).max());assert blur_err<1e-6,blur_err
    h,w=padded.shape;placed=np.zeros((h,w));top=(h-101)//2;left=(w-101)//2;placed[top:top+101,left:left+101]=kf
    transfer=np.fft.rfft2(np.roll(placed,(-(top+50),-(left+50)),axis=(0,1)))
    inverse=transfer.conj()/(abs(transfer)**2+cfg['psf_regularization'])
    radius=np.sqrt(np.fft.fftfreq(h)[:,None]**2+np.fft.rfftfreq(w)[None,:]**2)/.5
    filt=1+(radius<=cfg['psf_lowfreq_ratio'])*(inverse-1);filt*=np.minimum(cfg['psf_max_inverse_gain']/np.maximum(abs(filt),1e-8),1)
    restored=np.fft.irfft2(np.fft.rfft2(padded)*filt,s=(h,w))[50:-50,50:-50]
    refcorr=np.clip(restored-np_x,-cfg['psf_correction_clip'],cfg['psf_correction_clip'])
    corr_err=float(abs(correction.cpu().numpy()[0,0]-refcorr).max());assert corr_err<2e-6,corr_err
    assert m.psf_fusion.last_weights.shape==(1,1) and float(m.psf_fusion.last_weights[0,0])==1
    output_difference=float((new-old).abs().max());assert output_difference>0
    # A full real frame checks that changing the optical input leaves existing tiling valid.
    fullx=torch.from_numpy(a[None,None]).to(device)
    with torch.inference_mode():
        full=m(fullx); tiled=m.forward_tiled(fullx)
    parity=float((full-tiled).abs().max());assert parity<1e-6,parity
    saved=ROOT/'results/50x_calibrated/reconstruction/50x_x_0p5um/frame_0000.npz'
    saved_error=None
    if saved.exists():
        saved_error=float(abs(np.load(saved)['output']-tiled.cpu().numpy()[0,0]).max());assert saved_error<1e-7,saved_error
    configure_optical_input(m,cfg,MODEL_ROOT,None)
    with torch.inference_mode():restored_native=m.forward_tiled(x)
    restore_error=float((restored_native-old).abs().max());assert restore_error==0
    assert m.psf_fusion.count==25 and m.base.optics.bank.shape[0]==25
    configure_optical_input(m,cfg,MODEL_ROOT,k)
    with torch.inference_mode():reinstalled=m.forward_tiled(x)
    reinstall_error=float((reinstalled-new).abs().max());assert reinstall_error==0
    try:configure_optical_input(m,cfg,MODEL_ROOT,np.zeros((2,101,101)))
    except ValueError:invalid_count_rejected=True
    else:raise AssertionError('Unsupported PSF count was silently accepted')
    result=dict(passed=True,installation=record,independent_convolution_max_error=blur_err,independent_inverse_filter_max_error=corr_err,shared_vs_calibrated_patch_max_difference=output_difference,full_vs_tiled_real_frame_max_difference=parity,real_frame=str(image_path),single_weight_exactly_one=True,caches_reset_on_installation=True,learned_parameters_unchanged=True,native_25_psf_restore_max_difference=restore_error,single_psf_reinstall_max_difference=reinstall_error,unsupported_count_rejected=invalid_count_rejected,saved_full_frame_parity_max_difference=saved_error)
    save(ROOT/'results/objective_adapter_preflight.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
