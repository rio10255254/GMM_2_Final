from pathlib import Path
import json,hashlib,zipfile,html
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[1];B=R/'results/sem_corner9';REPO=R.parents[1]
report=R/'reports/R136_SEM_CORNER9_RESULTS.md'
lead='''這次新九顆：R128短步PI差3.708nm，優於R129的4.125nm，30次中23次較低，完整掃描配對差距範圍為−0.620至−0.221nm；起點相對位移R128與R129差距未明確。R128尺寸重拍波動9.527nm最小；但九顆平均直徑相對SEM偏大222.040nm，R61偏大115.803nm較小。不能把穩定性改善寫成尺寸準確度改善。R61曾使用相關SEM尺寸訓練，其優勢不是未知答案的獨立驗證。\n\n'''
t=report.read_text(encoding='utf-8');t=t.replace('## 回答先前的資料問題',lead+'## 回答先前的資料問題',1);report.write_text(t,encoding='utf-8')
p=B/'index.html';s=p.read_text(encoding='utf-8');s=s.replace('<pre>','<p>'+html.escape(lead)+'</p><pre>',1);p.write_text(s,encoding='utf-8')
# Independent recheck of shape/size summary, and include the nine SEM contours in package.
df=pd.read_csv(B/'shape_size/per_contour.csv');summary=pd.read_csv(B/'shape_size/summary.csv')
for row in summary.itertuples():
 d=df[df.model==row.model];assert len(d)==8370
 assert abs(np.sqrt(d.groupby(['index','pillar_id']).diameter_nm.var(ddof=1).mean())-row.diameter_repeat_sd_nm)<1e-9
 pts=np.load(B/f'shape_size/{row.model}_radial_profiles.npz')['radius_nm'].astype(float);pts-=pts.mean(axis=-1,keepdims=True)
 assert abs(np.sqrt(pts.var(axis=0,ddof=1).mean())-row.shape_repeat_sd_nm)<1e-4
truthpath=R.parent/'R135_UnifiedModelComparison/results/Raw/sem/points.npz';allp=np.load(truthpath);ids=[22,23,24,28,29,30,34,35,36]
np.savez_compressed(B/'sem_nine_original_reference_points.npz',**{f'SEM_{i}':allp[f'SEM_{i}'] for i in ids})
cfg=R/'config/sem_corner9_lsc_plan.json';(B/'selection_config.json').write_text(cfg.read_text(),encoding='utf-8')
status={'status':'repeated_measurements_and_group_sem_comparison_complete','frames_per_model':930,'centers_per_model':8370,'independent_circle_refits':33480,'plots_reviewed':['selected_nine.png','displacement_comparison.png','shape_size/figures/thirty_repeat_contours.png','shape_size/figures/repeatability.png','sem_contours_candidate1.png','sem_contours_candidate2.png'],'shape_summary_independently_rechecked':True,'sem_ids_set':ids,'individual_orientation':'two candidates retained; not uniquely confirmed','full_system_uncertainty':'unknown components remain','previous_results':'preserved','training':'untouched','sem_points_source':str(truthpath),'sem_points_source_sha256':hashlib.sha256(truthpath.read_bytes()).hexdigest()}
(B/'delivery_status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
note='R136十字中心九顆重算完成（2026-09-19）：四組各930張／8370圓心；R128短步差3.708nm、尺寸波動9.527nm最小；SEM九顆集合均徑差R61+115.803nm、R128+222.040nm。集合22,23,24,28,29,30,34,35,36；逐顆方向保留兩候選。舊九顆有影像與PI但未配SEM，不混成尺寸真值證據。'
link='[新九顆報告](Experiments/R136_PIRepeatability/reports/R136_SEM_CORNER9_RESULTS.md)';marker='<!-- R136_CORNER9_COMPLETE -->'
p=REPO/'PROJECT_STATE.md';s=p.read_text(encoding='utf-8-sig')
if marker not in s:
 s=s.replace('### Open Research / Side Tracks','### Open Research / Side Tracks\n'+marker+'\n'+note+' '+link+'\n',1)
 s=s.replace('### R136 SEM追加對照','### R136 十字中心九顆\n\n'+note+' '+link+'\n\n### R136 SEM追加對照',1);p.write_text(s,encoding='utf-8')
p=REPO/'Experiments/INDEX.md';s=p.read_text(encoding='utf-8-sig')
if marker not in s:p.write_text(s+'\n'+marker+'\n'+note+' [報告](R136_PIRepeatability/reports/R136_SEM_CORNER9_RESULTS.md)\n',encoding='utf-8')
p=REPO/'ESTIMATOR_POLICY.json';d=json.loads(p.read_text(encoding='utf-8-sig'))
def walk(x):
 if isinstance(x,dict):
  if x.get('round')=='R136' and x.get('experiment')=='Experiments/R136_PIRepeatability':x['sem_corner9']={'status':status['status'],'report':'Experiments/R136_PIRepeatability/reports/R136_SEM_CORNER9_RESULTS.md','note':note,'formal_promotion':False}
  else:
   for y in x.values():walk(y)
 elif isinstance(x,list):
  for y in x:walk(y)
walk(d);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (R/'HANDOFF.md').open('a',encoding='utf-8') as f:f.write('\n## Corner nine completed 2026-09-19\n'+note+' Full readouts, LSC checks, shape statistics, R129 uncertainty and SEM group-size comparison in results/sem_corner9. No GPU inference/training. Keep both SEM orientation candidates; never select by model score. Previous center9 preserved.\n')
manifest=[]
for p in B.rglob('*'):
 if p.is_file():manifest.append({'path':p.relative_to(B).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(B/'package_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
package=R/'output/R136_SEM_Corner9_Results.zip'
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
 for p in B.rglob('*'):
  if p.is_file():z.write(p,p.relative_to(B))
 z.write(report,report.name)
 for p in (R/'scripts').glob('*corner9*.py'):z.write(p,'scripts/'+p.name)
with zipfile.ZipFile(package) as z:assert z.testzip() is None
print('Rechecks passed; registered; package verified:',package,package.stat().st_size)
