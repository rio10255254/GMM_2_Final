"""Inspect restored, explicitly trusted research checkpoints using CPU only.

Identity, successful deserialization, finite tensors and inference are distinct
checks. A failed historical model is recorded rather than repaired or relabelled.
Only use this with the user's own trusted research files: legacy torch pickles
can execute code while loading.
"""
from __future__ import annotations
import argparse
import gc
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from research_recovery import digest, safe_relative, write_json

def read_manifest(path):
    if path.suffix=='.gz':
        with gzip.open(path,'rt',encoding='utf-8-sig') as stream:return json.load(stream)
    return json.loads(path.read_text(encoding='utf-8-sig'))

def summarize(checkpoint,torch):
    tensors=0;elements=0;nonfinite=[]
    def visit(value,name):
        nonlocal tensors,elements
        if isinstance(value,torch.Tensor):
            tensors+=1;elements+=value.numel()
            if not torch.isfinite(value).all():nonfinite.append(name)
        elif isinstance(value,dict):
            for key,item in value.items():visit(item,name+'/'+str(key))
        elif isinstance(value,(tuple,list)):
            for i,item in enumerate(value):visit(item,name+'/'+str(i))
    visit(checkpoint,'checkpoint')
    value={'tensor_count':tensors,'tensor_elements_including_optimizer':elements,
           'nonfinite_tensor_locations':nonfinite,'all_tensors_finite':not nonfinite,
           'has_optimizer_state':isinstance(checkpoint,dict) and any(checkpoint.get(k) for k in ['optimizer','optimizer_state_dict']),
           'state_dict_fingerprints':{}}
    if isinstance(checkpoint,dict):
        value['top_level_keys']=[str(k) for k in checkpoint]
        epoch=checkpoint.get('epoch')
        if isinstance(epoch,(int,float,str)):value['recorded_epoch']=epoch
        for key in ['state_dict','model_state_dict','ema_state_dict','model','ema']:
            state=checkpoint.get(key)
            if not isinstance(state,dict):continue
            h=hashlib.sha256();params=0;count=0
            for name,tensor in sorted(state.items()):
                if not isinstance(tensor,torch.Tensor):continue
                t=tensor.detach().cpu().contiguous()
                header=json.dumps([str(name),str(t.dtype),list(t.shape)],separators=(',',':')).encode()
                h.update(len(header).to_bytes(8,'little'));h.update(header)
                h.update(t.reshape(-1).view(torch.uint8).numpy().tobytes());params+=t.numel();count+=1
            value['state_dict_fingerprints'][key]={'sha256':h.hexdigest(),'elements_including_buffers':params,'tensors':count}
    return value

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--require-finite',action='store_true',help='Fail delivery checks on any nonfinite tensor; historical failure files are still recorded')
    args=parser.parse_args()
    if args.report.exists():raise FileExistsError('Do not overwrite an existing inspection report')
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(1)
    manifest=read_manifest(args.manifest)
    rows=[row for row in manifest['files'] if row['path'].lower().endswith(('.pth.tar','.pth','.pt'))
          and row.get('role','') not in ['input_numeric','training_tensor_bank']]
    if not rows:raise ValueError('No explicitly preserved torch checkpoint files')
    groups={};identities=[];started=time.time()
    for row in rows:
        path=args.root/safe_relative(row['path'])
        if not path.resolve().is_relative_to(args.root.resolve()):raise ValueError('Restored path redirects outside workspace')
        before=path.stat();actual=digest(path);after=path.stat()
        if actual!=row['sha256'] or before.st_size!=row['bytes'] or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise ValueError('Restored checkpoint identity changed: '+row['path'])
        identities.append({'path':row['path'],'sha256':actual,'bytes':row['bytes']})
        if actual in groups:
            groups[actual]['paths'].append(row['path']);continue
        record={'sha256':actual,'bytes':row['bytes'],'paths':[row['path']]}
        try:
            value=torch.load(path,map_location='cpu',weights_only=False)
            record.update(summarize(value,torch));record['load_status']='LOADABLE'
            del value;gc.collect()
        except Exception as error:
            record['load_status']='LOAD_ERROR_PRESERVED';record['error_type']=type(error).__name__
        groups[actual]=record
        if len(groups)%20==0:print('TRUSTED_CHECKPOINT_OBJECTS_INSPECTED',len(groups),flush=True)
    records=list(groups.values())
    bad=[r for r in records if r['load_status']!='LOADABLE' or not r.get('all_tensors_finite')]
    report={'status':'PASS' if not bad else 'HISTORICAL_MODEL_FAILURES_RECORDED',
      'file_identity_status':'PASS','paths_checked':len(identities),'unique_checkpoint_objects':len(records),
      'model_failures':len(bad),'device':'cpu','torch':torch.__version__,'torch_cuda_build':torch.version.cuda,
      'training_repeated':False,'inference_repeated':False,'historical_model_files_modified':False,
      'checks':records,'file_identities':identities,'seconds':time.time()-started}
    write_json(args.report,report)
    print('CHECKPOINT_HISTORY_INSPECTED',len(identities),'paths',len(records),'objects','failures',len(bad),flush=True)
    return 2 if args.require_finite and bad else 0

if __name__=='__main__':sys.exit(main())
