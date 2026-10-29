"""Shared read-only R129 model/readers; this round varies only output retention."""
import sys,os,json,time,datetime,hashlib
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent.parent;R131=ROOT.parent/'R131_RecurrentStepValidation'
sys.path.insert(0,str(R131/'scripts'))
import study as base
import numpy as np,pandas as pd,cv2,torch
from scipy.io import loadmat
PLAN=base.PLAN;PKG=base.PKG;OLD=base.OLD
load,save,sha,rec,now,status=base.load,base.save,base.sha,base.rec,base.now,base.status
WIDTHS=[80,64,32,16,0]

def blend(raw,pred,width):
    if width==0:return pred.copy()
    h,w=raw.shape;yy,xx=np.mgrid[:h,:w];d=np.minimum.reduce([yy,xx,h-1-yy,w-1-xx]).astype(np.float32)
    weight=np.clip((d-width)/16,0,1)
    return raw+(pred-raw)*weight

def write_image(p,a):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);image=np.rint(a*255).clip(0,255).astype(np.uint8)
    ok,b=cv2.imencode('.png',image);assert ok
    with p.open('xb') as f:f.write(b.tobytes())
    assert np.array_equal(cv2.imread(str(p),0),image)
    return rec(p)

def verify():
    base.verify_sources()
    for r in load(ROOT/'config/protocol.json')['sources']:assert sha(str(REPO / r['path']))==r['sha256'],str(REPO / r['path'])

def wait(p):
    while not Path(p).exists():
        if list((ROOT/'results').glob('failure_*.json')):raise RuntimeError('Study failure; retain partial records')
        time.sleep(.5)

def setup():
    for d in ['config','reports','results','runs/launcher_logs']:(ROOT/d).mkdir(parents=True,exist_ok=True)
    sources=[rec(R131/'config/protocol.json'),rec(PKG/'validation/extract_sem.m'),rec(PKG/'validation/sem_reference.mat')]
    for e in [13,14,15]:sources.append(rec(R131/f'results/edge_diagnostic/exposure{e}.npz'))
    sources.append(rec(R131/'results/edge_diagnostic/verified.json'))
    for p in [str(REPO / PLAN['checkpoint']['path']),str(REPO / PLAN['configuration']['path']),str(REPO / PLAN['locked_pairs']['path']),str(REPO / PLAN['adjacent_pairs']['path'])]:sources.append(rec(p))
    protocol=dict(utc=now(),question='Is the fixed80px Raw retention necessary, overly broad, or masking underlying size bias?',widths=WIDTHS,transition=16,zero_means='No retention and no transition: exact pre-guard output',checkpoint=PLAN['checkpoint'],steps=4,training_updates=0,
                  populations=dict(normal_SEM='exposures13/14/15, same36 pillars; outer20 and inner16 from source grid',motion='all201frames; locked120 and all194within-session;3repositionings retained',crop_context='same centralpillar16, left crop measurement-window margins0/16/32/64/96 for each of3 exposures; original fullfield reference retained'),
                  crop_limit='Crop tests change actual FOV and therefore global optical/quality statistics too; they test operational context sensitivity, not only neural padding. No independent new physical sample.',
                  metrics=['same fineSEM+signed size and centered shape','same LSC+worst pairs and source-defined edge windows','same-object cropped-vs-full appearance andSEM'],
                  decision='No composite score or invented application tolerance. Prefer complete object treatment; do not declare all pixel borders safe from pillars tens of pixels inside. Existing model unchanged until evidence interpreted. Report all tradeoffs.',
                  required=dict(whole_SEM_rows=540,crop_SEM_rows=75,motion_centers=9045,frames_per_width=201),sources=sources)
    save(ROOT/'config/protocol.json',protocol)
    (ROOT/'README.md').write_text('# R132 邊緣保護研究\n\n共享主線；固定R129四次與同一權重。比較80、64、32、16像素保留帶及完全不保留，非零寬度皆16像素過渡。完整201張與正常SEM；另做同一中央柱體不同邊距的裁切實測。沒有訓練、複製訓練資料或更換原模型。分支codex/r132-boundary-policy。\n',encoding='utf-8')
    (ROOT/'MANIFEST.md').write_text('# R132 Manifest\n\nShared-mainline. Reuse verified pre-guard float reconstructions read-only, preserve original imagery/weights/reports. New alternative PNGs, numerical readouts and context probes remain here;8GiB budget, no automatic deletion. External messages/PRs not part of this local study.\n',encoding='utf-8')
    (ROOT/'results/README.md').write_text('# Results\n\nimages:201fields at5policies;sem_cases:whole-field and cropped-context SEM inputs;measurements:lockedLSC points;all_sem:fixedSEM readout;context:cropped-view probes;failures retained. Pre-guard is the already anchored final model output, not an intermediate latent image.\n',encoding='utf-8')
    (ROOT/'reports/R132_METHODOLOGY.md').write_text('# R132 固定方法\n\n```json\n'+json.dumps({k:v for k,v in protocol.items() if k!='sources'},ensure_ascii=False,indent=2)+'\n```\n\n舊80像素版本必須逐像素重現；原模型不改。中央16與外圍20是來源位置分組，均不能替換36顆主結果。失敗保留；裁切測試若不足以支持最外側安全，必須明列。\n',encoding='utf-8')
    reg=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';v=load(reg);save(ROOT/'config/storage_before.json',v);assert not any(r.get('id')=='r132_boundary_policy' for r in v['entries'])
    v['entries'].append(dict(id='r132_boundary_policy',path=ROOT.relative_to(REPO).as_posix(),tier='active',state='frozen_guard_study',budget_gib=8,action='protect',priority=0,keep='All guard comparisons and context tests; source float data referenced without duplication; no old overwrite.',blocked_by=[]));reg.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    status(ROOT/'runs/launcher_logs/active_formal_run.json',dict(status='prepared',training=False,frames=201,widths=WIDTHS))
    print('R132 protocol fixed',flush=True)

if __name__=='__main__':setup()
