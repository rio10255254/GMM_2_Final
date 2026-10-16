"""Read-only anatomy of the frozen phase readout, never a replacement score.

The packed-spectrum magnitude and signed5x5 centroid follow the documented
OpenCV4.12.0 algorithm, independently reconstructed to expose its surface.
Primary source: https://github.com/opencv/opencv/blob/4.12.0/modules/imgproc/src/phasecorr.cpp
"""
import argparse,cv2
from common import ROOT,R125,save,sha,np,json

def edge(image):
    im=cv2.GaussianBlur(image.astype(np.float32),(0,0),1.)
    v=cv2.magnitude(cv2.Sobel(im,cv2.CV_32F,1,0,ksize=3),cv2.Sobel(im,cv2.CV_32F,0,1,ksize=3));v-=float(v.mean());sd=float(v.std())
    return v/sd if sd>1e-6 else v

def anatomy(a,b):
    aa,bb=edge(a),edge(b);h,w=aa.shape;assert (h,w)==(128,128)
    win=cv2.createHanningWindow((w,h),cv2.CV_32F)
    shift,response=cv2.phaseCorrelate(aa.copy(),bb.copy(),win)
    p=cv2.mulSpectrums(cv2.dft(aa*win),cv2.dft(bb*win),0,conjB=True)
    mag=np.zeros_like(p);mag[:,1:-1:2]=np.sqrt(p[:,1:-1:2].astype(float)**2+p[:,2:-1:2].astype(float)**2).astype(np.float32)
    for col in [0,w-1]:
        mag[0,col]=abs(p[0,col]);mag[-1,col]=abs(p[-1,col])
        mag[1:-1:2,col]=np.sqrt(p[1:-1:2,col].astype(float)**2+p[2:-1:2,col].astype(float)**2).astype(np.float32)
    normalized=cv2.divSpectrums(p,mag,0,conjB=False)
    surface=np.fft.fftshift(cv2.idft(normalized))
    py,px=np.unravel_index(np.argmax(surface),surface.shape)
    y0,y1=max(0,py-2),min(h,py+3);x0,x1=max(0,px-2),min(w,px+3)
    patch=surface[y0:y1,x0:x1].astype(float);yy,xx=np.mgrid[y0:y1,x0:x1]
    mass=patch.sum();cx=float((patch*xx).sum()/(mass+np.finfo(float).eps));cy=float((patch*yy).sum()/(mass+np.finfo(float).eps))
    reproduced=np.array([w/2-cx,h/2-cy]);error=float(np.max(np.abs(reproduced-shift)))
    info=dict(opencv_shift_xy=list(shift),opencv_response=float(response),reconstructed_shift_xy=reproduced.tolist(),reconstruction_error_px=error,integer_peak_shift_xy=[float(w/2-px),float(h/2-py)],peak_location_xy=[int(px),int(py)],signed_centroid_location_xy=[cx,cy],centroid_outside_local5x5=not(x0<=cx<=x1-1 and y0<=cy<=y1-1),signed_patch_mass=float(mass/(h*w)),positive_mass=float(patch[patch>0].sum()/(h*w)),negative_mass=float(patch[patch<0].sum()/(h*w)),local_surface=patch.tolist(),physical_shift_truth_available=False)
    return info,surface

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--evaluation',required=True);ap.add_argument('--name',required=True);args=ap.parse_args();ev=ROOT/'results'/args.evaluation
    panel=json.loads((R125/'results/real_panel_v2/frozen_panel.json').read_text());rows=[];surfaces={};sources={}
    for item in panel['motion_pairs']:
        seq=item['sequence'];x0,y0,x1,y1=item['core_xyxy'];raw=[];cand=[]
        for frame,s in enumerate(item['sources']):
            p=s['path'];assert sha(p)==s['sha256'];sources[p]=s['sha256'];im=cv2.imread(p,cv2.IMREAD_GRAYSCALE).astype(float)/255;raw.append(im[y0:y1,x0:x1])
            p=ev/'motion'/seq/f'frame{frame}'/'output_float.npz';sources[str(p)]=sha(p)
            lx,ly,ux,uy=item['core_in_context_xyxy']
            with np.load(p) as d:cand.append(d['output'][ly:uy,lx:ux])
        for kind,pair in [('Raw',raw),('candidate',cand)]:
            data,surface=anatomy(*pair);rows.append(dict(sequence=seq,kind=kind,**data));surfaces[f'{seq}_{kind}']=surface
    out=ROOT/'results'/args.name;out.mkdir(exist_ok=False);np.savez_compressed(out/'surfaces.npz',**surfaces)
    result=dict(opencv_version=cv2.__version__,evaluation=str(ev),rows=rows,maximum_numerical_replay_error_px=max(r['reconstruction_error_px'] for r in rows),sources=sources,primary_readout_changed=False,old_large_differences_not_deleted=True,reference_url='https://github.com/opencv/opencv/blob/4.12.0/modules/imgproc/src/phasecorr.cpp',interpretation='Signed centroid can extrapolate outside its local peak neighborhood. Integer maxima are diagnostic locations, not substituted precision estimates or physical ground truth.')
    save(out/'summary.json',result)
    for row in rows:print(json.dumps({k:v for k,v in row.items() if k!='local_surface'}),flush=True)

if __name__=='__main__':main()
