"""Original R148v2 material-boundary coordinates, with package-local geometry."""
import numpy as np
from . import geometry as g


def generate_labels(shape, category, views):
    axis=np.arange(144,240,dtype=float)+.5-192
    y,x=axis[:,None],axis[None,:]
    sdfs=[]
    valid=[]
    for view in views:
        score=g.object_score(x,y,shape,view['shift_xy'])
        gy,gx=np.gradient(score)
        distance=np.clip(score/(np.hypot(gx,gy)+1e-4),-8,8)
        sdfs.append(distance.astype(np.float16))
        valid.append(category!='flat_negative')
    return {'sdf':np.stack(sdfs),'valid':np.asarray(valid,dtype=np.uint8)}
