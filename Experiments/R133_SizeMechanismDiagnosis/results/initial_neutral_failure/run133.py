from common133 import *
import argparse,traceback

def metrics(image,target):
    r=image-target
    return dict(mae_gray=float(abs(r).mean()*255),gradient_error_gray=float((abs(np.diff(r,axis=-1)).mean()+abs(np.diff(r,axis=-2)).mean())*127.5),change_sign_mean_gray=float(r.mean()*255))

def generated(model):
    from data import Bank
    bank=Bank();out=ROOT/'results/generated';out.mkdir(exist_ok=False);rows=[];activity=[];start=time.perf_counter()
    for i in range(128):
        b=bank.batch('test',i,'cuda');lo,hi=b['core'];target=b['target'][:,:,lo:hi,lo:hi].cpu().numpy()[:,0]
        with torch.no_grad():arms,info=outputs(model,b['source'])
        arrays=dict(target=target,source=b['source'][:,:,lo:hi,lo:hi].cpu().numpy()[:,0])
        for arm,value in arms.items():
            arr=value[:,:,lo:hi,lo:hi].cpu().numpy()[:,0];arrays[arm]=arr
            for view in range(2):rows.append(dict(parent=i,view=view,category=b['metadata']['category'],arm=arm,**metrics(arr[view],target[view])))
        np.savez_compressed(out/f'parent_{i:03d}.npz',**arrays);activity.append(dict(parent=i,**info))
        if i%16==0:print('generated',i+1,'/128',round(time.perf_counter()-start,1),flush=True)
    pd.DataFrame(rows).to_csv(out/'metrics.csv',index=False);save(out/'activity.json',activity)
    save(out/'complete.json',dict(parents=128,views=256,rows=len(rows),source=rec(__file__),seconds=time.perf_counter()-start))

def controls(model):
    out=ROOT/'results/controls';out.mkdir(exist_ok=False);rows=[];points={};activity=[];convergence=[];start=time.perf_counter()
    for case in load(ROOT/'config/protocol.json')['controls']:
        target,source,coverage=render(case);x=torch.from_numpy(source.astype(np.float32)/255)[None,None].cuda()
        with torch.no_grad():arms,info=outputs(model,x)
        arrays={arm:v[0,0].cpu().numpy() for arm,v in arms.items()};arrays['Target']=target;arrays['coverage']=coverage.astype(np.float32)
        np.savez_compressed(out/f'case_{case["id"]:03d}.npz',**arrays);mask=coverage>=.5;center=(127.5+case['phase'],127.5+case['phase']);radius=case['radius']
        for arm in ['Target',*ARMS]:
            # All arms use the same 8bit export and known coarse mask. The target
            # is measured too: reader bias must not be called a network error.
            image=np.rint(arrays[arm]*255).clip(0,255).astype(np.uint8)
            result=core.measure_boundary_and_circles(image,center,radius,coarse_mask=mask,sample_count=144,normal_half_width_px=3.,polarity=case['polarity'])
            c=result.circles.lsc;points[f'{case["id"]}_{arm}']=result.inflection_points_xy
            rows.append(dict(**case,arm=arm,cx=c.cx,cy=c.cy,fitted_radius=c.radius,diameter_bias_px=float(2*(c.radius-radius)),center_error_px=float(np.hypot(c.cx-center[0],c.cy-center[1])),**metrics(arrays[arm],target)))
        activity.append(dict(id=case['id'],**info))
        if case['contrast']=='normal' and case['polarity']=='dark' and case['phase']==.35 and case['sigma'] in [0.,4.]:
            t16,s16,c16=render(case,16)
            for label,image,coarse8 in [('target',np.rint(t16*255).astype(np.uint8),mask),('source',s16,mask)]:
                result=core.measure_boundary_and_circles(image,center,radius,coarse_mask=coarse8,sample_count=144,normal_half_width_px=3.,polarity='dark');r8=next(r for r in rows if r['id']==case['id'] and r['arm']==('Target' if label=='target' else 'Raw'))
                convergence.append(dict(id=case['id'],label=label,diameter_readout_16_minus8_px=float(2*(result.circles.lsc.radius-r8['fitted_radius'])),area_8_error_px2=float(coverage.sum()-np.pi*radius*radius),area16_error_px2=float(c16.sum()-np.pi*radius*radius)))
        if case['id']%8==0:print('controls',case['id']+1,'/64',round(time.perf_counter()-start,1),flush=True)
    t=pd.DataFrame(rows);ref=t[t.arm=='Target'][['id','fitted_radius']].rename(columns={'fitted_radius':'target_readout_radius'});t=t.merge(ref,on='id',validate='many_to_one');t['diameter_change_vs_clean_readout_px']=2*(t.fitted_radius-t.target_readout_radius)
    t.to_csv(out/'measurements.csv',index=False);np.savez_compressed(out/'points.npz',**points);save(out/'activity.json',activity);pd.DataFrame(convergence).to_csv(out/'render_convergence.csv',index=False)
    save(out/'complete.json',dict(cases=64,rows=len(rows),render_convergence_rows=len(convergence),source=rec(__file__),seconds=time.perf_counter()-start))

def real(model):
    out=ROOT/'results/real';out.mkdir(exist_ok=False);cases=[];activity=[]
    for exposure in [13,14,15]:
        raw,x=base.tensor(PKG/f'validation/inputs/sem{exposure}.png')
        with torch.no_grad():arms,info=outputs(model,x)
        for arm,value in arms.items():
            arr=previous.blend(raw.astype(np.float32)/255,value[0,0].cpu().numpy(),16)
            path=out/f'{arm}/sem{exposure}.png';written=previous.write_image(path,arr)
            if arm=='Final':assert np.array_equal(cv2.imread(str(path),0),cv2.imread(str(R132/f'results/sem_cases/full_e{exposure}_W16.png'),0))
            np.save(path.with_suffix('.npy'),arr);cases.append(dict(arm=arm,exposure=exposure,image=written))
        activity.append(dict(exposure=exposure,**info));print('real',exposure,flush=True)
    save(out/'cases.json',dict(cases=cases,activity=activity));save(out/'inference_complete.json',dict(cases=len(cases),oldFinal_W16_exact=True))

def main():
    verify();model=base.model();digest=base.runtime.state_digest(model)
    # Verify the proposed neutral output contract without changing the old model.
    rows=[]
    with torch.no_grad():
        for name,x in [('random',torch.rand(1,1,193,201,device='cuda')),('constant',torch.full((1,1,193,201),.5,device='cuda'))]:
            old=model.anchor(x,x)[0];new=model.anchor(x,x-x)[0]
            assert torch.equal(new,x);rows.append(dict(input=name,old_mean_change_gray=float(abs(old-x).mean()*255),old_max_change_gray=float(abs(old-x).max()*255),new_exact_identity=True))
    save(ROOT/'results/neutral_contract.json',dict(rows=rows,meaning='Supplied neural=raw; output operator test, not trained-model performance'))
    real(model);generated(model);controls(model)
    assert base.runtime.state_digest(model)==digest;verify();save(ROOT/'results/inference_complete.json',dict(utc=now(),all_studies_complete=True,weights_unchanged=True));print('All frozen diagnoses executed',flush=True)

if __name__=='__main__':
    try:main()
    except BaseException:
        save(ROOT/f'results/failure_run_{time.time_ns()}.json',dict(error=traceback.format_exc(),utc=now()));raise
