"""Close out only when the R139 evidence record is truly complete."""
from pathlib import Path
import json
import pandas as pd
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from utils import ROOT,load,save,verify_frozen,verify_protected,verify_evaluation,now

def main():
 proof=load(ROOT/'results/complete.json');audit=load(ROOT/'results/final_audit.json');assert proof['updates']==8192 and proof['images']==930 and proof['circles']==8370
 assert audit['output_sha256_verified']==930 and audit['independent_aggregate_displacements']==10800
 verify_frozen(load(ROOT/'config/FORMAL_SOURCE_LOCK.json'));verify_protected();verify_evaluation()
 repo=ROOT.parents[1];report=ROOT/'reports/R139_RESULTS.md';assert report.is_file()
 p=repo/'PROJECT_STATE.md';text=p.read_text(encoding='utf-8-sig');marker='<!-- R139_UNET_PROTOTYPE_20260923 -->';lines=text.splitlines();i=lines.index(marker)
 lines[i+1]='R139 U-Net 加四次共享修正已完成固定8192次訓練、930張實拍重建及8370輪廓；相同資料與量測下的位移／尺寸／SEM結果見[報告](Experiments/R139_UNetRecurrentPrototype/reports/R139_RESULTS.md)。原模型與正式基準未自動更換。'
 p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
 p=repo/'Experiments/INDEX.md';text=p.read_text(encoding='utf-8-sig');text=text.replace('模型原型及資料相容前置檢查完成，**尚未訓練或產生實拍量測結論**。','模型已完成8192次訓練、930張實拍重建與量測；請讀 canonical R139_RESULTS 報告。');p.write_text(text,encoding='utf-8')
 registry=repo/'docs/operations/PROJECT_STORAGE_REGISTRY.json';v=load(registry)
 for row in v['entries']:
  if row['id']=='r139_unet_recurrent':row['state']='complete_research_not_promoted'
 save(registry,v)
 p=repo/'ESTIMATOR_POLICY.json';v=load(p);baseline=v['formal_baseline'].copy();v.setdefault('open_side_tracks',[])
 if not any(row.get('candidate_id')=='R139_UNetRecurrent' for row in v['open_side_tracks']):
  v['open_side_tracks'].append(dict(candidate_id='R139_UNetRecurrent',status='complete_research_not_promoted',report='Experiments/R139_UNetRecurrentPrototype/reports/R139_RESULTS.md',note='U-Net + shared4 refinements + V42-style y2 PSF; scratch8192 and full930 measurement. See report and PSF activity. Not a formal baseline promotion.'))
 assert v['formal_baseline']==baseline;save(p,v)
 save(ROOT/'results/closeout_complete.json',dict(completed_utc=now(),formal_baseline_changed=False))
 print('CLOSEOUT_VERIFIED report=',report,flush=True)
if __name__=='__main__':main()
