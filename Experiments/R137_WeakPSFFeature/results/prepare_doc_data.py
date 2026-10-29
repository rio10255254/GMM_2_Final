from pathlib import Path
import ast,json,hashlib,shutil,zipfile,datetime
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
PROJECT_ROOT = Path(__file__).resolve().parents[3]
R=Path(str(PROJECT_ROOT / 'Experiments/R137_WeakPSFFeature'));B=R.parent/'R130_Clean';P=Path(str(PROJECT_ROOT / 'Deliverables/Thesis_Handoffs/R137_WeakPSF_Web_Documents_20260922'))
assert not P.exists();P.mkdir()
for n in ['完整數據','圖表','閱讀文字版','來源與核對']:(P/n).mkdir()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
for rel,h in load(R/'config/source_lock.json').items():assert sha(R/rel)==h
for x in load(R/'config/protected_sources.json'):assert sha(str(PROJECT_ROOT / x['path']))==x['sha256']
t=load(R/'runs/formal_8192/training_complete.json');assert sha(t['final_checkpoint']['path'])==t['final_checkpoint']['sha256']
log=[json.loads(s) for s in (R/'runs/formal_8192/updates.jsonl').read_text().splitlines()];old=[json.loads(s) for s in (B/'runs/formal_8192/updates.jsonl').read_text().splitlines()]
assert len(log)==len(old)==8192
for a,b in zip(log,old):
 for k in ['step','epoch','position','parent_id','parent_sha256','input_sha256','noise_seed','learning_rate']:assert a[k]==b[k],(a['step'],k)
S=R/'results/comparison';tables={p.stem:pd.read_csv(p) for p in S.glob('*.csv')}
source=[]
def cp(src,dest):
 dst=P/dest;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);assert sha(src)==sha(dst);source.append(dict(copy=dst.relative_to(P).as_posix(),source=str(src),sha256=sha(src)))
for p in S.iterdir():
 if p.is_file():cp(p,'完整數據/'+p.name)
for n in ['PSF_activity_real_examples.csv','PSF_on_off_generated32.csv','reconstruction_runtime.csv','profile.json','final_audit.json','preflight.json','independent_status_review.json','independent_early_training_audit.json']:
 cp(R/'results'/n,'完整數據/'+n)
for n in ['config_r137_psf.yaml','model_r137_psf.py','batch_prediction.py','dataset_r137_psf.py','losses_r137_psf.py','compare_measurements.py','optical/feature.py','config/source_lock.json','calibration/INHERITED_PROVENANCE.json','calibration/measured_psf_bank.npz']:
 cp(R/n,'來源與核對/'+n)
for n in ['training_complete.json','run_config.json','updates.jsonl']:
 cp(R/'runs/formal_8192'/n,'完整數據/training/'+n)
for p in (R/'runs/formal_8192/evaluations').glob('*.json'):cp(p,'完整數據/training/evaluations/'+p.name)
for n in ['capture_plan.json','measurement_config.json','calibration.json','sem_scale.json','sem_mapping_candidates.json','sem_points.npz','tracking.csv']:cp(R/'evaluation'/n,'完整數據/evaluation/'+n)
for model in ['Raw','R129','R130-Clean','R137-WeakPSF']:
 base=R/'results/centers' if model=='R137-WeakPSF' else R/'evaluation/baseline_centers'/model
 for p in base.glob('*.npz'):cp(p,'完整數據/輪廓點/'+model+'/'+p.name)
# Document the user's qualified explanation; preserve observed timings unchanged.
explanation='2026年9月22日，使用者補充：這次較慢估計是 GPU 同時被另一個訓練程序佔用。此為使用者提出的可能原因；本輪沒有保存足以重建全程共用程度的 GPU 程序利用率時間序列，故不能量化影響，也不能證實所有時間差都由它造成。'
addendum='# R137 執行時間解讀補充\n\n'+explanation+'\n\n既有6.9887秒重建及12.7729秒含讀寫中位數保留為本次執行紀錄，不作模型固有效率排名，不宣稱PSF造成相應倍數減速。R130歷史1.384秒及1.867秒也不是同時控制資源條件的對照。若之後要正式比較速度，須在GPU獨占或負載受控、相同精度尺寸與暖機規則下重測；本次整理未新增測速。\n\n此補充調整速度的解讀，不變更已保存模型、重建、量測數據或原始計時。\n'
add=R/'reports/R137_RUNTIME_SCOPE_ADDENDUM.md';assert not add.exists();add.write_text(addendum,encoding='utf-8')
cp(add,'來源與核對/R137_RUNTIME_SCOPE_ADDENDUM.md');cp(R/'reports/R137_RESULTS.md','來源與核對/R137_RESULTS_original.md')
figs={}
for key,src in {'displacement':R/'reports/figures/displacement.png','onoff':R/'reports/figures/PSF_on_off_example.png','selected':Path(str(PROJECT_ROOT / 'Deliverables/Thesis_Handoffs/R129_Corrected_Corner9_Thesis_Handoff_20260920/03_Sampling_and_SEM/selected_nine.png'))}.items():cp(src,'圖表/'+key+'.png');figs[key]=P/'圖表'/(key+'.png')
colors={'Raw':'#777777','R129':'#2774AE','R130-Clean':'#E47722','R137-WeakPSF':'#198754'}
def figsave(fig,key):fig.savefig(P/'圖表'/(key+'.png'),dpi=180,bbox_inches='tight');fig.savefig(P/'圖表'/(key+'.svg'),bbox_inches='tight');plt.close(fig);figs[key]=P/'圖表'/(key+'.png')
fig,axs=plt.subplots(1,2,figsize=(11,3.6),layout='constrained')
for root,m in [(B,'R130-Clean'),(R,'R137-WeakPSF')]:
 l=[json.loads(v)['loss'] for v in (root/'runs/formal_8192/updates.jsonl').read_text().splitlines()];dev=[load(p) for p in sorted((root/'runs/formal_8192/evaluations').glob('dev_*.json'))]
 axs[0].plot(np.arange(128,8193,128),np.array(l).reshape(-1,128).mean(1),label=m,color=colors[m]);axs[1].plot([v['step'] for v in dev],[v['means']['total'] for v in dev],label=m,color=colors[m])
