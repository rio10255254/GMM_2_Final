"""Real four-view input, exact common losses, finite gradients and memory feasibility."""
from pathlib import Path
import argparse,copy,sys,time,traceback
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from study import save,read
from benchmark_core import *
from benchmark_models import make_model,SPECS,ADAPTATIONS


def main():
    parser=argparse.ArgumentParser();parser.add_argument('method',choices=list(SPECS));args=parser.parse_args()
    out=ROOT/'results/preflight';out.mkdir(parents=True,exist_ok=True)
    method=args.method
    try:
        cfg,bank,optics=prepare()
        model=make_model(method).cuda().train()
        optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=cfg['optimizer']['max_lr']/cfg['warmup'],weight_decay=cfg['optimizer']['weight_decay'])
        rows=[]
        for step in range(1,4):
            batch,epoch,index=batch_for_step(bank,step)
            optimizer.zero_grad(set_to_none=True)
            torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.perf_counter()
            output=model(batch['source'],batch['operator_psf_indices'],optics)
            assert output.shape==batch['source'].shape and output.dtype==torch.float32
            total,terms=objective(output,batch,optics)
            assert torch.isfinite(output).all() and torch.isfinite(total)
            total.backward()
            grads=[p.grad for p in model.parameters() if p.requires_grad]
            assert all(g is not None and torch.isfinite(g).all() for g in grads)
            norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
            optimizer.step();torch.cuda.synchronize()
            rows.append({'step':step,'seconds':time.perf_counter()-start,'gradient_norm':float(norm),
                         'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
                         'peak_reserved_bytes':torch.cuda.max_memory_reserved(),**losses_as_numbers(total,terms)})
            print(method,'PREFLIGHT',step,'seconds',round(rows[-1]['seconds'],3),'loss',float(total),flush=True)
        result={'status':'passed','method':method,'total_parameters':sum(p.numel() for p in model.parameters()),
                'trainable_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad),
                'specification':SPECS[method],'adaptations':ADAPTATIONS[method],
                'source_pretrained_weights_loaded':False,'four_view_shape':[4,1,384,384],
                'precision':'FP32; TF32 disabled','rows':rows,
                'training_seconds_per_update_after_warmup':float(np.median([r['seconds'] for r in rows[1:]]))}
    except Exception as error:
        result={'status':'failed_preflight','method':method,'error':repr(error),'traceback':traceback.format_exc()}
        print(result['traceback'],flush=True)
    save(out/(method+'.json'),result)
    print('PREFLIGHT_RESULT',method,result['status'],flush=True)
    if result['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
