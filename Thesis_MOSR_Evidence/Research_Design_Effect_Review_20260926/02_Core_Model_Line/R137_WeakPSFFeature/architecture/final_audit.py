from pathlib import Path
import time,json,numpy as np,pandas as pd,torch,cv2
from utils import ROOT,config,setup,load,save,now,sha,verify_protected,verify_frozen
from infer_r137_psf import load_own_model,predict_tensor
from dataset_r137_psf import Bank
from batch_prediction import predict_batch
from losses_r137_psf import objective

def main():
 cfg=config();setup(cfg['model_seed']);train=load(ROOT/'runs/formal_8192/training_complete.json');model,cp=load_own_model(train['final_checkpoint']['path']);plan=load(ROOT/'evaluation/capture_plan.json');checks=[];timing=[]
 assert cp['step']==8192 and all(torch.isfinite(v).all() for v in model.state_dict().values())
 assert float(model.optical_adapter.weight.abs().max())>0
 for index in [0,30,899,929]:
  f=plan['frames'][index];raw=cv2.imread(f['source']['path'],0);x=torch.from_numpy(raw[None,None].astype('float32')/255).cuda()
  with torch.inference_mode():
   torch.cuda.synchronize();tick=time.perf_counter();cue=model.optics(x);torch.cuda.synchronize();cue_seconds=time.perf_counter()-tick
   feature=.02*torch.tanh(model.optical_adapter(cue));assert float(feature.abs().max())<=.020000001
   on=model(x,optical_cue=cue);model.optical_enabled=False;calls=model.optics.calls;off=model(x);assert model.optics.calls==calls;model.optical_enabled=True
   zero=model(x,optical_cue=torch.zeros_like(cue));diff=on-off
   with np.load(ROOT/'results/reconstruction'/f['run']/f"{f['index']+1:02d}.npz") as z:expected=z['output']
   repeat_error=float(np.max(abs(on.cpu().numpy()[0,0]-expected)));assert repeat_error<=2e-6
   checks.append(dict(frame=index,run=f['run'],index=f['index'],PSF_cue_rms=float(cue.square().mean().sqrt()),feature_rms=float(feature.square().mean().sqrt()),feature_max=float(feature.abs().max()),on_minus_off_rms_gray=float(diff.square().mean().sqrt()*255),on_minus_off_max_gray=float(diff.abs().max()*255),actual_cue_vs_zero_rms_gray=float((on-zero).square().mean().sqrt()*255),repeat_output_max=repeat_error,optical_seconds=cue_seconds))
  if index==0:
   for mode in ['full','tiled']:
    for rep in range(2):
     with torch.inference_mode():
      torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();tick=time.perf_counter();y=predict_tensor(model,x,mode,512,96);torch.cuda.synchronize();seconds=time.perf_counter()-tick;err=float((y-on).abs().max());assert err<2e-6
      timing.append(dict(mode=mode,repeat=rep,seconds=seconds,max_difference=err,allocated_bytes=torch.cuda.max_memory_allocated(),reserved_bytes=torch.cuda.max_memory_reserved()))
   import matplotlib
   matplotlib.use('Agg')
   import matplotlib.pyplot as plt
   images=[x.cpu().numpy()[0,0],on.cpu().numpy()[0,0],off.cpu().numpy()[0,0]];fig,axs=plt.subplots(1,3,figsize=(11,4),layout='constrained')
   for ax,img,name in zip(axs,images,['Raw','R137 PSF on','R137 same weights PSF off']):ax.imshow(img[690:820,1555:1685],cmap='gray',vmin=0,vmax=1);ax.set_title(name);ax.axis('off')
   (ROOT/'reports/figures').mkdir(exist_ok=True);fig.savefig(ROOT/'reports/figures/PSF_on_off_example.png',dpi=180);plt.close(fig)
  del x,raw,cue,feature,on,off,zero,diff;torch.cuda.empty_cache()
 bank=Bank(cfg);generated=[]
 with torch.inference_mode():
  for i in range(32):
   batch=bank.batch('test',i,'cuda');model.optical_enabled=True;on=predict_batch(model,batch);lon,terms=objective(on,batch);model.optical_enabled=False;off=predict_batch(model,batch);loff,_=objective(off,batch);model.optical_enabled=True
   generated.append(dict(index=i,on_loss=float(lon),off_loss=float(loff),output_difference_rms_gray=float((on-off).square().mean().sqrt()*255)))
 pd.DataFrame(checks).to_csv(ROOT/'results/PSF_activity_real_examples.csv',index=False);pd.DataFrame(generated).to_csv(ROOT/'results/PSF_on_off_generated32.csv',index=False)
 assert max(x['actual_cue_vs_zero_rms_gray'] for x in checks)>0
 runtime=pd.read_csv(ROOT/'results/reconstruction_runtime.csv');assert len(runtime)==930
 for row in runtime.itertuples():assert sha(row.output_path)==row.output_sha256
 log=[json.loads(x) for x in (ROOT/'runs/formal_8192/updates.jsonl').read_text().splitlines()];assert len(log)==8192 and [x['step'] for x in log]==list(range(1,8193))
 assert all(int(v['step'])==8192 for v in cp['optimizer']['state'].values())
 for ep in range(16):assert len({v['parent_id'] for v in log if v['epoch']==ep})==512
 verify_protected();verify_frozen(load(ROOT/'config/source_lock.json'))
 save(ROOT/'results/profile.json',dict(device=torch.cuda.get_device_name(),precision='FP32',gain=.02,records=timing,scope='full available image optical FFT once + native neural; tile crops same full optical cue'))
 save(ROOT/'results/final_audit.json',dict(updates=8192,images_sha_verified=930,PSF_nonzero_effect_verified=True,feature_gain_fixed=.02,legacy25_PSF=True,independent_SEM_confirmation=False,original_protected_artifacts_unchanged=True,diagnostic_scope='4 predeclared real frames and32generated; same-weight toggle is mechanism check, not retrained ablation',completed_utc=now()))
 print('Final PSF activity, 930 output hashes, optimizer steps and protected sources verified',flush=True)
if __name__=='__main__':main()
