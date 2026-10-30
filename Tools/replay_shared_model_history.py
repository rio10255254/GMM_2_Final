"""Replay six fixed historical snapshots with the unchanged shared native reader.

This is a CPU portability check, not checkpoint selection or a repetition of the
old GPU experiment. Both the raw network state selected by that original reader
and its exact I/O path are retained. A forward hook records output for comparison
without modifying any network calculation.
"""
import argparse,contextlib,gc,hashlib,importlib.util,json,os,sys,time
from pathlib import Path
from research_recovery import digest,write_json,safe_relative

RUNS=[('R33_p95','training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260405_091941'),
      ('COMBO','training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525'),
      ('R39_strong','training_progress_GESR_v1_v5_ST0p8_SWP_r39_shape_mix_strong_20260428_180728')]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code-root',type=Path,required=True);p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reference',type=Path);a=p.parse_args()
    if a.output.exists():raise FileExistsError('Use a new replay result folder')
    a.output.mkdir(parents=True)
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch,cv2,numpy as np
    torch.set_num_threads(1);cv2.setNumThreads(1)
    if torch.version.cuda is not None:raise ValueError('Run this portability check in the verified CPU-only environment')
    folder=a.code_root/'Model';sys.path.insert(0,str(folder))
    native_path=folder/'GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py'
    spec=importlib.util.spec_from_file_location('preserved_shared_native',native_path);native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
    source_files={name:digest(folder/name) for name in ['GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py','GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py','GeoEdgeAlignSR_v1_Utils.py']}
    image=cv2.imdecode(np.fromfile(a.input,dtype=np.uint8),cv2.IMREAD_UNCHANGED)
    if image is None or min(image.shape[:2])<256:raise ValueError('The fixed optical input is unavailable or too small')
    h,w=image.shape[:2];x=w//2-128;y=h//2-128;crop=image[y:y+256,x:x+256]
    inputs=a.output/'input';inputs.mkdir();ok,encoded=cv2.imencode('.bmp',crop)
    if not ok:raise RuntimeError('Cannot encode the exact test crop')
    encoded.tofile(inputs/'fixed_center_crop.bmp')
    expected=json.loads(a.reference.read_text(encoding='utf-8')) if a.reference else None
    cases=[];original_ctor=native.GeoEdgeAlignSR_v1_v5_NoCoord
    for label,run in RUNS:
      for epoch in [5,100]:
        key=label+'_E'+str(epoch).zfill(3);relative='Experiments/Training_Runs/'+run+'/epoch_'+str(epoch).zfill(3)+'.pth.tar'
        weights=a.data_root/safe_relative(relative)
        deadline=time.time()+10800
        while not weights.exists():
            if time.time()>deadline:raise RuntimeError('The fixed GitHub checkpoint has not arrived: '+relative)
            time.sleep(3)
        captured=[]
        def ctor(*args,**kwargs):
            model=original_ctor(*args,**kwargs)
            def record(module,inputs,output):captured.append(output.detach().cpu().numpy().astype(np.float32).copy())
            model.register_forward_hook(record);return model
        native.GeoEdgeAlignSR_v1_v5_NoCoord=ctor
        sys.argv=[str(native_path),'--weights',str(weights),'--input-dir',str(inputs),'--recon-root',str(a.output/key),
          '--output-name','fixed_input','--device','cpu','--strict-load','--psf-from-ckpt']
        with (a.output/(key+'.log')).open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log):native.main()
        outputs=list((a.output/key).rglob('fixed_center_crop.bmp'))
        if len(captured)!=1 or len(outputs)!=1:raise RuntimeError('Native execution did not create exactly one output: '+key)
        prediction=captured[0];np.save(a.output/(key+'.npy'),prediction,allow_pickle=False)
        row={'key':key,'weights':relative,'weights_sha256':digest(weights),'source_sha256':source_files,
          'input_sha256':digest(a.input),'crop_xywh':[x,y,256,256],'crop_bmp_sha256':digest(inputs/'fixed_center_crop.bmp'),
          'state_used_by_unchanged_native_reader':'state_dict','output_shape':list(prediction.shape),
          'full_native_forward_float32_sha256':hashlib.sha256(prediction.tobytes()).hexdigest(),'bmp_sha256':digest(outputs[0]),
          'all_outputs_finite':bool(np.isfinite(prediction).all())}
        if not row['all_outputs_finite']:raise RuntimeError('Nonfinite native output')
        if expected and row!=next(r for r in expected['cases'] if r['key']==key):raise ValueError('GitHub native replay differs from original CPU reference: '+key)
        cases.append(row);del captured,prediction;gc.collect()
        print('SHARED_NATIVE_MODEL_REPLAYED',key,flush=True)
    write_json(a.output/'LEGACY_NATIVE_REPLAY_VERIFIED.json',{'status':'PASS','cases':cases,'device':'cpu',
      'torch':torch.__version__,'torch_cuda_build':torch.version.cuda,'original_CPU_reference_matched':expected is not None,
      'formal_checkpoint_selection_changed':False,'training_repeated':False,'historical_GPU_previews_claimed_bit_exact':False})

if __name__=='__main__':main()
