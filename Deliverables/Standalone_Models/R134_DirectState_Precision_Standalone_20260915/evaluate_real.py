"""Package-local preserved-precision SEM and motion monitoring."""
from runtime import *
from precision_io import write_values,read_values
from model.inference_policy import guard
from validation import reference_circle_core as core
from sem_metrics import score
import readout as rd
from scipy.io import savemat
import cv2,pandas as pd,subprocess,shutil

def matlab_path():
    name=os.environ.get('MATLAB_EXE') or shutil.which('matlab')
    if name and Path(name).is_file():return name
    values=sorted(Path(os.environ.get('ProgramFiles','C:/Program Files')).glob('MATLAB/*/bin/matlab.exe'))
    if values:return str(values[-1])
    raise RuntimeError('MATLAB with Image Processing Toolbox required')

def evaluate(model,out,step,device='cuda'):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if (out/'complete.json').exists():return load(out/'complete.json')
    panel=load(ROOT/'validation/panel.json');model.eval();tables=[];records=[]
    for item in panel['images']:
        source=ROOT/item['path'];assert sha(source)==item['sha256'];raw8=cv2.imdecode(np.fromfile(source,np.uint8),0);x=torch.from_numpy(raw8.astype(np.float32)/255)[None,None].to(device)
        with torch.no_grad():value=guard(x,model(x))[0,0].cpu().numpy()
        exact=out/(item['name']+'.npy')
        if exact.exists():
            if not np.array_equal(read_values(exact),value):raise RuntimeError('Retained incomplete evaluation differs; preserve and inspect it')
        else:write_values(out,item['name'],value)
        loaded=read_values(exact);records.append(dict(name=item['name'],values=record(exact),preview=record(out/(item['name']+'_preview8.png'))))
        if item['kind']=='sem':savemat(out/(item['name']+'_values.mat'),dict(image=loaded))
        else:
            t,p=rd.measure_frame(core,vars(rd),item['sequence'],item['frame_index'],panel['sequences'][item['sequence']],raw8.astype(float)/255,loaded.astype(float),'R134_P1');tables.append(t);np.savez_compressed(out/(item['name']+'_points.npz'),**p)
    centers=pd.concat(tables);assert len(centers)==216;centers.to_csv(out/'motion_centers.csv',index=False);pairs,_=rd.pair_table(centers,pd.DataFrame(panel['motion_pairs']),panel,'R134_P1');pairs.to_csv(out/'motion_pairs.csv',index=False)
    if not (out/'sem_masks.mat').exists():
        path=str(ROOT/'validation').replace('\\','/').replace("'","''");dest=str(out).replace('\\','/').replace("'","''");command=f"addpath('{path}');extract_sem_precise('{dest}');"
        with (out/'matlab.log').open('ab') as f:r=subprocess.run([matlab_path(),'-batch',command],stdout=f,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if r.returncode:raise RuntimeError('SEM extraction failed; inspect preserved MATLAB log')
    sem,points,info=score(out/'sem_masks.mat',ROOT/'validation/sem_reference.mat');sem.to_csv(out/'sem_measurements.csv',index=False);np.savez_compressed(out/'sem_points.npz',**points)
    result=dict(step=step,completed_utc=now(),SEM=info['summary'],SEM_measurements=108,motion_pairs=len(pairs),independent_SEM_refits=info['independent_diameter_refits'],motion={k:float(pairs[k].median()) for k in ['nominal_abs_error_nm','within_grid_sd_nm','cross_axis_abs_nm']},images=records,measurement_values='lossless float32 reloaded from disk; float optical cells preserved',scope='Reused development panel; no independent physicalY or material-edge qualification')
    save(out/'complete.json',result);print('Precision real panel',step,info['summary'],flush=True);return result
