"""Read an actual pair; ambiguous local estimates stay explicitly unavailable."""
import argparse,cv2
from common import *
from motion_reader_v4 import measure

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--first',required=True,type=Path);p.add_argument('--second',required=True,type=Path);p.add_argument('--roi',nargs=4,type=int,metavar=('X','Y','WIDTH','HEIGHT'));p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    images=[cv2.imread(str(path),cv2.IMREAD_UNCHANGED) for path in [args.first,args.second]]
    if any(a is None for a in images) or images[0].shape!=images[1].shape:raise ValueError('Two readable equal-sized images required')
    bit_depths=[str(a.dtype) for a in images]
    images=[cv2.cvtColor(a,cv2.COLOR_BGRA2GRAY if a.shape[2]==4 else cv2.COLOR_BGR2GRAY) if a.ndim==3 else a for a in images]
    images=[a.astype(float)/np.iinfo(a.dtype).max if np.issubdtype(a.dtype,np.integer) else a.astype(float) for a in images]
    if any(a.ndim!=2 or not np.isfinite(a).all() for a in images):raise ValueError('Finite gray images required')
    local=images
    if args.roi:
        x,y,w,h=args.roi
        if x<0 or y<0 or w<16 or h<16 or x+w>images[0].shape[1] or y+h>images[0].shape[0]:raise ValueError('ROI outside source or too small')
        local=[a[y:y+h,x:x+w] for a in images]
    forward=measure(*local,context=tuple(images) if args.roi else None);reverse=measure(*local[::-1],context=tuple(images[::-1]) if args.roi else None)
    cycle=float(np.hypot(forward['dx']+reverse['dx'],forward['dy']+reverse['dy'])) if forward['accepted'] and reverse['accepted'] else None
    valid=bool(cycle is not None and cycle<=.1)
    result=dict(status='image_translation_estimated' if valid else 'not_uniquely_measurable',displacement_xy_px=[forward['dx'],forward['dy']] if valid else None,measurement_scope=forward['measurement_scope'],ROI=args.roi,forward=forward,reverse=reverse,reverse_consistency_px=cycle,sources=[record(args.first),record(args.second)],original_bit_depths=bit_depths,absolute_stage_accuracy_qualified=False,units='source image pixels; no automatic micrometer conversion',algorithm='R127finite normalized matching with explicit spatial context')
    save(args.output,result);print(json.dumps({'status':result['status'],'displacement_xy_px':result['displacement_xy_px'],'scope':result['measurement_scope']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
