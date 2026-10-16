"""Validate and install a real PSF bank without silent substitution."""
from __future__ import annotations
import argparse,shutil
from pathlib import Path
import numpy as np
from utils import ROOT,load,save,sha,now,model_config

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True,help='NPZ with all_kernels [N,101,101]')
    p.add_argument('--provenance',required=True,help='JSON describing fit source, grid and image scale')
    p.add_argument('--test-only',action='store_true',help='Explicitly install synthetic calibration only in an isolated test copy')
    args=p.parse_args()
    cfg=model_config();source=Path(args.source);target=ROOT/cfg['psf_bank']
    lock=ROOT/'calibration/BANK_LOCK.json'
    if target.exists() or lock.exists():raise FileExistsError('Bank already installed; keep its evidence and make a new version')
    metadata=load(args.provenance)
    required=('origin','grid_rows','grid_cols','index_order','image_scale_um_per_px','sem_truth_dependency')
    missing=[key for key in required if key not in metadata]
    if missing:raise ValueError('Provenance is missing: '+', '.join(missing))
    if metadata.get('synthetic',False) and not args.test_only:
        raise ValueError('Synthetic bank cannot be installed as measured calibration')
    if metadata['grid_rows']*metadata['grid_cols']!=cfg['psf_count']:
        raise ValueError('PSF grid does not match model count')
    with np.load(source,allow_pickle=False) as z:
        if 'all_kernels' not in z.files:raise ValueError('Missing all_kernels')
        a=z['all_kernels']
    if a.shape!=(cfg['psf_count'],101,101) or a.dtype.kind not in 'fiu':
        raise ValueError('Wrong number or shape of real PSF kernels')
    if not np.isfinite(a).all() or (a<0).any() or (a.sum((1,2))<=0).any():
        raise ValueError('Invalid real PSF values')
    f=a.reshape(cfg['psf_count'],-1).astype('float64')
    norms=np.linalg.norm(f,axis=1)
    cosine=(f@f.T)/(norms[:,None]*norms[None,:])
    min_cos=float(cosine[np.triu_indices(cfg['psf_count'],1)].min())
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
    if sha(source)!=sha(target):raise RuntimeError('Installed bank hash mismatch')
    save(lock,dict(count=cfg['psf_count'],kernel_shape=[101,101],bank_sha256=sha(target),
                   source_path=str(source.resolve()),source_sha256=sha(source),
                   source_provenance=metadata,minimum_pairwise_cosine=min_cos,
                   installed_utc=now(),adaptive_identifiability_validated=False,
                   test_only=args.test_only))
    print('BANK_INSTALLED',target,'sha256',sha(target),'minimum_cosine',min_cos)
if __name__=='__main__':main()
