"""Finish the authorized qualification -> isolated package -> verified training chain.

Never changes admission thresholds, old evidence, source hashes, or defaults.
An error stops this coordinator and retains every diagnostic.
"""
from pathlib import Path
import sys,time,subprocess,traceback,os
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rt import load,save,atomic,record,sha,now,verify
import psutil

PKG=ROOT.parent.parent/'Deliverables/Standalone_Models/R134_DirectState_Standalone_20260915'
OUT=ROOT/'results/continuation'

def command(args,cwd=None,label='command'):
    log=OUT/(label+'.log')
    with log.open('xb') as f:
        result=subprocess.run([sys.executable,'-B',*map(str,args)],cwd=cwd or ROOT,stdout=f,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError(f'{label} failed; preserved log: {log}')
    return log

def status(phase,**extra):
    previous=load(OUT/'status.json').get('phase') if (OUT/'status.json').exists() else None
    atomic(OUT/'status.json',dict(phase=phase,pid=os.getpid(),updated_utc=now(),B_D_complete=False,model_promoted=False,**extra))
    if previous!=phase:
        from report134 import publish
        publish()

def require_admission(value):
    if not value.get('eligible'):return False
    assert value['arm']=='C' and value['selected_seed']==load(ROOT/'results/screening_decision.json')['selected_seed_by_dev_only']
    for key in ['stage1','motion12','motion201','checkpoint']:
        item=value[key];assert sha(item['path'])==item['sha256'],key
    assert load(ROOT/'results/motion_audit.json')['passed']
    final=load(value['motion201']['path']);assert final['frames']==201 and final['centers']==1809
    assert final['independent_center_refits']==1809 and all(r['passed'] for r in final['checks'])
    assert len(final['checks'])==20
    return True

def live(pid):
    if not psutil.pid_exists(pid):return False
    try:return psutil.Process(pid).status()!=psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:return False

def wait_training(predicate,timeout=7200):
    began=time.monotonic();deadline=began+timeout;p=PKG/'results/training/r134_long_01/status.json'
    while time.monotonic()<deadline:
        if p.exists():
            value=load(p)
            if value['status']=='failed':raise RuntimeError(value.get('error','Training failed'))
            if predicate(value):return value
            if not live(value['pid']) and time.monotonic()-began>30:raise RuntimeError('Training exited before the required state')
        time.sleep(3)
    raise TimeoutError('Training did not reach required state; no automatic retry')

def validate_public_images(pkg,output):
    import cv2,numpy as np
    for item in load(pkg/'verification/golden.json')['cases']:
        expected=pkg/item['expected'];actual=pkg/'results/inference'/output/(Path(item['input']).stem+'.png')
        assert np.array_equal(cv2.imread(str(expected),0),cv2.imread(str(actual),0))

def validate_initial_measurements():
    import pandas as pd,numpy as np
    seed=load(ROOT/'results/long_admission.json')['selected_seed'];folder=PKG/'results/training/r134_long_01/evaluations/step00000/real'
    a=pd.read_csv(folder/'motion_centers.csv').set_index(['sequence','frame_index','pillar_id']).sort_index()
    b=pd.read_csv(ROOT/f'results/motion/C_s{seed}/centers.csv').set_index(['sequence','frame_index','pillar_id']).sort_index()
    assert len(a)==len(b)==216 and a.index.equals(b.index)
    e=float(np.max(np.abs(a[['cx','cy']].to_numpy()-b[['lsc_center_x_px','lsc_center_y_px']].to_numpy())));assert e<1e-6
    a=pd.read_csv(folder/'sem_measurements.csv').set_index(['exposure','pillar']).sort_index()
    b=pd.read_csv(ROOT/f'results/real/C_s{seed}_p0512/measurements.csv').set_index(['exposure','pillar']).sort_index()
    keys=['radial_nm','correlation','diameter_error_nm','MZC_error_nm','centered_shape_nm'];assert len(a)==len(b)==108 and a.index.equals(b.index)
    sem=float(np.max(np.abs(a[keys].to_numpy()-b[keys].to_numpy())));assert sem<1e-5
    save(OUT/'initial_measurement_parity.json',dict(passed=True,motion_centers=216,SEM_reads=108,max_center_error_px=e,max_SEM_metric_difference=sem))

def expect_rejection(args,label):
    with (OUT/(label+'.log')).open('xb') as f:
        r=subprocess.run([sys.executable,'-B',*map(str,args)],cwd=PKG,stdout=f,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    assert r.returncode!=0,label

def relocate_and_verify():
    # Only this newly built package moves, within its explicitly named parent.
    parent=PKG.parent.resolve();source=PKG.resolve();target=(parent/'R134_搬移測試').resolve()
    assert source.parent==parent and target.parent==parent and source!=target and not target.exists()
    save(OUT/'relocation_paths_checked.json',dict(source=str(source),target=str(target),allowed_parent=str(parent)))
    source.rename(target)
    try:
        command([target/'verify_package.py'],cwd=ROOT.parent.parent,label='relocated_verify')
        command([target/'infer_r134.py','--output-name','relocation_check'],cwd=ROOT.parent.parent,label='relocated_public_inference')
        validate_public_images(target,'relocation_check')
        command([target/'train_r134.py','--dry-run'],cwd=ROOT.parent.parent,label='relocated_training_dryrun')
        save(OUT/'relocation_passed.json',dict(passed=True,unicode_path=True,different_working_directory=True,cases=2))
    finally:target.rename(source)

def main():
    OUT.mkdir(parents=True,exist_ok=False);status('waiting_full201')
    deadline=time.monotonic()+6*3600
    while not (ROOT/'results/long_admission.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Full201 admission did not finish')
        owner=load(ROOT/'config/packaging_source_binding.json')['full201_worker']
        if not live(owner['pid']) or abs(psutil.Process(owner['pid']).create_time()-owner['created'])>1:raise RuntimeError('Full201 worker stopped without admission; inspect its preserved error log')
        time.sleep(5)
    value=load(ROOT/'results/long_admission.json')
    if not require_admission(value):
        status('not_admitted',reason=value['reason'],long_training_started=False);return
    status('building_separate_package');command([ROOT/'scripts/build_long_package134.py'],label='build_package')
    status('verifying_actual_package');command([PKG/'preflight.py'],label='package_preflight')
    assert load(PKG/'results/preflight/complete.json')['passed']
    relocate_and_verify()
    status('testing_manual_training_controls')
    command([PKG/'control.py','start'],label='manual_start')
    started=wait_training(lambda s:s['completed_updates']>=2 and s['status']=='training')
    command([PKG/'control.py','pause'],label='manual_pause')
    paused=wait_training(lambda s:s['status']=='paused')
    # The run's finalizer must release its lock before resuming.
    lock=PKG/'results/training/r134_long_01/active.lock'
    deadline=time.monotonic()+60
    while lock.exists():
        if time.monotonic()>deadline:raise TimeoutError('Paused run did not release lock')
        time.sleep(.2)
    cp=paused['latest_checkpoint'];assert sha(PKG/cp['path'])==cp['sha256']
    validate_initial_measurements()
    expect_rejection([PKG/'train_r134.py'],'reject_duplicate_run')
    expect_rejection([PKG/'infer_r134.py','--output-name','relocation_check'],'reject_output_overwrite')
    assert sha(PKG/cp['path'])==cp['sha256']
    command([PKG/'control.py','status'],label='manual_status')
    command([PKG/'control.py','resume'],label='manual_resume')
    resumed=wait_training(lambda s:s['completed_updates']>=paused['completed_updates']+2 and s['status']=='training')
    save(OUT/'manual_controls_passed.json',dict(passed=True,started=started,paused=paused,resumed=resumed,preflight=record(PKG/'results/preflight/complete.json'),relocation=record(OUT/'relocation_passed.json')))
    status('long_training_running',package=str(PKG),training_pid=resumed['pid'],completed_updates=resumed['completed_updates'],planned_updates=8192)
    p=PKG/'results/training/r134_long_01/status.json'
    while True:
        s=load(p)
        if s['status']=='failed':raise RuntimeError(s.get('error','Training failed'))
        if s['status']=='paused':status('user_paused',package=str(PKG),training=s);return
        if s['status']=='complete':
            completion=PKG/'results/training/r134_long_01/completion.json';v=load(completion)
            assert s['completed_updates']==8192 and v['completed_updates']==8192
            for r in v['records']:assert sha(PKG/r['path'])==r['sha256']
            verify();command([PKG/'verify_package.py'],label='post_training_verification')
            status('final_full_comparison',package=str(PKG),completion=record(completion),training=s)
            command([ROOT/'scripts/compare_long134.py'],label='final_full201')
            assert load(ROOT/'results/long_final_comparison/complete.json')['frames']==201
            status('A_C_execution_complete_B_D_pending_calibration',package=str(PKG),completion=record(completion),final_comparison=record(ROOT/'results/long_final_comparison/complete.json'),training=s);return
        if not live(s['pid']):raise RuntimeError('Training process stopped without a completion or pause record')
        status('long_training_running',package=str(PKG),training=s)
        time.sleep(30)

if __name__=='__main__':
    try:main()
    except BaseException:
        # Do not leave an unverified training continuation running after a failed check.
        training=PKG/'results/training/r134_long_01/status.json'
        if training.exists() and load(training).get('status') not in ['complete','paused','failed']:
            subprocess.run([sys.executable,'-B',str(PKG/'control.py'),'pause'],cwd=PKG,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if OUT.exists():status('failed',error=traceback.format_exc())
        raise
