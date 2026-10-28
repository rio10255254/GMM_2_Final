"""Prepare publication numbers only after both data rechecks pass."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/separate_conditions'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=load(OUT/'20x_complete.json');b=load(OUT/'50x_complete.json');assert a['passed'] and b['passed']
scan=pd.read_csv(OUT/'20x_scan_sd.csv');fifty=pd.read_csv(OUT/'50x_condition_sd.csv');methods=['Raw','Wiener','MOSR']
sd20={m:scan[scan.method==m].sort_values('run_index').step_sd_nm.tolist() for m in methods}
pooled20={m:a['methods'][m]['pooled_within_scan_sd_nm'] for m in methods}
sd50={m:float(fifty[(fifty.sequence=='50x_x_1um')&(fifty.method==m)].step_sd_nm.iloc[0]) for m in methods}
gains20=100*(1-np.array(sd20['MOSR'])/np.array(sd20['Raw']))
gain20=100*(1-pooled20['MOSR']/pooled20['Raw']);gain50=100*(1-sd50['MOSR']/sd50['Raw'])
images={}
for m in ['Raw','MOSR']:
    p=ROOT/f'poster_build/scan_assets/repeat20x_{m}.png';assert Image.open(p).size==(96,96)
    images['20x_'+m]={'path':str(p),'width_px':96,'scale_um_per_px':.1725,'sha256':sha(p)}
    p=ROOT/f"inspection/images/1_0003_{'R152' if m=='MOSR' else m}.png"
    images['50x_'+m]={'path':str(p),'width_px':Image.open(p).size[0],'scale_um_per_px':.069,'sha256':sha(p)}
data=dict(public_model_name='MOSR',main_step_um=1.0,no_cross_condition_average=True,
          twenty=dict(condition='20x, 1 um',scans=30,steps_per_scan=30,scan_sd_nm=sd20,pooled_within_scan_sd_nm=pooled20,relative_reduction_pct=gain20,per_scan_reduction_min_pct=float(gains20.min()),per_scan_reduction_max_pct=float(gains20.max()),improved_scans=30),
          fifty=dict(condition='50x, 1 um',locked_pairs=30,step_sd_nm=sd50,relative_reduction_pct=gain50),
          supplementary_half_step=fifty[fifty.sequence=='50x_x_0p5um'].to_dict('records'),images=images,
          scientific_scope='Two acquisition cohorts at a common nominal 1 um step, displayed separately; no direct controlled comparison of magnification alone.',
          reader='Thesis normal-gradient geometric LSC, 64 boundary points at 20x and 96 at 50x; fixed initialization state per pillar.',
          source_hashes={str(p.relative_to(ROOT)):sha(p) for p in [OUT/'20x_scan_sd.csv',OUT/'20x_steps.csv',OUT/'50x_steps.csv',OUT/'50x_condition_sd.csv',OUT/'protocol_lock.json']})
(OUT/'poster_data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'gain20':gain20,'gain50':gain50,'values20':pooled20,'values50':sd50,'image_widths':{k:v['width_px'] for k,v in images.items()}},indent=2))
