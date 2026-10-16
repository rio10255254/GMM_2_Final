"""Validate completed methods on the fixed real set, then restore saved training."""
from pathlib import Path
import datetime, json, os, subprocess, sys, time, traceback
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from study import read, save, sha
from scripts.monitor_training import processes

METHODS=['Wiener','EDSR-x1','NAFNet','RDN-x1','RCAN-x1']
RUNTIME_METHODS=['RAW','Wiener','MOSR','EDSR-x1','NAFNet','RDN-x1','RCAN-x1']


def main():
    marker=ROOT/'runs/launcher_logs/VALIDATION_PRIORITY.json'
    assert marker.exists() and read(marker)['user_authorized_pause_training_for_validation']
    managers,workers=processes();assert not managers and not workers,'Training must release GPU before validation'
    logs=ROOT/'runs/validation_logs';logs.mkdir(parents=True,exist_ok=True)
    status={'state':'active','pid':os.getpid(),'methods':METHODS,'runtime_methods':RUNTIME_METHODS,
            'current_stage':None,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'runtime_completed':[],'reconstruction_completed':[],'measurement_completed':[]}
    env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    def launch(script,args,tag):
        status.update(current_stage=tag,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        save(logs/'status.json',status)
        handle=(logs/(tag+'.log')).open('a',encoding='utf-8')
        child=subprocess.Popen([sys.executable,'-B','-X','utf8',str(ROOT/'scripts'/script),*args],cwd=ROOT,env=env,
                               stdout=handle,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        handle.close();status['child_pid']=child.pid;save(logs/'status.json',status)
        return child
    def checked(child,tag):
        code=child.wait()
        if code!=0:raise RuntimeError(f'{tag} exited {code}; inspect preserved log')
    measurement=None;measurement_method=None
    try:
        for method in RUNTIME_METHODS:
            receipt=ROOT/'results/runtime'/(method+'.json')
            if not receipt.exists():checked(launch('benchmark_runtime.py',['--method',method],'runtime_'+method),'runtime '+method)
            assert read(receipt)['state']=='complete'
            status['runtime_completed'].append(method);save(logs/'status.json',status)
        for method in METHODS:
            receipt=ROOT/'results/reconstruction'/method/'reconstruction_complete.json'
            if not receipt.exists() or read(receipt)['state']!='complete':
                checked(launch('evaluate_real_method.py',[method,'--stage','reconstruct'],'reconstruct_'+method),'reconstruct '+method)
            assert read(receipt)['state']=='complete' and read(receipt)['images']==930
            status['reconstruction_completed'].append(method);save(logs/'status.json',status)
            if measurement is not None:
                checked(measurement,'measure '+measurement_method)
                status['measurement_completed'].append(measurement_method)
            receipt=ROOT/'results/readouts'/method/'measurement_complete.json'
            if not receipt.exists():
                measurement=launch('evaluate_real_method.py',[method,'--stage','measure'],'measure_'+method)
                measurement_method=method
            else:
                assert read(receipt)['state']=='complete';status['measurement_completed'].append(method)
                measurement=None
        if measurement is not None:
            checked(measurement,'measure '+measurement_method);status['measurement_completed'].append(measurement_method)
        status.update(current_stage='summarize',child_pid=None);save(logs/'status.json',status)
        checked(launch('summarize_available_real.py',[],'summarize'),'summarize')
        status.update(state='complete',completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),child_pid=None)
        save(logs/'status.json',status)
        record=read(marker);record.update(state='complete',validation_receipt='runs/validation_logs/status.json')
        save(logs/'training_pause_record.json',record)
        marker.unlink()
        # Training resumes only after the GPU comparison and result audit finish.
        checked(launch('monitor_training.py',['--ensure'],'restore_training'),'restore_training')
        print('AVAILABLE-METHOD VALIDATION COMPLETE; TRAINING RESTORE REQUESTED',flush=True)
    except BaseException as error:
        if measurement is not None and measurement.poll() is None:
            status['active_measurement_pid']=measurement.pid
        status.update(state='failed',error=repr(error),traceback=traceback.format_exc(),failed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        save(logs/'status.json',status)
        # Preserve marker: monitoring must repair the concrete failure before restarting training.
        raise


if __name__=='__main__':main()
