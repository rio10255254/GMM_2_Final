"""Add a truthful new research entry; do not rewrite historical receipts."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from common import *

def main():
    verification=load(ROOT/'results/verification.json')
    assert verification['optimizer_updates']==96 and verification['D_full_sem14_float_replay_exact']
    assert load(ROOT/'results/figure_sources.json')['CLI_sem14_matches_recorded_output_exactly']
    assert load(ROOT/'results/analysis_complete.json')['SEM_rows']==864
    report='Experiments/R129_OpticalPriorHybrid/reports/R129_RESULTS.md'
    assert (REPO/report).exists()
    backup=ROOT/'config/current_index_before_r129';backup.mkdir(exist_ok=False)
    paths=[REPO/'PROJECT_STATE.md',REPO/'ESTIMATOR_POLICY.json',REPO/'Experiments/INDEX.md',REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json']
    for path in paths:(backup/path.name).write_bytes(path.read_bytes())
    policy=load(REPO/'ESTIMATOR_POLICY.json');original_baseline=policy['formal_baseline'];original_alternates=policy['approved_alternates']
    item=dict(candidate_id='R129_optical_prior_hybrid',round='R129',experiment='Experiments/R129_OpticalPriorHybrid',status='bounded_pilot_complete_mixed_real_results',mainline_status='research_prototype_not_promoted',report=report,primary_architecture='D: measured optics and V42-style AA retained by user requirement',optimizer_updates=96,updates_per_arm=24,SEM_objects=36,normal_exposures=[13,14,15],SEM_measurements=864,motion_pairs_per_method=4,conclusion='Active/trainable modules; D improves centered shape on 27/36 vs converted control A but no overall replacement advantage; adaptive candidate selection has negligible effect on checked real image',limits=['Not full training','A differs from original R128 in common head and output anchor','Reused real/SEM development; inherited calibration','No temporal displacement SD from one pair per sequence','No academic novelty established'],checkpoint='Experiments/R129_OpticalPriorHybrid/runs/D/step24.pth',production_adoption=False,old_confirmation_access=False)
    assert not any(x.get('round')=='R129' for x in policy['open_side_tracks'])
    # Insert one object, preserving the existing file text and historical entries verbatim.
    path=REPO/'ESTIMATOR_POLICY.json';text=path.read_text(encoding='utf-8-sig')
    needle='  "open_side_tracks": [\n';assert text.count(needle)==1
    encoded=json.dumps(item,ensure_ascii=False,indent=2)
    encoded='\n'.join('    '+line for line in encoded.splitlines())
    text=text.replace(needle,needle+encoded+',\n',1)
    updated=json.loads(text);assert updated['formal_baseline']==original_baseline and updated['approved_alternates']==original_alternates
    assert updated['open_side_tracks'][1:]==policy['open_side_tracks']
    path.write_text(text,encoding='utf-8')
    path=REPO/'PROJECT_STATE.md';text=path.read_text(encoding='utf-8-sig')
    lines=text.splitlines();lines[2]='Last updated: 2026-09-12（R129 保留 V42 主要設計的接入短測完成；作用可驗證，但未超過既有模型，無正式升級）';text='\n'.join(lines)+'\n'
    bullet=f'- **R129 thesis-design integration pilot complete (2026-09-12):** [Actual implementation and results]({report}). Both measured-optics fusion and V42-style AA are retained in candidate D. Four identical-start/input arms completed 24 updates each (96 total), with 864/864 normal-SEM reads and four fixed ROI motion pairs per method. D improves centered shape on 27/36 pillars vs converted control A, but is not an overall improvement over original R128/V42. A also changes the common decoder/Raw anchor; it is not original R128. Learned optical selection is almost indistinguishable from uniform weights on the checked real image. Saved V42 adaptive output scale is zero. Independent input/metric replay passes; implementation success is not scientific efficacy or novelty. No full retraining, promotion, or old-confirmation access.\n'
    text=text.replace('### Open Research / Side Tracks\n','### Open Research / Side Tracks\n'+bullet,1)
    full=f'''### R129 V42-design integration: completed bounded pilot, retained prototype (2026-09-12)

Canonical report: [{report}]({report}). User requested preserving measured optical fusion and improved upsampling as thesis design requirements. New isolated D checkpoint retains both; A/B/C are experimental controls only. Four matched 24-update runs completed 96 updates, with actual initial tensors and all 24 consumed inputs independently rebuilt. V42 E120 calibration buffers alone are imported: 25 measured 101x101 kernels plus 4 very similar candidates; saved legacy adaptive beta_scale=0, so its default-loaded branch was inactive. New input-stage optics correct centroid origin/DC gain and remain active; V42-style AA matches the legacy operator. This is an adaptation, not a complete exact V42 transplant or new novelty proof.

Normal SEM 13-15: 36 pillars, 864 valid reads across all four arms before/after training. D24 radial/shape-correlation/CD/centered-shape/MZC-error medians = 41.579nm/0.668942/80.679nm/21.352nm/86.605nm; A24 = 41.869/0.643638/80.607/22.304/82.747. D improves centered shape on 27/36 but radial on only 16/36 and diameter on 15/36. D remains weaker than original R128/V42 on fine shape. All arms share a converted decoder and new Raw anchor: A is already weaker than original R128 at initialization, so total differences cannot be causally assigned to added optics/AA. Four ROI motion pairs only: D nominal/within-grid/cross-axis 6.746/8.828/6.933nm vs A 6.942/8.434/7.245; no temporal SD or complete thesis120-pair claim.

Full D SEM14 replay exact; disabling optics or AA changes output. Learned versus uniform optical weights changes that image by at most 1.1921e-7 (0-1 scale), so adaptive selection's independent benefit is not established. 864 contour rows refitted by independent two-parameter circle method, all 36 motion pairs recomputed, and 51 recorded source paths unchanged. Original deterministic-backward failure and original plan/source are retained; separate v2 preserves forward/criteria. Keep D as the user's requested architecture prototype; first repair conversion/output retention and verify meaningful instrument-specific optical variation before a justified larger training study. No model promotion, old-confirmation reuse, old evidence rebaselining or thesis edit.

'''
    text=text.replace('## Full Current State / 完整現況\n\n','## Full Current State / 完整現況\n\n'+full,1)
    start='<!-- QUICK_HANDOFF_START -->';end='<!-- QUICK_HANDOFF_END -->'
    before,rest=text.split(start,1);quick,after=rest.split(end,1)
    while len(quick.splitlines())>60:
        assert '\n\n' in quick;quick=quick.replace('\n\n','\n',1)
    text=before+start+quick+end+after;path.write_text(text,encoding='utf-8')
    path=REPO/'Experiments/INDEX.md';text=path.read_text(encoding='utf-8-sig')
    lines=text.splitlines();lines[2]='Last updated: 2026-09-12（R129 核心設計接入短測完成；保留設計，混合結果，不升級）';text='\n'.join(lines)+'\n'
    needle='| Round | 目錄 | 狀態 |\n|-------|------|------|\n';assert text.count(needle)==1
    row='| R129 保留論文設計的原型 | [實作、實拍與限制](R129_OpticalPriorHybrid/reports/R129_RESULTS.md) | 四組各24次更新共96次；正常SEM 864筆全數成功。D保留實測光學融合及改善上取樣，對同底版27/36顆細形狀改善，但未超過既有R128/V42；光學自適應選擇尚無可辨識額外作用。短程原型，未正式升級 |\n'
    path.write_text(text.replace(needle,needle+row,1),encoding='utf-8')
    path=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';registry=load(path)
    entry=next(x for x in registry['entries'] if x.get('id')=='r129_optical_prior_hybrid')
    entry['state']='bounded_pilot_complete_mixed_results'
    entry['report']=report
    entry['actual_gib']=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())/1024**3
    assert entry['actual_gib']<4
    registry['updated_at']=now();path.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    marker=ROOT/'runs/launcher_logs/active_formal_run.json'
    (backup/'run_status_before_closeout.json').write_bytes(marker.read_bytes())
    status=load(marker);status.update(status='bounded_pilot_complete_not_promoted',updated_utc=now(),scientific_verdict='mixed_real_results_not_qualified',canonical_report=report,verification='results/verification.json',formal_full_training_complete=False)
    marker.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save(ROOT/'results/index_registration.json',dict(completed_utc=now(),source=record(__file__),backups=[record(p) for p in backup.iterdir()],updated_files=[record(p) for p in paths],formal_baseline_and_approved_alternates_unchanged=True,all_previous_policy_side_tracks_unchanged=True,quick_handoff_lines=len(quick.splitlines()),old_receipt_hashes_not_rebaselined=True))
    print('R129 research indexes registered; historical policy entries preserved')

if __name__=='__main__':main()
