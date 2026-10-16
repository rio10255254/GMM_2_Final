"""Close out only when the R140 evidence record is truly complete."""
from pathlib import Path
import json
import pandas as pd
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from utils import ROOT,load,save,verify_frozen,verify_protected,verify_evaluation,now

def main():
 proof=load(ROOT/'results/complete.json');audit=load(ROOT/'results/final_audit.json');assert proof['updates']==8192 and proof['images']==930 and proof['circles']==8370
 assert audit['output_sha256_verified']==930 and audit['independent_aggregate_displacements']==12600
 verify_frozen(load(ROOT/'config/FORMAL_SOURCE_LOCK.json'));verify_protected();verify_evaluation()
 repo=ROOT.parents[1];report=ROOT/'reports/R140_RESULTS.md';assert report.is_file()
 p=repo/'PROJECT_STATE.md';text=p.read_text(encoding='utf-8-sig');marker='<!-- R140_STABLE_UNET_20260923 -->';lines=text.splitlines();i=lines.index(marker)
 lines[i+1]='R140 改良U-Net已完成固定8192次訓練及930張實拍、8370輪廓；早期飽和門檻已核對，實際位移、尺寸及PSF作用請讀[結果](Experiments/R140_StableUNet/reports/R140_RESULTS.md)。不自動取代既有模型或正式基準。'
 p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
 p=repo/'Experiments/INDEX.md';text=p.read_text(encoding='utf-8-sig');text=text.replace('先用固定生成配對做256次丟棄權重短測，通過才開始正式訓練；目前無最終量測結論。','短測通過後完成8192次訓練、930張實拍與共同量測；請讀 canonical R140_RESULTS 報告。');p.write_text(text,encoding='utf-8')
 registry=repo/'docs/operations/PROJECT_STORAGE_REGISTRY.json';v=load(registry)
 for row in v['entries']:
  if row['id']=='r140_stable_unet':row['state']='complete_research_not_promoted'
 save(registry,v)
 p=repo/'ESTIMATOR_POLICY.json';v=load(p);baseline=v['formal_baseline'].copy();v.setdefault('open_side_tracks',[])
 if not any(row.get('candidate_id')=='R140_StableUNet' for row in v['open_side_tracks']):
  v['open_side_tracks'].append(dict(candidate_id='R140_StableUNet',status='complete_research_not_promoted',report='Experiments/R140_StableUNet/reports/R140_RESULTS.md',note='Pixel-local normalized U-Net + shared4 refinements + V42-style decoder PSF; early saturation gates passed before full8192 and930. Assess practical metrics and PSF effect in report. No formal promotion.'))
 assert v['formal_baseline']==baseline;save(p,v)
 save(ROOT/'results/closeout_complete.json',dict(completed_utc=now(),formal_baseline_changed=False))
 print('CLOSEOUT_VERIFIED report=',report,flush=True)
if __name__=='__main__':main()
