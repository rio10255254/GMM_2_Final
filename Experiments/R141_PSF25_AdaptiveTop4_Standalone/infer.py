"""Numerical inference with PSF selection and provenance receipt."""
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
    p.add_argument('--checkpoint',help='Default: package derived checkpoint if available')
    p.add_argument('--device',default='cuda' if torch.cuda.is_available() else 'cpu')
    args=p.parse_args()
    cfg=model_config();bank=ROOT/cfg['psf_bank']
    if not bank.is_file():raise FileNotFoundError(f'Real {cfg["psf_count"]}-PSF bank has not been installed: {bank}')
    bank_lock=verify_bank_lock()
    if bank_lock.get('test_only',False):raise RuntimeError('Synthetic test PSF bank cannot be used for operational inference')
    checkpoint_path=Path(args.checkpoint) if args.checkpoint else ROOT/'weights/derived_from_R140v2.pth'
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
    if cp.get('checkpoint_kind') not in ('derived_selector_untrained','trained_model'):
        raise RuntimeError('Checkpoint status is not usable for inference')
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
    block=model.refiner.optics
    receipt=dict(model_name=cfg['model_name'],checkpoint_kind=cp['checkpoint_kind'],
                 selector_trained=cp.get('selector_trained',False),
                 selector_adaptivity_validated=cp.get('selector_adaptivity_validated',False),
                 warning=None if cp.get('selector_adaptivity_validated',False) else 'Selection is operational but has not been validated as useful on this measured PSF bank',
                 input_path=str(Path(args.input).resolve()),input_sha256=sha(args.input),
                 checkpoint_path=str(checkpoint_path.resolve()),checkpoint_sha256=sha(checkpoint_path),
                 psf_bank_sha256=sha(bank),psf_bank_count=cfg['psf_count'],top_k=cfg['psf_topk'],
                 chosen_indices=block.last_indices[0].cpu().tolist(),
                 chosen_weights=[float(v) for v in block.last_sparse_weights[0][block.last_indices[0]].cpu()],
                 beta_effective=block.last_beta,shape=list(raw.shape),output_sha256=sha(output),
                 device=args.device,completed_utc=now())
    output.with_suffix('.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print('RECONSTRUCTION_SAVED',output,'PSF',receipt['chosen_indices'],'trained_selector',receipt['selector_trained'])
if __name__=='__main__':main()
