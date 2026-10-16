"""Reconstruct fixed real frames, then run the unchanged per-pillar optical reader."""
from pathlib import Path
import argparse,concurrent.futures,datetime,sys,time,traceback,shutil
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import cv2,numpy as np,pandas as pd,torch
from study import MOSR_SOURCE,read,save,sha
from inference_methods import load_method,choose_mode,forward_with_mode
from evaluation.measurement_interface import measure_image
torch.set_num_threads(4)
torch.backends.cuda.matmul.allow_tf32=False
torch.backends.cudnn.allow_tf32=False


def frame_output(method,frame):
    if method=='MOSR':return MOSR_SOURCE/'results/reconstruction'/frame['run']/f'{frame["index"]+1:02d}.npz'
    return ROOT/'results/reconstruction'/method/frame['run']/f'{frame["index"]+1:02d}.npz'


def reconstruct(method):
    if method in ('RAW','MOSR'):
        raise ValueError('The fixed RAW/MOSR reconstructions and circle fits are reused, never repeated here')
    model,optics,checkpoint=load_method(method)
    plan=read(MOSR_SOURCE/'evaluation/capture_plan.json')
    out=ROOT/'results/reconstruction'/method;out.mkdir(parents=True,exist_ok=True)
    mode_file=out/'inference_mode.json';mode=read(mode_file)['mode'] if mode_file.exists() else None
    runtime_file=ROOT/'results/runtime'/(method+'.json')
    runtime=read(runtime_file) if runtime_file.exists() else None
    if runtime:
        assert runtime['checkpoint_sha256']==checkpoint
        if mode is not None:assert mode==runtime['mode'], 'Real and measured runtime strategies differ'
    records=[];errors=[]
    for n,frame in enumerate(plan['frames'],1):
        dest=frame_output(method,frame);receipt=dest.with_suffix('.json')
        if receipt.exists():
            old=read(receipt)
            assert old['checkpoint_sha256']==checkpoint and old['source_sha256']==frame['source']['sha256']
            assert sha(dest)==old['output_sha256'] and old['mode']==mode
            records.append(old);continue
        if shutil.disk_usage(ROOT).free<50*2**30:raise OSError('D free space below 50 GiB reserve')
        try:
            assert sha(frame['source']['path'])==frame['source']['sha256']
            image=cv2.imread(frame['source']['path'],cv2.IMREAD_UNCHANGED)
            assert image.dtype==np.uint8 and image.shape==(1544,2064)
            x=torch.from_numpy(image.astype(np.float32)[None,None]/255).cuda()
            torch.cuda.synchronize();start=time.perf_counter()
            with torch.inference_mode():
                if mode is None:
                    if runtime:
                        mode=runtime['mode'];fallback=runtime['memory_only_fallback']
                        output=forward_with_mode(method,model,optics,x,mode)
                    else:
                        output,mode,fallback=choose_mode(method,model,optics,x)
                    save(mode_file,{'method':method,'mode':mode,'memory_only_fallback':fallback,
                                   'choice_made_before_measurement_metrics':True,'checkpoint_sha256':checkpoint})
                else:output=forward_with_mode(method,model,optics,x,mode)
            torch.cuda.synchronize();seconds=time.perf_counter()-start
            values=output.cpu().numpy()[0,0]
            assert values.dtype==np.float32 and values.shape==(1544,2064) and np.isfinite(values).all()
            dest.parent.mkdir(parents=True,exist_ok=True)
            temporary=dest.with_suffix('.tmp')
            with temporary.open('wb') as f:np.savez_compressed(f,output=values)
            temporary.replace(dest)
            record={'method':method,'run':frame['run'],'index':frame['index'],'source_sha256':frame['source']['sha256'],
                    'checkpoint_sha256':checkpoint,'output_sha256':sha(dest),'mode':mode,'forward_seconds':seconds,
                    'shape':list(values.shape),'dtype':str(values.dtype),'out_of_0_1_fraction':float(np.mean((values<0)|(values>1))),
                    'post_sharpen_registration_diameter_or_contrast_correction':False}
            save(receipt,record);records.append(record)
            del x,output,values
        except Exception as error:
            errors.append({'method':method,'run':frame['run'],'index':frame['index'],'error':repr(error),'traceback':traceback.format_exc()})
            save(out/'reconstruction_failures.json',errors)
            # Runtime/resource failures remain failures; no model or per-frame strategy is changed.
        if n%10==0 or n==930:
            save(out/'status.json',{'state':'reconstruction','attempted':n,'total':930,'succeeded':len(records),'failed':len(errors)})
            print(method,'RECON',n,'/930','failed',len(errors),flush=True)
    save(out/'reconstruction_complete.json',{'state':'complete' if len(records)==930 else 'incomplete',
         'method':method,'images':len(records),'attempted':930,'failed_images':len(errors),'checkpoint_sha256':checkpoint,'mode':mode})
    if errors:raise RuntimeError('Real reconstruction incomplete; failures preserved for '+method)


