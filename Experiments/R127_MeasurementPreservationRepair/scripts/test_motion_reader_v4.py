"""Known-answer finite-domain tests and genuine ambiguity negatives."""
import cv2,time
from scipy import ndimage
from common import *
from motion_reader_v4 import measure

def main():
    panel=json.loads((R125/'results/real_panel_v2/frozen_panel.json').read_text());rows=[];start=time.perf_counter()
    for i,item in enumerate(panel['motion_pairs']):
        path=item['sources'][0]['path'];assert sha(path)==item['sources'][0]['sha256'];im=cv2.imread(path,0).astype(float)/255;h,w=im.shape;cx,cy=w//2,h//2
        for j,(dx,dy) in enumerate([(0,0),(7,-3),(-15,2),(23,17)]):
            a=im[cy-128:cy+128,cx-128:cx+128]
            # Shift of the visible pattern is minus the crop-window offset.
            b=im[cy-128-dy:cy+128-dy,cx-128-dx:cx+128-dx]
            for noise in [0.,1/255]:
                rng=np.random.default_rng(1271000+100*i+10*j+int(noise>0));aa=a+rng.normal(0,noise,a.shape);bb=b+rng.normal(0,noise,b.shape)
                ph,pw=h-160,w-160;py0=cy-ph//2;px0=cx-pw//2
                pa=im[py0:py0+ph,px0:px0+pw].copy();pb=im[py0-dy:py0+ph-dy,px0-dx:px0+pw-dx].copy()
                assert pa.shape==pb.shape==(ph,pw)
                prng=np.random.default_rng(1276000+100*i+10*j+int(noise>0));pa+=prng.normal(0,noise,pa.shape);pb+=prng.normal(0,noise,pb.shape)
                ky,kx=ph//2,pw//2;pa[ky-128:ky+128,kx-128:kx+128]=aa;pb[ky-128:ky+128,kx-128:kx+128]=bb
                assert np.array_equal(pa[ky-128:ky+128,kx-128:kx+128],aa) and np.array_equal(pb[ky-128:ky+128,kx-128:kx+128],bb)
                r=measure(aa,bb,context=(pa,pb));error=float(np.hypot(r['dx']-dx,r['dy']-dy)) if r['accepted'] else None
                rows.append(dict(source=item['sequence'],kind='real_texture_crop_control',true_dx=dx,true_dy=dy,independent_noise_sigma=noise,measurement=r,error_px=error))
    rng=np.random.default_rng(1273001)
    # Nonperiodic smooth physical texture on an8xgrid; continuous shift precedes
    # area integration and independent sensor noise. Gaussian-blurred blobs.
    for i in range(24):
        n=128;f=8;axis=(np.arange(n*f)+.5)/f;x=axis[None,:];y=axis[:,None];dx,dy=rng.uniform(-15,15,2);params=[(rng.uniform(10,118),rng.uniform(10,118),rng.uniform(2,9),rng.uniform(-.15,.15)) for _ in range(30)];images=[]
        for sx,sy in [(0,0),(dx,dy)]:
            z=np.full((n*f,n*f),.5)
            for px,py,width,amp in params:z+=amp*np.exp(-((x-sx-px)**2+(y-sy-py)**2)/(2*width**2))
            a=z.reshape(n,f,n,f).mean((1,3));a+=rng.normal(0,.5/255,a.shape);images.append(a)
        r=measure(*images);error=float(np.hypot(r['dx']-dx,r['dy']-dy)) if r['accepted'] else None;rows.append(dict(source=f'continuous_{i}',kind='continuous8x_blobs',true_dx=float(dx),true_dy=float(dy),measurement=r,error_px=error))
    negatives=[]
    y,x=np.mgrid[:128,:128]
    for name,a,b in [('flat',np.full((128,128),.5),np.full((128,128),.5)),('periodic',.5+.2*np.cos(2*np.pi*x/16),.5+.2*np.cos(2*np.pi*(x-5)/16)),('unrelated',rng.normal(0,1,(128,128)),rng.normal(0,1,(128,128)))]:negatives.append(dict(name=name,measurement=measure(a,b)))
    admitted=[r for r in rows if r['measurement']['accepted']];crop=[r for r in rows if r['kind']=='real_texture_crop_control'];passed=sum(r['measurement']['accepted'] for r in crop)>=.9*len(crop) and max((r['error_px'] for r in admitted),default=999)<=.1 and not any(x['measurement']['accepted'] for x in negatives)
    result=dict(rows=rows,negative_controls=negatives,accepted=len(admitted),total=len(rows),maximum_admitted_error=max((r['error_px'] for r in admitted),default=None),real_texture_crop_acceptance=sum(r['measurement']['accepted'] for r in crop)/len(crop),all_negative_controls_rejected=not any(x['measurement']['accepted'] for x in negatives),engineering_checks_passed=bool(passed),protocol_sha256=sha(ROOT/'config/motion_protocol_v4.json'),reader_sha256=sha(ROOT/'scripts/motion_reader_v4.py'),seconds=time.perf_counter()-start,live_physical_validation=False)
    save(ROOT/'results/motion_hierarchy_calibration_v4.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['rows','negative_controls']}),flush=True)

if __name__=='__main__':main()
