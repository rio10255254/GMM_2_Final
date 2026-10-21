"""Freeze the common LSC population and existing R61/R128 identities."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd,cv2

def main():
    out=ROOT/'results/lsc_comparison';out.mkdir(parents=True,exist_ok=False)
    repo=ROOT.parent.parent;exps=ROOT.parent
    cfgpath=repo/'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/config/sequence_center9_50x20x.json'
    cfg=load(cfgpath)
    old=exps/'R119_SequenceGeometryValidation/results/formal_lsc/analysis/tables/combined_lsc_per_pair.csv'
    pairs=pd.read_csv(old);pairs=pairs[pairs.method=='Raw'].copy();assert len(pairs)==120
    topfile=repo/'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/tables/top30_raw_motion_selection.csv'
    top=pd.read_csv(topfile);top=top[top.top30_raw_motion_selected.astype(str).str.lower().isin(['true','1','yes'])]
    assert set(zip(pairs.sequence,pairs.end_frame_index))==set(zip(top.sequence,top.end_frame_index))
    assert (pairs.end_frame_index==pairs.start_frame_index+1).all()
    r61=load(exps/'R113_CausalStructureDissection/config/experiment.json')['models']['R61_v16']
    assert sha(r61['checkpoint'])==r61['sha256']
    cp=load(ROOT/'trial/manifest.json')['checkpoint'];assert sha(cp['path'])==cp['sha256']
    structure=load(ROOT/'results/structure_check/plan.json');reused=load(ROOT/'results/structure_check/inference.json')
    prev={s['key']:s for s in structure['sources']}
    byhash={prev[x['key']]['source']['sha256']:x['output'] for x in reused['outputs']}
    frames=[];manifests={}
    for seq,g in pairs.groupby('sequence',sort=False):
        spec=cfg['sequences'][seq];base=repo/('20260702_100MG_displacement_analysis' if seq.startswith('50x') else '20260704_20x_5x_analysis')
        short=seq.replace('50x_','') if seq.startswith('50x') else seq
        manifest=base/f'r61_v16_psfoff_{short}_manifest.json';m=load(manifest)
        assert Path(m['weights']).resolve()==Path(r61['checkpoint']).resolve()
        assert Path(m['input_dir']).resolve()==Path(spec['raw_dir']).resolve()
        assert '--weak-psf-disable' in m['command'] and '--no-psf-from-ckpt' in m['command']
        assert m['command'][m['command'].index('--psf-phys-alpha')+1]=='0.0'
        manifests[seq]=dict(record=record(manifest),inference_source=record(m['infer_script']),inference_log=record(m['infer_log']),runtime=m)
        for idx in sorted(set(g.start_frame_index)|set(g.end_frame_index)):
            raw=Path(spec['raw_dir'])/f'frame_{idx:04d}.bmp';r=Path(m['case_bmp_dir'])/raw.name
            pixels=cv2.imread(str(raw),cv2.IMREAD_UNCHANGED);rec=cv2.imread(str(r),cv2.IMREAD_UNCHANGED)
            assert pixels is not None and rec is not None and pixels.shape==rec.shape and pixels.ndim==2 and pixels.dtype==rec.dtype==np.uint8
            source=record(raw);reuse=byhash.get(source['sha256'])
            if reuse:assert sha(reuse['path'])==reuse['sha256']
            frames.append(dict(sequence=seq,frame_index=int(idx),source=source,R61=record(r),R128_reuse=reuse,shape=list(pixels.shape)))
    helper=exps/'R80_InflectionReferenceCircleSEMValidation/scripts'
    sources=[cfgpath,old,topfile,helper/'run_displacement_lsc.py',helper/'reference_circle_core.py',exps/'R116_CoherentGeometryAnchorScratch/validation/run_lsc_e42.py',exps/'R111_R109V42ThesisReplacementQualification/results/lsc_current_top30/tables/four_method_lsc_centers_current_top30.csv',ROOT/'results/competitive_review/summary.csv',ROOT/'results/competitive_review/paired_comparisons.csv',ROOT/'trial/manifest.json',ROOT/'evaluation/real.py',ROOT/'model/network.py',exps/'R124_RealFirstPrototype/inference/tiling.py',repo/'Model/GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py',repo/'Model/GeoEdgeAlignSR_v1_Utils.py']
    session=cfgpath.parent.parent/'diagnostics/unified_displacement_step_audit/tables/session_anchor_summary.csv';sources.append(session)
    plan=dict(created_utc=now(),question='Measure R128 and historical R61v16 with the same locked LSC protocol and compare against Raw/Wiener/R109/R119; combine with existing paired SEM findings.',
      checkpoint_R128=cp,checkpoint_R61=record(r61['checkpoint']),sources=[record(p) for p in sources],configuration=record(cfgpath),sessions=record(session),historical_pairs=record(old),R61_manifests=manifests,frames=frames,
      methods_new=['R128_P_s1285002','R61v16_PSFOFF'],methods_historical=['Raw','Wiener','V42 E120','R109 E48','R119_B_E42'],
      primary='Unchanged deterministic ACM-inflection-LSC using the historical Raw-selected120pairs, same nine identities, Raw-derived session windows, calibration, per-pillar curvature reset. 64/96 samples and13/15iterations follow that specific historical LSC protocol, not the separate720-ray size readout.',
      input_policy='Native full-frame reconstruction before LSC cropping. R128 existing trial core256/requiredhalo/full-FOVboundaryguard, round(output*255) to uint8 PNG. R61 reuse original PSF-off8bit BMPs, verify selected source outputs by fresh inference before relying on them.',
      primary_metrics=['step_sd_nm','mean_nominal_abs_error_nm','median_within_grid_sd_nm','median_cross_axis_abs_nm'],
      additional='Keep per-sequence, per-pair and per-pillar measurements, max and95thpercentile nominal deviation, candidate changes fromRaw; no hidden dropped failures or new frame selection. Global primary stepSD is mean of four within-sequence SDs. No IID pair bootstrap because adjacent pairs share frames.',
      limitations=['Reused real development sequences, not unseen confirmation.','Nominal stage command is not independent physical position truth.','R119 causal-audit correction supersedes old causal/closeout claims.','V42 training overlap limits historical results; R61 is distinct checkpoint.','Paired SEM specimen differs from motion specimen: do not attach SEM ground truth to motion pillars.'],
      completion='All required native outputs, all4sequences/120pairs/9pillars for bothnewmethods or explicit unchanged-population failures; oldRaw reader parity and independent arithmetic verification; report all metrics and unfavorable cases.',
      no_training=True,no_model_or_existing_expected_hash_changes=True,no_confirmation_access=True,preparation_source=record(__file__))
    save(out/'plan.json',plan)
    with (out/'locked_pairs.csv').open('x',newline='',encoding='utf-8') as f:pairs.to_csv(f,index=False)
    print({'frames':len(frames),'pairs':len(pairs),'R128_reuse':sum(x['R128_reuse'] is not None for x in frames),'R61_existing':len(frames),'sequences':list(manifests)})

if __name__=='__main__':main()