for ax,title in zip(axs,['Training loss, 128-update mean','Fixed synthetic development']):ax.set(title=title,xlabel='Update',ylabel='Objective');ax.legend();ax.grid(alpha=.2)
figsave(fig,'training')
g=tables['shape_size_summary'];fig,axs=plt.subplots(1,3,figsize=(12,3.5),layout='constrained')
for ax,key,title in zip(axs,['diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm'],['Diameter repeatability','Contour repeatability','Size-removed shape repeatability']):
 v=[g[g.model==m].iloc[0][key] for m in colors];bars=ax.bar(list(colors),v,color=list(colors.values()));ax.bar_label(bars,fmt='%.2f',fontsize=8);ax.set(title=title,ylabel='SD nm',ylim=(0,max(v)*1.2));ax.tick_params(axis='x',labelrotation=25,labelsize=8)
figsave(fig,'repeatability')
sem=tables['SEM_comparison'];fig,axs=plt.subplots(1,3,figsize=(12,3.5),layout='constrained')
for ax,key,title in zip(axs,['mean_diameter_difference_nm','full_radial_difference_nm','de_size_shape_difference_nm'],['Signed diameter difference','Full radial difference','Size-removed shape difference']):
 for cand,off in [(1,-.18),(2,.18)]:
  z=[sem[(sem.model==m)&(sem.mapping_candidate==cand)].iloc[0][key] for m in colors];ax.bar(np.arange(4)+off,z,.34,label='Mapping '+str(cand),alpha=1 if cand==1 else .5,color=list(colors.values()))
 ax.set_xticks(range(4),list(colors),rotation=25,fontsize=8);ax.set(title=title,ylabel='nm');ax.legend(fontsize=8)
figsave(fig,'SEM')
# Compute readable per-pillar and per-position statistics from the complete saved observations.
C=tables['all_circles'];assert len(C)==33480
plan=load(R/'evaluation/capture_plan.json');runs=[v['run'] for v in plan['runs']];pillars=[];positions=[]
for m in colors:
 z=C[C.model==m].copy();z['order']=z.run.map({r:i for i,r in enumerate(runs)});z=z.sort_values(['order','index','pillar_id']);di=z.diameter_nm.to_numpy().reshape(30,31,9)
 with np.load(S/(m+'_radial_profiles.npz')) as f:rad=f['radius_nm'].astype(float)
 shape=rad-rad.mean(-1,keepdims=True)
 for k in range(9):pillars.append(dict(model=m,pillar_id=k+1,diameter_mean_nm=di[:,:,k].mean(),diameter_sd_nm=np.sqrt(di[:,:,k].var(0,ddof=1).mean()),contour_sd_nm=np.sqrt(rad[:,:,k].var(0,ddof=1).mean()),shape_sd_nm=np.sqrt(shape[:,:,k].var(0,ddof=1).mean())))
 for j in range(31):positions.append(dict(model=m,position=j,diameter_mean_nm=di[:,j].mean(),diameter_sd_nm=np.sqrt(di[:,j].var(0,ddof=1).mean()),contour_sd_nm=np.sqrt(rad[:,j].var(0,ddof=1).mean()),shape_sd_nm=np.sqrt(shape[:,j].var(0,ddof=1).mean())))
pd.DataFrame(pillars).to_csv(P/'完整數據/per_pillar_statistics.csv',index=False);pd.DataFrame(positions).to_csv(P/'完整數據/per_position_geometry.csv',index=False)

save(P/'來源與核對/SOURCE_COPIES.json',source)
