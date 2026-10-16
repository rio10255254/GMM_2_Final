"""Time standalone prefixes, excluding intermediate output exports."""
from study import *
import inspect,random,traceback

def main():
    while not (ROOT/'results/inference_complete.json').exists():
        if list((ROOT/'results').glob('failure_infer_*.json')):raise RuntimeError('Inference failed')
        time.sleep(2)
    # Original verified path, changed only in the loop bound. Final anchoring once.
    source=inspect.getsource(original_predict).replace('def predict(', 'def predict_n(').replace('return_latent=False):','return_latent=False,iterations=4):').replace('range(4)','range(iterations)')
    namespace=dict(torch=torch,F=F,tiled_prior=tiled_prior);exec(source,namespace);fn=namespace['predict_n']
    save(ROOT/'results/standalone_prefix_source.json',dict(source=source,original=rec(R129/'scripts/sequence_inference.py'),rule='Only loop bound varied; one final anchor and FOV guard, no intermediate exports'))
    verify_sources();m=model();before=runtime.state_digest(m);rows=[];parity=[]
    cases=[('SEM14',PKG/'validation/inputs/sem14.png'),('full_field',Path(PLAN['frames'][0]['source']['path']))]
    for name,path in cases:
        raw,x=tensor(path)
        with torch.no_grad():
            for n in range(5):
                got=guard(x,fn(m,x,iterations=n));expected=ROOT/'results'/('sem' if name=='SEM14' else 'images')/f'N{n}'/('sem14.png' if name=='SEM14' else f"{PLAN['frames'][0]['sequence']}/frame_{PLAN['frames'][0]['frame_index']:04d}.png")
                arr=np.rint(got[0,0].cpu().numpy()*255).clip(0,255).astype(np.uint8)
                assert np.array_equal(arr,cv2.imread(str(expected),0));parity.append(dict(case=name,step=n,PNG_exact=True))
            order=list(range(5))*3;random.Random(13142).shuffle(order)
            for n in order:
                torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();start=time.perf_counter()
                got=guard(x,fn(m,x,iterations=n));torch.cuda.synchronize();seconds=time.perf_counter()-start
                rows.append(dict(case=name,step=n,seconds=seconds,peak_allocated_gib=torch.cuda.max_memory_allocated()/1024**3))
        print('timed',name,flush=True)
    assert runtime.state_digest(m)==before;pd.DataFrame(rows).to_csv(ROOT/'results/runtime.csv',index=False)
    save(ROOT/'results/runtime_verified.json',dict(utc=now(),warmup_per_step_per_case=1,timed_repeats=3,randomized_order=True,precision='FP32 TF32off',intermediate_exports_timed=False,parity=parity,weights_unchanged=True))
if __name__=='__main__':
    try:main()
    except BaseException:
        save(ROOT/f'results/failure_benchmark_{time.time_ns()}.json',dict(error=traceback.format_exc(),utc=now()));raise
