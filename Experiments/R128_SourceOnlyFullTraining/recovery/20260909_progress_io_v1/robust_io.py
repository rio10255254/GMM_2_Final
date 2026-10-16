"""Explicit operational I/O adapter; the frozen scientific implementation stays intact."""
import os,json,time,uuid,threading
from pathlib import Path
REC=Path(__file__).resolve().parent
ROOT=REC.parents[1]
_event_lock=threading.Lock()

def event(kind,**details):
    row=dict(kind=kind,pid=os.getpid(),time_unix=time.time(),**details)
    try:
        with _event_lock:
            with (REC/f'io_events_{os.getpid()}.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    except OSError:
        print(json.dumps(dict(io_event_write_failed=True,**row)),flush=True)

def atomic_bytes(path,data,timeout=30.,replace=None):
    path=Path(path).resolve();pending=REC/'pending';pending.mkdir(exist_ok=True)
    temp=pending/f'{os.getpid()}_{uuid.uuid4().hex}.pending'
    with temp.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    replacer=os.replace if replace is None else replace
    deadline=time.monotonic()+timeout;tries=0;delay=.02
    while True:
        try:
            replacer(temp,path)
            if tries:event('replacement_recovered',path=str(path),retries=tries)
            return
        except OSError as exc:
            retryable=getattr(exc,'winerror',None) in [5,32,33]
            if not retryable or time.monotonic()>=deadline:
                event('replacement_failed',path=str(path),pending=str(temp),retries=tries,error=str(exc))
                raise
            tries+=1
            if tries==1:event('replacement_temporarily_denied',path=str(path),error=str(exc))
            time.sleep(min(delay,max(0,deadline-time.monotonic())));delay=min(delay*1.7,.5)

def atomic(path,value):
    """Only explicitly mutable execution metadata may be replaced."""
    path=Path(path).resolve()
    if not mutable_metadata(path):raise ValueError(f'Recovery adapter cannot replace evidence: {path}')
    atomic_bytes(path,json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False).encode('utf-8'))

def mutable_metadata(path):
    path=Path(path).resolve()
    return path.is_relative_to(ROOT/'runs') and path.name in ['status.json','latest_checkpoint.json','progress.json','active_formal_run.json']

def read_json_retry(path,timeout=30.):
    path=Path(path);deadline=time.monotonic()+timeout;tries=0;delay=.01
    while True:
        try:
            data=json.loads(path.read_text(encoding='utf-8-sig'))
            if tries:event('read_recovered',path=str(path),retries=tries)
            return data
        except (PermissionError,FileNotFoundError) as exc:
            if time.monotonic()>=deadline:
                event('read_failed',path=str(path),retries=tries,error=str(exc));raise
            tries+=1;time.sleep(min(delay,max(0,deadline-time.monotonic())));delay=min(delay*1.7,.5)

def progress(text):
    atomic_bytes(ROOT/'reports/TRAINING_PROGRESS.md',text.encode('utf-8'))
