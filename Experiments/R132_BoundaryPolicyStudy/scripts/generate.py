"""Reuse stored full-field pre-guard values; generate separately bounded crop tests."""
from common132 import *
import traceback,argparse

def fields():
    verify();records=[];start=time.perf_counter()
    for j,f in enumerate(PLAN['frames']):
        case=f"{f['sequence']}/frame_{f['frame_index']:04d}";oldrec=OLD/'images'/case/'record.json';r=load(oldrec)
        for k in ['source','output_float','image']:assert sha(r[k]['path'])==r[k]['sha256']
        a=np.load(r['output_float']['path']);pred=a['neural_output'];original=a['output'];raw=cv2.imread(r['source']['path'],0).astype(np.float32)/255
        assert pred.shape==raw.shape and np.isfinite(pred).all();out=[]
        for width in WIDTHS:
            value=blend(raw,pred,width)
            if width==80:assert np.array_equal(value,original),case
            p=ROOT/f'results/images/W{width}'/(case+'.png');im=write_image(p,value);out.append(dict(width=width,**im))
            if width==80:assert np.array_equal(cv2.imread(str(p),0),cv2.imread(r['image']['path'],0))
        record=dict(**f,source_record=rec(oldrec),pre_guard=r['output_float'],outputs=out);save(ROOT/'results/records'/(case+'.json'),record);records.append(record)
        status(ROOT/'results/generation_status.json',dict(status='running',frames=j+1,total=201,seconds=time.perf_counter()-start))
        if j%25==0:print('fields',j+1,'/201',round(time.perf_counter()-start,1),flush=True)
    save(ROOT/'results/generation_complete.json',dict(frames=201,outputs=1005,old80_float_and_PNG_exact=True,records=records,source=rec(__file__)))
    status(ROOT/'results/generation_status.json',dict(status='complete',frames=201,total=201));verify()

def contexts():
    verify();m=base.model();digest=base.runtime.state_digest(m);ref=loadmat(PKG/'validation/sem_reference.mat',variable_names=['global_index','opt_centers']);grid=ref['global_index'];centers=ref['opt_centers'];cases=[];stats=[]
    # One current full-field replay verifies the saved pre-guard semantics before reuse.
    f=PLAN['frames'][0];r=load(OLD/f"images/{f['sequence']}/frame_{f['frame_index']:04d}/record.json");raw,x=base.tensor(f['source']['path'])
    with torch.no_grad():p=base.original_predict(m,x)[0,0].cpu().numpy()
    old=np.load(r['output_float']['path'])['neural_output'];assert float(abs(p-old).max())<1e-6
    save(ROOT/'results/current_forward_verified.json',dict(source=f['source'],old=r['output_float'],max_abs=float(abs(p-old).max()),pre_guard_semantics='already anchored final output beforeFOVretention'))
    gy,gx=np.argwhere(grid==16)[0];cx,cy=centers[int(gy)*6+int(gx)];anchor_x=int(np.floor(cx+.5))-1;anchor_y=int(np.floor(cy+.5))-1
    for e in [13,14,15]:
        data=np.load(R131/f'results/edge_diagnostic/exposure{e}.npz');raw=data['raw'];pred=data['pre_guard'];native=raw.astype(np.float32)/255
        for width in WIDTHS:
            name=f'full_e{e}_W{width}';im=write_image(ROOT/f'results/sem_cases/{name}.png',blend(native,pred,width))
            cases.append(dict(name=name,scope='full',exposure=e,width=width,image=im,origin_x=0,origin_y=0,pillars=[int(v) for v in grid.ravel()],margin=-1))
        for margin in [0,16,32,64,96]:
            x0=anchor_x-52-margin;cropped=raw[:,x0:];x=torch.from_numpy(cropped.astype(np.float32)/255)[None,None].cuda()
            with torch.no_grad():part=base.original_predict(m,x)[0,0].cpu().numpy()
            sl=np.s_[anchor_y-52:anchor_y+52,anchor_x-x0-52:anchor_x-x0+52]
            reference=pred[:,x0:];rawf=cropped.astype(np.float32)/255
            np.savez_compressed(ROOT/f'results/context/e{e}_m{margin}.npz',pre_guard=part,full_reference=reference,raw=cropped,origin_x=x0)
            for width in WIDTHS:
                name=f'crop_e{e}_m{margin}_W{width}';value=blend(rawf,part,width);im=write_image(ROOT/f'results/sem_cases/{name}.png',value)
                cases.append(dict(name=name,scope='crop',exposure=e,width=width,image=im,origin_x=x0,origin_y=0,pillars=[16],margin=margin))
                stats.append(dict(exposure=e,margin=margin,width=width,pre_guard_vs_full_mean_gray=float(abs(part[sl]-reference[sl]).mean()*255),pre_guard_vs_full_max_gray=float(abs(part[sl]-reference[sl]).max()*255),output_vs_full_mean_gray=float(abs(value[sl]-reference[sl]).mean()*255),model_change_mean_gray=float(abs(value[sl]-rawf[sl]).mean()*255)))
            print('context',e,margin,flush=True)
    assert base.runtime.state_digest(m)==digest;verify();pd.DataFrame(stats).to_csv(ROOT/'results/context/differences.csv',index=False)
    save(ROOT/'results/sem_cases.json',dict(cases=cases,full_expected_rows=540,crop_expected_rows=75,source=rec(__file__)))
    save(ROOT/'results/context_complete.json',dict(exposures=3,margins=5,cropped_forwards=15,SEM_cases=len(cases),weights_unchanged=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['fields','contexts']);a=p.parse_args();(ROOT/'results/context').mkdir(parents=True,exist_ok=True)
    try:fields() if a.mode=='fields' else contexts()
    except BaseException:
        save(ROOT/f'results/failure_{a.mode}_{time.time_ns()}.json',dict(error=traceback.format_exc(),utc=now()));raise
