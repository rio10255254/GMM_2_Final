"""Replay fixed saved models through each round's unchanged native inference.

Only CPU inference is performed. The reference mode reads original sources;
verification mode reads the independently restored GitHub tree and checks both
full floating output arrays and encoded BMP bytes against that CPU reference.
Historical GPU preview panels are preserved separately, not used as bitwise
references. The two endpoints per round do not constitute checkpoint selection.
"""
from __future__ import annotations
import argparse
import gc
import hashlib
import importlib.util
import os
from pathlib import Path
import sys

from four_round_recovery_common import ROUNDS, ENDPOINTS, CONTENT_ID, new_output, read_json, sha, write_json

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value
    spec.loader.exec_module(value)
    return value

def finite_states(checkpoint, torch):
    # Models and optimizer state are checked without moving anything to a GPU.
    count=0
    def walk(value):
        nonlocal count
        if isinstance(value,torch.Tensor):
            count+=1
            if not torch.isfinite(value).all():raise ValueError('Nonfinite checkpoint tensor')
        elif isinstance(value,dict):
            for item in value.values():walk(item)
        elif isinstance(value,(tuple,list)):
            for item in value:walk(item)
    walk(checkpoint)
    return count

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--audit-all-checkpoints',action='store_true')
    args=parser.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import cv2
    import numpy as np
    import torch
    torch.set_num_threads(1)
    cv2.setNumThreads(1)
    out=new_output(args.root,args.output)
    expected=read_json(args.reference) if args.reference else None
    report={'schema':1,'status':'PASS','device':'cpu','torch':torch.__version__,
            'torch_cuda_build':torch.version.cuda,'numpy':np.__version__,'opencv':cv2.__version__,
            'historical_GPU_panels_used_as_pixel_reference':False,'training_repeated':False,
            'checkpoints':[],'outputs':[]}
    for number,name in ROUNDS.items():
        folder=args.root/'Experiments'/name;active=read_json(folder/'runs/active_run.json')
        design=read_json(folder/'config/experiment_design.json')
        if active['dataset_content_sha256']!=CONTENT_ID:raise ValueError('Different source bank')
        model_path=folder/f'model/r{number}_model.py';inference_path=folder/'inference/reconstruct.py'
        if sha(model_path)!=active['model_sha256']:raise ValueError('Model source differs from recorded training')
        model_module=module(f'preserved_r{number}_model',model_path)
        inference=module(f'preserved_r{number}_infer',inference_path)
        weights=folder/'weights/formal'/f"seed_{active['seed']}"/active['run_id']/'weights'
        selected={weights/f'epoch_{epoch:03d}.pth.tar' for epoch in ENDPOINTS[number]}
        paths=sorted((folder/'weights').rglob('*.pth.tar')) if args.audit_all_checkpoints else sorted(selected)
        for path in paths:
            checkpoint=torch.load(path,map_location='cpu',weights_only=False)
            tensors=finite_states(checkpoint,torch)
            record={'path':path.relative_to(args.root).as_posix(),'sha256':sha(path),
                    'epoch':int(checkpoint['epoch']),'finite_tensors':tensors,
                    'has_optimizer_state':bool(checkpoint.get('optimizer_state_dict')),
                    'top_level_keys':sorted(checkpoint)}
            report['checkpoints'].append(record)
            if path not in selected:
                del checkpoint;gc.collect();continue
            epoch=int(checkpoint['epoch'])
            model=model_module.build_model(base=int(design['training']['model_width']))
            state_key='ema_state_dict'
            if state_key not in checkpoint:raise ValueError('Expected saved EMA state')
            model.load_state_dict(checkpoint[state_key],strict=True);model.eval()
            for source in sorted((folder/'data/live_validation').glob('*.bmp')):
                raw=cv2.imdecode(np.fromfile(source,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
                if raw is None:raise ValueError('Unreadable fixed preview input')
                image=torch.from_numpy(raw.astype(np.float32)/255.0)[None,None]
                with torch.inference_mode():
                    result=inference.reconstruct_tensor(model,image,core_size=512,halo=192,tile_batch=1)[0,0].numpy()
                if not np.isfinite(result).all():raise ValueError('Nonfinite inference output')
                encoded=np.rint(np.clip(result,0,1)*255.0).astype(np.uint8)
                ok,bmp=cv2.imencode('.bmp',encoded)
                if not ok:raise ValueError('BMP encoding failed')
                prefix=f'R{number}_epoch{epoch:03d}_{source.stem}'
                bmp.tofile(out/(prefix+'.bmp'));np.save(out/(prefix+'.npy'),result,allow_pickle=False)
                row={'key':prefix,'round':number,'epoch':epoch,'checkpoint_sha256':record['sha256'],
                     'model_source_sha256':sha(model_path),'native_inference_sha256':sha(inference_path),
                     'input_sha256':sha(source),'shape':list(result.shape),
                     'float32_sha256':hashlib.sha256(result.tobytes()).hexdigest(),
                     'bmp_sha256':sha(out/(prefix+'.bmp')),'state':state_key,'core':512,'halo':192}
                if expected:
                    reference=next(r for r in expected['outputs'] if r['key']==prefix)
                    if row!=reference:raise ValueError('Independent CPU replay differs: '+prefix)
                report['outputs'].append(row)
                write_json(out/'IN_PROGRESS.json',{'completed_outputs':len(report['outputs']),'latest':prefix})
                print('NATIVE_MODEL_CPU_REPLAYED',prefix,flush=True)
            del checkpoint,model;gc.collect()
    if len(report['outputs'])!=32:raise ValueError('Incomplete fixed model/input replay')
    report['independent_reference_matched']=expected is not None
    write_json(out/'MODEL_REPLAY_VERIFIED.json',report)

if __name__=='__main__':main()
