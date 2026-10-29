"""Frozen R129 prefix experiment. No optimizer, source edits or training."""
import os,sys,json,hashlib,datetime,time
from pathlib import Path
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]; REPO=ROOT.parent.parent
R129=ROOT.parent/'R129_OpticalPriorHybrid'
OLD=R129/'results/continuous_lsc'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def rec(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False)
def status(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    for attempt in range(20):
        try:
            temp=p.with_suffix('.writing');temp.write_text(json.dumps(v,ensure_ascii=False),encoding='utf-8');os.replace(temp,p);return
        except PermissionError:time.sleep(.1)
    raise RuntimeError('status write remained locked')
PLAN=load(OLD/'plan.json'); PKG=Path(REPO / PLAN['package'])
sys.path.insert(0,str(R129/'scripts'))
from sequence_inference import tiled_prior,predict as original_predict
from continuous_common import reader
sys.path.insert(0,str(PKG))
import runtime,torch,numpy as np,pandas as pd,cv2
from torch.nn import functional as F
from model.inference_policy import guard

def model():
    runtime.setup(1319001)
    p=torch.load(str(REPO / PLAN['checkpoint']['path']),map_location='cpu');runtime.verify_binding(p['binding'])
    m,_=runtime.create('cuda');m.load_state_dict(p['model'],strict=True);m.eval()
    return m

def prefixes(m,raw,maximum=4,core=512):
    """Same computations as original predict; final output policy after each prefix.
    Intermediate anchored outputs NEVER become recurrent inputs.
    """
    assert 0<=maximum<=4
    conditioned,_=m.optics(raw,True,False)
    lift=lambda x,f:x.repeat_interleave(f,-2).repeat_interleave(f,-1)
    original=lift(conditioned,4);o2=lift(conditioned,2);state=original
    p=torch.cat([conditioned[...,:1],conditioned,conditioned[...,-1:]],-1)
    p=torch.cat([p[...,:1,:],p,p[...,-1:,:]],-2)
    dx=(p[...,1:-1,2:]-p[...,1:-1,:-2])*.5
    dy=(p[...,2:,1:-1]-p[...,:-2,1:-1])*.5
    lap=p[...,1:-1,2:]+p[...,1:-1,:-2]+p[...,2:,1:-1]+p[...,:-2,1:-1]-4*conditioned
    mean=F.avg_pool2d(conditioned,5,1,2,count_include_pad=False)
    fixed=[lift(v,2) for v in [dx,dy,lap,mean]]
    for n in range(maximum+1):
        if n:
            native=conditioned+F.avg_pool2d(state-original,4)
            features=torch.cat([F.avg_pool2d(state,2),o2,lift(conditioned-native,2),*fixed],1)
            correction=tiled_prior(m.prior,features,core,16)
            state=(state+.25*torch.sigmoid(m.step_logits[n-1])*correction).clamp(0,1)
            del features,correction
        neural=(conditioned+F.avg_pool2d(state-original,4)).clamp(0,1)
        final,_=m.anchor(raw,neural)
        yield n,guard(raw,final)

def tensor(path):
    raw=cv2.imdecode(np.fromfile(path,np.uint8),0)
    assert raw is not None
    return raw,torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()

def verify_sources():
    p=load(ROOT/'config/protocol.json')
    for r in p['protected_sources']:assert sha(str(REPO / r['path']))==r['sha256'],str(REPO / r['path'])

def prepare():
    for name in ('config','reports','results','runs/launcher_logs'):(ROOT/name).mkdir(parents=True,exist_ok=True)
    panel=load(PKG/'validation/panel.json')
    protected={str(Path(REPO / r['path'])):r for r in PLAN['protected_sources']+[PLAN['checkpoint']]}
    for p in [*PKG.glob('model/*.py'),PKG/'runtime.py',PKG/'validation/panel.json',PKG/'validation/sem_reference.mat',PKG/'validation/reference_circle_core.py',PKG/'validation/readout_helpers.py',PKG/'validation/extract_sem.m',R129/'scripts/sequence_inference.py',R129/'scripts/continuous_common.py',R129/'scripts/common.py',OLD/'plan.json',OLD/'comparison_summary.csv']:
        protected[str(p)]=rec(p)
    for image in panel['images']:
        if image['kind']=='sem':protected[str(PKG/image['path'])]=rec(PKG/image['path'])
    protocol=dict(created_utc=now(),question='Does the current frozen four-step R129 benefit from each recurrent step?',
                  design='Frozen prefix n=0,1,2,3,4; identical checkpoint, optics, input-derived features, per-step scalars, final anchor and FOV guard. No retraining; not causal proof of separately trained architecture superiority.',
                  primary=['SEM normal13-15 all36: radial, signed diameter, centered shape, MZC','Same locked120LSC; all194within-session pairs and3repositioning separately','Standalone0-4 runtime on same full image'],
                  sources='Previously used development scenes, never unseen holdout',frames=201,sem_exposures=[13,14,15],steps=[0,1,2,3,4],
                  zero_definition='Skip learned updates; keep optical conditioning and final anchor. Raw is a separate reference.',
                  numerical_tolerance=1e-6,require_four_step_PNG_parity=True,
                  decision='Report all endpoints, paired gains and tradeoffs. Fewer steps are supported for further testing only if primary geometry/motion do not worsen meaningfully; no posthoc composite score or automatic adoption. No application equivalence margin is invented.',
                  completion='Preflight prefix equivalence, all204images*5prefixes,108SEMrows*5,1809LSCcenters*5,all populations, timing, independent saved-point refits and source integrity. Failures retained.',
                  checkpoint=PLAN['checkpoint'],protected_sources=list(protected.values()))
    save(ROOT/'config/protocol.json',protocol)
    (ROOT/'README.md').write_text('# R131 四次修復驗證\n\n共享主線型態。保持 R129 長訓練權重不變，量零至四次修復的真實輪廓、完整連續位移與成本。零次仍保留光學及輸出處理，不等於原圖。此為已訓練模型的使用次數診斷，不是不同次數從零訓練的公平架構比較。原模型與舊結果唯讀。\n\n[固定方法](reports/R131_METHODOLOGY.md)；完成結果另列。分支 codex/r131-recurrent-steps。無訓練啟動器或外部發文。\n',encoding='utf-8')
    (ROOT/'MANIFEST.md').write_text('# R131 Manifest\n\nProfile: shared-mainline; frozen R129 checkpoint and real validation references. No training data copy, optimizer updates or model promotion. Results budget12GiB. New stage PNGs, representative floats, all measured contours, summaries and failure records stay here; no automatic deletion or archival.\n',encoding='utf-8')
    (ROOT/'results/README.md').write_text('# Outputs\n\nsem: all normal real panels at0-4 updates. images: all201nativeframes at0-4 updates. measurements: actualLSCcenters/points. preflight: numerical checks, not model efficacy. All outputs development-only; original sources retained elsewhere. No old confirmation data accessed.\n',encoding='utf-8')
    (ROOT/'reports/R131_METHODOLOGY.md').write_text('# R131 固定比較方法\n\n'+json.dumps({k:v for k,v in protocol.items() if k!='protected_sources'},ensure_ascii=False,indent=2)+'\n\n相同權重依原順序停止；每個中間狀態經相同最終輸出規則，但最終輸出不回灌下一步。這檢驗現有模型的步數收益，不能證明從零訓練一至三步的能力上限。SEM非圓起伏與平均尺寸分開；固定120對與全部194對分開；不以名義平台步距宣稱絕對真值。既有Raw及四步結果必須重現。\n',encoding='utf-8')
    reg=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';v=load(reg);save(ROOT/'config/storage_before.json',v)
    assert not any(r.get('id')=='r131_recurrent_steps' for r in v['entries'])
    v['entries'].append(dict(id='r131_recurrent_steps',path=ROOT.relative_to(REPO).as_posix(),tier='active',state='frozen_prefix_validation',budget_gib=12,action='protect',priority=0,keep='Preserve all step comparisons, failures and source references. No original R129 changes.',blocked_by=[]))
    reg.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    status(ROOT/'runs/launcher_logs/active_formal_run.json',dict(status='prepared',training=False,frames=201,steps=5))
    print('Protocol fixed',len(protected),'protected files',flush=True)

def preflight():
    verify_sources();m=model();before=runtime.state_digest(m);rows=[]
    with torch.no_grad():
        for shape in [(193,201),(221,227)]:
            x=torch.rand(1,1,*shape,device='cuda');out=list(prefixes(m,x,4,128));states=[]
            d=m.forward_details(x,step_observer=lambda i,s:states.append(s))
            cond,_=m.optics(x,True,False);origin=cond.repeat_interleave(4,-2).repeat_interleave(4,-1)
            for n,y in out:
                native=cond if n==0 else (cond+F.avg_pool2d(states[n-1]-origin,4)).clamp(0,1)
                expected=guard(x,m.anchor(x,native)[0]);err=float((y-expected).abs().max());assert err<1e-6
                rows.append(dict(shape=shape,step=n,max_abs=err))
            assert torch.equal(out[-1][1],guard(x,d.output))
        for level in [0.,.5,1.]:
            x=torch.full((1,1,193,197),level,device='cuda')
            for n,y in prefixes(m,x):assert torch.isfinite(y).all() and y.min()>=0 and y.max()<=1
        raw,x=tensor(PKG/'validation/inputs/sem14.png');out=list(prefixes(m,x));old=guard(x,original_predict(m,x))
        assert torch.equal(out[-1][1],old)
    assert runtime.state_digest(m)==before
    save(ROOT/'results/preflight.json',dict(passed=True,prefix_reference_rows=rows,real_four_step_exact=True,constant_inputs_finite=True,weights_unchanged=True,source=rec(__file__)))
    print('Preflight PASS',flush=True)

def infer():
    verify_sources();assert load(ROOT/'results/preflight.json')['passed'];m=model();digest=runtime.state_digest(m)
    cases=[dict(kind='sem',name=f'sem{e}',source=rec(PKG/f'validation/inputs/sem{e}.png')) for e in [13,14,15]]
    cases += [dict(kind='sequence',name=f"{f['sequence']}/frame_{f['frame_index']:04d}",source=f['source'],sequence=f['sequence'],frame_index=f['frame_index']) for f in PLAN['frames']]
    save(ROOT/'results/inference_started.json',dict(utc=now(),pid=os.getpid(),source=rec(__file__),cases=cases,checkpoint=PLAN['checkpoint']))
    start=time.perf_counter();stats=[]
    for j,c in enumerate(cases):
        assert sha(str(REPO / c['source']['path']))==c['source']['sha256'];raw,x=tensor(str(REPO / c['source']['path']));previous=None;images=[]
        with torch.no_grad():
            for n,y in prefixes(m,x):
                value=y[0,0].cpu().numpy();image=np.rint(value*255).clip(0,255).astype(np.uint8)
                p=ROOT/'results'/('sem' if c['kind']=='sem' else 'images')/f'N{n}'/(c['name']+'.png');p.parent.mkdir(parents=True,exist_ok=True)
                ok,b=cv2.imencode('.png',image);assert ok
                with p.open('xb') as f:f.write(b.tobytes())
                assert np.array_equal(cv2.imread(str(p),0),image)
                if n==4 and c['kind']=='sequence':
                    old=load(OLD/'images'/c['name']/'record.json')['image'];assert sha(old['path'])==old['sha256']
                    assert np.array_equal(image,cv2.imread(old['path'],0)),c['name']
                if c['kind']=='sem' or j==3:
                    np.save(p.with_suffix('.npy'),value)
                stats.append(dict(case=c['name'],kind=c['kind'],step=n,mean_change_gray=float(np.abs(value-raw.astype(np.float32)/255).mean()*255),increment_gray=0. if previous is None else float(np.abs(value-previous).mean()*255),saturated_fraction=float(((value==0)|(value==1)).mean())))
                previous=value.copy();images.append(dict(step=n,**rec(p)))
        rp=ROOT/'results/records'/(c['name']+'.json');save(rp,dict(**c,images=images))
        status(ROOT/'results/inference_status.json',dict(status='running',finished=j+1,total=len(cases),elapsed_seconds=time.perf_counter()-start,pid=os.getpid()))
        if j<4 or j%10==0:print('inference',j+1,'/',len(cases),round(time.perf_counter()-start,1),'s',flush=True)
    pd.DataFrame(stats).to_csv(ROOT/'results/stage_changes.csv',index=False)
    assert runtime.state_digest(m)==digest;verify_sources()
    save(ROOT/'results/inference_complete.json',dict(cases=len(cases),images=len(cases)*5,four_step_old_PNG_parity_frames=201,weights_unchanged=True,seconds=time.perf_counter()-start))
    status(ROOT/'results/inference_status.json',dict(status='complete',finished=len(cases),total=len(cases)))

if __name__=='__main__':
    import argparse,traceback
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','preflight','infer']);a=p.parse_args()
    try:globals()[a.mode]()
    except BaseException:
        if a.mode!='prepare':save(ROOT/f'results/failure_{a.mode}_{time.time_ns()}.json',dict(error=traceback.format_exc(),utc=now()))
        raise
