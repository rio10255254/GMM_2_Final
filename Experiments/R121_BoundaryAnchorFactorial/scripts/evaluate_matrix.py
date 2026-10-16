"""One frozen evaluation population for all eight trained probes."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,sys
import cv2,numpy as np,pandas as pd,torch
import torch.nn.functional as F
from torch.utils.data import DataLoader
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from inference.run import load,tiled,read,write
from training.factorial_dataset import Scenes,flatten
from training.objectives import gradient
BENCH=ROOT.parent/'R119_SequenceGeometryValidation/analysis/controlled_boundary_factors_20260906'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False)
def checkpoints():
    data=json.loads((ROOT/'results/matrix_finished_v2.json').read_text())
    assert len(data['runs'])==8
    return [(r['run_id'],ROOT/'runs'/r['run_id']/'weights/epoch_012.pth') for r in data['runs']]

def readout():
    before=list(sys.path)
    spec=importlib.util.spec_from_file_location('r119_controlled_readout',BENCH/'run.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);sys.path[:]=before
    return module

@torch.inference_mode()
def development():
    out=ROOT/'results/development';out.mkdir(exist_ok=False)
    ds=Scenes('validation',0,96,'A');loader=DataLoader(ds,batch_size=4,num_workers=0)
    rows=[];hashes={}
    for name,path in checkpoints():
        model=load(path,'cuda');source_hash=hashlib.sha256();target_hash=hashlib.sha256()
        for item in loader:
            source_hash.update(item['source'].numpy().tobytes());target_hash.update(item['target'].numpy().tobytes())
            batch=flatten(item,'cuda');prediction=model(batch['source']);target=batch['target'];raw=batch['source']
            residual=prediction-target;raw_residual=raw-target
            grad=gradient(residual);raw_grad=gradient(raw_residual)
            hp=lambda value:value-F.avg_pool2d(F.pad(value,(1,1,1,1),mode='reflect'),3,1)
            metrics={'mae_gray':residual.abs().mean((1,2,3))*255,'Raw_mae_gray':raw_residual.abs().mean((1,2,3))*255,
                     'gradient_mae_gray':(grad[0].abs()+grad[1].abs()).mean((1,2,3))*255,
                     'Raw_gradient_mae_gray':(raw_grad[0].abs()+raw_grad[1].abs()).mean((1,2,3))*255,
                     'highpass_mae_gray':hp(residual).abs().mean((1,2,3))*255,'Raw_highpass_mae_gray':hp(raw_residual).abs().mean((1,2,3))*255}
            assert all(torch.isfinite(v).all() for v in metrics.values())
            for i in range(len(prediction)):
                rows.append({'method':name,'scene_id':int(item['scene_index'][i//2]),'view':i%2,'role':item['role'][i//2],'family':item['family'][i//2],**{k:float(v[i]) for k,v in metrics.items()}})
        hashes[name]={'source':source_hash.hexdigest(),'target':target_hash.hexdigest(),'checkpoint':sha(path)}
        del model;print(json.dumps({'development_done':name}),flush=True)
    assert len({(v['source'],v['target']) for v in hashes.values()})==1
    pd.DataFrame(rows).to_csv(out/'per_view.csv',index=False,mode='x');save(out/'identity.json',hashes)

@torch.inference_mode()
def controlled():
    out=ROOT/'results/controlled';out.mkdir(exist_ok=False);core=readout()
    groups=[('primary','cases',json.loads((BENCH/'protocol.json').read_text())['cases']),
            ('radiometry','radiometry_cases',json.loads((BENCH/'radiometry_protocol.json').read_text())['cases'])]
    rows=[];identity={}
    for name,path in checkpoints():
        model=load(path,'cuda');dest=out/name;dest.mkdir()
        for bank,folder,specs in groups:
            for row in specs:
                p=BENCH/folder/f"{row['case_id']:03d}"/'images.npz'
                with np.load(p) as original:raw=original['Raw'];reference=original['reference']
                key=f"{bank}_{row['case_id']}"
                current={'source_sha256':hashlib.sha256(raw.tobytes()).hexdigest(),'reference_sha256':hashlib.sha256(reference.tobytes()).hexdigest()}
                if key in identity:assert identity[key]==current,'Evaluation inputs changed between arms'
                else:identity[key]=current
                tensor=torch.from_numpy(raw)[None,None].cuda();prediction=model(tensor)[0,0].cpu().numpy()
                if not np.isfinite(prediction).all():raise FloatingPointError(name)
                coords,nx,ny=core.samples(row['shape'],row.get('dx',0.),row.get('dy',0.))
                if bank=='radiometry':inside,outside=row['inside'],row['outside']
                else:
                    inside,outside=(.15,.75) if row['polarity']==-1 else (.75,.15)
                    inside*=row['gain'];outside*=row['gain']
                tp,tv,_,tw=core.measure(reference,coords,inside,outside)
                pos,valid,count,width=core.measure(prediction,coords,inside,outside)
                rp,rv,_,rw=core.measure(raw,coords,inside,outside)
                valid &=tv;error=pos-tp
                np.savez_compressed(dest/f"{bank}_{row['case_id']:03d}.npz",error=error,valid=valid,width=width,Raw_error=rp-tp,Raw_valid=rv&tv,target_width=tw)
                if (bank=='primary' and row['case_id'] in [5,85,165]) or (bank=='radiometry' and row['case_id'] in [24,61,74]):
                    np.savez_compressed(dest/f"preview_{bank}_{row['case_id']:03d}.npz",prediction=prediction)
                rows.append({'method':name,'bank':bank,**row,'valid_profiles':int(valid.sum()),'multiple_crossing_profiles':int((count>1).sum()),'image_mae_gray':float(np.abs(prediction-reference).mean()*255)})
        del model;print(json.dumps({'controlled_done':name}),flush=True)
    pd.DataFrame(rows).to_csv(out/'raw_summary.csv',index=False,mode='x');save(out/'input_identity.json',identity)

@torch.inference_mode()
def sem_render():
    out=ROOT/'results/sem';out.mkdir(exist_ok=False)
    src=ROOT.parent/'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack'
    records=[]
    for name,path in checkpoints():
        model=load(path,'cuda');dest=out/'recon'/name;dest.mkdir(parents=True)
        for e in range(13,25):
            source=src/f'{e}.bmp';raw=read(source)
            prediction=tiled(model,torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda())[0,0].cpu().numpy()
            target=dest/f'{e}.png';write(target,np.rint(np.clip(prediction,0,1)*255).astype(np.uint8))
            records.append({'method':name,'exposure':e,'source_sha256':sha(source),'output_sha256':sha(target),'checkpoint_sha256':sha(path)})
        del model;print(json.dumps({'sem_render_done':name}),flush=True)
    save(out/'render_manifest.json',records)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['development','controlled','sem']);args=parser.parse_args()
    torch.set_num_threads(4);cv2.setNumThreads(1)
    frozen=json.loads((ROOT/'config/source_freeze_v2.json').read_text());assert all(sha(ROOT/p)==value for p,value in frozen.items())
    inputs=json.loads((ROOT/'config/evaluation_inputs.json').read_text());assert all(sha(p)==value for p,value in inputs.items())
    {'development':development,'controlled':controlled,'sem':sem_render}[args.phase]()
