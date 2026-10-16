"""Lossless model-value storage; previews are never measurement inputs."""
from pathlib import Path
import numpy as np,cv2

def write_values(folder,name,value):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    if value.dtype!=np.float32 or value.ndim!=2 or not np.isfinite(value).all() or value.min()<0 or value.max()>1:raise ValueError('Require finite normalized float32 model output')
    exact=folder/(name+'.npy');preview=folder/(name+'_preview8.png');high=folder/(name+'_view16.png')
    if any(p.exists() for p in [exact,preview,high]):raise FileExistsError('New output names required')
    with exact.open('xb') as f:np.save(f,value,allow_pickle=False)
    if not np.array_equal(np.load(exact,allow_pickle=False),value):raise RuntimeError('Lossless storage failed')
    for path,maximum,dtype in [(preview,255,np.uint8),(high,65535,np.uint16)]:
        image=np.rint(value*maximum).clip(0,maximum).astype(dtype);ok,data=cv2.imencode('.png',image);assert ok
        with path.open('xb') as f:f.write(data.tobytes())
        back=cv2.imdecode(np.fromfile(path,np.uint8),cv2.IMREAD_UNCHANGED)
        if not np.array_equal(image,back):raise RuntimeError('Image storage failed')
    return exact,preview,high

def read_values(path):
    path=Path(path)
    if path.suffix.lower()!='.npy':raise ValueError('Measurement requires lossless .npy; previews are not accepted')
    value=np.load(path,allow_pickle=False)
    if value.dtype!=np.float32 or value.ndim!=2 or not np.isfinite(value).all() or value.min()<0 or value.max()>1:raise ValueError('Invalid normalized model values')
    return value
