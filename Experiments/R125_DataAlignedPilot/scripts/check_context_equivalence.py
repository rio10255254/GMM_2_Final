"""Actual-data output/loss/gradient parity for support-aware trainingwindows."""
import pathlib,sys,json,time
import numpy as np,torch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'R124_RealFirstPrototype'))
from prototype.network import build_model
from prototype.factorized_observation import from_observation
from model.calibration import observation_from_profile
from training.context import window_for,crop_arrays
from training.objectives import objective
def main():
    dest=ROOT/'results/context_equivalence.json'
    if dest.exists():raise FileExistsError(dest)
    torch.set_num_threads(2);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
    package=ROOT/'data/package_v2';manifest=json.loads((package/'manifest.json').read_text());entries=manifest['scenes'];metas=[json.loads((package/e['metadata_path']).read_text()) for e in entries]
    lengths=[len(m['profile']['kernel']['values']) for m in metas];order=sorted(range(64),key=lambda i:(lengths[i],i));selected=[order[0],order[len(order)//2],order[-1]];rows=[];weights=json.loads((ROOT/'config/pilot.json').read_text())['loss_weights']
    for idx in selected:
        meta=metas[idx];torch.manual_seed(1259500+idx);model=build_model({'checkpoint_blocks':True},from_observation(observation_from_profile(meta['profile'])).cuda()).cuda().train()
        with torch.no_grad():model.prior.head.weight.normal_(0,.02)
        win=window_for(model,meta)
        with np.load(package/entries[idx]['arrays_path']) as z:cpu={k:z[k] for k in ['source','target','latent_target','sdf','boundary']}
        runs=[]
        for cropped in [False,True]:
            model.zero_grad(set_to_none=True);arr=crop_arrays(cpu,win) if cropped else cpu;source=torch.from_numpy(arr['source'].astype(np.float32)/255)[:,None].cuda();target={k:torch.from_numpy(v)[:,None].cuda() for k,v in arr.items() if k!='source'};md={**meta,'training_core_slice':win['core']} if cropped else meta
            torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();t=time.perf_counter();d=model.forward_details(source);loss,terms=objective(model,d,source,target,md,weights,True);loss.backward();torch.cuda.synchronize();core=win['core'] if cropped else [256,384,256,384]
            runs.append({'loss':float(loss),'terms':{k:float(v) for k,v in terms.items()},'gradient':torch.cat([p.grad.detach().flatten().cpu() for p in model.parameters()]),'output':d.output[...,core[0]:core[1],core[2]:core[3]].detach().cpu(),'seconds':time.perf_counter()-t,'peak_gib':torch.cuda.max_memory_allocated()/2**30})
            del d,loss,terms,source,target;torch.cuda.empty_cache()
        g0,g1=runs[0]['gradient'],runs[1]['gradient'];grad_abs=float((g0-g1).abs().max());grad_rel=float((g0-g1).norm()/g0.norm().clamp_min(1e-12));output_error=float((runs[0]['output']-runs[1]['output']).abs().max());loss_error=abs(runs[0]['loss']-runs[1]['loss'])
        row={'scene_id':meta['scene_id'],'window':win,'output_max_error':output_error,'loss_abs_error':loss_error,'gradient_max_error':grad_abs,'gradient_relative_l2_error':grad_rel,'full_seconds':runs[0]['seconds'],'window_seconds':runs[1]['seconds'],'full_peak_gib':runs[0]['peak_gib'],'window_peak_gib':runs[1]['peak_gib']};rows.append(row);print(json.dumps(row),flush=True)
        assert output_error<=2e-6 and loss_error<=2e-5 and grad_rel<=2e-4,row
        del model,cpu,runs;torch.cuda.empty_cache()
    dest.write_text(json.dumps({'status':'passed','rows':rows,'optimizer_updates':0,'scope':'Sameoriginal128core withallrequiredcontext; no scientificdatarestriction or changedtargets'},indent=2))
if __name__=='__main__':main()
