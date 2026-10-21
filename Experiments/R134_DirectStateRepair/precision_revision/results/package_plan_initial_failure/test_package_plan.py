"""Executable pre-build checks; do not substitute for actual package tests."""
from common import *
import ast
import tiled
def main():
    protected();files=list(P.glob('*.py'))
    for p in files:ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    tree=ast.parse((P/'build_package.py').read_text());wrapper=next(n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith('from .network import Network'))
    sys.modules['net.staged']=tiled;scope={'__package__':'net','__name__':'net.precision_package_probe'};exec(compile(wrapper,'precision_package_wrapper','exec'),scope);m=create('C',1342001,'cpu');state=torch.load(E/'runs/R134_C_s1342001/step0512.pth',map_location='cpu')['model'];m.load_state_dict(state);m.eval();b=np.load(E/'calibration/measured_psf_bank.npz');n=scope['Hybrid'](torch.from_numpy(b['mean']),torch.from_numpy(b['candidates']));n.load_state_dict(state);n.eval();x=torch.rand(1,1,193,201)
    with torch.no_grad():a=m(x);v=n(x)
    assert torch.equal(a,v)
    source=E.parent.parent/'Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/R129_OpticalHybrid_Standalone_20260912'
    train=(source/'train_r129.py').read_text(encoding='utf-8-sig').replace('R129_OpticalHybrid_LongTraining','R134_Precision_LongTraining').replace('r129','r134p').replace('R129','R134P');tree=ast.parse(train);name=next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MODEL_NAME_BASE' for t in n.targets));assert name=='R134_Precision_LongTraining' and "default='r134p_long_01'" in train
    assert 'im2uint8(mat2gray(cellim))' not in (P/'validation/extract_sem_precise.m').read_text()
    # Retain original helper/reference bytes, with only the declared new MATLAB output precision.
    for name in ['reference_circle_core.py','readout_helpers.py','sem_reference.mat']:assert sha(P/'validation'/name)==sha(source/'validation'/name)
    save(P/'results/package_plan_checks.json',dict(passed=True,parsed_sources=len(files),trained_CPU_output_exact=True,launcher_identity=name,reference_helpers_unchanged=True,actual_package_preflight_still_required=True));print('Package source plan checks passed')
if __name__=='__main__':main()
