"""Update current research status; preserve all original run evidence and defaults."""
import sys,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
def main():
    out=ROOT/'results/long_training_review_20260913_v2';v=load(out/'verification.json');pkg=Path(v['package'])
    assert v['unique_updates']==8192 and v['final_public_inference_replay_exact']
    report=ROOT/'reports/R129_LONG_TRAINING_RESULTS.md';rel=report.relative_to(REPO).as_posix()
    paths=[REPO/'PROJECT_STATE.md',REPO/'ESTIMATOR_POLICY.json',REPO/'Experiments/INDEX.md',REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json',ROOT/'README.md',ROOT/'reports/R129_RESULTS.md',ROOT/'MANIFEST.md']
    before=out/'current_index_before';before.mkdir(exist_ok=False)
    for i,p in enumerate(paths):(before/f'{i}_{p.name}').write_bytes(p.read_bytes())
    p=REPO/'ESTIMATOR_POLICY.json';d=load(p);baseline=json.dumps(d['formal_baseline'],sort_keys=True);entry=next(x for x in d['open_side_tracks'] if x.get('round')=='R129')
    entry['status']='long_training_complete_mixed_results_not_adopted'
    entry['long_training'].update(status='complete_not_adopted',full_training_complete=True,observed_updates=8192,observed_utc=v['training_finished_utc'],report=rel,result_summary='Centered shape improves on36/36, diameter worsens on31/36; partial motion benefit; no default model replacement',audit=out.relative_to(REPO).as_posix()+'/verification.json')
    assert json.dumps(d['formal_baseline'],sort_keys=True)==baseline;p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    p=REPO/'PROJECT_STATE.md';s=p.read_text(encoding='utf-8-sig');lines=s.splitlines();lines[2]='Last updated: 2026-09-13（R129長訓練完成並核對：細部形狀改善、尺寸退步，保留研究成果，不採用終點模型）'
    for i,line in enumerate(lines):
        if line.startswith('- **R129 standalone long training active'):
            lines[i]=f'- **R129 long training complete, not adopted (2026-09-13):** [Fixed endpoint results]({rel}). Finished8192updates/16epochs at2026-09-12 22:20Taipei; all17dev/5real/finaltest outputs verified. Real36pillars: centeredshape21.352→16.397nm (36/36 improve), diameter80.679→96.380nm (31/36 worsen), radial41.579→49.523nm. Fourmotionpairs: within-grid8.828→7.434nm, nominal6.746→6.970nm andcross6.933→7.721nm.64inputs independently rebuilt,540SEMrows refitted,20motionpairs recomputed andfinalpublicimage replay exact. KeepR129architecture; investigate sizebias before further training. Default initial model unchanged; no promotion or unseen-holdout claim.'
    s='\n'.join(lines)+'\n';needle='### R129 V42-design integration: completed bounded pilot, retained prototype (2026-09-12)\n\n'
    paragraph=f'2026-09-13 completed long-run audit: [{rel}]({rel}). One8192-update continuation finished2026-09-12T14:20:12UTC. All8192rowsunique/inorder,all512parents per16epochs;64actualinputs independently rebuilt.24completion records and1603package resources unchanged; checkpoint/optimizer at8192. Full17dev,5real andfinaltest present. Native dev4.87358→2.68142, but SEM radius41.579→49.523nm anddiameter80.679→96.380nm worsen. Centeredshape21.352→16.397nm improvesall36;MZCerror86.605→62.651 improves31/36, diameter worsens31/36. Four-pairwithin-grid8.828→7.434, nominal6.746→6.970,cross6.933→7.721nm;no temporalSD. Independent540-rowcircle-refit/20pairarithmetic andpublicfinalSEM14replay pass. First inference invocation returnedexit1withoutdiagnostics; initialreviewstoppedonmissingimage; separate retry/v2passedunchangedtests, failures retained. No endpoint adoption, auto-default replacement, oldexpectedhashrefresh or confirmationaccess. KeepR129design; address sizebias with bounded causal checks instead of more epochs by default.\n\n'
    assert needle in s;s=s.replace(needle,needle+paragraph,1)
    assert len(s.split('<!-- QUICK_HANDOFF_START -->')[1].split('<!-- QUICK_HANDOFF_END -->')[0].splitlines())<=60;p.write_text(s,encoding='utf-8')
    p=REPO/'Experiments/INDEX.md';lines=p.read_text(encoding='utf-8-sig').splitlines()
    for i,line in enumerate(lines):
        if line.startswith('| R129 架構與獨立長訓練 |'):
            lines[i]='| R129 架構與獨立長訓練 | [長訓練結果與核對](R129_OpticalPriorHybrid/reports/R129_LONG_TRAINING_RESULTS.md) | 8192次完整結束；36/36顆細形狀改善，但31/36顆尺寸退步，位移有取捨。來源、逐次執行、獨立量測重算及最後實拍重跑已核對。不採用終點，原模型保留 |'
    p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    p=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';d=load(p)
    next(x for x in d['entries'] if x.get('id')=='r129_standalone_long_training').update(state='long_training_complete_not_adopted',report=rel)
    d['updated_at']=now();p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name,note in [
        ('README.md','\n## Completed long-run result, 2026-09-13\n\nThe8192-update continuation completed with mixed real results: all36centered-shape errors improve, but31diameter errors worsen. See [verified long-run results](reports/R129_LONG_TRAINING_RESULTS.md). The initial model remains default; the endpoint is not adopted.\n'),
        ('reports/R129_RESULTS.md','\n## 2026-09-13 長訓練完成結果\n\n[完整長訓練核對](R129_LONG_TRAINING_RESULTS.md)：8192次及所有指定驗證完成。36/36顆細形狀改善，但31/36顆尺寸誤差增加，位移有取捨。保留架構與研究結果，不採用最後模型；這是後續研究結果，不改寫前面的短程成績。\n'),
        ('MANIFEST.md','\nLong-run follow-up completed2026-09-12; audited2026-09-13. See reports/R129_LONG_TRAINING_RESULTS.md and results/long_training_review_20260913_v2/verification.json. No default or scientific promotion; original package files and run records remain unchanged.\n')]:
        with (ROOT/name).open('a',encoding='utf-8') as f:f.write(note)
    mirror=pkg/'results/final_review_20260913';(mirror/'figures').mkdir(parents=True,exist_ok=False)
    shutil.copy2(report,mirror/'REPORT.md')
    for name in ['R129_long_training_tradeoff.png','R129_long_training_pillar18.png']:shutil.copy2(ROOT/'reports/figures'/name,mirror/'figures'/name)
    save(mirror/'SOURCE.json',dict(canonical_report=record(report),copy_sha256=sha(mirror/'REPORT.md'),audit=record(out/'verification.json'),not_an_editable_report_source=True))
    save(out/'registration.json',dict(completed_utc=now(),source=record(__file__),updated_files=[record(p) for p in paths],canonical_report=record(report),package_readonly_report_copy=record(mirror/'REPORT.md'),model_default_unchanged=True))
    print('Current research status updated; frozen package files and model default unchanged')
if __name__=='__main__':main()
