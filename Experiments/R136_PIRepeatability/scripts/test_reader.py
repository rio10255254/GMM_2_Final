import os
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='1'
from common import *
from reader import *
import cv2,time
plan=load(ROOT/'config/plan.json');a=cv2.imread(plan['frames'][0]['source']['path'],0).astype(np.float64)/255
rows=[]
for dx,dy in [(0,0),(5.8,.09),(-5.8,-.09),(-174.1,2.8),(.17,-.31)]:
    shifted=fft.ifftn(ndimage.fourier_shift(fft.fftn(a),[dy,dx])).real
    start=time.perf_counter();r=measure(a,shifted,plan['rois']['primary']);error=float(np.hypot(r['dx_px']-dx,r['dy_px']-dy))
    rows.append(dict(dx=dx,dy=dy,error_px=error,seconds=time.perf_counter()-start,**r));print(rows[-1],flush=True)
assert max(r['error_px'] for r in rows)<.01
f=plan['frames'][30];b=cv2.imread(f['source']['path'],0).astype(np.float64)/255
r=measure(a,b,plan['rois']['primary']);back=measure(b,a,plan['rois']['primary']);reversal=float(np.hypot(r['dx_px']+back['dx_px'],r['dy_px']+back['dy_px']))
assert reversal<.002
save(ROOT/'results/reader_verified.json',dict(synthetic=rows,actual_first_last=r,reverse_error_px=reversal,scope='image translation numerical correctness; no physical accuracy certification'))
print('Real first-last',r,'reverse_error',reversal,flush=True)
