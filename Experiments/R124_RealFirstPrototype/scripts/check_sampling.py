"""Quantify subcell approximation against an analytic continuous edge.

This is an operator discretization diagnostic, not real-image model selection.
"""
import json,math,pathlib,sys
import numpy as np,torch
from scipy.special import ndtr
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model.observation import LinearObservation

def primitive(x,sigma):
    z=x/sigma
    return sigma*(z*ndtr(z)+np.exp(-.5*z*z)/np.sqrt(2*np.pi))
def average(center,width,sigma,phase):
    return (primitive(center+width/2-phase,sigma)-primitive(center-width/2-phase,sigma))/width
def main():
    torch.set_num_threads(2);rows=[];native=np.arange(-20,21,dtype=float)
    for support in [4,6]:
        for intrinsic in [.4,1.0]:
            for phase in [-.4,0,.4]:
                exact=average(native,1.,math.hypot(intrinsic,.8),phase)
                for factor in [2,4,8]:
                    radius=support*factor;axis=torch.arange(-radius,radius+1,dtype=torch.float64);k=torch.exp(-axis.square()/(2*(.8*factor)**2));k/=k.sum()
                    obs=LinearObservation(k[:,None]*k[None,:],sampling_factor=factor)
                    centers=-20.5+(np.arange(41*factor)+.5)/factor
                    cells=average(centers,1/factor,intrinsic,phase)
                    latent=torch.from_numpy(np.tile(cells,(17*factor,1)))[None,None]
                    with torch.no_grad():out=obs(latent)[0,0,8].numpy()
                    keep=abs(native)<=10;error=float(np.max(abs(out[keep]-exact[keep])))
                    rows.append({'support_radius_native_px':support,'intrinsic_sigma_px':intrinsic,'optical_sigma_px':.8,'phase_px':phase,'sampling_factor':factor,'max_normalized_intensity_error':error,'max_gray_error':255*error})
    # The initial monotonic-error assertion was false: with fixed truncated
    # support, endpoint quadrature and normalization change the tail error.
    # Preserve the original 4px-support measurements and add a separately
    # identified longer-support check; never replace the original numbers.
    old=json.loads((ROOT/'results/sampling_initial_failure_rows.json').read_text())['rows']
    for r in old:
        current=next(x for x in rows if x['support_radius_native_px']==4 and x['intrinsic_sigma_px']==r['intrinsic'] and x['phase_px']==r['phase'] and x['sampling_factor']==r['factor'])
        assert abs(current['max_gray_error']-r['max_gray_error'])<1e-12
    summaries={str(support):{str(s):max(r['max_gray_error'] for r in rows if r['sampling_factor']==s and r['support_radius_native_px']==support) for s in [2,4,8]} for support in [4,6]}
    result={'status':'approximation_and_truncation_sensitivity_quantified_not_instrument_qualified','cases':rows,'worst_gray_error_by_support_and_factor':summaries,'initial_monotonic_assertion':'failed_and_withdrawn_as_unjustified; initial source/log/all18numbers retained','interpretation':'An exact discrete adjoint does not imply exact continuous optics. Finer grids are not guaranteed to monotonically reduce total error at fixed truncated support or floating-point floor. The separate6px-support check reduces tail error. No universal physical precision or real efficacy follows; prototype network supports2x only.'}
    (ROOT/'results/sampling_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(summaries))
if __name__=='__main__':main()
