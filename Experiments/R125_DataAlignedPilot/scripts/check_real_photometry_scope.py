"""Post-pilot source-only coverage diagnostic; never changes the training recipe."""
import json,pathlib,hashlib
import cv2,numpy as np
from scipy.io import loadmat
from scipy.ndimage import distance_transform_edt
ROOT=pathlib.Path(__file__).resolve().parents[1];EXP=ROOT.parent
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def main():
    package=ROOT/'data/package_v2';manifest=json.loads((package/'manifest.json').read_text());training=[]
    for e in manifest['scenes']:
        m=json.loads((package/e['metadata_path']).read_text());p=m['photometry']
        training.append({'scene_id':m['scene_id'],'low_gray':p['low']*255,'high_gray':p['high']*255,'contrast_gray':(p['high']-p['low'])*255})
    old=EXP/'R119_SequenceGeometryValidation';primary=old/'results/formal_sem/results/masks/acm_primary_masks.mat';archive=old/'analysis/R109_comparison_20260907/acm_arrays.mat'
    g=loadmat(primary,variable_names=['global_index','opt_centers']);masks=loadmat(archive,variable_names=['truth_historical'])['truth_historical']
    centers={int(g['global_index'][r,c]):np.floor(g['opt_centers'][r*6+c]+.5).astype(int)-1 for r in range(6) for c in range(6)}
    yy,xx=np.mgrid[:104,:104];radius=np.hypot(xx-51.5,yy-51.5);real=[];sources={str(primary):sha(primary),str(archive):sha(archive)}
    for exposure in [13,24]:
        p=EXP/'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack'/f'{exposure}.bmp';sources[str(p)]=sha(p);raw=cv2.imdecode(np.fromfile(p,dtype=np.uint8),0).astype(float)
        for pid in range(1,37):
            cx,cy=centers[pid];cell=raw[cy-52:cy+52,cx-52:cx+52];mask=masks[:,:,pid-1].astype(bool)
            inside=distance_transform_edt(mask)>8;outside=(distance_transform_edt(~mask)>8)&(radius<50)
            lo=float(np.median(cell[inside]));hi=float(np.median(cell[outside]));real.append({'exposure':exposure,'pillar':pid,'low_gray':lo,'high_gray':hi,'contrast_gray':hi-lo})
    envelope={k:{'minimum':min(x[k] for x in training),'maximum':max(x[k] for x in training)} for k in ['low_gray','high_gray','contrast_gray']}
    summary=[]
    for e in [13,24]:
        rows=[x for x in real if x['exposure']==e]
        summary.append({'exposure':e,'pillars':36,**{f'median_{k}':float(np.median([x[k] for x in rows])) for k in ['low_gray','high_gray','contrast_gray']},'outside_training_level_envelope':sum(not(envelope['low_gray']['minimum']<=x['low_gray']<=envelope['low_gray']['maximum'] and envelope['high_gray']['minimum']<=x['high_gray']<=envelope['high_gray']['maximum']) for x in rows)})
    result={'status':'post_pilot_source_coverage_diagnostic','training_scenes':64,'training_level_envelope':envelope,'real_summary':summary,'training':training,'real_rows':real,'source_sha256':sources,'method':'Known synthetic plateau levels vs the unchanged historical Raw SEM-profile plateau estimator; optical readout and material semantics are not requalified','limitations':['Post-pilot diagnostic; did not select or modify training examples, weights, metrics or hyperparameters.','Different populations and target-vs-observed intensities; this is a coverage warning, not a distributional or causal proof.','No claim that brightness alone caused model regression; real optical-model mismatch remains unqualified.'],'training_or_model_changed':False}
    (ROOT/'results/real_photometry_scope.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({'training_envelope':envelope,'real':summary},indent=2))
if __name__=='__main__':main()
