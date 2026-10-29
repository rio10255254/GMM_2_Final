"""One-time, no-tuning evaluation of R119 B E42 on the sealed 144-scene set."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import cv2, numpy as np, torch
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'validation'))
from inference.run import load
from sequence_metrics import estimate_position
PROJECT_ROOT = Path(__file__).resolve().parents[3]

SOURCE_ROOT=Path(str(PROJECT_ROOT / 'Experiments/R118_PhysicalCoordinateRepairScratch/data/confirmation'))
SOURCE_MANIFEST=SOURCE_ROOT/'manifest.json'

def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def gradient_error(value,target):
 gy,gx=np.gradient(value-target);return float(np.mean(np.abs(gx))+np.mean(np.abs(gy)))

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',required=True);parser.add_argument('--output',required=True);parser.add_argument('--name',default='R119_B_E42');parser.add_argument('--batch-size',type=int,default=12);args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
 if (out/'consumption.json').exists():raise FileExistsError(out/'consumption.json')
 seal=json.loads(SOURCE_MANIFEST.read_text(encoding='utf-8-sig'));records=seal['records'];
 if seal.get('status')!='sealed_not_evaluated' or seal.get('training_inclusion') is not False or seal.get('model_predictions_generated') is not False or len(records)!=144:raise ValueError('confirmation seal declaration is not pristine')
 checkpoint=Path(args.checkpoint).resolve(); checkpoint_hash=sha(checkpoint); manifest_hash=sha(SOURCE_MANIFEST);device='cuda' if torch.cuda.is_available() else 'cpu';model=load(checkpoint,device);rows=[]
 for start in range(0,len(records),args.batch_size):
  batch=records[start:start+args.batch_size];a=[];b=[];ta=[];tb=[]
  for r in batch:
   x=np.load(SOURCE_ROOT/r['file']);a.append(x['source_a'].astype(np.float32));b.append(x['source_b'].astype(np.float32));ta.append(x['target_a'].astype(np.float32));tb.append(x['target_b'].astype(np.float32))
  with torch.inference_mode():
   oa=model(torch.from_numpy(np.stack(a)[:,None]).to(device)).float().cpu().numpy()[:,0];ob=model(torch.from_numpy(np.stack(b)[:,None]).to(device)).float().cpu().numpy()[:,0]
  for r,source_a,source_b,target_a,target_b,out_a,out_b in zip(batch,a,b,ta,tb,oa,ob):
   shift=np.asarray(r['shift_xy'],float);pos_raw_a=estimate_position(source_a,target_a);pos_model_a=estimate_position(out_a,target_a);pos_raw_b=estimate_position(source_b,target_b);pos_model_b=estimate_position(out_b,target_b)
   rows.append({'file':r['file'],'family':r['family'],'seed':r['seed'],'true_shift_xy_px':shift.tolist(),'raw_a_mae_gray':float(np.mean(np.abs(source_a-target_a))*255),'model_a_mae_gray':float(np.mean(np.abs(out_a-target_a))*255),'raw_b_mae_gray':float(np.mean(np.abs(source_b-target_b))*255),'model_b_mae_gray':float(np.mean(np.abs(out_b-target_b))*255),'raw_a_gradient_error':gradient_error(source_a,target_a),'model_a_gradient_error':gradient_error(out_a,target_a),'raw_b_gradient_error':gradient_error(source_b,target_b),'model_b_gradient_error':gradient_error(out_b,target_b),'raw_a_position':None if not pos_raw_a.valid else [pos_raw_a.x_px,pos_raw_a.y_px],'model_a_position':None if not pos_model_a.valid else [pos_model_a.x_px,pos_model_a.y_px],'raw_b_position':None if not pos_raw_b.valid else [pos_raw_b.x_px,pos_raw_b.y_px],'model_b_position':None if not pos_model_b.valid else [pos_model_b.x_px,pos_model_b.y_px],'raw_a_valid':pos_raw_a.valid,'model_a_valid':pos_model_a.valid,'raw_b_valid':pos_raw_b.valid,'model_b_valid':pos_model_b.valid})
 fam={}
 for r in rows:fam.setdefault(r['family'],[]).append(r)
 def median(key,items):return float(np.median([r[key] for r in items]))
 summary={'all':{'scenes':len(rows),'raw_mae_gray':median('raw_a_mae_gray',rows),'model_mae_gray':median('model_a_mae_gray',rows),'raw_gradient_error':median('raw_a_gradient_error',rows),'model_gradient_error':median('model_a_gradient_error',rows),'raw_b_mae_gray':median('raw_b_mae_gray',rows),'model_b_mae_gray':median('model_b_mae_gray',rows)},'families':{k:{'scenes':len(v),'raw_mae_gray':median('raw_a_mae_gray',v),'model_mae_gray':median('model_a_mae_gray',v),'raw_gradient_error':median('raw_a_gradient_error',v),'model_gradient_error':median('model_a_gradient_error',v)} for k,v in sorted(fam.items())}}
 out_rows=out/'per_scene.jsonl';out_rows.write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8');(out/'summary.json').write_text(json.dumps({'schema_version':1,'status':'complete','candidate':args.name,'checkpoint_sha256':checkpoint_hash,'confirmation_manifest_sha256':manifest_hash,'summary':summary,'no_tuning':True,'development_or_confirmation':'confirmation'},indent=2),encoding='utf-8');consumption={'schema_version':1,'status':'consumed_once','consumed_at_utc':datetime.now(timezone.utc).isoformat(),'candidate':args.name,'checkpoint':str(checkpoint),'checkpoint_sha256':checkpoint_hash,'confirmation_manifest':str(SOURCE_MANIFEST.resolve()),'confirmation_manifest_sha256':manifest_hash,'scene_count':len(rows),'model_predictions_generated':True,'training_inclusion':False,'selection_or_tuning_after_read':False,'source_seal_modified':False,'outputs':['per_scene.jsonl','summary.json'],'meaning':'The sealed confirmation was evaluated exactly once after P09/P10/P11 freeze. It is no longer unseen.'};(out/'consumption.json').write_text(json.dumps(consumption,indent=2),encoding='utf-8');print(json.dumps({'status':'consumed_once','scene_count':len(rows),'summary':summary['all']},indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
