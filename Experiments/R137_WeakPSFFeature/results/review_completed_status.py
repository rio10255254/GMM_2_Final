from pathlib import Path
import json,hashlib,numpy as np,pandas as pd,shutil,datetime
P=Path(r'D:\GMM_2_Final\Experiments\R137_WeakPSFFeature');repo=P.parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
for rel,h in load(P/'config/source_lock.json').items():assert sha(P/rel)==h,rel
for x in load(P/'config/protected_sources.json'):assert sha(x['path'])==x['sha256'],x['path']
t=load(P/'runs/formal_8192/training_complete.json');assert t['unique_updates']==8192 and sha(t['final_checkpoint']['path'])==t['final_checkpoint']['sha256']
rows=[json.loads(s) for s in (P/'runs/formal_8192/updates.jsonl').read_text().splitlines()];assert [r['step'] for r in rows]==list(range(1,8193))
C=pd.read_csv(P/'results/comparison/all_circles.csv');D=pd.read_csv(P/'results/comparison/all_displacements.csv');assert len(C)==33480 and len(D)==7200
u=np.array(load(P/'evaluation/calibration.json')['axis_unit_vector']);errors=[]
for (m,run),g in C.groupby(['model','run']):
 xy=g.sort_values(['index','pillar_id'])[['center_x_px','center_y_px']].to_numpy().reshape(31,9,2)
 for kind in ['adjacent','start']:
  z=D[(D.model==m)&(D.run==run)&(D.kind==kind)].sort_values('j');delta=xy[1:]-(xy[:-1] if kind=='adjacent' else xy[:1]);pred=(np.median(delta,axis=1)@u*.1725-z.pi_displacement_um.to_numpy())*1000;errors.extend(abs(pred-z.error_nm.to_numpy()))
assert max(errors)<1e-8
runpd=pd.read_csv(P/'results/reconstruction_runtime.csv');assert len(runpd)==930 and all(Path(p).is_file() for p in runpd.output_path)
proof=dict(checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checkpoint_sha256=t['final_checkpoint']['sha256'],training_updates=8192,reconstruction_files_present=930,all_methods_circle_rows=len(C),independent_aggregate_displacements=len(D),maximum_difference_nm=max(errors),protected_sources_unchanged=True,formal_baseline_changed=False)
save(P/'results/independent_status_review.json',proof)
# Close out the active status only after verifying the actual products.
p=P/'README.md';s=p.read_text(encoding='utf-8');s=s.replace('狀態：前置檢查通過，正式8192次訓練執行中；完成後自動驗證930張影像。','狀態：8192次訓練、930張重建與8370次圓量測已完成，2026-09-22另行核對全部7200筆四方法位移相符。');s+='\n## 結果摘要\n\n相對R130，短步平均差4.121→3.917nm，直徑重拍16.422→14.262nm，輪廓重拍18.579→17.710nm；平均直徑較SEM偏大219.409→222.383nm。長距離平均差未明確改善。PSF確實有作用，但不是所有指標都更好；保留研究版本，不自動更換正式基準。[完整結果](reports/R137_RESULTS.md)\n';p.write_text(s,encoding='utf-8')
summary='R137弱PSF測試完成（2026-09-22複核）：舊25PSF固定平均、特徵強度0.02，scratch8192次、930影像／8370圓。相對R130短步差4.121→3.917nm、直徑重拍16.422→14.262nm、輪廓重拍18.579→17.710nm；SEM尺寸偏大增至222.383nm、長距離無明確改善。完整7200筆四方法位移另行重算相符；保留研究版本，不升級正式基準。 [結果](Experiments/R137_WeakPSFFeature/reports/R137_RESULTS.md)'
p=repo/'PROJECT_STATE.md';s=p.read_text(encoding='utf-8-sig');lines=s.splitlines();i=lines.index('<!-- R137_WEAK_PSF_20260921 -->');lines[i+1]=summary;p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
p=repo/'Experiments/INDEX.md';s=p.read_text(encoding='utf-8-sig').replace('獨立8192次scratch與930影像驗證執行中，固定舊25PSF弱特徵輔助0.02；結果尚未完成，不升級基準。','獨立8192次scratch與930影像驗證完成；短步及輪廓重拍小幅改善，尺寸偏大仍存在，不升級基準。');p.write_text(s,encoding='utf-8')
p=repo/'docs/operations/PROJECT_STORAGE_REGISTRY.json';v=load(p)
for e in v['entries']:
 if e['id']=='r137_weak_psf_feature':e['state']='complete_verified_research_not_promoted'
save(p,v)
p=repo/'ESTIMATOR_POLICY.json';v=load(p);baseline=v['formal_baseline'].copy();v.setdefault('open_side_tracks',[])
if not any(q.get('candidate_id')=='R137_WeakPSFFeature' for q in v['open_side_tracks']):v['open_side_tracks'].append(dict(candidate_id='R137_WeakPSFFeature',status='complete_research_not_promoted',report='Experiments/R137_WeakPSFFeature/reports/R137_RESULTS.md',note='Legacy25 PSF feature gain0.02; scratch8192/full930 complete. Short-step and repeatability improve modestly vs R130; SEM diameter bias worsens slightly; runtime comparison is historical, not a matched causal benchmark.'))
assert v['formal_baseline']==baseline;save(p,v)
print(json.dumps(proof));print('Status documents now reflect verified completion; formal baseline unchanged')
