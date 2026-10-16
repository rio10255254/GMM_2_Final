"""Repair latent occupancy, without changing the original diagnostic evidence."""
import json,itertools
import numpy as np
from scipy.ndimage import gaussian_filter
import verify_operators as o

def occupancy(shape,phase,ss,n=96):
    axis=(np.arange(n*ss)+.5)/ss-n/2-.5
    xx,yy=np.meshgrid(axis,axis);half=.5/ss
    if shape=='line':return np.clip((xx-phase)*ss+.5,0,1)
    r=float(shape[6:]);center=phase-r;inside=np.zeros_like(xx)
    nodes,weights=np.polynomial.legendre.leggauss(4)
    for node,weight in zip(nodes,weights):
        y=yy+node*half;extent=np.sqrt(np.maximum(r*r-y*y,0))
        left,right=center-extent,center+extent
        overlap=np.maximum(0,np.minimum(xx+half,right)-np.maximum(xx-half,left))*ss
        inside+=weight*.5*overlap*(abs(y)<=r)
    return 1-inside
def render(shape,sigma,phase,contrast,ss):
    n=96;latent=occupancy(shape,phase,ss,n)
    observed=gaussian_filter(latent,sigma*ss,mode='nearest',truncate=5)
    pixels=observed.reshape(n,ss,n,ss).mean((1,3));x=np.arange(n)-n/2;keep=abs(x)<=12
    return x[keep],80+contrast*pixels[n//2,keep]
def main():
    o.OUT=o.E/'results/area_render_v2';o.OUT.mkdir(exist_ok=False)
    o.render=render
    summary,conv=o.physical_fit()
    checks=[]
    for shape,phase in itertools.product(['circle8','circle16'],[-.4,0,.4]):
        r=float(shape[6:]);area=float(np.sum(1-occupancy(shape,phase,8))/64)
        checks.append({'shape':shape,'phase':phase,'area_error_px2':area-np.pi*r*r})
    o.table('area_checks.csv',checks)
    # Independently known continuous box-integrated line; includes optical approximation error.
    lines=[]
    for sigma,phase in itertools.product([.8,1.5,3],[-.4,0,.4]):
        x,y=render('line',sigma,phase,120,32);fit=o.fit_edge(x,y)
        exact=80+120*o.integrated_edge(x,phase,sigma)
        lines.append({'sigma':sigma,'phase':phase,'fitted_position_error_px':fit['center']-phase,'max_intensity_error_gray':float(abs(y-exact).max())})
    o.table('line_analytic_checks.csv',lines)
    result={'physical_fit':summary,'render_convergence':conv,'area_checks':{'count':len(checks),'max_abs_error_px2':max(abs(r['area_error_px2']) for r in checks)},'line_checks':{'count':len(lines),'max_abs_position_error_px':max(abs(r['fitted_position_error_px']) for r in lines),'max_intensity_error_gray':max(r['max_intensity_error_gray'] for r in lines)},'supersedes':'original physical_fit.csv for physical position/motion conclusions only; original retained as rasterization-confounded diagnostic'}
    (o.OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
