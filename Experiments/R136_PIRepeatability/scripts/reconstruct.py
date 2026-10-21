from common import *
import argparse,time,traceback,shutil
import cv2,numpy as np,torch

def setup():
    torch.set_num_threads(4);torch.manual_seed(136001)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.use_deterministic_algorithms(True)

def build(tag,plan):
    setup();info=plan['models'][tag];cp=Path(info['checkpoint']['path'])
    assert sha(cp)==info['checkpoint']['sha256']
    if tag=='R61':
        path=Path(info['command'][1]);sys.path.insert(0,str(path.parent));mod=module('r136_r61_infer',path);captured={}
        class Captured(BaseException):pass
        original=mod.run_one
        def capture(model,device,in_path,out_path,align_factor,**kw):
            captured.update(model=model,align=align_factor,options=kw);raise Captured()
        mod.run_one=capture;args=info['command'][1:].copy()
        for opt,val in [('--input-dir',str(Path(plan['frames'][0]['source']['path']).parent)),('--recon-root',str(ROOT/'results/R61/loader')),('--output-name','loader')]:args[args.index(opt)+1]=val
        old=sys.argv;sys.argv=args
        try:mod.main()
        except Captured:pass
        finally:sys.argv=old;mod.run_one=original
        model=captured['model']
        def predict(raw):
            x=raw.astype(np.float32)/255;p,h,w=mod.pad_to_multiple_np(x,captured['align'])
            with torch.inference_mode():return model(torch.from_numpy(p)[None,None].cuda()).clamp(0,1)[0,0,:h,:w].cpu().numpy()
        def native_verify(raw_path,value):
            taps=[];denorm=mod.denormalize_to_dtype
            def tap(v,dtype):taps.append(v.copy());return denorm(v,dtype)
            mod.denormalize_to_dtype=tap
            try:original(model,torch.device('cuda'),Path(raw_path),ROOT/'results/R61/native_probe.png',captured['align'],**captured['options'])
            finally:mod.denormalize_to_dtype=denorm
            assert np.array_equal(taps[0],value)
            return dict(native_output_exact=True,loader=record(path))
    elif tag=='R128':
        directory=REPO/'Experiments/R128_SourceOnlyFullTraining';sys.path.insert(0,str(directory));import importlib
        net=importlib.import_module('model.network');payload=torch.load(cp,map_location='cpu');model=net.Model(payload['model_config']).cuda();model.load_state_dict(payload['model'],strict=True);model.eval()
        tile=module('r136_r128_tiling',REPO/'Experiments/R124_RealFirstPrototype/inference/tiling.py')
        def predict(raw):
            x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
            with torch.inference_mode():v=tile.tiled_forward(model,x,core=256,halo=model.required_halo);return net.boundary_guard(x,v,model.required_halo,16)[0][0,0].cpu().numpy()
        def native_verify(raw_path,value):
            raw=cv2.imread(str(raw_path),0);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
            with torch.inference_mode():v=tile.tiled_forward(model,x,core=320,halo=model.required_halo);v=net.boundary_guard(x,v,model.required_halo,16)[0][0,0].cpu().numpy()
            error=float(np.max(np.abs(v-value)));assert error<1e-6
            return dict(alternate_core_max_abs_error=error,required_halo=model.required_halo,boundary_transition=16,network=record(directory/'model/network.py'),tiling=record(REPO/'Experiments/R124_RealFirstPrototype/inference/tiling.py'))
    else:
        pkg=Path(info['package']);sys.path.insert(0,str(pkg));runtime=module('r136_r129_runtime',pkg/'runtime.py')
        model,_=runtime.create();model.load_state_dict(torch.load(cp,map_location='cpu')['model'],strict=True);model.eval()
        tile=module('r136_r129_tiling',REPO/'Experiments/R129_OpticalPriorHybrid/scripts/sequence_inference.py')
        guard=module('r136_r129_guard',pkg/'model/inference_policy.py').guard
        def predict(raw):
            x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
            with torch.inference_mode():return guard(x,tile.predict(model,x,512))[0,0].cpu().numpy()
        def native_verify(raw_path,value):
            raw=cv2.imread(str(raw_path),0);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
            with torch.inference_mode():v=guard(x,tile.predict(model,x,384))[0,0].cpu().numpy()
            error=float(np.max(np.abs(v-value)));assert error<1e-6
            return dict(alternate_core_max_abs_error=error,tiling=record(REPO/'Experiments/R129_OpticalPriorHybrid/scripts/sequence_inference.py'))
    setup();model.eval();return predict,native_verify

def main():
    a=argparse.ArgumentParser();a.add_argument('model',choices=['R61','R129','R128']);a.add_argument('--limit',type=int,default=0);args=a.parse_args()
    plan=load(ROOT/('config/r128_extension.json' if args.model=='R128' else 'config/plan.json'));out=ROOT/'results'/args.model;out.mkdir(parents=True,exist_ok=True)
    predict,verify=build(args.model,plan);records=[];start=time.perf_counter()
    frames=plan['frames'][:args.limit] if args.limit else plan['frames']
    try:
        for k,f in enumerate(frames,1):
            folder=out/f['run'];folder.mkdir(exist_ok=True);stem=f"{f['index']+1:02d}";meta=folder/(stem+'.json')
            if meta.exists():
                r=load(meta)
                if all(Path(r[key]['path']).exists() for key in ['values','image']):records.append(r);continue
            tick=time.perf_counter();raw=cv2.imread(f['source']['path'],0);value=predict(raw).copy()
            assert value.shape==raw.shape and np.isfinite(value).all()
            if not (out/'verified_probe.json').exists():save(out/'verified_probe.json',verify(f['source']['path'],value))
            np.savez_compressed(folder/(stem+'.npz'),output=value)
            image=np.rint(value*65535).clip(0,65535).astype(np.uint16);assert cv2.imwrite(str(folder/(stem+'.png')),image)
            r=dict(run=f['run'],index=f['index'],source=f['source'],values=record(folder/(stem+'.npz')),image=record(folder/(stem+'.png')),shape=list(value.shape),seconds=time.perf_counter()-tick)
            save(meta,r);records.append(r)
            save(ROOT/f'results/status_{args.model}.json',dict(status='running',finished=k,total=len(frames),elapsed_s=time.perf_counter()-start,updated_utc=now(),pid=os.getpid()))
            if k<=3 or k%10==0:print(args.model,k,'/',len(frames),round(r['seconds'],2),'s',flush=True)
            if shutil.disk_usage(out).free<4*2**30:raise RuntimeError('Less than4GiB free; retain completed work')
        status='probe_complete' if args.limit else 'complete'
        save(out/('probe_complete.json' if args.limit else 'complete.json'),dict(status=status,records=records,frames=len(records),checkpoint=plan['models'][args.model]['checkpoint'],elapsed_s=time.perf_counter()-start,completed_utc=now()))
        save(ROOT/f'results/status_{args.model}.json',dict(status=status,finished=len(records),total=len(frames),updated_utc=now()))
    except BaseException:
        save(ROOT/f'results/status_{args.model}.json',dict(status='failed',finished=len(records),error=traceback.format_exc(),updated_utc=now()));raise
if __name__=='__main__':main()
