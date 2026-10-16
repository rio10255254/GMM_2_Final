"""Reproduce the real Windows sharing failure and verify exact training replay."""
import os,sys,json,time,threading,ctypes,random
from pathlib import Path
REC=Path(__file__).resolve().parent;ROOT=REC.parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT))
from common import load,save,sha,record,now,atomic as original_atomic
from robust_io import atomic_bytes,atomic

def main():
    out=REC/'tests';out.mkdir(exist_ok=False);rows=[]
    def checked(name,**details):
        rows.append(dict(name=name,passed=True,**details));print(json.dumps(rows[-1]),flush=True)
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p];api.CreateFileW.restype=ctypes.c_void_p
    api.CloseHandle.argtypes=[ctypes.c_void_p];api.CloseHandle.restype=ctypes.c_int
    def hold(path):
        handle=api.CreateFileW(str(path),0x80000000,3,None,3,0,None)
        if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        return handle
    old=out/'original.json';save(old,dict(value='before'))
    h=hold(old)
    try:
        try:original_atomic(old,dict(value='after'))
        except PermissionError as exc:
            assert exc.winerror in [5,32,33];code=exc.winerror
        else:raise AssertionError('Expected original Windows failure was not reproduced')
        assert load(old)==dict(value='before')
    finally:api.CloseHandle(h)
    checked('original_failure_reproduced_with_real_Windows_reader',winerror=code)
    fixed=out/'recovered.json';save(fixed,dict(value='before'));h=hold(fixed)
    def release():time.sleep(.4);assert api.CloseHandle(h)
    thread=threading.Thread(target=release);thread.start();start=time.perf_counter()
    atomic_bytes(fixed,b'{"value":"after"}');thread.join()
    assert load(fixed)==dict(value='after')
    checked('same_actual_file_lock_recovered_without_deleting_target',waited_seconds=time.perf_counter()-start)
    denied=out/'persistent_lock.json';save(denied,dict(value='original'));h=hold(denied);before=sha(denied)
    try:
        try:atomic_bytes(denied,b'{"value":"changed"}',timeout=.12)
        except PermissionError:pass
        else:raise AssertionError('Persistent denial was hidden')
        assert sha(denied)==before
    finally:api.CloseHandle(h)
    checked('persistent_denial_raises_and_preserves_old_content')
    for path in [ROOT/'config/study.json',ROOT/'results/data_audit.json',ROOT/'runs/I_s1285001/checkpoints/step1280.pth']:
        before=sha(path)
        try:atomic(path,dict(fake='invalid'))
        except ValueError:pass
        else:raise AssertionError('Adapter could overwrite scientific evidence')
        assert sha(path)==before
    checked('scientific_files_outside_adapter_write_scope')
    target=out/'stress.json';save(target,dict(n=0,values=[0]*50));finished=threading.Event();errors=[];reads=[]
    def reader():
        while not finished.is_set():
            try:
                d=load(target)
                if d['values']!=[d['n']]*50:errors.append('partial document')
                reads.append(d['n'])
            except BaseException as exc:errors.append(str(exc))
    reader_thread=threading.Thread(target=reader);reader_thread.start()
    try:
        for i in range(1,201):atomic_bytes(target,json.dumps(dict(n=i,values=[i]*50)).encode())
    finally:finished.set();reader_thread.join()
    assert not errors and load(target)['n']==200 and reads
    checked('concurrent_progress_reads_never_observe_partial_document',writes=200,reads=len(reads))
    # Replay original recorded updates, using the exact last saved model and
    # optimizer state. No candidate selection or old-record replacement.
    import numpy as np,torch
    from training.engine import create,restore,update
    from training.data import Bank
    from train import verify_binding
    verify_binding(load(ROOT/'config/frozen_training.json'))
    cfg=load(ROOT/'config/study.json');snap=load(REC/'interruption_snapshot.json')
    ledger=[]
    for p in sorted((ROOT/'runs/I_s1285001').glob('updates_*.jsonl')):
        ledger += [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()]
    expected={r['update']:r for r in ledger};model,opt=create(1285001,'cuda',cfg)
    binding=dict(frozen_training_sha256=sha(ROOT/'config/frozen_training.json'))
    start_step=restore(snap['last_checkpoint']['path'],model,opt,binding,'I',1285001)
    assert start_step==1280
    bank=Bank();replays=[]
    for step in range(1281,1285):
        epoch=(step-1)//512;position=(step-1)%512;index=int(bank.order(epoch)[position])
        batch=bank.batch('train',index,'cuda',epoch)
        row=update(model,opt,batch,step,'I',cfg);oldrow=expected[step]
        fields=['learning_rate','loss','terms','gradient_norm','actual_input_sha256','source_uint8_sha256','parent_id','parent_arrays_sha256','noise_seed','noise_sigma_gray','kernel_sha256']
        mismatches={k:[row[k],oldrow[k]] for k in fields if row[k]!=oldrow[k]}
        if mismatches:save(out/f'replay_difference_{step}.json',mismatches);raise AssertionError('Original learning step did not reproduce')
        py_state=random.getstate();np_state=np.random.get_state();cpu_state=torch.get_rng_state().clone();gpu_state=torch.cuda.get_rng_state().clone()
        atomic_bytes(out/f'replayed_{step}.json',json.dumps(row).encode())
        assert random.getstate()==py_state and np.array_equal(np.random.get_state()[1],np_state[1]) and torch.equal(torch.get_rng_state(),cpu_state) and torch.equal(torch.cuda.get_rng_state(),gpu_state)
        replays.append(dict(step=step,all_learning_fields_exact=True))
    checked('original_checkpoint_and_four_updates_reproduce_exactly',updates=replays,adapter_does_not_consume_training_RNG=True)
    result=dict(passed=True,created_utc=now(),checks=rows,source_sha256={str(p):sha(p) for p in REC.glob('*.py')},original_frozen_study=record(ROOT/'config/frozen_training.json'),pre_recovery_snapshot=record(REC/'interruption_snapshot.json'),diagnostic_updates=4,diagnostic_weights_not_used_for_full_training=True)
    save(REC/'verification.json',result)

if __name__=='__main__':main()
