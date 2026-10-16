"""Interrupt a real completed epoch before validation, then resume without training it twice."""
from pathlib import Path
import subprocess,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
import normal_training as train
from study import save


if __name__=='__main__':
    out=ROOT/'results/epoch_boundary_probe'
    original=train.validation
    count=0
    def interrupt_second(*args,**kwargs):
        global count
        count+=1
        if count==2:raise RuntimeError('Intentional verification interruption before epoch validation')
        return original(*args,**kwargs)
    train.validation=interrupt_second
    try:train.run('EDSR-x1',out,max_updates=512,assessment_limit=1)
    except RuntimeError as error:
        assert str(error)=='Intentional verification interruption before epoch validation'
    else:raise AssertionError('The epoch-boundary interruption did not occur')
    before=torch.load(out/'last.pth',map_location='cpu',weights_only=False)
    assert before['step']==512 and before['completed_epochs']==0
    # Release this process's CUDA context allocations before the resumed subprocess.
    torch.cuda.empty_cache()
    subprocess.run([sys.executable,'-B','-X','utf8',str(ROOT/'scripts/train_external.py'),'EDSR-x1',
                    '--output-dir',str(out),'--max-updates','512','--assessment-limit','1'],check=True)
    after=torch.load(out/'last.pth',map_location='cpu',weights_only=False)
    assert after['step']==512 and after['completed_epochs']==1 and after['best_epoch']==1
    assert len(after['history'])==512 and len(after['dev'])==2
    for name in before['model']:assert torch.equal(before['model'][name],after['model'][name]),name
    save(ROOT/'results/epoch_boundary_resume_verified.json',{'status':'passed','actual_training_updates':512,
         'completed_epoch_validation_resumed_without_retraining':True,'all_model_tensors_unchanged_during_validation_resume':True})
    print('EPOCH BOUNDARY RESUME PASSED',flush=True)
