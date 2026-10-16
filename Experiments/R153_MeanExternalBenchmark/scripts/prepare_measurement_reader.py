"""Freeze the original measurement code and test per-pillar failure isolation on synthetic data."""
from pathlib import Path
import sys,shutil,importlib,json
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from study import MOSR_SOURCE,sha,read,save


def main():
    directory=ROOT/'evaluation';directory.mkdir(exist_ok=True)
    records=[]
    for name in ('reference_circle_core.py','measurement_interface.py'):
        src=MOSR_SOURCE/'evaluation'/name;dest=directory/name
        if dest.exists():assert sha(dest)==sha(src)
        else:shutil.copy2(src,dest)
        records.append({'name':name,'source_sha256':sha(src),'copy_sha256':sha(dest)})
    init=directory/'__init__.py'
    if not init.exists():init.write_text('"""Unchanged fixed optical measurement reader."""\n',encoding='utf-8')
    import numpy as np
    from scipy.ndimage import gaussian_filter
    from evaluation.measurement_interface import measure_image
    cfg=read(MOSR_SOURCE/'evaluation/measurement_config.json')
    y,x=np.mgrid[:128,:128];seeds=np.array([(xx,yy) for yy in (31.,64.,97.) for xx in (31.,64.,97.)])
    mask=np.zeros((128,128),dtype=bool)
    for xx,yy in seeds:mask|=(x-xx-.13)**2+(y-yy+.21)**2<8.1**2
    image=gaussian_filter(np.where(mask,.15,.85),.8)
    together,detail=measure_image(image,seeds,cfg)
    separate=[];points=[]
    for k,seed in enumerate(seeds,1):
        rows,value=measure_image(image,seed[None],cfg);rows[0]['pillar_id']=k
        separate.extend(rows);points.append(value['points'][0])
    assert together==separate
    assert np.array_equal(detail['points'],np.stack(points))
    save(ROOT/'results/fixed_measurement_reader_verified.json',{'status':'passed','original_code_copies':records,
         'synthetic_per_pillar_vs_all_nine_exact':True,'original_RAW_or_MOSR_circle_refits':0,
         'new_external_measurement_definition_changed':False})
    print('Frozen reader copied exactly; synthetic per-pillar isolation equals the original nine-pillar call.',flush=True)


if __name__=='__main__':main()
