"""Read-only source recovery for the IMPACT R152 follow-up; never trains or substitutes data."""
from pathlib import Path
import hashlib, json, shutil, sys, subprocess
import numpy as np
import pandas as pd
from scipy.io import loadmat
from PIL import Image

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('D:/GMM_2_Final')
R152 = SOURCE / 'Experiments/R152_R148v2_SafeAdaptivePSF'
R80 = SOURCE / 'Experiments/R80_InflectionReferenceCircleSEMValidation'
CENTER = SOURCE / 'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9'
PAPER = Path('C:/Users/Rio/OneDrive/學業/碩班/論文/投稿/IMPACT2026')
SEQUENCES = ['50x_x_0p5um', '50x_x_1um', '20x_0p5um', '20x_1um']
OUT = ROOT / 'results'
SNAP = ROOT / 'sources'
for d in (OUT, SNAP, ROOT/'reports', ROOT/'poster_assets', ROOT/'qa'):
    d.mkdir(parents=True, exist_ok=True)

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8*1024*1024), b''): h.update(b)
    return h.hexdigest()

def load(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p, v): Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
records = []
def register(p, role, copy_name=None):
    p = Path(p)
    rec = dict(role=role, path=str(p), exists=p.is_file())
    if rec['exists']:
        rec.update(bytes=p.stat().st_size, sha256=sha(p))
        if copy_name:
            target=SNAP/copy_name
            shutil.copyfile(p,target)
            assert sha(target)==rec['sha256']
            rec['snapshot']=str(target.relative_to(ROOT))
    records.append(rec)
    return rec

