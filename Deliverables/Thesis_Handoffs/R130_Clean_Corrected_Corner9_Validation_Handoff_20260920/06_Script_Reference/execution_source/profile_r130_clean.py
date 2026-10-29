import time
import numpy as np,torch,cv2
from utils import ROOT,config,load,save,setup,now
from infer_r130_clean import load_own_model,predict_tensor
def segmented(model,x):
 events=[]
 def stamp(name):
  ev=torch.cuda.Event(enable_timing=True);ev.record();events.append((name,ev))
 stamp('start');fixed=model.features(x);stamp('fixed_features');r=torch.zeros_like(x);z=x
 for i in range(4):
  f=torch.cat([z,x,z-x,*fixed],1);stamp(f'features_{i+1}')
  d=torch.tanh(model.backbone(f));eta=model.cfg['eta_max']*torch.sigmoid(model.step_logits[i]);r=(r+eta*d).clamp(-model.cfg['r_max'],model.cfg['r_max']);z=(x+r).clamp(0,1);stamp(f'update_{i+1}')
 stamp('output');torch.cuda.synchronize()
 return z,{events[i][0]:events[i-1][1].elapsed_time(events[i][1])/1000 for i in range(1,len(events))}
def main():
 cfg=config();setup(cfg['model_seed']);complete=load(ROOT/'runs/formal_8192/training_complete.json');model,_=load_own_model(complete['final_checkpoint']['path']);f=load(ROOT/'evaluation/capture_plan.json')['frames'][0];raw=cv2.imread(f['source']['path'],0);cpu=torch.from_numpy(raw.astype('float32')[None,None]/255)
 a=time.perf_counter();x=cpu.cuda();torch.cuda.synchronize();transfer=time.perf_counter()-a;records=[]
 with torch.inference_mode():
  model(x)
  for mode in ['full','tiled']:
   for repeat in range(3):
    torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();tick=time.perf_counter();y=predict_tensor(model,x,mode,512,96);torch.cuda.synchronize();seconds=time.perf_counter()-tick
    if mode=='full':reference=y.detach().clone()
    error=float((y-reference).abs().max());assert error<=cfg['preflight_tolerances']['full_tile_abs']
    records.append(dict(mode=mode,repeat=repeat,seconds=seconds,peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),max_difference_vs_full=error))
  y,stages=segmented(model,x);assert float((y-reference).abs().max())<=cfg['preflight_tolerances']['full_tile_abs']
  # Core stitching cost measured on the same fixed grid, separately from neural work.
  start=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True);dst=torch.empty_like(reference);start.record()
  for yy in range(0,x.shape[-2],512):
   for xx in range(0,x.shape[-1],512):dst[...,yy:yy+512,xx:xx+512]=reference[...,yy:yy+512,xx:xx+512]
  end.record();torch.cuda.synchronize();stitch=start.elapsed_time(end)/1000
 result=dict(model='R130-Clean',precision='FP32',tf32=False,device=torch.cuda.get_device_name(),shape=list(raw.shape),parameter_count=sum(p.numel() for p in model.parameters()),data_transfer_seconds=transfer,full_image_and_tile_records=records,segmented_forward_seconds=stages,tiled_core_copy_only_seconds=stitch,ACM_measurement=load(ROOT/'results/comparison/measurement_timing.json'),runtime_scope='full native1544x2064; GPU synchronization; 3 repeats after warmup; tiled totals include launches and stitch, copy-only number not subtracted from totals',R129_baseline='No historical checkpoint loaded. End-to-end cached R129 run timing may be reported separately, not presented as matched fresh neural profiling.',completed_utc=now())
 save(ROOT/'results/profile.json',result);print(result,flush=True)
if __name__=='__main__':main()
