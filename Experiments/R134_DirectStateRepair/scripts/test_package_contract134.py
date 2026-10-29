"""Pre-build executable checks. These do not mark a package or model qualified."""
from pathlib import Path
import sys,ast
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from rt import *
from continue_qualified134 import require_admission
import tiled

def main():
    assert not require_admission({'eligible':False})
    rejected=0
    for value in [{'eligible':True,'arm':'A'}, {'eligible':True,'arm':'C','selected_seed':-1}]:
        try:require_admission(value)
        except (AssertionError,KeyError):rejected+=1
        else:raise AssertionError('Invalid admission accepted')
    tree=ast.parse((ROOT/'scripts/build_long_package134.py').read_text(encoding='utf-8'))
    wrapper=next(n.value.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='wrapper' for x in n.targets))
    sys.modules['net.staged']=tiled;scope={'__package__':'net','__name__':'net.package_contract'};exec(compile(wrapper,'package_wrapper','exec'),scope)
    m=create('C',1342001,'cpu');state=torch.load(ROOT/'runs/R134_C_s1342001/step0512.pth',map_location='cpu')['model'];m.load_state_dict(state);m.eval();bank=np.load(ROOT/'calibration/measured_psf_bank.npz');n=scope['Hybrid'](torch.from_numpy(bank['mean']),torch.from_numpy(bank['candidates']));n.load_state_dict(state,strict=True);n.eval();x=torch.rand(1,1,193,201)
    with torch.no_grad():a=m(x);b=n(x)
    assert torch.equal(a,b)
    try:n.forward_details(x)
    except NotImplementedError:rejected+=1
    else:raise AssertionError('Legacy misleading diagnostics exposed')
    sources=[*ROOT.glob('scripts/*.py'),*ROOT.glob('package_templates/*.py')]
    for p in sources:ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    source=ROOT.parent.parent/'Deliverables/Standalone_Models/R129_OpticalHybrid_Standalone_20260912'
    assert '(d - 80) / 16' in (source/'model/inference_policy.py').read_text()
    verify();save(ROOT/'results/package_contract_prebuild.json',dict(passed=True,CPU_trained_image_exact=True,image_shape=list(x.shape),rejected_unsafe_contracts=rejected,parsed_sources=len(sources),not_package_preflight=True,not_long_admission=True))
    print('Pre-build contracts passed; actual package tests remain mandatory',flush=True)
if __name__=='__main__':main()
