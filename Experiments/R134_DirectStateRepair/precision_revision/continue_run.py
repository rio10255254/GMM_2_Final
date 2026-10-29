"""Run the authorized precision qualification and conditional independent long training."""
from common import *
from report import publish
import subprocess,psutil,traceback,cv2,pandas as pd
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PKG=E.parent.parent/'Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/R134_DirectState_Precision_Standalone_20260915'
OPS=P/'results/operations'

def stage(phase,**kw):status(phase,**kw);publish()

def command(args,name,cwd=None,rejection=None):
    log=OPS/(name+'.log')
    with log.open('xb') as f:r=subprocess.run([sys.executable,'-B',*map(str,args)],cwd=cwd or P,stdout=f,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if rejection:
        if r.returncode==0 or rejection not in log.read_text(encoding='utf-8',errors='replace'):raise RuntimeError('Expected rejection not established: '+str(log))
    elif r.returncode:raise RuntimeError('Command failed; preserved log: '+str(log))

def get_complete(group):
    path=P/f'results/{group}/complete.json';deadline=time.monotonic()+6*3600
    while not path.exists():
        fail=P/f'results/{group}_failure.json'
        if fail.exists():raise RuntimeError(load(fail)['error'])
        started=P/f'results/{group}/started.json'
        if started.exists() and not psutil.pid_exists(load(started)['pid']) and not path.exists():raise RuntimeError(group+' worker exited without completed results')
        if time.monotonic()>deadline:raise TimeoutError(group+' qualification timeout')
        time.sleep(3)
    # Producers pre-serialize; tolerate the short final-file write interval.
    for _ in range(40):
        try:return load(path)
        except json.JSONDecodeError:time.sleep(.25)
    raise RuntimeError('Incomplete qualification result: '+str(path))

def wait_training(test,timeout=7200):
    began=time.monotonic();path=PKG/'results/training/r134p_long_01/status.json'
    while time.monotonic()-began<timeout:
        if path.exists():
            try:s=load(path)
            except json.JSONDecodeError:time.sleep(.2);continue
            if s['status']=='failed':raise RuntimeError(s.get('error','Training failed'))
            if test(s):return s
            if not psutil.pid_exists(s['pid']) and time.monotonic()-began>30:raise RuntimeError('Training exited without expected state')
        time.sleep(3)
    raise TimeoutError('Training state timeout')

def initial_parity():
    folder=PKG/'results/training/r134p_long_01/evaluations/step00000/real';keys=['sequence','frame_index','pillar_id'];a=pd.read_csv(folder/'motion_centers.csv').set_index(keys);b=pd.read_csv(P/'results/motion/C_s1342001/centers.csv').set_index(keys).loc[a.index];error=float(np.abs(a[['lsc_center_x_px','lsc_center_y_px']].values-b[['lsc_center_x_px','lsc_center_y_px']].values).max());assert len(a)==216 and error<1e-9
    a=pd.read_csv(folder/'sem_measurements.csv').set_index(['exposure','pillar']).sort_index();b=pd.read_csv(P/'results/sem/C_s1342001/measurements.csv').set_index(['exposure','pillar']).sort_index();cols=['radial_nm','diameter_error_nm','centered_shape_nm','correlation','MZC_error_nm'];semerr=float(np.abs(a[cols].values-b[cols].values).max());assert len(a)==108 and semerr<1e-5
    save(OPS/'initial_measurement_parity.json',dict(motion_centers=216,motion_max_error_px=error,SEM_rows=108,SEM_max_error=semerr))

def main():
    OPS.mkdir(exist_ok=False);stage('qualifying');motion=get_complete('motion');sem=get_complete('sem');protected()
    for v in [motion,sem]:
        for r in v['sources']:assert sha(r['path'])==r['sha256']
    assert motion['frames']==motion['original_preview_exact_replays']==273 and motion['independent_center_refits']==2457 and sem['rows']==sem['independent_refits']==540
    checks=motion['full201_checks']+motion['matched12_checks']+sem['checks'];eligible=all(x['passed'] for x in checks);assert eligible==(motion['passed'] and sem['passed'])
    cp=E/'runs/R134_C_s1342001/step0512.pth';save(P/'results/admission.json',dict(eligible=eligible,checks=checks,checkpoint=record(cp),motion=record(P/'results/motion/complete.json'),sem=record(P/'results/sem/complete.json'),protocol=record(P/'config/protocol.json'),original_negative_admission_unchanged=record(E/'results/long_admission.json'),scope='R134 P1 engineering longtraining admission, reused development data; no model promotion'))
    if not eligible:stage('not_admitted',failed=[r for r in checks if not r['passed']]);return
    for r in load(P/'config/package_sources.json')['sources']:assert sha(str(PROJECT_ROOT / r['path']))==r['sha256']
    stage('building_package');command([P/'build_package.py'],'build_package');stage('package_preflight',package=str(PKG));command([PKG/'preflight.py'],'package_preflight')
    parent=PKG.parent.resolve();target=(parent/'R134P_搬移實測').resolve();assert PKG.resolve().parent==parent and target.parent==parent and not target.exists();save(OPS/'relocation_paths_checked.json',dict(source=str(PKG.resolve()),target=str(target),allowed_parent=str(parent)));PKG.rename(target)
    try:
        command([target/'verify_package.py'],'relocation_verify',cwd=E.parent.parent);command([target/'infer_r134p.py','--output-name','relocation_check'],'relocation_infer',cwd=E.parent.parent)
        for g in load(target/'verification/golden.json')['cases']:assert np.array_equal(np.load(target/g['expected']),np.load(target/'results/inference/relocation_check'/(Path(g['input']).stem+'.npy')))
        command([target/'train_r134p.py','--dry-run'],'relocation_training',cwd=E.parent.parent)
    finally:target.rename(PKG)
    save(OPS/'relocation_passed.json',dict(passed=True,lossless_golden_parity=True,different_working_directory=True,unicode_path=True))
    stage('manual_control_test',package=str(PKG));command([PKG/'control.py','start'],'manual_start');started=wait_training(lambda s:s['status']=='training' and s['completed_updates']>=2);command([PKG/'control.py','pause'],'manual_pause');paused=wait_training(lambda s:s['status']=='paused')
    deadline=time.monotonic()+60
    while (PKG/'results/training/r134p_long_01/active.lock').exists():
        if time.monotonic()>deadline:raise TimeoutError('Pause lock not released')
        time.sleep(.2)
    cp=paused['latest_checkpoint'];assert sha(PKG/cp['path'])==cp['sha256'];initial_parity();command([PKG/'train_r134p.py'],'reject_duplicate_run',rejection='Run exists; choose Resume');command([PKG/'infer_r134p.py','--output-name','relocation_check'],'reject_duplicate_output',rejection='Output already exists');assert sha(PKG/cp['path'])==cp['sha256'];command([PKG/'control.py','status'],'manual_status');command([PKG/'control.py','resume'],'manual_resume');resumed=wait_training(lambda s:s['status']=='training' and s['completed_updates']>=paused['completed_updates']+2)
    save(OPS/'manual_controls_passed.json',dict(passed=True,started=started,paused=paused,resumed=resumed));stage('long_training',package=str(PKG),training=resumed)
    while True:
        s=load(PKG/'results/training/r134p_long_01/status.json')
        if s['status']=='failed':raise RuntimeError(s.get('error','Training failed'))
        if s['status']=='paused':stage('paused',package=str(PKG),training=s);return
        if s['status']=='complete':
            completion=PKG/'results/training/r134p_long_01/completion.json';v=load(completion);assert s['completed_updates']==v['completed_updates']==8192
            for r in v['records']:assert sha(PKG/r['path'])==r['sha256']
            command([PKG/'verify_package.py'],'after_training_verify');protected();stage('final_comparison',package=str(PKG),completion=record(completion));command([P/'final_compare.py'],'final_full201');assert load(P/'results/final_full201/complete.json')['frames']==201;stage('complete',package=str(PKG),completion=record(completion),comparison=record(P/'results/final_full201/complete.json'));return
        if not psutil.pid_exists(s['pid']):raise RuntimeError('Training stopped without completion or pause')
        status('long_training',package=str(PKG),training=s);time.sleep(30)
if __name__=='__main__':
    try:main()
    except BaseException:
        s=PKG/'results/training/r134p_long_01/status.json'
        if s.exists() and load(s).get('status') not in ['complete','failed','paused']:
            subprocess.run([sys.executable,'-B',str(PKG/'control.py'),'pause'],cwd=PKG,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        stage('failed',error=traceback.format_exc());raise
