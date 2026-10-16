"""Keep the first edge-crop preview; select a central source pillar for the presentation."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/show_real_reconstructions.py').read_text(encoding='utf-8')
source=source.replace('visual_review_20260914','visual_review_20260914_v2')
old="gy,gx=np.argwhere(ref['global_index']==18)[0];center=np.rint(ref['opt_centers'][int(gy)*6+int(gx)]).astype(int)-1"
new="source_centers=ref['opt_centers']-1;chosen=int(np.argmin(np.sum((source_centers-np.array([410,410]))**2,axis=1)));center=np.rint(source_centers[chosen]).astype(int)"
assert old in source
source=source.replace(old,new).replace('Existing fixed pillar18, exposure14; selected by source grid, not candidate output','Exposure14 source-grid pillar nearest image center; away from FOV guard; not chosen from model results')
destination=ROOT/'scripts/show_real_reconstructions_v2.py'
with destination.open('x',encoding='utf-8') as f:f.write(source)
