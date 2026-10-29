"""Verify historical SEM identities and prepare original R129 output policy on CPU."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import hashlib,json,shutil
import numpy as np
from scipy.io import savemat
PROJECT_ROOT = Path(__file__).resolve().parents[3]
R=Path(__file__).resolve().parents[1]; O=R/'results/sem_reference_followup';O.mkdir(exist_ok=True)
old=R.parent/'R135_UnifiedModelComparison'
sem=Path('H:/From_2TB_D_disk/13_thesis/SEM_data');copy=Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/20260618_100MG/SEM_data'));legacy=Path(str(PROJECT_ROOT / 'Shared_Sources/SEM_Originals'))
records=[]
for kind in ['P','V']:
 for i in range(1,10):
  name=f'{kind}-{i:02d}.tiff';paths=[sem/name,copy/name,legacy/name]
  hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths];assert len(set(hashes))==1
  records.append(dict(file=name,sha256=hashes[0],copies=[str(p) for p in paths]))
for name in ['SEM_center36_file_mapping.csv','SEM_P_V_pairing_map.png','P_3x3_verified_order.png','V_3x3_verified_order.png']:
 shutil.copy2(sem/'ordering_result_20260729'/name,O/name)
(O/'reference_inventory.json').write_text(json.dumps(dict(records=records,verified_files=18,current_R136_identity='pending; old 36-to-new 9 mapping not established'),indent=2),encoding='utf-8')
out=O/'R129_original80';out.mkdir(exist_ok=True)
for e in [13,14,15]:
 raw=np.load(old/f'results/Raw/sem/sem{e}_values.npz')['image'].astype(np.float32)
 v=np.load(old/f'results/R129_W16/sem/sem{e}_values.npz')['image']
 h,w=raw.shape;y,x=np.indices((h,w));d=np.minimum.reduce([y,h-1-y,x,w-1-x]);weight=np.clip((d-80)/16,0,1).astype(np.float32)
 result=raw+(v-raw)*weight
 assert np.array_equal(result[d<=80],raw[d<=80])
 # Preserve the stored interior exactly; second arithmetic pass can introduce one ulp.
 result[d>=96]=v[d>=96]
 savemat(out/f'sem{e}_values.mat',{'image':result})
 np.savez_compressed(out/f'sem{e}_values.npz',image=result)
(out/'policy.json').write_text(json.dumps({'source':'R135 stored R129_W16 floats, same fixed8192 checkpoint','transform':'raw + (W16-raw)*clip((edge_distance-80)/16,0,1); copy interior distance>=96 exactly','scope':'All positions used by guard80 transition have W16 weight=1; no inference/training. Underlying stored float has original guard arithmetic rounding.','boundary_guard':80,'transition':16,'original_sem_batch':True,'not_R136_30_scans':True},indent=2),encoding='utf-8')
print('18/18 SEM files matched across all 3 copies. Original80 R129 SEM floats prepared on CPU.')
