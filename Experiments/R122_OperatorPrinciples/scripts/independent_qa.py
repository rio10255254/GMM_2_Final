"""Independent arithmetic, analytic quadrature, and immutable-source verification.

No pass condition demands scientific success. Failed operator/fit cases must remain.
"""
import csv, hashlib, json, pathlib
import numpy as np
from scipy.integrate import quad
from scipy.special import ndtr
import verify_operators as o
E=o.E
def load(name):return json.loads((E/'results'/name).read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def main():
    summary=load('operator_summary.json');rows=list(csv.DictReader((E/'results/operator_matrix.csv').open(encoding='utf-8')))
    for mode,data in summary['operator'].items():
        rr=[r for r in rows if r['mode']==mode];assert len(rr)==data['count']
        assert sum(r['position_pass']=='False' for r in rr)==data['position_fail']
        assert sum(r['width_pass']=='False' for r in rr)==data['width_fail']
        assert max(float(r['position_error_px']) for r in rr)==data['max_position_error_px']
    assert summary['operator']['pixel_linear']['position_fail']>0
    assert summary['operator']['pixel_linear']['width_fail']>0
    # Independently integrate the continuous model over a physical pixel.
    quadrature=[]
    for c in [-.4,0,.4]:
        for sigma in [.3,.8,1.5,3]:
            for x in [-4,0,4]:
                ref=quad(lambda t:ndtr((t-c)/sigma),x-.5,x+.5,epsabs=1e-12)[0]
                actual=float(o.integrated_edge(np.array([x]),c,sigma)[0]);quadrature.append(abs(ref-actual))
    assert max(quadrature)<1e-12
    # Held-out analytic inputs to the fitter, generated differently from the 2D renderer.
    fits=[]
    x=np.arange(-12,13,dtype=float)
    for c in [-.37,.13,.41]:
        for sigma in [.65,1.2,2.4]:
            y=np.array([45+95*quad(lambda t:ndtr((t-c)/sigma),xx-.5,xx+.5,epsabs=1e-11)[0] for xx in x])
            f=o.fit_edge(x,y);fits.append(abs(f['center']-c))
    assert max(fits)<1e-7
    # Finite derivative of measured continuous profile parameters, including asymmetry.
    jac=[];t=np.arange(-32,32+1/1024,1/512);h=.005
    for family in ['gaussian','logistic','asymmetric']:
        c=o.brentq(lambda z:o.profile(z,family,1.5,.13)-.5,-10,10)
        def measure(delta,g):return np.array(o.crossings(t,o.profile(c+g*(t-c-delta),family,1.5,.13)))
        d=(measure(h,1.2)-measure(-h,1.2))/(2*h);g=(measure(0,1.2+h)-measure(0,1.2-h))/(2*h)
        target_width=measure(0,1)[1];err=max(abs(d[0]-1),abs(d[1]),abs(g[0]),abs(g[1]+target_width/1.2**2));jac.append(float(err))
    assert max(jac)<2e-4
    physical=list(csv.DictReader((E/'results/physical_fit.csv').open(encoding='utf-8')))
    for shape,data in summary['physical_fit'].items():
        rr=[r for r in physical if r['shape']==shape];assert len(rr)==data['count']
        for name in ['position','motion']:assert sum(r[name+'_pass']=='False' for r in rr)==data[name+'_failure']
    # Make noise-free limits explicit instead of concealing noisy failures.
    noiseless={}
    for shape in o.P['physical_fit']['shapes']:
        rr=[r for r in physical if r['shape']==shape and float(r['noise'])==0]
        noiseless[shape]={'count':len(rr),'max_abs_position_px':max(abs(float(r['position_error_px'])) for r in rr),'max_abs_motion_px':max(abs(float(r['motion_error_px'])) for r in rr)}
    protected={**load('protected_inputs.json'),**load('protected_extension.json')}
    changed=[p for p,h in protected.items() if sha(p)!=h];assert not changed,changed
    # Old R109/R119 protected expectations are read as-is, never rewritten.
    oldroot=E.parent/'R119_SequenceGeometryValidation/analysis/R109_comparison_20260907'
    old_candidates=list(oldroot.glob('*snapshot*.json'))+list(oldroot.glob('*protected*.json'))
    old_checks=[]
    for p in old_candidates:
        data=json.loads(p.read_text(encoding='utf-8-sig'))
        if isinstance(data,dict) and data and all(isinstance(v,str) and len(v)==64 for v in data.values()):
            bad=[f for f,h in data.items() if sha(f)!=h];assert not bad,bad;old_checks.append({'manifest':str(p),'unchanged':len(data)})
    result={'operator_rows_recounted':len(rows),'physical_rows_recounted':len(physical),'quadrature_checks':len(quadrature),'quadrature_max_error':max(quadrature),'analytic_fit_checks':len(fits),'analytic_fit_max_center_error':max(fits),'separability_jacobian_checks':len(jac),'jacobian_max_error':max(jac),'noise_free_fit':noiseless,'protected_current_inputs_unchanged':len(protected),'historical_protected_checks':old_checks,'meaning':'Numerical implementation and provenance consistency verified. Pixel operator and mismatched physical model have recorded scientific failures; no model is approved.'}
    (E/'results/independent_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
