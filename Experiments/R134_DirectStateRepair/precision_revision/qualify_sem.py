from common import *
from precision_io import write_values,read_values
from sem_metrics import score
from scipy.io import savemat,loadmat
import cv2,pandas as pd,subprocess,traceback
def main():
    out=P/'results/sem';out.mkdir(exist_ok=False);protected();tables=[];allrecords=[]
    save(out/'started.json',dict(utc=now(),pid=os.getpid(),sources=[record(P/n) for n in ['qualify_sem.py','sem_metrics.py','precision_io.py','common.py','validation/extract_sem_precise.m','validation/sem_reference.mat','config/protocol.json']]))
    for tag in ['Raw','A_s1342001','C_s1342001','A_s1342002','C_s1342002']:
        d=out/tag;d.mkdir();m=None
        if tag!='Raw':
            arm,seed=tag.split('_s');seed=int(seed);cp=E/f'runs/R134_{arm}_s{seed}/step0512.pth';m=create(arm,seed);m.load_state_dict(torch.load(cp,map_location='cpu')['model']);m.eval()
        for e in [13,14,15]:
            source=E/f'validation/inputs/sem{e}.png';raw8=cv2.imread(str(source),0)
            if m is None:value=raw8.astype(float)/255
            else:
                x=torch.from_numpy(raw8.astype(np.float32)/255)[None,None].cuda()
                # Match the original R134 SEM probe's16pixel guard exactly.
                h,w=x.shape[-2:];yy=torch.arange(h,device=x.device)[:,None];xx=torch.arange(w,device=x.device)[None,:];dd=torch.minimum(torch.minimum(yy,h-1-yy),torch.minimum(xx,w-1-xx));weight=((dd-16)/16).clamp(0,1)
                with torch.no_grad():value=(x+(m(x)-x)*weight)[0,0].cpu().numpy()
                old=E/f'results/real/{tag}_p0512/sem{e}.npy';assert np.array_equal(value,np.load(old,allow_pickle=False));path,preview,high=write_values(d,f'sem{e}',value);value=read_values(path);allrecords.append(dict(tag=tag,exposure=e,checkpoint=record(cp),values=record(path),previous_values=record(old),exact_replay=True))
            savemat(d/f'sem{e}_values.mat',dict(image=value));loaded=loadmat(d/f'sem{e}_values.mat')['image'];assert np.array_equal(value,loaded)
        if m is not None:del m;torch.cuda.empty_cache()
        command=f"addpath('{(P/'validation').as_posix()}');extract_sem_precise('{d.as_posix()}');"
        with (d/'matlab.log').open('xb') as f:r=subprocess.run([r'C:\Program Files\MATLAB\R2025b\bin\matlab.exe','-batch',command],stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode:raise RuntimeError('SEM extraction failed: '+str(d/'matlab.log'))
        t,p,summary=score(d/'sem_masks.mat',P/'validation/sem_reference.mat');t['method']=tag;t.to_csv(d/'measurements.csv',index=False);np.savez_compressed(d/'points.npz',**p);save(d/'complete.json',summary);tables.append(t);print('Precision SEM',tag,summary['summary'],flush=True)
    t=pd.concat(tables);t.to_csv(out/'all_measurements.csv',index=False);checks=[];dev=pd.read_csv(E/'results/development_summary.csv')
    for seed in [1342001,1342002]:
        a=t[t.method==f'A_s{seed}'].set_index(['pillar','exposure']);c=t[t.method==f'C_s{seed}'].set_index(['pillar','exposure']);raw=t[t.method=='Raw'].set_index(['pillar','exposure']);useful=[];flags=[]
        for key in ['diameter_error_nm','centered_shape_nm']:
            relative=float((c[key]-a[key]).groupby('pillar').median().median()/a[key].groupby('pillar').median().median());rawrelative=float((c[key]-raw[key]).groupby('pillar').median().median()/raw[key].groupby('pillar').median().median());useful.append(relative<=-.05);flags.extend([relative<=.02,rawrelative<=.02]);checks.append(dict(seed=seed,metric=key,paired_relative_change_vsA=relative,paired_relative_change_vsRaw=rawrelative,passed=relative<=.02 and rawrelative<=.02))
        d=dev[(dev.arm=='C')&(dev.seed==seed)].iloc[0];flags.extend([any(useful),d.dev_mae_gray<d.Raw_dev_mae_gray,d.clean_identity_mae_gray<=1]);checks.append(dict(seed=seed,metric='stage1_all',passed=all(flags),useful_SEM_gain=any(useful),generated_validation_unchanged=True))
    protected();save(out/'complete.json',dict(passed=all(r['passed'] for r in checks),checks=checks,rows=len(t),groups=5,independent_refits=540,original_float_replays=12,records=allrecords,sources=load(out/'started.json')['sources']));print('Precision SEM qualification',all(r['passed'] for r in checks),flush=True)
if __name__=='__main__':
    try:main()
    except BaseException:
        save(P/'results/sem_failure.json',dict(error=traceback.format_exc(),utc=now()));raise
