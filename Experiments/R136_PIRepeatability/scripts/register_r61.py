from common import *
import re
def main():
    out=ROOT/'results/r61_analysis';assert load(out/'verification.json')['complete'];assert load(out/'visual_review.json')['passed']
    data=load(out/'key_results.json');a=next(r for r in data['comparisons'] if r['view']=='nominal_all30' and r['kind']=='adjacent');s=next(r for r in data['comparisons'] if r['view']=='nominal_all30' and r['kind']=='start')
    rel='Experiments/R136_PIRepeatability/reports/R136_R61_RESULTS.md';report=REPO/rel
    ir=data['intensity_reader']
    sentence=f'R136原圖／R61的30次PI回授比較已完成，各930張、900段相鄰位移及900筆起點相對位移。主讀法每步平均絕對誤差原圖{a["raw_mae_nm"]:.3f}nm、R61{a["r61_mae_nm"]:.3f}nm；起點相對誤差{s["raw_mae_nm"]:.3f}／{s["r61_mae_nm"]:.3f}nm。亮度讀法則原圖{ir["raw_mae_nm"]:.3f}優於R61{ir["r61_mae_nm"]:.3f}nm，不能宣稱全面更準。全30次與前6次校正／後24次檢驗分開。R129仍運算，無模型升級。'
    path=REPO/'PROJECT_STATE.md';text=path.read_text(encoding='utf-8-sig');notice=f'**R136先行結果（2026-09-16）：** {sentence} [完整報告]({rel})'
    if '<!-- R136_R61 -->' not in text:text=text.replace('### Open Research / Side Tracks','### Open Research / Side Tracks\n<!-- R136_R61 -->\n'+notice,1)
    if '### R136 原圖與R61先行比較' not in text:text=text.replace('## Full Current State / 完整現況\n','## Full Current State / 完整現況\n\n### R136 原圖與R61先行比較\n\n'+notice+'\n',1)
    text=re.sub(r'(?m)^Last updated:.*$','Last updated: 2026-09-16（R136原圖與R61完整30次統計完成；R129續跑，讀法差異保留）',text,count=1)
    path.write_text(text,encoding='utf-8')
    path=REPO/'ESTIMATOR_POLICY.json';p=load(path);entry=dict(candidate_id='r136_pi_repeatability',round='R136',experiment='Experiments/R136_PIRepeatability',status='raw_r61_complete_r129_running',report=rel,models_completed=['Raw','R61'],scans=30,frames_per_method=930,main_results=data['comparisons'],model_promoted=False,total_expanded_uncertainty_available=False,notes='Same sample/session PI-referenced reader comparison;not universal generalization or independent SI calibration. R129 remains active.')
    entry['intensity_reader']=ir
    existing=next((x for x in p['open_side_tracks'] if x.get('candidate_id')=='r136_pi_repeatability'),None)
    if existing:existing.update(entry)
    else:p['open_side_tracks'].insert(0,entry)
    save(path,p)
    path=REPO/'Experiments/INDEX.md';text=path.read_text(encoding='utf-8-sig')
    line=f'| R136 PI重拍比較 | [原圖／R61先行結果](R136_PIRepeatability/reports/R136_R61_RESULTS.md) | 30次完整比較；每步誤差{a["raw_mae_nm"]:.3f}→{a["r61_mae_nm"]:.3f}nm；R129續跑，未升級 |'
    if '| R136 PI重拍比較 |' not in text:text+='\n## R136 位移重拍比較\n\n| 項目 | 報告 | 狀態 |\n|---|---|---|\n'+line+'\n'
    else:text=re.sub(r'(?m)^\| R136 PI重拍比較 \|.*$',line,text)
    path.write_text(text,encoding='utf-8')
    with (ROOT/'README.md').open('a',encoding='utf-8') as f:f.write('\n## 原圖／R61完整先行結果\n\n[30次統計與論文圖表](reports/R136_R61_RESULTS.md)已完成；R129維持背景執行。\n')
    with (ROOT/'MANIFEST.md').open('a',encoding='utf-8') as f:f.write('\nR61 first delivery: results/r61_analysis and reports/R136_R61_RESULTS.md; full30Raw/R61 scan analysis,16,200reader rows,7PNG/PDFfigures,verification andvisualreview complete. R129/full-comparison marker remains active.\n')
    with (ROOT/'HANDOFF.md').open('a',encoding='utf-8') as f:f.write('\n## R61 first delivery completed\n\nUser requested R61 statistics first. Complete Raw/R61 report is reports/R136_R61_RESULTS.md; tables results/r61_analysis/tables; figures reports/r61_figures. Project registration now contains R136 partial completion; when full3-method analysis completes, UPDATE existing R136 entries instead of duplicating them. R129 and all-method automatic completion remain active. Shared analyze/figures/verify scripts accept --models and output-directory options; defaults still execute the original3-method pipeline.\n')
    with (ROOT/'HANDOFF.md').open('a',encoding='utf-8') as f:f.write('\nImportant result: primary short-stepMAE Raw7.956799nm vsR614.777029nm,30/30improve; but intensity-readerMAE Raw2.695605nm vsR614.041300nm,30/30R61worse. Long-startMAE Raw14.768615 vsR6115.087716,no clearimprovement. Do NOT bury reader-dependence or callR61universallymoreaccurate. Photometric independent samplecheck differs upto38.014492nm; primaryreplay exact. Final3-model publish.py must add these material sensitivity findings to its lead conclusion too.\n')
    path=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';registry=load(path);entry=next(x for x in registry['entries'] if x.get('id')=='r136_pi_repeatability');entry.update(state='raw_r61_complete_r129_running',report=rel,actual_gib_snapshot=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())/2**30);registry['updated_at']=now();save(path,registry)
    save(out/'delivery_complete.json',dict(report=record(report),coverage=data['coverage'],figures=load(out/'figures_complete.json')['figures'],visual_review=record(out/'visual_review.json'),verification=record(out/'verification.json'),completed_utc=now(),R129_full_task_still_active=True))
    print(sentence,flush=True)
if __name__=='__main__':main()
