"""Independent diagnosis checks, with a rounding bound derived from float32 arithmetic."""
from pathlib import Path
from dataclasses import replace
import hashlib,json,sys
import pandas as pd,numpy as np,torch
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT))
from model.ops import warp_local
from inference.run import load
from training.r119_dataset import R119Scenes,flatten
from training.objectives import objective
from model.network import continuous_width
from torch.utils.data._utils.collate import default_collate
torch.set_num_threads(4)
f=pd.read_csv(OUT/'synthetic_path_effects.csv')
assert len(f)==384 and not f.duplicated(['epoch','split','scene_id']).any()
assert f.groupby(['split','scene_id']).input_sha256.nunique().eq(1).all()
changes=f.filter(like='_weighted_change')
discrepancy=(changes.sum(axis=1)-f.loss_change_no_shift_minus_full).abs()
# Original objective totals are sequential sums of nonnegative float32 terms.
# Computing (sum b - sum a) and sum(w*(b_i-a_i)) changes rounding order.
# A conservative forward-error bound uses operation count and data magnitude,
# not the observed maximum error or a fitted tolerance.
eps=np.finfo(np.float32).eps;n=changes.shape[1]+2
gamma=n*eps/(1-n*eps)
bound=gamma*(f.full_loss.abs()+f.no_shift_loss.abs()+changes.abs().sum(axis=1))+np.finfo(float).eps
assert (discrepancy<=bound).all()
x=torch.arange(128.)[None,None,None,:].repeat(1,1,16,1)
image=torch.sigmoid((x-63.5)/2);flow=torch.zeros(1,2,16,128);flow[:,0]=.25
out=warp_local(image,flow)[0,0,8].numpy()
def crossing(profile):
    i=np.flatnonzero((profile[:-1]<=.5)&(profile[1:]>.5))[0]
    return i+(.5-profile[i])/(profile[i+1]-profile[i])
shift=crossing(out)-crossing(image[0,0,8].numpy());assert abs(shift+.25)<.02
model=load(ROOT/'runs/formal_B_s1195001/weights/epoch_042.pth','cuda');spots=[]
weights=json.loads((ROOT/'config/experiment.json').read_text())['training']['weights']
for split,index in [('train',1),('validation',1),('validation',13)]:
    ds=R119Scenes(split,42,96,'B',1196001);item=ds[index];batch=flatten(default_collate([item]),'cuda')
    with torch.inference_mode():
        d=model.forward_details(batch['source'])
        off=(continuous_width(batch['source'],d.width_gain,d.sdf,d.normals,21)+d.detail).clamp(0,1)
        full,_=objective(model,d,batch,weights);other,_=objective(model,replace(d,output=off),batch,weights)
    saved=f[(f.epoch==42)&(f.split==split)&(f.scene_id==item['scene_index'])].iloc[0]
    error=abs(float(other-full)-saved.loss_change_no_shift_minus_full);assert error<2e-6
    spots.append({'split':split,'scene_id':item['scene_index'],'absolute_loss_change_replay_difference':error})
for row in json.loads((OUT/'known_answer_fixtures.json').read_text()):
    assert row['compensated_output_max_difference']==0 and row['compensated_objective_max_term_difference']==0
    assert row['compensating_detail_max_gray']<24
    assert row['expansion_loss_increases']['local_edge_error']>0
    assert row['expansion_loss_increases']['location_xy']<1e-10
    assert row['joint_sign_change_render_max_difference']==0
snapshot=json.loads((OUT/'input_snapshot.json').read_text())
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return h.hexdigest()
assert all(sha(p)==digest for p,digest in snapshot.items())
record={'paired_records':len(f),'unique_common_input_hash_groups':192,
        'weighted_sum_max_difference':float(discrepancy.max()),'weighted_sum_max_fraction_of_derived_roundoff_bound':float((discrepancy/bound).max()),
        'known_positive_input_flow_output_shift_px':float(shift),'fresh_forward_spots':spots,
        'protected_files_unchanged':len(snapshot),'source_code_sha256':sha(__file__),
        'prior_check_failure':'An initial ad hoc absolute 2e-7 term-sum threshold failed at 3.3999e-7. No result was changed. This check instead uses the float32 forward-error bound from operation count and nonnegative total magnitudes, with all residuals within the bound.'}
with (OUT/'numerical_verification.json').open('x') as stream:json.dump(record,stream,indent=2)
print(json.dumps(record,indent=2))
