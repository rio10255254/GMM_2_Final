"""Frozen diagnostic arms, explicit output contracts, original R129 untouched."""
from pathlib import Path
import sys,os,ast,json,time,itertools,copy
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent.parent
R132=ROOT.parent/'R132_BoundaryPolicyStudy';sys.path.insert(0,str(R132/'scripts'))
import common132 as previous
base=previous.base;PKG=previous.PKG;PLAN=previous.PLAN;R131=previous.R131
load,save,sha,rec,now,status=previous.load,previous.save,previous.sha,previous.rec,previous.now,previous.status
import numpy as np,pandas as pd,torch,cv2
from scipy.ndimage import gaussian_filter
from scipy.io import loadmat
ARMS=['Raw','Optics','Neural','Final','NoOptics','ResidualHP','DirectResidual','MatchedHP','MatchedDirect']
from validation import reference_circle_core as core
from validation.readout_helpers import mask_center_radius,radial_signature

def corrected_output(model,raw,neural,quality,highpass=True):
    difference=neural-raw
    if highpass:
        k=model.anchor_kernel;F=torch.nn.functional
        low=F.conv2d(torch.cat([difference[...,1:7].flip(-1),difference,difference[...,-7:-1].flip(-1)],-1),k[None,None,None,:])
        low=F.conv2d(torch.cat([low[...,1:7,:].flip(-2),low,low[...,-7:-1,:].flip(-2)],-2),k[None,None,:,None]);difference=difference-low
    correction=.35*(.78+.3*quality[:,None,None,None])*difference
    correction=correction-correction.mean((2,3),keepdim=True)
    return (raw+correction).clamp(0,1)

def outputs(model,raw):
    detail=model.forward_details(raw,trace=True);neural=detail.neural;final=detail.output
    optics,_=model.optics(raw,True,False)
    noopt=model.anchor(raw,model.backbone(raw)[0])[0]
    residual_hp=corrected_output(model,raw,neural,detail.quality,True)
    gain=.35*(.78+.3*detail.quality[:,None,None,None])
    direct=corrected_output(model,raw,neural,detail.quality,False)
    def matched(target):
        old=final-raw;new=target-raw
        alpha=(new.square().mean((1,2,3))/(old.square().mean((1,2,3))+1e-20)).sqrt()
        value=(raw+alpha[:,None,None,None]*old).clamp(0,1)
        ratio=((value-raw).square().mean((1,2,3))/(new.square().mean((1,2,3))+1e-20)).sqrt()
        return value,alpha,ratio
    mh,ah,rh=matched(residual_hp);md,ad,rd=matched(direct)
    return dict(zip(ARMS,[raw,optics,neural,final,noopt,residual_hp,direct,mh,md])),dict(gain= gain.flatten().tolist(),matched_hp_alpha=ah.tolist(),matched_hp_rms_ratio=rh.tolist(),matched_direct_alpha=ad.tolist(),matched_direct_rms_ratio=rd.tolist())

def verify():
    previous.verify()
    for r in load(ROOT/'config/protocol.json')['sources']:assert sha(r['path'])==r['sha256'],r['path']

def disk_coverage(radius,phase,ss=8,n=256):
    # Same area-overlap quadrature as repaired R122, translated to a centered disk.
    axis=(np.arange(n*ss)+.5)/ss-.5;xx=axis[None,:];yy=axis[:,None];center=(n-1)/2+phase;half=.5/ss
    inside=np.zeros((n*ss,n*ss),np.float64);nodes,weights=np.polynomial.legendre.leggauss(4)
    for node,weight in zip(nodes,weights):
        y=yy+node*half-center;extent=np.sqrt(np.maximum(radius*radius-y*y,0));left,right=center-extent,center+extent
        overlap=np.maximum(0,np.minimum(xx+half,right)-np.maximum(xx-half,left))*ss
        inside+=weight*.5*overlap*(abs(y)<=radius)
    return inside

def render(case,ss=8):
    n=256;inside=disk_coverage(case['radius'],case['phase'],ss,n)
    low,high=(.2,.8) if case['contrast']=='normal' else (.4,.52)
    target=low+(high-low)*(1-inside if case['polarity']=='dark' else inside)
    source=gaussian_filter(target,case['sigma']*ss,mode='reflect',truncate=5) if case['sigma'] else target.copy()
    target=target.reshape(n,ss,n,ss).mean((1,3));source=source.reshape(n,ss,n,ss).mean((1,3));coverage=inside.reshape(n,ss,n,ss).mean((1,3))
    return target.astype(np.float32),np.rint(source*255).clip(0,255).astype(np.uint8),coverage

