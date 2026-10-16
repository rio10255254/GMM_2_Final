"""Read-only final checks; writes only a new record, never updates expectations."""
from pathlib import Path
import hashlib,json
import cv2,numpy as np,pandas as pd
OUT=Path(__file__).resolve().parent
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
snapshot=json.loads((OUT/'input_snapshot.json').read_text())
changed=[p for p,h in snapshot.items() if not Path(p).is_file() or sha(p)!=h]
assert not changed,changed
render=json.loads((OUT/'render_audit.json').read_text())
for record in render['exposures']:
    folder=OUT/'images'/str(record['exposure'])
    for name,digest in record['files'].items():assert sha(folder/name)==digest
    arrays={m:cv2.imread(str(folder/f'{m}.png'),0).astype(float) for m in ['Raw','base','no_shift','attenuation']}
    correction=lambda m:float(np.abs(arrays[m]-arrays['Raw']).mean())
    assert abs(correction('no_shift')-correction('attenuation'))<2e-6
    assert record['base_reproduction']['different_pixels']==0
    assert record['detail_component_shared_exactly']
f=pd.read_csv(OUT/'measurements.csv');assert len(f)==1728 and (f.valid==1).all()
assert not f.duplicated(['exposure','pillar','method']).any()
assert set(f.method)=={'Raw','base','no_shift','attenuation'}
assert all(n==36 for n in f.groupby(['exposure','method']).size())
p=f.pivot(index=['exposure','pillar'],columns='method',values='boundary')
s=json.loads((OUT/'analysis_summary.json').read_text())
delta=p.no_shift-p.base
assert (delta<0).sum()==s['no_shift_vs_base_observations']['improved']
assert (delta>0).sum()==s['no_shift_vs_base_observations']['worsened']
assert (delta.groupby(level='exposure').median()<0).sum()==s['exposures_with_negative_median_no_shift_vs_base']
assert (delta.groupby(level='pillar').median()<0).sum()==s['no_shift_vs_base_pillars']['improved']
for name in ['cross_exposure_results.png','all_exposure_images.png','review_examples.png']:
    image=cv2.imread(str(OUT/name));assert image is not None and min(image.shape[:2])>500
old_helper=(OUT.parent/'causal_audit_20260905/audit_sem_paths.m').read_text().split('function centers = sort_grid_centers',1)[1]
new_helper=(OUT/'measure_sem.m').read_text().split('function centers = sort_grid_centers',1)[1]
assert old_helper==new_helper
report={'verification':'observations, historical parity, source preservation and paired counts checked',
        'protected_files_checked':len(snapshot),'changed_protected_files':changed,
        'historical_raw_base_masks_exact':864,'image_outputs_checked':48,'measurement_rows':1728,
        'initial_export_check_failure':'Preserved; explained by known historical mat2gray display export. Separate replay checks historical display exports and original intensity crops on all 864 cases.',
        'scientific_scope':'One frozen model, one sample, all 12 existing exposures. No training, promotion or unseen-confirmation claim.',
        'verification_code_sha256':sha(__file__),
        'code_and_protocol_sha256':{p.name:sha(p) for p in OUT.iterdir() if p.suffix in ['.py','.m'] or p.name in ['protocol.json','input_snapshot.json']}}
with (OUT/'verification.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))