def main():
    cfg_path=CENTER/'config/sequence_center9_50x20x.json'
    cfg=load(cfg_path)
    selection_path=R80/'results/tables/displacement_raw_locked_selection_all.csv'
    pairs_path=R80/'results/tables/displacement_lsc_per_pair_all.csv'
    centers_path=R80/'results/tables/displacement_lsc_centers_all.csv'
    session_path=CENTER/'diagnostics/unified_displacement_step_audit/tables/session_anchor_summary.csv'
    audit_path=session_path.with_name('raw_eligibility_locked_before_v42.csv')
    fixed=[(cfg_path,'original capture and nine-pillar configuration','sequence_config.json'),
           (selection_path,'original locked 120 pairs','original_locked_pairs.csv'),
           (pairs_path,'submitted historical pair-level measurements','historical_per_pair.csv'),
           (centers_path,'submitted historical center measurements','historical_centers.csv'),
           (session_path,'original crop anchor metadata','session_anchors.csv'),
           (audit_path,'raw eligibility before reconstruction','raw_eligibility.csv'),
           (R80/'scripts/reference_circle_core.py','submission measurement functions','reference_circle_core.py'),
           (R80/'scripts/run_displacement_lsc.py','submission measurement driver','run_displacement_lsc.py'),
           (PAPER/'source/build_impact_assets.py','submission statistics and figure source','build_impact_assets.py'),
           (PAPER/'Measurement-Oriented Microscopy Reconstruction for Cross-Magnification Micro-Displacement Inspection.pdf','submitted two-page paper','submitted_paper.pdf'),
           (R152/'reports/R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md','complete R152 record','R152_complete_record.md'),
           (SOURCE/'PROJECT_STATE.md','current source checkout project state','source_project_state.md'),
           (SOURCE/'ESTIMATOR_POLICY.json','current formal baseline policy','source_estimator_policy.json')]
    for p,role,name in fixed: register(p,role,name)
    sel=pd.read_csv(selection_path); pairs=pd.read_csv(pairs_path); centers=pd.read_csv(centers_path)
    raw_audit=pd.read_csv(audit_path)
    assert len(sel)==120 and len(pairs)==360 and not sel.duplicated(['sequence','start_frame_index','end_frame_index']).any()
    manifests=[]; counts=[]; center_pair_errors=[]; stats=[]
    for seq in SEQUENCES:
        spec=cfg['sequences'][seq]; locked=sel[sel.sequence==seq].reset_index(drop=True)
        assert len(locked)==30 and (locked.end_frame_index-locked.start_frame_index).eq(1).all()
        candidates=raw_audit[(raw_audit.sequence==seq)&raw_audit.raw_eligible_25pct.astype(bool)&~raw_audit.cross_session.astype(bool)].copy()
        candidates['err']=(candidates.raw_boundary_dx_um-candidates.expected_signed_step_um).abs()
        reproduced=candidates.sort_values(['err','raw_within_grid_nm','start_frame_index'],kind='mergesort').head(30).sort_values('start_frame_index')
        assert np.array_equal(locked[['start_frame_index','end_frame_index']].to_numpy(),reproduced[['start_frame_index','end_frame_index']].to_numpy())
        frame_ids=sorted(set(locked.start_frame_index)|set(locked.end_frame_index))
        for i in frame_ids:
            p=Path(spec['raw_dir'])/f'frame_{i:04d}.bmp'
            rec=register(p, f'locked raw {seq} frame {i}')
            if rec['exists']:
                with Image.open(p) as im: rec.update(width=im.width,height=im.height,mode=im.mode)
            manifests.append(dict(sequence=seq,frame_index=int(i),**rec))
            register(Path(spec['v42_dir'])/f'frame_{i:04d}.bmp',f'historical submitted MOSR image {seq} frame {i}; not R152')
        counts.append(dict(sequence=seq,pairs=30,unique_frames=len(frame_ids),scale_um_per_px=spec['object_um_per_px'],raw_dir=spec['raw_dir']))
        for method in ['Raw','Wiener','MOSR']:
            sub=pairs[(pairs.sequence==seq)&(pairs.method==method)].sort_values('pair_rank_raw_locked')
            assert np.array_equal(sub[['start_frame_index','end_frame_index']].to_numpy(),locked[['start_frame_index','end_frame_index']].to_numpy())
            assert sub.pair_rank_raw_locked.tolist()==list(range(1,31))
            c=centers[(centers.sequence==seq)&(centers.method==method)].set_index(['frame_index','pillar_id'])
            for row in sub.itertuples():
                dx=np.array([(c.loc[(row.end_frame_index,pid),'lsc_center_x_px']-c.loc[(row.start_frame_index,pid),'lsc_center_x_px'])*spec['object_um_per_px'] for pid,_,_ in spec['centers']])
                actual=[abs(np.median(dx)),abs(abs(np.median(dx))-spec['nominal_step_um'])*1000,np.std(dx,ddof=1)*1000]
                expected=[row.measured_step_um,row.nominal_abs_error_nm,row.within_grid_sd_nm]
                err=np.abs(np.array(actual)-expected)
                assert err.max()<1e-7
                center_pair_errors.append(dict(sequence=seq,method=method,pair_rank=row.pair_rank_raw_locked,max_numeric_error=float(err.max())))
            stats.append(dict(sequence=seq,method=method,n_pairs=30,step_sd_nm=sub.measured_step_um.std(ddof=1)*1000,nominal_mae_nm=sub.nominal_abs_error_nm.mean(),median_within_grid_sd_nm=sub.within_grid_sd_nm.median()))
    pd.DataFrame(manifests).to_csv(OUT/'raw_frame_manifest.csv',index=False)
    pd.DataFrame(counts).to_csv(OUT/'condition_inventory.csv',index=False)
    pd.DataFrame(center_pair_errors).to_csv(OUT/'historical_center_to_pair_check.csv',index=False)
    stats=pd.DataFrame(stats);stats.to_csv(OUT/'historical_condition_metrics.csv',index=False)
    expected={'Raw':[8.88,7.00,12.55],'Wiener':[7.91,6.42,5.98],'MOSR':[7.29,5.74,4.89]}
    agg=[]
    for method,vals in expected.items():
        s=stats[stats.method==method]; p=pairs[pairs.method==method]
        actual=[s.step_sd_nm.mean(),s.nominal_mae_nm.mean(),p.within_grid_sd_nm.median()]
        assert np.all(np.abs(np.array(actual)-vals)<0.005)
        agg.append(dict(method=method,step_sd_nm=actual[0],nominal_mae_nm=actual[1],median_within_grid_sd_nm=actual[2],status='historical submitted model, NOT R152'))
    pd.DataFrame(agg).to_csv(OUT/'historical_aggregate_metrics.csv',index=False)
    optics=[]
    fitroot=SOURCE/'PSF_Fitting/output/pillar_via_junction_psf_20260713'
    for mag in ['20x','50x']:
        sweep=SOURCE/f'PSF_Fitting/tests/artifacts/cd_verification_20260714/{mag}_deconvolution_sweep.mat'
        fit=fitroot/mag/'fit_result/PSF_fitted_2D_FOVstack.mat'
        meta=fitroot/mag/'selected_frame.json'
        for p,role in [(sweep,'original Wiener optical data'),(fit,'original calibrated PSF fit'),(meta,'objective and pixel scale calibration provenance')]:register(p,role)
        m=load(meta);register(m['selected_image'],'original PSF calibration image')
        a=np.asarray(loadmat(sweep,variable_names=['psf'])['psf'],float)
        b=np.squeeze(loadmat(fit,variable_names=['psf_grid'])['psf_grid']).astype(float); b/=b.sum()
        assert a.shape==(101,101) and np.isfinite(a).all() and (a>=0).all() and np.allclose(a,b,rtol=0,atol=1e-14)
        optics.append(dict(magnification=mag,object_um_per_px=m['object_pixel_um'],kernel_count=1,kernel_shape=list(a.shape),sum=float(a.sum()),max_sweep_fit_difference=float(abs(a-b).max()),wiener_nsr=0.0565,r152_25_kernel_compatibility=False,fit_path=str(fit),sweep_path=str(sweep)))
    save(OUT/'original_optics_audit.json',optics)
    mc=load(R152/'config/model.json'); receipt=load(R152/'runs/formal_8192/training_complete.json'); banklock=load(R152/'calibration/BANK_LOCK.json')
    for name in ['model.py','base_model.py','optical/adaptive_fourier_psf.py','optical/fullres_psf.py','config/model.json','config/SOURCE_LOCK.json','calibration/BANK_LOCK.json','runs/formal_8192/training_complete.json']:
        register(R152/name,'R152 delivered implementation and identity', 'r152_'+name.replace('/','_'))
    for p,expected_hash in [(Path(mc['base_checkpoint']),mc['base_checkpoint_sha256']),(Path(receipt['deployed_checkpoint']['path']),receipt['deployed_checkpoint']['sha256']),(R152/mc['psf_bank'],banklock['bank_sha256'])]:
        rec=register(p,'R152 immutable inference dependency'); assert rec.get('sha256')==expected_hash
    verified=[]
    for s in ['verify_package.py','verify_complete_record.py']:
        run=subprocess.run([sys.executable,'-B',str(R152/'scripts'/s)],cwd=R152,capture_output=True,text=True,encoding='utf-8')
        assert run.returncode==0,run.stderr
        verified.append(dict(script=s,result=json.loads(run.stdout)))
    save(OUT/'r152_package_verification.json',verified)
    import torch
    cp=torch.load(receipt['deployed_checkpoint']['path'],map_location='cpu',weights_only=False)
    basecp=torch.load(mc['base_checkpoint'],map_location='cpu',weights_only=False)
    frozen_equal=all(torch.equal(cp['model']['base.'+k],v) for k,v in basecp['model'].items())
    assert frozen_equal and float(cp['model']['deployment_scale'])==1
    save(OUT/'r152_model_identity.json',dict(checkpoint=receipt['deployed_checkpoint'],base_checkpoint_sha256=mc['base_checkpoint_sha256'],deployment_scale=1,base_state_items=len(basecp['model']),frozen_base_identical=frozen_equal,optical_state={k:list(v.shape) for k,v in cp['model'].items() if 'bank' in k or 'mean_kernel' in k or 'psf_descriptors' in k},delivered_optical_scale_um_per_px=banklock['object_um_per_px'],compatible_50x_bank_found=False))
    save(OUT/'source_manifest.json',records)
    missing=[r for r in records if not r['exists']]
    gate=dict(status='BLOCKED_50X_OPTICS',instruction='User clarified that the chat request itself is the execution instruction; no separate instruction file is missing.',locked_pairs=120,raw_unique_frames=len(manifests),missing_files=missing,historical_statistics_match_paper=True,full_r152_inference_started=False,retraining=False,formal_baseline_changed=False,blocking_items=[dict(id='R152_50X_OPTICS',detail='Original 50x Wiener PSF exists (one 101x101 kernel at 0.069 um/px). Delivered R152 requires 25 indexed kernels and contains fixed 20x optics at 0.1725 um/px in both the base and added branch. No source-locked 50x 25-kernel bank and verified same-weight installation path found. Do not tile, resize, duplicate, or borrow the 20x bank.')])
    full=OUT/'full120/complete.json'
    if full.exists() and load(full).get('state')=='complete_objective_calibrated_full120' and (OUT/'preflight_status.json').exists():
        gate=load(OUT/'preflight_status.json')
        gate['missing_files']=missing
        gate['source_recheck_passed']=not missing
    save(OUT/'preflight_status.json',gate)
    print(json.dumps(gate,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