def measure_run(job):
    method,run=job
    cv2.setNumThreads(1)
    plan=read(MOSR_SOURCE/'evaluation/capture_plan.json');cfg=read(MOSR_SOURCE/'evaluation/measurement_config.json')
    tracking=pd.read_csv(MOSR_SOURCE/'evaluation/tracking.csv')
    frames=[f for f in plan['frames'] if f['run']==run]
    assert [f['index'] for f in frames]==list(range(31)), 'Fixed frame order changed'
    rows=[];points=[];failures=[];elapsed=[];identities=[]
    for frame in frames:
        dest=frame_output(method,frame);receipt=read(dest.with_suffix('.json'))
        assert sha(dest)==receipt['output_sha256']
        with np.load(dest,allow_pickle=False) as z:image=z['output'].astype(np.float64)
        seeds=tracking[(tracking.run==run)&(tracking['index']==frame['index'])].sort_values('pillar_id')[['seed_x_px','seed_y_px']].to_numpy()
        assert seeds.shape==(9,2)
        frame_points=np.full((9,64,2),np.nan);start=time.perf_counter()
        for k,seed in enumerate(seeds,1):
            try:
                values,detail=measure_image(image,seed[None],cfg)
                row=values[0];row['pillar_id']=k;row['valid']=True
                frame_points[k-1]=detail['points'][0]
            except Exception as error:
                row={'pillar_id':k,'center_x_px':np.nan,'center_y_px':np.nan,'radius_px':np.nan,'valid':False}
                failures.append({'method':method,'run':run,'index':frame['index'],'pillar_id':k,'error':repr(error)})
            rows.append({'method':method,'run':run,'run_index':frame['run_index'],'index':frame['index'],**row})
        points.append(frame_points);elapsed.append(time.perf_counter()-start)
        identities.append({'index':frame['index'],'output_sha256':receipt['output_sha256'],'source_sha256':frame['source']['sha256']})
    directory=ROOT/'results/readouts'/method;directory.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(directory/(run+'.csv'),index=False,encoding='utf-8-sig')
    np.savez_compressed(directory/(run+'.npz'),points=np.stack(points))
    result={'method':method,'run':run,'attempted_images':31,'attempted_pillars':279,'failed_pillars':len(failures),
            'failure_rate':len(failures)/279,'failures':failures,'measurement_seconds':elapsed,'verified_outputs':identities,
            'reader_sha256':sha(ROOT/'evaluation/measurement_interface.py'),'core_sha256':sha(ROOT/'evaluation/reference_circle_core.py')}
    save(directory/(run+'.json'),result)
    return result


def measure(method):
    if method in ('RAW','MOSR'):raise ValueError('Reuse the saved RAW/MOSR circle fits')
    complete=read(ROOT/'results/reconstruction'/method/'reconstruction_complete.json')
    assert complete['state']=='complete' and complete['images']==930
    plan=read(MOSR_SOURCE/'evaluation/capture_plan.json');directory=ROOT/'results/readouts'/method
    directory.mkdir(parents=True,exist_ok=True)
    pending=[(method,r['run']) for r in plan['runs'] if not (directory/(r['run']+'.json')).exists()]
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        for result in pool.map(measure_run,pending):print(method,'MEASURED',result['run'],'failed',result['failed_pillars'],flush=True)
    receipts=[read(directory/(r['run']+'.json')) for r in plan['runs']]
    failed=sum(r['failed_pillars'] for r in receipts)
    save(directory/'measurement_complete.json',{'state':'complete','method':method,'scans':30,'images':930,
         'attempted_pillars':8370,'failed_pillars':failed,'failure_rate':failed/8370,
         'complete_valid_scans':sum(r['failed_pillars']==0 for r in receipts),'failed_observations_preserved':True,
         'identical_reader_verified_on_synthetic_data':True})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('method');parser.add_argument('--stage',choices=['reconstruct','measure','all'],default='all')
    args=parser.parse_args()
    if args.stage in ('reconstruct','all'):reconstruct(args.method)
    if args.stage in ('measure','all'):measure(args.method)


if __name__=='__main__':main()
