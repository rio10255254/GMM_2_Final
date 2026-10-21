"""Evaluate the formal R119 checkpoint on the same synthetic sequence bank."""
from __future__ import annotations
import argparse, csv, hashlib, importlib.util, json
from datetime import datetime, timezone
from pathlib import Path
import cv2, numpy as np, torch
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'data'));sys.path.insert(0,str(ROOT/'validation'))
from sequence_bank import SequenceBank, sha
from sequence_metrics import estimate_position, summarize_sequence
from inference.run import load
R109_CHECKPOINT=Path(r'D:/GMM_2_Final/Experiments/R109_StagedMidpointWidthScratch/weights/selected/R109.pth');R109_SOURCE=Path(r'D:/GMM_2_Final/Experiments/R109_StagedMidpointWidthScratch/model/r109_model.py')

def load_r109(device):
 spec=importlib.util.spec_from_file_location('r109_formal_ref',R109_SOURCE);m=importlib.util.module_from_spec(spec);assert spec.loader is not None;spec.loader.exec_module(m);saved=torch.load(R109_CHECKPOINT,map_location='cpu',weights_only=False);model=m.build_model();model.load_state_dict(saved['model']);return model.to(device).eval().requires_grad_(False)
def write_csv(path,rows):
 keys=list(dict.fromkeys(k for row in rows for k in row));path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',newline='',encoding='utf-8-sig') as f:csv.DictWriter(f,fieldnames=keys).writeheader();csv.DictWriter(f,fieldnames=keys).writerows(rows)

def evaluate(checkpoint, name, output, batch_size, device_name):
 bank=SequenceBank(ROOT/'data/development_sequences');device=torch.device('cuda' if device_name=='auto' and torch.cuda.is_available() else device_name if device_name!='auto' else 'cpu');candidate=load(checkpoint,str(device));r109=load_r109(device);methods={'Raw':None,name:candidate,'R109_E48':r109};positions=[];shapes=[];reps={}
 for method,model in methods.items():
  for start in range(0,len(bank.records),batch_size):
   records=bank.records[start:start+batch_size];sources=[];refs=[]
   for row in records:
    source,ref,_=bank.load(row);sources.append(np.rint(source*255).astype(np.uint8));refs.append(ref)
   if model is None:outputs=[s.astype(np.float32)/255 for s in sources]
   else:
    x=torch.from_numpy(np.stack(sources).astype(np.float32)/255)[:,None].to(device)
    with torch.inference_mode():outputs=model(x).float().clamp(0,1).cpu().numpy()[:,0]
   for row,source,ref,image in zip(records,sources,refs,outputs):
    roi=None if row['complete_object_in_roi'] else (20,20,236,236);est=estimate_position(image,ref,roi);positions.append({'method':method,'sequence_id':row['sequence_id'],'scene_id':row['scene_id'],'family':row['family'],'protocol':row['protocol'],'condition_id':row['condition_id'],'frame_index':row['frame_index'],'feature_id':row['scene_id'],'estimator':'fixed_reference_registration_v1','true_x_px':row['true_x_px'],'true_y_px':row['true_y_px'],'estimated_x_px':est.x_px,'estimated_y_px':est.y_px,'valid':est.valid,'failure_reason':None if est.valid else est.reason,'source_sha256':row['source_sha256']})
    raw=source.astype(np.float32)/255;diff=image-ref;gy,gx=np.gradient(diff);shapes.append({'method':method,'scene_id':row['scene_id'],'sequence_id':row['sequence_id'],'condition_id':row['condition_id'],'frame_index':row['frame_index'],'image_mae_gray':float(np.mean(np.abs(diff))*255),'gradient_error':float(np.mean(np.abs(gx))+np.mean(np.abs(gy))),'edge_change_fraction':float(np.mean(np.abs(diff)>.08)),'output_min':float(image.min()),'output_max':float(image.max())});reps.setdefault(row['family'],{})[method]=(source,np.rint(image*255).astype(np.uint8),np.rint(ref*255).astype(np.uint8))
   del sources,refs,outputs
 groups={}
 for row in positions:groups.setdefault((row['method'],row['sequence_id'],row['protocol'],row['condition_id']),[]).append(row)
 summaries=[]
 for (method,seq,protocol,condition),rows in groups.items():
  first=rows[0];summaries.append({'method':method,'sequence_id':seq,'scene_id':first['scene_id'],'family':first['family'],'protocol':protocol,'condition_id':condition,**summarize_sequence(rows)})
 steps=[]
 for (method,seq,protocol,condition),rows in groups.items():
  if protocol not in {'motion_x','motion_y','motion_diag'}:continue
  ordered=sorted((r for r in rows if r['valid']),key=lambda r:r['frame_index'])
  for a,b in zip(ordered,ordered[1:]):steps.append({'method':method,'sequence_id':seq,'start_frame':a['frame_index'],'end_frame':b['frame_index'],'true_dx_px':b['true_x_px']-a['true_x_px'],'true_dy_px':b['true_y_px']-a['true_y_px'],'measured_dx_px':b['estimated_x_px']-a['estimated_x_px'],'measured_dy_px':b['estimated_y_px']-a['estimated_y_px'],'error_dx_px':(b['estimated_x_px']-a['estimated_x_px'])-(b['true_x_px']-a['true_x_px']),'error_dy_px':(b['estimated_y_px']-a['estimated_y_px'])-(b['true_y_px']-a['true_y_px']),'valid':True})
 out=Path(output);out.mkdir(parents=True,exist_ok=True);write_csv(out/'positions.csv',positions);write_csv(out/'steps.csv',steps);write_csv(out/'sequence_summary.csv',summaries);write_csv(out/'shape_detail.csv',shapes)
 panels=[]
 for family in sorted(reps):
  vals=reps[family];r=vals['Raw'][0];t=vals['Raw'][2];c=vals[name][1];q=vals['R109_E48'][1];panels.append(np.concatenate([cv2.resize(x,(160,160)) for x in (r,c,q,t)],axis=1))
 cv2.imwrite(str(out/'representative_panels.png'),np.concatenate(panels,axis=0));audit={'schema_version':1,'status':'complete','created_at_utc':datetime.now(timezone.utc).isoformat(),'candidate':name,'checkpoint':str(Path(checkpoint).resolve()),'checkpoint_sha256':sha(Path(checkpoint)),'r109_checkpoint_sha256':sha(R109_CHECKPOINT),'bank_manifest_sha256':sha(ROOT/'data/development_sequences/manifest.json'),'device':str(device),'bank_count':len(bank),'positions_rows':len(positions),'steps_rows':len(steps),'summary_rows':len(summaries),'shape_rows':len(shapes),'methods':list(methods),'population':'development common bank; no confirmation','invalid_rows_retained':True};(out/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');return audit

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',required=True);parser.add_argument('--name',default='R119_B_E42');parser.add_argument('--output',required=True);parser.add_argument('--batch-size',type=int,default=16);parser.add_argument('--device',default='auto');args=parser.parse_args();result=evaluate(args.checkpoint,args.name,args.output,args.batch_size,args.device);print(json.dumps(result,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
