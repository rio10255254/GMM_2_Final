"""Full-default runtime checks; preserves failures and never performs optimizer updates."""
from __future__ import annotations
import argparse,hashlib,json,sys,time,traceback
from pathlib import Path
import cv2,numpy as np,torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model.network import build_model
from model.calibration import load_observation,observation_from_profile
from inference.tiling import tiled_forward

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return cv2.imdecode(np.fromfile(path,dtype=np.uint8),0).astype(np.float32)/255
def save(path,record):path.write_text(json.dumps(record,indent=2,allow_nan=False),encoding='utf-8')
def sync():
    if torch.cuda.is_available():torch.cuda.synchronize()
def nonneutral(model):
    with torch.no_grad():torch.nn.init.normal_(model.prior.head.weight,std=.02);model.prior.head.bias.fill_(.01)
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--mode',choices=['tiles','backward'],required=True);args=p.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    protocol=json.loads((ROOT/'config/verification_protocol.json').read_text());device='cuda' if torch.cuda.is_available() else 'cpu';torch.set_num_threads(2);torch.manual_seed(1249001)
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
    record={'status':'running','mode':args.mode,'device':device,'torch':torch.__version__,'optimizer_updates':0,'calibration_qualified':False,'protocol_sha256':sha(ROOT/'config/verification_protocol.json')};save(out/'status.json',record)
    try:
        if args.mode=='tiles':
            path=ROOT.parent/'R119_SequenceGeometryValidation/validation/inputs/Raw/20x_mixed_raw.bmp';digest=sha(path)
            raw=torch.tensor(read(path)[:321,:377])[None,None].to(device)
            model=build_model(observation=load_observation(ROOT/'config/gaussian_diagnostic.json',device)).to(device).eval();nonneutral(model)
            sync();start=time.perf_counter()
            with torch.inference_mode():full=model(raw)
            rows=[]
            for core,oy,ox in protocol['tile_test']['default_cases']:
                tiled=tiled_forward(model,raw,core=core,origin=(oy,ox));diff=(full-tiled).abs()
                edge=torch.zeros_like(diff,dtype=torch.bool);edge[...,:3,:]=edge[...,-3:,:]=True;edge[...,:,:3]=edge[...,:,-3:]=True
                row={'core':core,'origin':[oy,ox],'halo':model.required_halo,'maximum_abs_difference':float(diff.max()),'global_edge_maximum':float(diff[edge].max()),'mean_abs_difference':float(diff.mean())};rows.append(row);print(json.dumps(row),flush=True)
                assert row['maximum_abs_difference']<=protocol['tile_test']['default_absolute_tolerance'],row
            # Bypass the public guard solely to demonstrate artificial tile borders.
            with torch.inference_mode():
                bad=torch.empty_like(raw)
                for y in range(0,321,128):
                    for x in range(0,377,128):bad[...,y:y+128,x:x+128]=model(raw[...,y:y+128,x:x+128])
            missing_context=float((bad-full).abs().max());change=float((full-raw).abs().max());assert missing_context>1e-4 and change>1e-4
            np.savez_compressed(out/'default_tile_outputs.npz',full=full.cpu().numpy(),insufficient_context=bad.cpu().numpy())
            del model,full,bad,raw
            if device=='cuda':torch.cuda.empty_cache()
            # Same dependency graph at maximum supported kernel; channel count reduced
            # for the separate support test. Default 64-channel path is tested above.
            profile=json.loads((ROOT/'config/gaussian_diagnostic.json').read_text());profile['kernel'].update(radius_native_px=16,sigma_native_px=3.2);profile['calibration_id']='max_support_diagnostic_only'
            large=build_model({'channels':8},observation_from_profile(profile,device)).to(device).eval();nonneutral(large)
            torch.manual_seed(1249002);raw=.2+.6*torch.rand(1,1,645,707,device=device)
            with torch.inference_mode():full=large(raw)
            tiled=tiled_forward(large,raw,core=320,origin=(17,31));maximum=float((full-tiled).abs().max());assert maximum<=protocol['tile_test']['max_kernel_absolute_tolerance'],maximum
            assert sha(path)==digest
            sync();record.update(status='passed',default_parameter_count=sum(x.numel() for x in build_model().parameters()),cases=rows,zero_context_difference=missing_context,nonneutral_output_change=change,max_kernel={'channels':8,'radius_native':16,'halo':large.required_halo,'maximum_abs_difference':maximum},elapsed_seconds=time.perf_counter()-start,input_sha256=digest,interpretation='Nonneutral numerical tile parity; not real image efficacy or calibration qualification')
        else:
            if device!='cuda':raise RuntimeError('Requested full-size GPU memory check requires CUDA')
            source=ROOT.parent/'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack';paths=[source/'13.bmp',source/'24.bmp'];hashes={str(p):sha(p) for p in paths};images=[]
            for p in paths:
                a=read(p);h,w=a.shape;y,x=(h-640)//2,(w-640)//2;assert y>=0 and x>=0;images.append(a[y:y+640,x:x+640])
            raw=torch.from_numpy(np.stack(images)[:,None]).to(device)
            model=build_model({'checkpoint_blocks':True},load_observation(ROOT/'config/gaussian_diagnostic.json',device)).to(device).train();nonneutral(model)
            weights=[x.detach().clone() for x in model.parameters()];torch.cuda.reset_peak_memory_stats();sync();free,total=torch.cuda.mem_get_info();start=time.perf_counter()
            details=model.forward_details(raw,trace=False);c=details.output[...,256:384,256:384]
            # This scalar only exercises derivatives. It is not a training recipe or target.
            loss=c.square().mean()+.001*sum(v[...,256:384,256:384].square().mean() for v in details.geometry.values())
            loss.backward();sync();elapsed=time.perf_counter()-start
            norms={n:float(p.grad.norm()) if p.grad is not None else None for n,p in model.named_parameters()};assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
            assert all(torch.equal(old,p.detach()) for old,p in zip(weights,model.parameters()))
            assert norms['prior.stem.weight']>0 and norms['prior.head.weight']>0
            peak=torch.cuda.max_memory_allocated()/2**30;assert peak<protocol['backward_smoke']['maximum_allocated_gib'],peak
            for p,h in hashes.items():assert sha(p)==h
            record.update(status='passed',shape=list(raw.shape),internal_shape=list(details.latent.shape),parameter_count=sum(p.numel() for p in model.parameters()),checkpoint_blocks=True,loss_scalar=float(loss.detach()),elapsed_seconds=elapsed,peak_allocated_gib=peak,peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30,free_before_gib=free/2**30,total_device_gib=total/2**30,gradient_norms=norms,weights_unchanged=True,input_hashes=hashes,interpretation='Full paired 640px forward/backward mechanics only; no optimizer, training or scientific objective evaluation')
        save(out/'status.json',record);print(json.dumps(record,indent=2),flush=True)
    except BaseException as exc:
        record.update(status='failed',error=repr(exc),traceback=traceback.format_exc());save(out/'status.json',record);raise
if __name__=='__main__':main()
