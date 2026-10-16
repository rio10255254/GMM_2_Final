from common import *
import csv,shutil
import cv2
def main():
    for name in ['config','reports','results','runs/launcher_logs']:(ROOT/name).mkdir(parents=True,exist_ok=True)
    previous=load(REPO/'Experiments/R135_UnifiedModelComparison/config/plan.json')
    frames=[];runs=[]
    for ri,p in enumerate(sorted(SOURCE.glob('*/positions.csv')),1):
        rows=list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
        assert len(rows)==31 and [r['image'] for r in rows]==[f'{i}.bmp' for i in range(1,32)]
        runs.append(dict(run=p.parent.name,run_index=ri,positions=record(p),count=len(rows),time_block='early6' if ri<=6 else 'late24'))
        for i,r in enumerate(rows):
            path=p.parent/r['image'];im=cv2.imread(str(path),0);assert im is not None and im.shape==(1544,2064)
            frames.append(dict(run=p.parent.name,run_index=ri,index=i,image=r['image'],source=record(path),pi_x_um=float(r['x']),pi_y_um=float(r['y']),recorded_at=r['recorded_at'],frame=int(r['frame']),exposure_us=float(r['exposure_us'])))
    assert len(runs)==30 and len(frames)==930
    r129=load(REPO/'Experiments/R129_OpticalPriorHybrid/results/continuous_lsc/plan.json')
    models=dict(R61=previous['models']['R61'],R129=dict(checkpoint=r129['checkpoint'],package=r129['package'],guard_width=80,guard_transition=16,updates=8192))
    for info in models.values():assert sha(info['checkpoint']['path'])==info['checkpoint']['sha256']
    plan=dict(created_utc=now(),runs=runs,frames=frames,models=models,primary='paired full-scan comparison against synchronous PI feedback',units_confirmed_by_user='um',scale_status='pending capture calibration',raw_unchanged=True,training_updates=0,rois=dict(primary=[128,128,1808,1288],inner=[256,256,1552,1032],junction=[1050,450,650,750]),reader=dict(primary='unwindowed overlap-refined intensity translation with illumination offset/scale',secondary='gradient phase correlation'),scan_exclusions=[],output_precision='float32 NPZ plus lossless16bit PNG',analysis_scope='same sample and capture session; not universal model generalization')
    save(ROOT/'config/plan.json',plan)
    save(ROOT/'runs/launcher_logs/active_formal_run.json',dict(status='prepared',created_utc=now(),expected_frames_per_model=930,models=['R61','R129'],training_updates=0))
    (ROOT/'README.md').write_text('# R136 PI referenced repeated displacement\n\nShared-mainline analysis of 30 complete 31-frame captures. Raw, fixed R61 v16 PSF-off and fixed R129 step8192 original80/16 output. No training or per-result model selection. Full details: config/plan.json; results/status_*.json; reports/R136_RESULTS.md. Branch codex/r136-pi-repeatability.\n',encoding='utf-8')
    (ROOT/'MANIFEST.md').write_text('# R136 manifest\n\nShared-mainline. Original captures and model sources referenced without moving or copying. 930 raw images; 1860 planned reconstructions. Every within-run adjacent and start-relative pair attempted for every method. Complete run is the comparison unit. Outputs budget 30GiB; retain results and reproducible scripts on D, no deletion in this task. Calibration must be independent or explicitly separated from evaluation.\n',encoding='utf-8')
    (ROOT/'results/README.md').write_text('# Results\n\nR61 and R129 retain full precision arrays and16bit viewable reconstructions. Original photographs remain at source. tables and figures contain reproducible measurements. Status files are progress, not completion evidence. D storage budget30GiB; future H archival only by separate instruction.\n',encoding='utf-8')
    p=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';reg=load(p)
    reg['entries'].append(dict(id='r136_pi_repeatability',path='Experiments/R136_PIRepeatability',tier='active',state='authorized_reconstruction_and_analysis',action='protect',priority=0,estimated_gib=30,keep='Two fixed models,930frames each; source images referenced; retain values,readouts,figures,provenance. No automatic cleanup.',blocked_by=[]));reg['updated_at']=now();save(p,reg)
    print('Prepared',len(frames),'frames;freeGiB',round(shutil.disk_usage(ROOT).free/2**30,2),flush=True)
if __name__=='__main__':main()