def setup():
    for d in ['config','reports','results','runs/launcher_logs']:(ROOT/d).mkdir(parents=True,exist_ok=True)
    sources=[rec(PKG/p) for p in ['engine.py','data.py','config/training.json','training_data/manifest.json','model/output_policy.py','model/hybrid.py']]
    sources+=[rec(ROOT.parent/'R128_SourceOnlyFullTraining/data/generator.py'),rec(ROOT.parent/'R122_OperatorPrinciples/scripts/physical_fit_area.py')]
    cases=[dict(id=i,radius=r,sigma=s,contrast=c,polarity=p,phase=f) for i,(r,s,c,p,f) in enumerate(itertools.product([24.,40.],[0.,1.,2.2,4.],['normal','low'],['dark','bright'],[0.,.35]))]
    protocol=dict(utc=now(),question='Does frozenR129 enlarge known geometry, and which pipeline stage changes size?',arms=ARMS,controls=cases,sources=sources,
                  evaluations=dict(existing_generated_test='All128parents/256views, nativeimage/gradient error bycategory; no generic shape metric inferred from imageMAE',physical_controls='64 area-rendered disks with knownradius, zero-noise apartfrom8bitquantization;16/8render sensitivity subset',real='Three normalSEMfields all36objects eacharm, same16/16guard; primaryFinalreproduceR132'),
                  readout='Same fine-boundary/circle method as realSEM; controls use known common coarse material mask to isolate readout. Report true-radius and clean-target-reader errors separately; not a deployable oracle.',
                  attribution='Frozen co-adapted checkpoint interventions, not matched retrained architecture. RMSmatched original-output controls are input-only and postclip mismatch is reported.',
                  output_contract='ResidualHP injects HP(neural-raw), DirectResidual uses neural-raw with samegain andglobalmean; both neutral whenneural=raw. Neither frozen change is automatically adopted.',
                  required=['all128generatedparents','all64controlledcases withtruth/Target/9arms','normalSEM3x36x9','identity/output/lossfixtures','independent readout recomputation','concrete next architecture/data/training plan'],
                  no_training=True,no_old_confirmation_access=True,model_promotion=False)
    save(ROOT/'config/protocol.json',protocol)
    (ROOT/'README.md').write_text('# R133 尺寸偏差底層診斷\n\n固定R129，檢查既有合成測試、已知尺寸控制，以及真實SEM。拆開光學、網路與最後輸出，另以修正強度匹配避免混淆。沒有訓練或修改原模型。分支codex/r133-size-mechanisms。\n',encoding='utf-8')
    (ROOT/'MANIFEST.md').write_text('# R133 Manifest\n\nShared-mainline diagnostic. Original weights/data/SEM references read-only. New controlled disks are evaluation-only, not a new sealedholdout. Budget4GiB; preserve all failing/numerical cases and intervention results. No external messages or training launcher.\n',encoding='utf-8')
    (ROOT/'results/README.md').write_text('# Outputs\n\ncontrols:known-shape diagnostics;generated:all128existingheldparents;real:unchangedreadoutSEM;contract:neutral andgeometry objective checks. No change tooldreceipts or modeldefaults.\n',encoding='utf-8')
    (ROOT/'reports/R133_METHODOLOGY.md').write_text('# R133 固定設計\n\n```json\n'+json.dumps({k:v for k,v in protocol.items() if k not in ['sources','controls']},ensure_ascii=False,indent=2)+'\n```\n\n合成控制的已知遮罩只供共同量測初始化，不提供給模型；區分相對材料幾何與相對乾淨影像讀法的誤差。每種固定權重介入不是從頭訓練的替代架構。\n',encoding='utf-8')
    reg=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';v=load(reg);save(ROOT/'config/storage_before.json',v);assert not any(x.get('id')=='r133_size_mechanism' for x in v['entries']);v['entries'].append(dict(id='r133_size_mechanism',path=ROOT.relative_to(REPO).as_posix(),tier='active',state='mechanism_diagnosis',budget_gib=4,action='protect',priority=0,keep='Frozen interventions, synthetictruth, realSEM, allfailures; no originalchanges',blocked_by=[]));reg.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    status(ROOT/'runs/launcher_logs/active_formal_run.json',dict(status='prepared',training=False,controls=64,generated_parents=128,real_SEM_rows=972));print('R133 protocol fixed',flush=True)
if __name__=='__main__':setup()
