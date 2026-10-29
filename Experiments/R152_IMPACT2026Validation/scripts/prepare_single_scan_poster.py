"""Select the earliest thesis evaluation scan for the equal-30-step main poster."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/separate_conditions';SRC=Path(str(PROJECT_ROOT / 'Experiments/R152_R148v2_SafeAdaptivePSF'))
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
lock=load(OUT/'single_scan_presentation_lock.json');base=load(OUT/'poster_data.json');assert load(OUT/'20x_complete.json')['passed'] and load(OUT/'50x_complete.json')['passed']
twenty=pd.read_csv(OUT/'20x_steps.csv');twenty=twenty[twenty.run==lock['20x_run']].sort_values(['method','step'])
fifty=pd.read_csv(OUT/'50x_steps.csv');fifty=fifty[fifty.sequence==lock['50x_sequence']].sort_values(['method','start'])
methods=['Raw','Wiener','MOSR'];s20={};s50={};p20={};p50={}
for m in methods:
 a=twenty[twenty.method==m].displacement_nm.to_numpy();b=fifty[fifty.method==m].step_nm.to_numpy();assert len(a)==len(b)==30
 s20[m]=float(a.std(ddof=1));s50[m]=float(b.std(ddof=1));p20[m]=a.tolist();p50[m]=b.tolist()
full=load(OUT/'poster_data.json');plan=load(SRC/'evaluation/capture_plan.json');frame=next(f for f in plan['frames'] if f['run']==lock['20x_run'] and f['index']==0)
rawpath=Path(frame['source']['path']);assert sha(rawpath)==frame['source']['sha256'];raw=np.asarray(Image.open(rawpath),dtype=float)/255
reconpath=SRC/f"results/reconstruction/{lock['20x_run']}/01.npz";receipt=load(reconpath.with_suffix('.json'));assert sha(reconpath)==receipt['output_sha256'];recon=np.load(reconpath)['output']
centers=pd.read_csv(OUT/'20x_all_centers.csv');centers=centers[(centers.run==lock['20x_run'])&(centers['index']==0)&(centers.method=='Raw')]
x0=int(np.floor(centers.center_x_px.min()))-18;y0=int(np.floor(centers.center_y_px.min()))-18
side=max(int(np.ceil(centers.center_x_px.max()))+19-x0,int(np.ceil(centers.center_y_px.max()))+19-y0)
assets=ROOT/'poster_build/single_scan_assets';assets.mkdir(exist_ok=True)
images={}
for m,a in [('Raw',raw),('MOSR',recon)]:
 p=assets/f'20x_1um_{m}.png';Image.fromarray(np.rint(np.clip(a[y0:y0+side,x0:x0+side],0,1)*255).astype('uint8')).save(p)
 images['20x_'+m]=dict(path=str(p),width_px=side,scale_um_per_px=.1725,sha256=sha(p),source=str(rawpath if m=='Raw' else reconpath),crop=[x0,y0,x0+side,y0+side],display_range=[0,1])
 images['50x_'+m]=base['images']['50x_'+m]
deviations=np.concatenate([np.array(d[m])-1000 for d in [p20,p50] for m in methods]);limit=max(20,int(np.ceil(abs(deviations).max()/10))*10)
data=dict(public_model_name='MOSR',main_step_um=1.0,no_cross_condition_average=True,
 twenty=dict(condition='20x, 1 um',run=lock['20x_run'],run_index=lock['20x_run_index'],n_steps=30,step_sd_nm=s20,steps_nm=p20,relative_reduction_pct=100*(1-s20['MOSR']/s20['Raw'])),
 fifty=dict(condition='50x, 1 um',locked_pairs=30,step_sd_nm=s50,steps_nm=p50,relative_reduction_pct=100*(1-s50['MOSR']/s50['Raw'])),
 common_curve_axis_nm=[-limit,limit],images=images,selection_rule=lock['selection_rule'],source_hashes={str(p.relative_to(ROOT)):sha(p) for p in [OUT/'20x_steps.csv',OUT/'50x_steps.csv',OUT/'single_scan_presentation_lock.json']})
(OUT/'poster_data_30steps.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
twenty.to_csv(OUT/'main_20x_30steps.csv',index=False);fifty.to_csv(OUT/'main_50x_30pairs.csv',index=False)
print(json.dumps({'twenty':{k:v for k,v in data['twenty'].items() if k!='steps_nm'},'fifty':{k:v for k,v in data['fifty'].items() if k!='steps_nm'},'curve_range':[-limit,limit]},ensure_ascii=False,indent=2))
