from r135_common import *
import importlib,cv2
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def build(tag):
    plan=load(ROOT/'config/plan.json');info=plan['models'][tag];cp=Path(PROJECT_ROOT / info['checkpoint']['path']);assert sha(cp)==info['checkpoint']['sha256'];setup();details={}
    if tag in ['V42_old','R61']:
        path=Path(str(PROJECT_ROOT / info['inference']) if tag=='V42_old' else str(PROJECT_ROOT / info['command'][1]));sys.path.insert(0,str(path.parent));mod=module('legacy_native_inference',path);captured={}
        class Captured(BaseException):pass
        def capture(model,device,in_path,out_path,align_factor,**kw):captured.update(model=model,device=device,align=align_factor,options=kw);raise Captured()
        original_run=mod.run_one;mod.run_one=capture
        if tag=='V42_old':args=[str(path),'--weights',str(cp),'--device','cuda:0','--input-dir',str(Path(PROJECT_ROOT / plan['frames'][0]['source']['path']).parent),'--recon-root',str(ROOT/'results'/tag/'native_loader'),'--output-name','loader','--strict-load']
        else:
            args=[a if a.startswith('-') or not ('/' in a or '\\' in a) else str(PROJECT_ROOT / a) for a in info['command'][1:]]
            for opt,val in [('--weights',str(cp)),('--input-dir',str(Path(PROJECT_ROOT / plan['frames'][0]['source']['path']).parent)),('--recon-root',str(ROOT/'results'/tag/'native_loader')),('--output-name','loader')]:args[args.index(opt)+1]=val
        previous=sys.argv;sys.argv=args
        try:mod.main()
        except Captured:pass
        finally:sys.argv=previous;mod.run_one=original_run
        if not captured:raise RuntimeError('Native loader never reached inference')
        m=captured['model'];state=mod.extract_state_dict(torch.load(cp,map_location='cpu'));verified=0
        for key,value in m.named_parameters():
            if key in state and not key.startswith(('physics_layer.','weak_psf_block.')):assert torch.equal(value.detach().cpu(),state[key]);verified+=1
        assert verified>10;details.update(native_loader=record(path),command=args,neural_parameter_tensors_verified=verified,alignment=captured['align'])
        def predict(raw):
            x=mod.normalize_to_01(raw,raw.dtype);p,h,w=mod.pad_to_multiple_np(x,captured['align']);tensor=torch.from_numpy(p)[None,None].cuda()
            with torch.no_grad():v=m(tensor).clamp(0,1)[0,0].cpu().numpy().astype(np.float32)[:h,:w]
            if tag=='R61':return v # Original R61 run_one has no external anchor stage.
            kw=captured['options'];return mod.apply_anchor_output(x,v,mode=kw.get('anchor_output_mode','none'),alpha=kw.get('anchor_alpha',.1),sigma=kw.get('anchor_sigma',2.),detail_gain=kw.get('anchor_detail_gain',.35))
        def native_verify(raw_path,value,dest):
            taps=[];original=mod.denormalize_to_dtype
            def tapped(x,dtype):taps.append(x.copy());return original(x,dtype)
            mod.denormalize_to_dtype=tapped
            try:
                with torch.no_grad():original_run(m,torch.device('cuda'),Path(raw_path),Path(dest),captured['align'],**captured['options'])
            finally:mod.denormalize_to_dtype=original
            assert len(taps)==1 and np.array_equal(value,taps[0]);return True
        details['verify_native']=native_verify
    elif tag=='V42_clean':
        directory=REPO/'Experiments/R130_CleanV42Comparison';mod=module('clean_v42_runtime',directory/'scripts/common.py');m,_=mod.create();m.load_state_dict(torch.load(cp,map_location='cpu')['model']);m.eval()
        def predict(raw):
            x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
            with torch.no_grad():return guard(x,m(x),80)[0,0].cpu().numpy()
    elif tag=='R128':
        directory=REPO/'Experiments/R128_SourceOnlyFullTraining';sys.path.insert(0,str(directory));net=importlib.import_module('model.network');state=torch.load(cp,map_location='cpu');m=net.Model(state['model_config']).cuda();m.load_state_dict(state['model']);m.eval();tile=module('r128_verified_tiling',REPO/'Experiments/R124_RealFirstPrototype/inference/tiling.py')
        def predict(raw):
            x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
            with torch.no_grad():value=tile.tiled_forward(m,x,core=256,halo=m.required_halo);return net.boundary_guard(x,value,m.required_halo,16)[0][0,0].cpu().numpy()
    else:
        directory=Path(PROJECT_ROOT / info['package']) if tag=='R134_P1' else REPO/'Deliverables/Standalone_Models/R129_OpticalHybrid_Standalone_20260912';sys.path.insert(0,str(directory));runtime=module('frozen_package_runtime',directory/'runtime.py');m,_=runtime.create();m.load_state_dict(torch.load(cp,map_location='cpu')['model']);m.eval();tile=module('r129_staged',P134.parent/'tiled.py')
        def predict(raw):
            x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
            with torch.no_grad():v=m(x) if tag=='R134_P1' or max(raw.shape)<=1024 else tile.predict(m,x);return guard(x,v,16)[0,0].cpu().numpy()
    setup();m.eval();return predict,details

def cached(tag,f):
    seq,i=f['sequence'],f['frame_index']
    if tag=='R134_P1':
        path=P134/f'results/final_full201/{seq}/frame_{i:04d}/reconstruction.npy';r=next(x for x in load(P134/'results/final_full201/complete.json')['records'] if Path(x['values']['path']).resolve()==path.resolve());assert r['source']==f['source'] and sha(path)==r['values']['sha256'];return np.load(path,allow_pickle=False),dict(record=r['values'],source=r['source'],transform='identity')
    if tag=='R129_W16':
        path=REPO/f'Experiments/R129_OpticalPriorHybrid/results/continuous_lsc/images/{seq}/frame_{i:04d}/record.json'
    elif tag=='R128':path=REPO/f'Experiments/R128_SourceOnlyFullTraining/results/lsc_comparison/R128_images/{seq}/frame_{i:04d}/record.json'
    else:return None,None
    if not path.exists():return None,None
    r=load(path);assert r['source']==f['source'];v=r['output_float'];assert sha(v['path'])==v['sha256'];data=np.load(v['path']);value=data['neural_output'] if tag=='R129_W16' else data['output']
    if tag=='R129_W16':
        raw=cv2.imread(str(PROJECT_ROOT / f['source']['path']),0);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda();y=torch.from_numpy(value)[None,None].cuda();value=guard(x,y,16)[0,0].cpu().numpy()
    return value,dict(record=v,source_record=record(path),transform='guard16 from stored preguard output' if tag=='R129_W16' else 'identity')
