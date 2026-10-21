"""One-off independent launch; unchanged R128 trainer and recovery coordinator."""
import os,sys,json,time,ctypes,argparse,traceback,runpy
from pathlib import Path
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8';sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OLD=ROOT/'recovery/20260909_progress_io_v1'
sys.path.insert(0,str(OLD));sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT))
from common import load,save,record,sha,now

def job_membership():
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.GetCurrentProcess.restype=ctypes.c_void_p
    api.IsProcessInJob.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_int)]
    api.IsProcessInJob.restype=ctypes.c_int;flag=ctypes.c_int()
    if not api.IsProcessInJob(api.GetCurrentProcess(),None,ctypes.byref(flag)):raise ctypes.WinError(ctypes.get_last_error())
    return bool(flag.value)

def probe():
    from train import verify_binding
    from run_child import verify_recovery
    from training.engine import create,restore,update
    from training.data import Bank
    import torch
    verify_binding(load(ROOT/'config/frozen_training.json'));verify_recovery()
    assert not job_membership(),'Launcher is still in a controlling job'
    cfg=load(ROOT/'config/study.json');snap=load(HERE/'snapshot.json')
    model,opt=create(1285002,'cuda',cfg)
    binding={'frozen_training_sha256':sha(ROOT/'config/frozen_training.json')}
    cp=snap['last_complete_checkpoint'];assert sha(cp['path'])==cp['sha256']
    step=restore(cp['path'],model,opt,binding,'I',1285002);assert step==5248
    old={}
    for p in (ROOT/'runs/I_s1285002').glob('updates_*.jsonl'):
        for line in p.read_text(encoding='utf-8').splitlines():
            row=json.loads(line);old[row['update']]=row
    bank=Bank();comparisons=[]
    for step in range(5249,5253):
        epoch=(step-1)//512;position=(step-1)%512;index=int(bank.order(epoch)[position])
        row=update(model,opt,bank.batch('train',index,'cuda',epoch),step,'I',cfg)
        fields=['learning_rate','loss','terms','gradient_norm','actual_input_sha256','source_uint8_sha256','parent_id','noise_seed','kernel_sha256']
        errors=[k for k in fields if row[k]!=old[step][k]]
        if errors:save(HERE/f'probe_difference_{step}.json',dict(errors=errors,new=row,old=old[step]));raise AssertionError('Exact replay failed')
        comparisons.append(dict(step=step,all_learning_fields_exact=True))
    save(HERE/'independent_launch_test.json',dict(passed=True,verified_utc=now(),pid=os.getpid(),parent_pid=os.getppid(),in_any_Windows_job=False,CUDA_device=torch.cuda.get_device_name(0),original_checkpoint=cp,exact_replayed_updates=comparisons,diagnostic_updates=4,diagnostic_weights_not_used_for_training=True,entry_source=record(__file__),frozen_study=record(ROOT/'config/frozen_training.json'),recovery_manifest=record(OLD/'recovery_manifest.json')))

def train():
    manifest=load(HERE/'launch_manifest.json')
    for item in manifest['records']:
        if sha(item['path'])!=item['sha256']:raise RuntimeError('Independent launch binding changed')
    if job_membership():raise RuntimeError('Training launcher is not independent')
    save(HERE/'launched.json',dict(utc=now(),pid=os.getpid(),parent_pid=os.getppid(),in_any_Windows_job=False,manifest=record(HERE/'launch_manifest.json'),scientific_implementation_unchanged=True))
    runpy.run_path(str(OLD/'coordinate.py'),run_name='__main__')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--probe',action='store_true');args=parser.parse_args()
    role='probe' if args.probe else 'training'
    # Both stdout/stderr belong to this one-off process and survive its caller.
    logfile=HERE/f'{role}_{os.getpid()}.log'
    with logfile.open('x',encoding='utf-8',buffering=1) as stream:
        sys.stdout=stream;sys.stderr=stream
        try:
            print(json.dumps(dict(role=role,pid=os.getpid(),parent_pid=os.getppid(),in_job=job_membership())),flush=True)
            probe() if args.probe else train()
        except BaseException:
            traceback.print_exc();save(HERE/f'{role}_{os.getpid()}_failure.json',dict(utc=now(),error=traceback.format_exc()))
            raise
