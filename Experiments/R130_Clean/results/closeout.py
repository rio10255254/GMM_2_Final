"""Record checked findings and navigation only. Frozen execution code stays intact."""
from pathlib import Path
import sys,json,hashlib,os,shutil
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1];sys.path.insert(0,str(ROOT))
from utils import load,save,sha,verify_frozen,verify_protected,now

def main():
 final=load(ROOT/'results/complete.json');audit=load(ROOT/'results/independent_review/verification.json');train=load(ROOT/'results/independent_final_training_audit.json')
 assert final['training_updates']==8192 and final['images']==930 and audit['outputs_sha256_verified']==930 and train['all_final_optimizer_steps']==8192
 verify_frozen(load(ROOT/'config/source_lock.json'));verify_protected()
 timing=load(ROOT/'results/runtime_comparison_scope.json');profile=load(ROOT/'results/profile.json');fresh=load(ROOT/'results/profile_tiled_fresh.json')
 dims=pd.read_csv(ROOT/'results/comparison/shape_size_summary.csv').set_index('model');disp=pd.read_csv(ROOT/'results/comparison/displacement_summary.csv');sem=pd.read_csv(ROOT/'results/comparison/SEM_comparison.csv');blocks=pd.read_csv(ROOT/'results/independent_review/time_block_sensitivity.csv')
 pct=100*(1-dims.loc['R130-Clean','diameter_repeat_sd_nm']/dims.loc['R129','diameter_repeat_sd_nm']);speed=timing['R129_historical_load_infer_save_median_seconds']/timing['R130_load_infer_save_median_seconds']
 verdict='值得保留為快速、來源乾淨的純神經研究版本；已保留R129的主要位移穩定性，但沒有解決尺寸偏大，也不是所有形狀指標都更好。'
 addition=f'''

## 獨立複核後的決斷

**{verdict}** 不自動替換R129或論文主模型，也不改正式基準。

- 短步平均PI差R129 4.125nm、R130-Clean 4.121nm，差距只有約0.004nm。完整掃描配對及分開前6／後24的時間分組範圍均包含零，應解讀為相近，不宣稱精度勝出。
- 尺寸重拍波動19.231→16.422nm，降低{pct:.1f}%；輪廓重拍18.437→18.579nm相近；去平均半徑後的形狀重拍15.789→16.670nm稍退。
- 觀察最大短步PI差16.868→20.414nm，需與平均值一起保留。距起點平均表現也未明確分出勝負。
- SEM平均直徑偏大224.472→219.409nm，只少約5.064nm；拿掉明確光學路徑並未自然消除此問題。不能把多處架構與訓練差異直接當成PSF單項因果實驗。
- SEM去尺寸形狀差在方向1由32.636→28.093nm，但方向2由17.243→19.409nm。方向仍未唯一確認，不能挑有利方向宣稱全面形狀改善。
- 完整1544×2064影像，純神經約1.38秒；含讀取／寫檔約1.87秒。R129歷史同類含讀寫紀錄約11.18秒，描述性比值約{speed:.2f}倍；不是此次重新載入R129作同時段微基準。

### 低記憶體操作的補核

另以只跑切塊的新程序確認，固定512core／96halo、FP32，後兩次約{np.median([x['seconds'] for x in fresh['records'][1:]]):.3f}秒／完整影像。峰值張量配置{max(x['allocated_peak_bytes'] for x in fresh['records'])/1024**3:.3f}GiB，CUDA預留{max(x['reserved_peak_bytes'] for x in fresh['records'])/1024**3:.3f}GiB；兩者都不含其他程序與驅動佔用，不可把張量數字直接當整張卡的需求。原full-first混合測試的reserved值會保留前面整張推論的allocator快取，故另存這份fresh結果。

切塊與原整張輸出的最大灰階差為{fresh['max_difference_from_saved_full']:.3g}（0–1灰階），通過事前2e-6容許值；沒有羽化或縮小實際影像。此為浮點範圍內相符，不稱逐位元完全相同。

### 來源及結果再次核對

8192筆順序／種子／損失算術與最終optimizer步數全部核對；48次實際輸入獨立重建吻合。最終所有參數有限，初始scratch狀態由新種子獨立重現。930個新NPZ逐檔SHA256與原記錄符合；直接由圓心再算三方法位移摘要，最大差1.78e-15nm。新8370圓另行擬合最大差3.21e-7像素。所有受保護舊檔保持原樣，沒有重設歷史預期雜湊。

{blocks.to_markdown(index=False,floatfmt='.3f')}

### 圖像及形狀檢視

已查看固定首張完整視野、同一量測區域、最大短步誤差案例及九顆平均形狀。所看影像主結構仍存在，並非輸出成完全正圓；最差例仍有局部暗斑或灰階起伏。這些觀察不認證任意細節真實，亦不能排除光學解析度以外的過度平滑。與SEM的對應／尺寸限制依舊適用。

![九顆平均形狀及SEM工作方向](figures/independent_mean_shapes.png)

![最大短步誤差案例](figures/worst_adjacent_observation.png)

獨立核對位於results/independent_review；檢查程式另存results/independent_result_review.py及自身雜湊。這些是完成後的獨立審閱，不改動凍結訓練、模型或共同讀法。
'''
 p=ROOT/'reports/R130_CLEAN_RESULTS.md';s=p.read_text(encoding='utf-8');assert '## 獨立複核後的決斷' not in s;p.write_text(s+addition,encoding='utf-8')
 p=ROOT/'README.md';s=p.read_text(encoding='utf-8');i=s.index('\n\n');s=s[:i]+f'\n\n**本輪已完成：8192次scratch訓練、930張原尺寸重建、8370輪廓及全部指定比較／效率檢查。** {verdict} 完整數字見 [結果報告](reports/R130_CLEAN_RESULTS.md)。\n'+s[i:];p.write_text(s,encoding='utf-8')
 before=ROOT/'results/governance_before_closeout';before.mkdir(exist_ok=True)
 for name in ['PROJECT_STATE.md','ESTIMATOR_POLICY.json','Experiments/INDEX.md','docs/operations/PROJECT_STORAGE_REGISTRY.json']:
  shutil.copy2(REPO/name,before/Path(name).name)
 p=REPO/'PROJECT_STATE.md';s=p.read_text(encoding='utf-8-sig');a=s.index('<!-- R130_CLEAN_SCRATCH_20260920 -->');b=s.index('\n\n',a)
 s=s[:a]+'''<!-- R130_CLEAN_SCRATCH_20260920 -->
R130-Clean完整執行及獨立複核完成（2026-09-20）：PSF OFF、scratch8192更新、930原尺寸影像及8370輪廓；短步差4.121nm與R1294.125nm相近，尺寸重拍16.422nm較R12919.231nm低；形狀波動稍退、SEM尺寸偏大仍219.409nm。原尺寸神經推論約1.38秒；full/tile差1.49e-7。保留為快速純神經研究版本，不改正式基準或自動換論文模型。 [結果](Experiments/R130_Clean/reports/R130_CLEAN_RESULTS.md)
'''+s[b:];p.write_text(s,encoding='utf-8')
 p=REPO/'Experiments/INDEX.md';s=p.read_text(encoding='utf-8-sig');a=s.index('## R130-Clean 原尺寸 scratch 新規格');b=s.find('\n## ',a+4);b=len(s) if b<0 else b
 s=s[:a]+'''## R130-Clean 原尺寸 scratch 新規格

2026-09-20完成：300101參數、PSF OFF、生成資料scratch8192更新及930張固定實拍驗收。位移保留R129水準、尺寸重拍改善，尺寸偏差仍在；完整影像神經推論約1.38秒。未升級正式基準。 [操作與來源](R130_Clean/README.md) · [完整結果](R130_Clean/reports/R130_CLEAN_RESULTS.md)
'''+s[b:];p.write_text(s,encoding='utf-8')
 p=REPO/'ESTIMATOR_POLICY.json';policy=load(p);baseline=json.dumps(policy['formal_baseline'],sort_keys=True);assert not any(x.get('candidate_id')=='R130_Clean_NativeScratch' for x in policy['open_side_tracks'])
 policy['open_side_tracks'].insert(0,dict(candidate_id='R130_Clean_NativeScratch',round='R130-Clean user specification 20260920',experiment='Experiments/R130_Clean',status='completed_clean_scratch_research_not_promoted',mainline_status='research_only_formal_baseline_unchanged',training=dict(initialization='scratch',pretrained=False,PSF='off',real_training=False,updates=8192,final_checkpoint_sha256=final['final_checkpoint_sha256']),evaluation=dict(images=930,circles=8370,source_scope='existing corrected corner9,30scans,20x',adjacent_mae_nm=4.121476418004834,diameter_repeatability_nm=float(dims.loc['R130-Clean','diameter_repeat_sd_nm']),interpretation=verdict),reports=dict(results_md=str(ROOT/'reports/R130_CLEAN_RESULTS.md'),provenance_md=str(ROOT/'reports/TRAINING_PROVENANCE.md'))))
 policy['notes'].append('2026-09-20 R130-Clean: new native-resolution scratch model per user specification; no historical neural weights or explicit PSF, no real/SEM/PI training.8192updates and930-image fixed-reader comparison complete. PI accuracy similar toR129, diameter repeatability improves, shape-repeatability and worst adjacent error trade off;SEM size bias unresolved. No formal promotion or thesis-model replacement. Historical evidence preserved.')
 assert json.dumps(policy['formal_baseline'],sort_keys=True)==baseline;save(p,policy)
 p=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';registry=load(p)
 own_bytes=0
 for directory,subdirs,files in os.walk(ROOT):
  subdirs[:]=[x for x in subdirs if not (Path(directory)/x).is_junction()]
  own_bytes+=sum((Path(directory)/x).stat().st_size for x in files)
 bulk_bytes=sum(p.stat().st_size for p in (ROOT/'results/reconstruction').glob('*/*') if p.is_file())
 entry=next(x for x in registry['entries'] if x['id']=='r130_clean_native_scratch');entry.update(state='completed_training_and_fixed_real_comparison_not_promoted',size_gib_snapshot=own_bytes/1024**3,active_bulk_gib_snapshot=bulk_bytes/1024**3);registry['updated_at']=now();save(p,registry)
 verify_frozen(load(ROOT/'config/source_lock.json'));verify_protected()
 summary=dict(state='complete_and_independently_reviewed',scope=verdict,training_updates=8192,images=930,circles=8370,parameter_count=300101,final_checkpoint_sha256=final['final_checkpoint_sha256'],old_sources_unchanged=True,formal_baseline_unchanged=True,thesis_model_not_automatically_changed=True,program_and_small_artifacts_GiB=own_bytes/1024**3,bulk_output_GiB=bulk_bytes/1024**3,reviewed_figures=['training_curves.png','displacement.png','repeatability.png','native_nine_example.png','independent_mean_shapes.png','worst_adjacent_observation.png'],completed_utc=now())
 save(ROOT/'results/final_review_complete.json',summary)
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
