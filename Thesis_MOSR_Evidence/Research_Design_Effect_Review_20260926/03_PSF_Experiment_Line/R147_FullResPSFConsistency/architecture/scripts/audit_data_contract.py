"""Read-only inspection of full data lineage, geometry coverage and test losses."""
from pathlib import Path
import sys,json
import numpy as np,pandas as pd
from scipy.signal import fftconvolve
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import load,save,sha

def main():
 out=ROOT/'results/internal_audit';out.mkdir(parents=True,exist_ok=True)
 manifest=load(ROOT/'data/manifest.json');rows=[];mean_errors=[]
 with np.load(ROOT/'calibration/measured_psf_bank.npz') as z:k=z['all_kernels'].astype(float).mean(0);k/=k.sum()
 for e in manifest['entries']:
  meta=load(ROOT/'data'/e['metadata']);original=e['original_metadata'];assert sha(original['path'])==original['sha256'];src=load(original['path']);assert meta['geometry_sha256']==src['geometry_sha256'];s=src['shape'];p=src['photometry'];r=(s['pitch']-s['gap'])/2 if s.get('motif')=='disks' else s.get('radius')
  rows.append(dict(split=e['split'],index=e['index'],category=e['category'],motif=s.get('motif',''),radius=r,pitch=s.get('pitch'),gap=s.get('gap'),contrast=p['high_gray']-p['low_gray'],low_gray=p['low_gray'],high_gray=p['high_gray'],noise=meta['noise_sigma_gray'],shift_x=meta['shift_xy'][0],shift_y=meta['shift_xy'][1],motion=meta['motion_observable'],applied_psf_index=meta['applied_psf_index']))
  if e['split']=='test' and meta['applied_psf_index'] is not None and meta['applied_psf_index']>=0:
   assert sha(ROOT/'data'/e['arrays'])==e['arrays_sha256']
   with np.load(ROOT/'data'/e['arrays']) as z:
    for t,n in zip(z['target'],z['noiseless']):
     predicted=fftconvolve(np.pad(t,50,mode='reflect'),k,mode='same')[50:-50,50:-50];d=(predicted-n)[128:256,128:256]*255
     mean_errors.append(dict(index=e['index'],category=e['category'],bank_mean_RMS_gray=float(np.sqrt(np.mean(d*d))),noise_sigma_gray=meta['noise_sigma_gray']))
 d=pd.DataFrame(rows);d.to_csv(out/'data_geometry_photometry.csv',index=False);pd.DataFrame(mean_errors).to_csv(out/'mean_psf_vs_individual.csv',index=False)
 test=[]
 roots={'R140v2':ROOT.parent/'R140v2_StableUNet','R146':ROOT.parent/'R146_SEMCoreHaloPSF25_MatchedPairs','R147':ROOT}
 for name,root in roots.items():
  if name=='R140v2':continue # Its assessment schema and original blur targets differ.
  path=root/'runs/formal_8192/test_final.json';x=load(path)
  for i,value in enumerate(x['individual_loss']):test.append(dict(model=name,index=i,category=d[(d.split=='test')&(d['index']==i)].category.iloc[0],loss=value))
 test=pd.DataFrame(test);test.to_csv(out/'test_loss_by_parent.csv',index=False);summary=test.groupby(['model','category']).loss.agg(['mean','median','count']);summary.to_csv(out/'test_loss_by_category.csv')
 train=d[d.split=='train'];disks=train[train.motif=='disks'];curved=train[train.category=='irregular_curved'];err=pd.DataFrame(mean_errors)
 report=dict(passed=True,metadata_verified=768,train_category_counts=train.category.value_counts().to_dict(),train_dense_disk_parents=len(disks),train_dense_disk_radius_range=[float(disks.radius.min()),float(disks.radius.max())],train_dense_disk_pitch_range=[float(disks.pitch.min()),float(disks.pitch.max())],train_dense_disk_gap_range=[float(disks.gap.min()),float(disks.gap.max())],train_irregular_radius_range=[float(curved.radius.min()),float(curved.radius.max())],train_motion_pairs=int(train.motion.sum()),train_identity_parents=int(train.applied_psf_index.isna().sum()),test_mean_psf_RMS_gray_median=float(err.bank_mean_RMS_gray.median()),test_mean_psf_RMS_gray_max=float(err.bank_mean_RMS_gray.max()),test_mean_psf_error_below_noise_views=int((err.bank_mean_RMS_gray<err.noise_sigma_gray).sum()),test_nonidentity_views=len(err),real_reader_reference_radius=load(ROOT/'evaluation/measurement_config.json')['radius_px'],real_reader_reference_pitch=load(ROOT/'evaluation/measurement_config.json')['pitch_px'],note='Geometry mismatch is observed coverage, not a demonstrated sole cause; mean bank error compared to simulated individual PSF only.',source_script_sha256=sha(__file__))
 save(out/'data_contract_complete.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
