"""Compare the thesis and recent evaluation populations and source definitions."""
import json,hashlib,re
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/thesis_v34_review_20260912'
THESIS=Path('C:/Users/Rio/OneDrive/學業/碩班/論文');V34=THESIS/'可用/_thesis_assets_v34/lsc_mzc_comparison'
def record(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
    old=pd.read_csv(V34/'per_pair_lsc_mzc.csv');old=old[(old.method=='Raw') & (old.center=='LSC')]
    recent=pd.read_csv(ROOT/'results/lsc_comparison/locked_pairs.csv')
    keys=['sequence','start_frame_index','end_frame_index'];a=set(map(tuple,old[keys].to_numpy()));b=set(map(tuple,recent[keys].to_numpy()))
    oldplan=json.loads((ROOT/'results/lsc_comparison/plan.json').read_text(encoding='utf-8'));cache={(f['sequence'],f['frame_index']) for f in oldplan['frames']}
    rows=[];frames=[]
    for seq,g in old.groupby('sequence',sort=False):
        h=recent[recent.sequence==seq];ka=set(map(tuple,g[keys].to_numpy()));kb=set(map(tuple,h[keys].to_numpy()));fa=set(g.start_frame_index)|set(g.end_frame_index);fb=set(h.start_frame_index)|set(h.end_frame_index)
        rows.append(dict(sequence=seq,thesis_pairs=len(g),recent_pairs=len(h),shared_pairs=len(ka&kb),thesis_only_pairs=len(ka-kb),recent_only_pairs=len(kb-ka),thesis_frames=len(fa),recent_frames=len(fb),thesis_frames_missing_from_recent=sorted(int(x) for x in fa-fb)))
        frames.extend(dict(sequence=seq,frame_index=int(i),in_recent_cache=(seq,i) in cache) for i in sorted(fa))
    centers=pd.read_csv(V34/'centers_lsc_mzc.csv');source_provenance=[]
    for method,g in centers.groupby('method'):
        valid_name=g.source_path.astype(str).str.extract(r'frame_(\d+)\.bmp',expand=False).astype(int)==g.frame_index
        source_provenance.append(dict(method=method,rows=len(g),unique_recorded_source_paths=int(g.source_path.nunique()),source_filename_matches_frame_rows=int(valid_name.sum()),mismatched_rows=int((~valid_name).sum())))
    settings=json.loads((ROOT/'config/study.json').read_text(encoding='utf-8'))
    items=[THESIS/'analyze_v34_lsc_mzc.py',THESIS/'benchmark_v34_eight_models.py',V34/'analysis_manifest.json',V34/'per_pair_lsc_mzc.csv',V34/'centers_lsc_mzc.csv',ROOT/'results/lsc_comparison/plan.json',ROOT/'results/lsc_comparison/locked_pairs.csv',ROOT/'reports/R128_METHODOLOGY.md',ROOT.parent/'R81_MultiArchitectureReferenceCircleBenchmark/scripts/evaluate_model.py',ROOT.parent/'R80_InflectionReferenceCircleSEMValidation/scripts/run_sem36_contour_validation.py']
    result=dict(source_records=[record(p) for p in items],pairs=dict(thesis=len(a),recent=len(b),shared=len(a&b),thesis_only=sorted([list(x) for x in a-b]),recent_only=sorted([list(x) for x in b-a])),per_sequence=rows,thesis_frames=len(frames),required_frames_missing_from_recent=sum(not f['in_recent_cache'] for f in frames),thesis_center_provenance=source_provenance,
        reader_difference='v34andR81do not reset skimage alternating curvature cycle per pillar; recentR128reader does. Fixed original processing order may remain reproducible, but values cannot be pooled across these reader states without replay.',
        sem_difference='Thesisusesmaxgradientrefinedpoints(180SEM/144optical)and720angularradialsignature,geometricLSC,andMZCzonewidthdifference; recentcomparisonusesMATLABcoarseACMmasks,sharedRawtranslation,IoU/perimeter/pixel-correctedcircularity.',
        exposure_difference='Thesisprimary12exposures13-24;recentcompletecontourprimary3normalexposures13-15.',
        inference_difference='R81learningbaselinesreconstructRaw-derivedROIwith128tiles/64overlap/32batch; thesisFP32speedtableuses256tiles/128overlap/8batchfullimage. R128validatedpipelineusesfullFOV,core256/halo64andFOVRawguard.',
        R128_model_parameters=301832,thesis_MOSR_parameters_rounded=4021000,parameter_reduction_pct=100*(1-301832/4021000),
        no_new_training=True,no_original_changes=True)
    (OUT/'protocol_inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    pd.DataFrame(rows).to_csv(OUT/'pair_population_comparison.csv',index=False)
    pd.DataFrame(frames).to_csv(OUT/'thesis_required_frames.csv',index=False)
    print(json.dumps({k:result[k] for k in ['per_sequence','thesis_frames','required_frames_missing_from_recent','thesis_center_provenance','parameter_reduction_pct']},ensure_ascii=True,indent=2))
    print('Sharedpairs',len(a&b))
if __name__=='__main__':main()
