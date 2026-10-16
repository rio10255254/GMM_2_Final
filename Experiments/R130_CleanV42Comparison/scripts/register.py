"""Register the completed practical comparison while preserving the existing R129 entry."""
import sys,json,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
def main():
    verify_frozen();audit=load(ROOT/'results/audit/verified.json');published=load(ROOT/'results/published.json')
    assert audit['epochs']==32 and audit['full_reconstructed_frames']==201 and audit['all_declared_R129_sources_unchanged']
    report=ROOT/'reports/R130_RESULTS.md';rel=report.relative_to(REPO).as_posix();before=ROOT/'results/registration_before';before.mkdir(exist_ok=False)
    paths=[REPO/'PROJECT_STATE.md',REPO/'ESTIMATOR_POLICY.json',REPO/'Experiments/INDEX.md',REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json',ROOT/'README.md',ROOT/'MANIFEST.md']
    for i,p in enumerate(paths):(before/f'{i}_{p.name}').write_bytes(p.read_bytes())
    p=REPO/'ESTIMATOR_POLICY.json';policy=load(p);old_r129=copy.deepcopy(next(x for x in policy['open_side_tracks'] if x.get('round')=='R129'));baseline=copy.deepcopy(policy['formal_baseline'])
    assert not any(x.get('round')=='R130' for x in policy['open_side_tracks'])
    policy['open_side_tracks'].insert(0,dict(candidate_id='R130_clean_V42',round='R130',experiment=ROOT.relative_to(REPO).as_posix(),status='32epoch_fresh_training_and_real_comparison_complete',mainline_status='research_not_promoted',report=rel,epochs=32,unique_updates=4096,actual_update_calls=4098,replayed_updates=[1537,1538],unique_parent_pairs=16384,source_only_targets=True,no_legacy_learned_weights_or_teacher=True,shared_historical_calibration_is_a_limit=True,comparison='Fixed existing R129 versus fresh V42; not fully matched training histories',real_SEM=dict(V42_diameter_nm=91.95135619036304,R129_diameter_nm=96.38029372672358,V42_centered_shape_nm=16.425487791000695,R129_centered_shape_nm=16.397177134895387),locked120_LSC=dict(V42_step_sd_nm=6.919372715755828,R129_step_sd_nm=6.991056173178826,V42_within_nm=4.6821259256152405,R129_within_nm=4.203668723685402),inference_seconds=dict(V42=.42785920001915656,R129=9.975710300001083),R129_unchanged=True,model_promoted=False))
    assert next(x for x in policy['open_side_tracks'] if x.get('round')=='R129')==old_r129 and policy['formal_baseline']==baseline
    p.write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    p=REPO/'PROJECT_STATE.md';s=p.read_text(encoding='utf-8-sig');lines=s.splitlines();lines[2]='Last updated: 2026-09-14（R130乾淨V42從頭訓練32epoch並完成實拍比較；R129保持原樣，兩者互有取捨）';s='\n'.join(lines)+'\n'
    bullet=f'- **R130 clean V42 comparison complete (2026-09-14):** [Fresh32epoch V42 versus frozen R129]({rel}). OnefreshV42, same512source-onlyparents,4096uniqueupdates/16384parents;no oldneuralweights/teacher/realSEM targets. SharedlegacyPSF remains aqualificationlimit. SEM V42/R129 diameter91.951/96.380nm,centeredshape16.425/16.397;locked120stepSD6.919/6.991,within4.682/4.204,cross5.237/4.798. All201frames/1809LSCcenters,540scheduledSEMreads completed;independentrebuild/refits/publicreplay pass. Samefull-frameFP32benchmark0.428sV42/9.976sR129. IOlockafter12epochs recoveredwithout changingfrozenmath;2replayedupdates exact andretained. Practicalsingle-seedcomparison,notisolatedanswer-removalcausality ornewholdout. R129andformalbaseline unchanged.\n'
    s=s.replace('### Open Research / Side Tracks\n','### Open Research / Side Tracks\n'+bullet,1)
    detail=f'''### R130 clean V42 practical comparison complete (2026-09-14)

Canonical report: [{rel}]({rel}). User explicitly requested keeping R129 unchanged and training only a fresh pure V42 for tens of epochs on similar clean data. Preserved V42 encoder-decoder/AA/directional boundary/Raw-anchor/quality architecture, fresh seed1309001, no legacy neural weights or teacher. Fixed legacy PSF buffers are shared with R129; new V42 constructor weak scale is active(.35effective), unlike old saved0. Deterministic pad/bilinear backward adaptation preserves original forward. Same512/128/128 source-only split,32epochs,4parents/update,4096updates,16384parents. R129 lineage has16408parents but different batch/optimizer/objectives and prior selection; not a fully balanced architecture causal experiment.

All33dev,5realSEM panels andfinalgeneratedtest complete;all201nativefields and1809LSCcenters,locked120andall194within-sessionpairs measured with matching reader/FOV rule. FinalV42/R129 radial46.392/49.523nm,diameter91.951/96.380,correlation.7473/.6919,centeredshape16.425/16.397,MZCerror66.351/62.651. Paired V42 improves diameter29/36,centeredshape25/36,MZC24/36,despite slightly worse overall shape/MZCmedians. Locked120stepSD6.919/6.991,nominal6.200/6.302,within4.682/4.204,cross5.237/4.798nm. Full194SD29.308/29.098. Sameimage FP32 one-warmup/three-repeat timing.428sV42/9.976sR129. OldV42shape6.810nm advantage not reproduced, but differences cannot solely be assigned to answer removal because data/initialization/training/inference differ.

WinError5 status-file lock afterstep1538: checkpoint1536 intact. Preserve allfailurefiles andoriginalfrozen sources; process-local IOretry wrapper resumed unchanged computations, actualreadlock testpassed. Steps1537/1538 replay exactly;4098calls but4096uniqueupdates. Freshinit reproduced,256parent inputs independently rebuilt,108finalSEM contours and1809LSCcircles independently refitted,publicSEM14replay exact. R129files andmetadata entry unchanged;no model promotion or oldconfirmation access. Both models remain research references; independent calibration/new physical samples and sizebias remain open.

'''
    s=s.replace('## Full Current State / 完整現況\n\n','## Full Current State / 完整現況\n\n'+detail,1)
    a,rest=s.split('<!-- QUICK_HANDOFF_START -->',1);q,b=rest.split('<!-- QUICK_HANDOFF_END -->',1)
    while len(q.splitlines())>60:q=q.replace('\n\n','\n',1)
    p.write_text(a+'<!-- QUICK_HANDOFF_START -->'+q+'<!-- QUICK_HANDOFF_END -->'+b,encoding='utf-8')
    p=REPO/'Experiments/INDEX.md';s=p.read_text(encoding='utf-8-sig');needle='| Round | 目錄 | 狀態 |\n|-------|------|------|\n';assert needle in s
    row='| R130 乾淨V42實用比較 | [32epoch訓練與真實比較](R130_CleanV42Comparison/reports/R130_RESULTS.md) | V42從頭訓練、共用乾淨合成來源；R129保持原樣。201張與SEM／LSC核對完成，尺寸偏V42、柱間一致性與橫向偏R129，細形狀相近；V42快很多。單次實用比較，非完整因果或未知資料證明，無升級 |\n'
    p.write_text(s.replace(needle,needle+row,1),encoding='utf-8')
    p=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';registry=load(p);entry=next(x for x in registry['entries'] if x.get('id')=='r130_clean_v42');entry.update(state='32epoch_comparison_complete_research_only',report=rel,actual_gib=sum(x.stat().st_size for x in ROOT.rglob('*') if x.is_file())/1024**3);registry['updated_at']=now();p.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (ROOT/'README.md').open('a',encoding='utf-8') as f:f.write('\n## Completed\n\n32epochs and all real comparisons are complete. [Results and real-image figures](reports/R130_RESULTS.md) show mixed tradeoffs, not automatic adoption. Model: runs/v42_clean/checkpoints/step04096.pth. Single-image entry: scripts/infer_image.py --input IMAGE --output NEW.png. The completed run should not be resumed; further training requires a distinct plan/run. R129 remains unchanged.\n')
    with (ROOT/'MANIFEST.md').open('a',encoding='utf-8') as f:f.write('\nCompleted32epochs:4096uniqueupdates,4098actualcalls due2exact recovery replays. All201realimages/1809LSCcenters,540scheduledSEMmeasurements; independent audit, SEMpublicreplay and matched runtime benchmark saved. Recovery wrapper changes only status IO and is separately recorded; no old/frozen hash rebaseline. No R129 change or promotion.\n')
    verify_frozen()
    save(ROOT/'results/registration.json',dict(completed_utc=now(),source=record(__file__),report=record(report),updated_files=[record(p) for p in paths],R129_policy_entry_unchanged=True,all_frozen_original_sources_unchanged=True,formal_baseline_unchanged=True))
    print('R130 completion registered; R129 preserved')
if __name__=='__main__':main()
