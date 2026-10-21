"""Index the verified LSC follow-up without rewriting prior evidence."""
import sys,json,re,time,uuid,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];REPO=ROOT.parent.parent;sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import pandas as pd

def write(path,text):
    temp=path.with_name(path.name+'.lsc-'+uuid.uuid4().hex+'.tmp');temp.write_text(text,encoding='utf-8')
    for i in range(15):
        try:temp.replace(path);return
        except PermissionError:
            if i==14:raise
            time.sleep(.2)

def main():
    out=ROOT/'results/lsc_comparison';v=load(out/'verification.json');assert v['all7primary_methods_same120pairs'] and load(out/'worst_replay_verification.json')['passed']
    assessment=load(out/'assessment.json');report=ROOT/'reports/R128_LSC_R61_COMPARISON.md';assert report.is_file()
    for dest in re.findall(r'\]\(([^)]+)\)',report.read_text(encoding='utf-8')):assert (report.parent/dest).resolve().is_file(),dest
    names=['PROJECT_STATE.md','ESTIMATOR_POLICY.json','Experiments/INDEX.md','RECON_GALLERY.md','Experiments/R128_SourceOnlyFullTraining/README.md'];before=out/'mutable_context_before';before.mkdir(exist_ok=False)
    for name in names:
        with (before/name.replace('/','__')).open('xb') as f:f.write((REPO/name).read_bytes())
    summary=pd.read_csv(out/'combined_summary.csv');s=summary[summary.scope=='all_four_sequences'].set_index('method');r128=s.loc['R128_P_s1285002'];r61=s.loc['R61v16_PSFOFF'];r109=s.loc['R109 E48']
    rel='Experiments/R128_SourceOnlyFullTraining/reports/R128_LSC_R61_COMPARISON.md'
    p=REPO/'PROJECT_STATE.md';text=p.read_text(encoding='utf-8-sig');lines=text.splitlines();lines[2]='Last updated: 2026-09-10（R128與R61同條件LSC補測完成；完整輪廓與位移比較已核對，逐組差異與邊緣影響保留，未正式升級）'
    found=[i for i,line in enumerate(lines) if line.startswith('- **R128 matched competitive review complete')];assert len(found)==1
    lines[found[0]]=f'- **R128/R61 matched LSC follow-up complete (2026-09-10):** [Verified comparison]({rel}). Same159nativeframes/120Raw-lockedpairs/four20x+50xsequences/ninepillars. R128stepSD{r128.step_sd_nm:.6f}nm, R61v16PSF-off{r61.step_sd_nm:.6f}, R109E48{r109.step_sd_nm:.6f}, Raw9.745101. R128within-gridmedian{r128.median_within_grid_sd_nm:.6f}nm versusR61{r61.median_within_grid_sd_nm:.6f}. OriginalRaw1431centers reproduce;fourR61nativeimages replay exactly;all5724saved-boundaryfits and159R128outputs independently verified;worstR128-vs-R61pair reruns bitwise. Samecheckpoint/no training. Rawretention affects some20xwindows;unrestrictedoutput is diagnostic only. PairedSEMcontour/area/perimeter stronger than listedoldmodels, circularity reference-sensitive. '+assessment['short_decision']
    text='\n'.join(lines)+'\n';anchor='### R128 completed four-run study, one follow-up candidate, no production adoption (2026-09-09)\n\n';assert text.count(anchor)==1
    detail=f'2026-09-10 same-protocol LSC completion: {rel}. This supersedes the earlier pending-LSC status below, while preserving those time-stamped reports. 159nativeframes (150newR128forwards+9verifiedreused),120fixedRaw-selectedpairs,4sequencesand9pillars. HistoricalR61v16PSF-offcheckpoint verified andonefullframepersequence reproduces saved8bitoutputs exactly. Raw159frames/1431centers reproduce historicalreader values to about4.55e-13px. R128andR61each add1431centersand120pair measurements;withRawreplayandfinalFOVguarddiagnostic,5724saved-boundarycircles independently refitted,all pair arithmetic independently recomputed. All7primarymethods use identicalpairs;nofailed/missingrowsorposthocframechoice. WorstpairvsR61replayed through the publictrialentry with exactfloat/neural/PNGoutputs andmatchingLSC.\n\n'+assessment['lead']+'\n\n'+f'PrimarymeansequenceSDnm:Raw9.745101,Wiener7.391651,R61{r61.step_sd_nm:.6f},R109{r109.step_sd_nm:.6f},R1197.260884,R128{r128.step_sd_nm:.6f}. R128medianwithin-gridSD{r128.median_within_grid_sd_nm:.6f}nm;nominalMAE{r128.mean_nominal_abs_error_nm:.6f}nm;cross-axis{r128.median_cross_axis_abs_nm:.6f}nm. Preserve per-sequence andworst-case findings in report. Source-definedFOVcontext:all50xwindowsfullyneural;20x0.5um180/306fullyneuraland27fullyRaw,20x1um333/360and3fullyRaw. Both-frameall-nine-neural diagnostic subset95pairs, neverreplacesmain120. Guard-off is sameforwarddiagnostic,notanothertrainedmodeloradoptedoutput. SEMpairedspecimen is separatefrommotionimages;no same-pillarSEMtruthclaimforLSC. V42trainingoverlap andR119causalauditcorrection remain authoritative. No training/modelchanges,oldhashreplacement,productionpromotionoroldconfirmationaccess.\n\n'
    text=text.replace(anchor,anchor+detail);quick=text.split('<!-- QUICK_HANDOFF_START -->')[1].split('<!-- QUICK_HANDOFF_END -->')[0];assert len(quick.strip().splitlines())<=60;write(p,text)
    p=REPO/'ESTIMATOR_POLICY.json';policy=load(p);old=copy.deepcopy(policy);found=[]
    def visit(node):
        if isinstance(node,dict):
            if node.get('candidate_id')=='R128_source_only_full_training':found.append(node)
            for value in list(node.values()):visit(value)
        elif isinstance(node,list):
            for value in node:visit(value)
    visit(policy);assert len(found)==1 and 'lsc_followup' not in found[0]
    metrics=['step_sd_nm','mean_nominal_abs_error_nm','median_within_grid_sd_nm','median_cross_axis_abs_nm']
    found[0]['lsc_followup']=dict(completed_utc=now(),report=rel,verification='Experiments/R128_SourceOnlyFullTraining/results/lsc_comparison/verification.json',R128_same_protocol_LSC_measured=True,common_pairs=120,native_frames=159,new_R128_forwards=150,reused_R128_outputs=9,R61_full_frame_replays_exact=4,independently_refitted_circles=5724,primary_metrics={m:{k:float(s.loc[m,k]) for k in metrics} for m in ['Raw','Wiener','R61v16_PSFOFF','R109 E48','R119_B_E42','R128_P_s1285002']},source_defined_all_neural_pair_subset=95,guard_off_diagnostic_only=True,worst_pair_public_trial_replay_exact=True,decision=assessment['short_decision'],new_training_updates=0,production_adopted=False,physical_accuracy_qualified=False,original_expected_hashes_unchanged=True)
    found[0]['lsc_followup'].pop('new_R128_forwards')
    found[0]['lsc_followup']['primary_new_R128_forwards']=150
    found[0]['lsc_followup']['worst_case_R128_replay_forwards']=2
    found[0]['lsc_followup']['total_R128_forwards_this_followup']=152
    found[0]['competitive_review']['pending_LSC_status_superseded_by']='lsc_followup'
    assert policy['formal_baseline']==old['formal_baseline'];write(p,json.dumps(policy,indent=2,ensure_ascii=False)+'\n')
    p=REPO/'Experiments/INDEX.md';lines=p.read_text(encoding='utf-8-sig').splitlines();lines[2]='Last updated: 2026-09-10（R128與R61相同120對影格的LSC比較完成；完整位移、輪廓與不利案例已核對）'
    match=[i for i,line in enumerate(lines) if line.startswith('| R128 完整研究訓練 |')];assert len(match)==1
    lines[match[0]]=f'| R128 完整研究訓練 | [R61與近期模型完整比較](R128_SourceOnlyFullTraining/reports/R128_LSC_R61_COMPARISON.md)・[SEM輪廓](R128_SourceOnlyFullTraining/reports/R128_COMPETITIVE_REVIEW.md) | 同159張／120對／9顆LSC：R128波動{r128.step_sd_nm:.3f}奈米，R61{r61.step_sd_nm:.3f}，R109{r109.step_sd_nm:.3f}。輪廓與周長有優勢；逐組差異、圓度參考與影像邊緣影響保留。最不利案例重現，無新訓練或正式採用 |';write(p,'\n'.join(lines)+'\n')
    p=ROOT/'README.md';text=p.read_text(encoding='utf-8-sig');assert 'R128_LSC_R61_COMPARISON.md' not in text;write(p,text+'\n2026-09-10 LSC follow-up complete: same159nativeframes/120Raw-lockedpairs/four sequences/ninepillars forR128andR61. OriginalRawreaderparity,4exactR61full-image replays,5724independentcirclefits,159R128outputchecksandworstpairpublictrialreplay completed. See [full R61/LSC/contour comparison](reports/R128_LSC_R61_COMPARISON.md). This supersedes prior pending-LSCstatus;originalreportsremain unchanged. One researchcandidate,no training/promotion;FOVguard-off isdiagnostic only.\n')
    p=REPO/'RECON_GALLERY.md';text=p.read_text(encoding='utf-8-sig');marker='## R128 — 與近期模型的同條件比較（2026-09-10）';assert text.count(marker)==1
    entry='## R128 — 補齊與R61的LSC及輪廓對照（2026-09-10）\n\n'+assessment['lead']+' 見 [完整結果]('+rel+')。\n\n![相同120對位移比較](Experiments/R128_SourceOnlyFullTraining/reports/figures/R128_R61_LSC_comparison.png)\n\n![R61與R128配對SEM輪廓](Experiments/R128_SourceOnlyFullTraining/reports/figures/R61_R128_SEM_comparison.png)\n\n';write(p,text.replace(marker,entry+marker))
    save(out/'registration.json',dict(completed_utc=now(),report_links_valid=True,quick_handoff_lines=len(quick.strip().splitlines()),formal_baseline_unchanged=True,files={n:record(REPO/n) for n in names},source=record(__file__)))
    print('LSC follow-up indexed; original reports preserved; no model promotion.')

if __name__=='__main__':main()
