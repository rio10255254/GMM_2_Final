from utils import ROOT,load,save,verify_frozen,verify_protected,now

def main():
 c=load(ROOT/'results/complete.json');a=load(ROOT/'results/final_audit.json');assert c['updates']==8192 and c['images']==930 and c['circles']==8370 and a['output_hashes_verified']==930
 verify_frozen(load(ROOT/'config/source_lock.json'));verify_protected()
 p=ROOT/'README.md';s=p.read_text(encoding='utf-8-sig');s=s.replace('狀態：CPU前置檢查通過，正式訓練啟動中。','狀態：CPU完整8192次訓練及930影像驗證完成。');s+='\n[完整結果](reports/R138_RESULTS.md)。原模型保持不變，無正式基準升級。\n';p.write_text(s,encoding='utf-8')
 repo=ROOT.parents[1];p=repo/'PROJECT_STATE.md';s=p.read_text(encoding='utf-8-sig');lines=s.splitlines();mark='<!-- R138_V42_PSF8_20260923 -->'
 if mark in lines:
  i=lines.index(mark);lines[i+1]='R138已完成CPU8192次訓練、930影像及8370輪廓；V42八候選PSF的新模型實際比較見[結果](Experiments/R138_V42PSF8/reports/R138_RESULTS.md)。原R137與正式基準未變更。'
 p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
 p=repo/'Experiments/INDEX.md';s=p.read_text(encoding='utf-8-sig');s=s.replace('R138：CPU訓練與驗證執行中','R138：CPU訓練與驗證完成');p.write_text(s,encoding='utf-8')
 p=repo/'docs/operations/PROJECT_STORAGE_REGISTRY.json';v=load(p)
 for e in v['entries']:
  if e['id']=='r138_v42_psf8':e['state']='complete_research_not_promoted'
 save(p,v)
 p=repo/'ESTIMATOR_POLICY.json';v=load(p);v.setdefault('open_side_tracks',[])
 if not any(x.get('candidate_id')=='R138_V42PSF8' for x in v['open_side_tracks']):v['open_side_tracks'].append(dict(candidate_id='R138_V42PSF8',status='complete_research_not_promoted',report='Experiments/R138_V42PSF8/reports/R138_RESULTS.md',note='CPU scratch8192, full930, V42 auto8 from original25. All gating records retained. See metrics before judging benefit; no baseline promotion.'))
 save(p,v)
 save(ROOT/'results/closeout_complete.json',dict(completed_utc=now(),formal_baseline_changed=False))
if __name__=='__main__':main()
