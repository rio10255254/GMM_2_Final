"""Full local data audit, actual optimizer/resume test and fixed real reader parity."""
import time,sys,traceback
import numpy as np,pandas as pd,torch,cv2
from runtime import *
from data import Bank
from engine import update,checkpoint,restore,objective
from evaluate_real import evaluate
from verify_package import verify

def main():
    out=ROOT/'results/preflight';out.mkdir(exist_ok=False)
    save(out/'started.json',dict(utc=now(),source=record(__file__)))
    audit=verify(full=True);save(out/'data_and_package.json',audit)
    cfg=load(ROOT/'config/training.json');bind=binding(cfg);verify_binding(bind);bank=Bank()
    assert len(set(bank.order(0)))==512 and not np.array_equal(bank.order(0),bank.order(1))
    model,opt=create();initial=state_digest(model)
    b0=bank.batch('train',0,'cuda',0);b1=bank.batch('train',0,'cuda',1)
    assert b0['cpu_input_sha256']!=b1['cpu_input_sha256']
    indices=[int(i) for i in bank.order(0)[:8]];rows=[];start=time.perf_counter()
    for step,index in enumerate(indices,1):
        rows.append(update(model,opt,bank.batch('train',index,'cuda',0),step,cfg))
    elapsed=time.perf_counter()-start;digest8=state_digest(model)
    assert digest8!=initial
    m2,o2=create()
    for step,index in enumerate(indices[:4],1):update(m2,o2,bank.batch('train',index,'cuda',0),step,cfg)
    temp=out/'resume_check';temp.mkdir();cp=checkpoint(temp,m2,o2,4,bind)
    m3,o3=create();assert restore(cp,m3,o3,bind)==4
    for step,index in enumerate(indices[4:],5):update(m3,o3,bank.batch('train',index,'cuda',0),step,cfg)
    assert state_digest(m3)==digest8
    for key,value in opt.state_dict()['state'].items():
        other=o3.state_dict()['state'][key]
        for k,v in value.items():
            if torch.is_tensor(v):assert torch.equal(v,other[k])
            else:assert v==other[k]
    save(out/'optimizer_resume.json',dict(passed=True,actual_probe_optimizer_updates=16,discarded_probe_weights=True,uninterrupted_vs_resume_exact=True,first8_seconds=elapsed,rows=rows,new_noise_each_epoch=True,initial_parameter_sha256=initial))
    del model,opt,m2,o2,m3,o3;torch.cuda.empty_cache()
    model,_=create();result=evaluate(model,out/'real_initial',0)
    for item in result['images']:
        assert np.array_equal(cv2.imread(str(ROOT/item['image']['path']),0),cv2.imread(str(ROOT/'validation/baseline'/(item['name']+'.png')),0))
    new=pd.read_csv(out/'real_initial/sem_measurements.csv');old=pd.read_csv(ROOT/'validation/baseline/sem_per_measurement.csv');old=old[old.tag=='D_24']
    joined=new.merge(old,on=['exposure','pillar'],suffixes=('_new','_old'),validate='one_to_one')
    metrics=['radial_nm','correlation','diameter_error_nm','MZC_error_nm','centered_shape_nm']
    differences={k:float(abs(joined[k+'_new']-joined[k+'_old']).max()) for k in metrics}
    assert len(joined)==108 and max(differences.values())<1e-8,differences
    motion=pd.read_csv(out/'real_initial/motion_centers.csv');old=pd.read_csv(ROOT/'validation/baseline/motion_centers.csv');old=old[old.tag=='D_24']
    merged=motion.merge(old,on=['sequence','frame_index','pillar_id'],suffixes=('_new','_old'),validate='one_to_one')
    md=max(float(abs(merged[k+'_new']-merged[k+'_old']).max()) for k in ['cx','cy']);assert len(merged)==72 and md<1e-8
    verify_binding(bind)
    save(out/'complete.json',dict(passed=True,completed_utc=now(),training_config_sha256=sha(ROOT/'config/training.json'),package_manifest_sha256=sha(ROOT/'PACKAGE_MANIFEST.json'),source=record(__file__),all_local_data_verified=True,optimizer_resume_exact=True,actual_probe_optimizer_updates=16,real_images_exact=11,SEM_rows_reproduced=108,SEM_max_differences=differences,motion_centers_reproduced=72,motion_max_difference_px=md,mean_training_update_seconds=elapsed/8,rough_training_hours_excluding_evaluation=elapsed/8*cfg['updates']/3600,scientific_efficacy_not_certified=True))
    print('Preflight complete; same initial model, exact resume and real reader parity',flush=True)

if __name__=='__main__':
    try:main()
    except BaseException:
        folder=ROOT/'results/preflight';folder.mkdir(exist_ok=True)
        save(folder/f'failure_{time.time_ns()}.json',dict(utc=now(),error=traceback.format_exc()))
        raise
