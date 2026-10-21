"""Numerical inference with fixed native-grid PSF and provenance receipt."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import cv2,numpy as np,torch
from model import Model
from utils import ROOT,model_config,setup,sha,now,verify_bank_lock

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True,help='8- or 16-bit grayscale image')
    p.add_argument('--output',required=True,help='New .npz path for FP32 reconstruction')
    p.add_argument('--checkpoint',help='Default: package final scratch checkpoint')
    p.add_argument('--device',default='cuda' if torch.cuda.is_available() else 'cpu')
    args=p.parse_args()
    cfg=model_config();bank=ROOT/cfg['psf_bank']
    if not bank.is_file():raise FileNotFoundError(f'Real {cfg["psf_count"]}-PSF bank has not been installed: {bank}')
    bank_lock=verify_bank_lock()
    if bank_lock.get('test_only',False):raise RuntimeError('Synthetic test PSF bank cannot be used for operational inference')
    checkpoint_path=Path(args.checkpoint) if args.checkpoint else ROOT/'runs/formal_8192/checkpoints/step08192.pth'
    if not checkpoint_path.is_file():
        raise FileNotFoundError('No usable checkpoint yet. Install the real bank and complete training first.')
    output=Path(args.output)
    if output.suffix.lower()!='.npz':raise ValueError('Output must be .npz')
    if output.exists() or output.with_suffix('.json').exists() or output.with_suffix('.png').exists():
        raise FileExistsError('Choose a new output basename; existing evidence is never overwritten')
    setup(1309001)
    cp=torch.load(checkpoint_path,map_location='cpu',weights_only=False)
    if cp['model_config']!=cfg or cp['bank_sha256']!=sha(bank):
        raise RuntimeError('Checkpoint model or PSF bank differs from package')
    if cp.get('checkpoint_kind')!='trained_model':
        raise RuntimeError('Checkpoint status is not usable for inference')
    if cp.get('psf_mode')!=cfg['psf_mode']:
        raise RuntimeError('Checkpoint native PSF method differs from package')
    model=Model(cfg,ROOT).to(args.device).eval()
    model.load_state_dict(cp['model'],strict=True)
    raw=cv2.imread(args.input,cv2.IMREAD_UNCHANGED)
    if raw is None or raw.ndim!=2 or raw.dtype not in (np.uint8,np.uint16):
        raise ValueError('Input must be an 8- or 16-bit single-channel image')
    if min(raw.shape)<202:raise ValueError('Input needs at least 202 pixels in each direction')
    divisor=int(np.iinfo(raw.dtype).max)
    x=torch.from_numpy(raw.astype('float32')[None,None]/divisor).to(args.device)
    with torch.inference_mode():
        y=model(x).cpu().numpy()[0,0]
    if not np.isfinite(y).all():raise FloatingPointError('Nonfinite reconstruction')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as f:np.savez_compressed(f,output=y)
    if not cv2.imwrite(str(output.with_suffix('.png')),(np.rint(y*65535).clip(0,65535)).astype('uint16')):
        raise OSError('Failed to save PNG preview')
    receipt=dict(model_name=cfg['model_name'],checkpoint_kind=cp['checkpoint_kind'],
                 psf_mode=cfg['psf_mode'],research_only_psf=bank_lock.get('research_only',False),
                 selector_trained=False,
                 input_path=str(Path(args.input).resolve()),input_sha256=sha(args.input),
                 checkpoint_path=str(checkpoint_path.resolve()),checkpoint_sha256=sha(checkpoint_path),
                 psf_bank_sha256=sha(bank),psf_bank_count=cfg['psf_count'],
                 fixed_psf_weights=[1/cfg['psf_count']]*cfg['psf_count'],
                 physical_step_strengths=(cfg['optical_step_max']*torch.sigmoid(model.optical_step_logits)).detach().cpu().tolist(),
                 shape=list(raw.shape),output_sha256=sha(output),
                 device=args.device,completed_utc=now())
    output.with_suffix('.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print('RECONSTRUCTION_SAVED',output,'PSF_MODE',receipt['psf_mode'])
if __name__=='__main__':main()
