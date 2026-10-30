"""Fresh paired speed check with the thesis tiling recipe and explicit arithmetic."""
import os,sys,ast,time,gc,importlib.util
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,torch,cv2
from model.network import Model

def main():
    out=ROOT/'results/thesis_v34_review_20260912/paired_runtime';out.mkdir(exist_ok=False)
    source=Path('C:/Users/Rio/OneDrive/學業/碩班/論文/benchmark_v34_eight_models.py')
    loader=ROOT.parent.parent/'LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/benchmark_models.py'
    v42=ROOT.parent.parent/'Deliverables/Standalone_Models/V42_SoftLabelSNR_FullStandalone_20260709/results/training_results/training_progress_V42_SoftLabelSNR_full_training_20260709_202710_20260709_202713/epoch_120.pth.tar'
    cp=load(ROOT/'trial/manifest.json')['checkpoint'];assert sha(cp['path'])==cp['sha256'];assert sha(v42)=='89942bc9b31125e836a17b6a3490d078126807e1c8bd179b73588a38c2301f83'
    frame=ROOT.parent.parent/'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp/frame_0000.bmp'
    save(out/'plan.json',dict(created_utc=now(),source=record(__file__),helper=record(source),V42_loader=record(loader),V42_checkpoint=record(v42),R128_checkpoint=cp,input=record(frame),
        common_recipe=dict(tile_size=256,overlap=128,tile_batch=8,patch_warmups=10,patch_iterations=30,full_warmups=2,full_iterations=8),
        arithmetic='Both models explicit strictFP32/TF32off/deterministic, fresh paired control. Do not directly rank these new timings against older published scores with unspecified TF32 flags.',
        R128_validated_pipeline='Additionally time originalfullFOVcore256/halo64/Rawguard,onewarmup/three timed calls,withoutcompressedfileI/O.',
        limitations='Commonrecipe is speedonly andnotqualifiedas identicaloutputtoR128validatedcontextpipeline. No updatedmodel or newquality claim. Sameoneimage,noproductionthroughputclaim.',new_training_updates=0))
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.use_deterministic_algorithms(True)
    scope=dict(np=np,torch=torch,time=time)
    wanted={'tile_positions','feather_window','synchronize','summarize_times','patch_benchmark','common_tiled_forward'}
    nodes=[n for n in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name in wanted];assert len(nodes)==len(wanted);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),scope)
    image=cv2.imread(str(frame),0);device=torch.device('cuda');patch=torch.from_numpy(image[640:896,896:1152].astype(np.float32)/255)[None,None].to(device)
    rows=[];timings=[]
    for name in ['V42','R128']:
        if name=='V42':
            spec=importlib.util.spec_from_file_location('v34_original_model_loader',loader);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);model,payload=mod.load_mosr_model(device)
        else:
            payload=torch.load(cp['path'],map_location='cpu');model=Model(payload['model_config']).to(device);model.load_state_dict(payload['model'])
        model.eval();nparams=sum(p.numel() for p in model.parameters());patch_times,patch_peak=scope['patch_benchmark'](model,patch,device,warmups=10,iterations=30)
        first=None;times=[]
        for k in range(10):
            result,seconds,tiles=scope['common_tiled_forward'](model,image,device,tile_size=256,overlap=128,tile_batch=8)
            if k==1:torch.cuda.reset_peak_memory_stats(device)
            if k>=2:times.append(seconds)
            if first is None:first=result
            else:assert np.array_equal(first,result),'Repeated commonrecipe output changed'
        peak=torch.cuda.max_memory_allocated(device)/2**20
        assert cv2.imwrite(str(out/f'{name}_common_recipe.png'),first)
        row=dict(model=name,parameters=nparams,patch_median_ms=float(np.median(patch_times)*1000),common_full_median_ms=float(np.median(times)*1000),common_full_p95_ms=float(np.percentile(times,95)*1000),common_peak_MB=float(peak),tiles=tiles,all_repeated_outputs_exact=True)
        if name=='R128':
            # The image-only helper is imported only after V42 has been released.
            from evaluation.real import predict
            raw=image.astype(np.float32)/255;valid_times=[]
            for k in range(4):
                torch.cuda.synchronize();start=time.perf_counter();applied,neural,w=predict(model,raw);torch.cuda.synchronize();elapsed=time.perf_counter()-start
                if k:valid_times.append(elapsed)
            saved=load(ROOT/'results/lsc_comparison/R128_images/50x_x_0p5um/frame_0000/record.json')
            with np.load(saved['output_float']['path']) as d:assert np.array_equal(applied,d['output'])
            row['validated_full_median_ms']=float(np.median(valid_times)*1000);row['validated_output_matches_previous']=True
            timings.append(dict(model=name,validated_seconds=valid_times))
        rows.append(row);timings.append(dict(model=name,patch_seconds=patch_times,common_seconds=times));print(json.dumps(row),flush=True)
        del model,payload;gc.collect();torch.cuda.empty_cache()
    save(out/'results.json',dict(completed_utc=now(),rows=rows,timings=timings,source=record(__file__),plan=record(out/'plan.json'),gpu=torch.cuda.get_device_name(),new_training_updates=0))
if __name__=='__main__':main()
