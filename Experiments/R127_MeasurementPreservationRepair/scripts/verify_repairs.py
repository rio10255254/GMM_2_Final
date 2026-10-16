"""Independent arithmetic, source and scope verification of the final repairs."""
import ast,cv2,pandas as pd
from scipy.io import loadmat
from common import *
from motion_reader import features,surface

def main():
    failures=[];checks=[]
    def check(ok,name):
        checks.append(dict(name=name,passed=bool(ok)))
        if not ok:failures.append(name)
    for name in ['motion_hierarchy_calibration_v4','motion_hierarchy_validation_v4','motion_hierarchy_prospective_v4']:
        d=json.loads((ROOT/'results'/f'{name}.json').read_text());check(d['engineering_checks_passed'] and d['total']==72 and d['all_negative_controls_rejected'],name)
        accepted=[r for r in d['rows'] if r['measurement']['accepted']]
        errors=[np.hypot(r['measurement']['dx']-r['true_dx'],r['measurement']['dy']-r['true_dy']) for r in accepted]
        check(abs(max(errors)-d['maximum_admitted_error'])<1e-12,name+' errors recomputed')
    for name in ['motion_reader_tests','motion_reader_tests_v2','motion_reader_validation_v3']:
        check(json.loads((ROOT/'results'/f'{name}.json').read_text())['engineering_checks_passed'] is False,name+' failure retained')
    # Direct finite overlap dot products independently verify FFT normalization/sign.
    rng=np.random.default_rng(1280101);a=rng.random((51,57));b=rng.random((51,57));numerical=[]
    for kind in ['intensity','gradient']:
        value,shifts,_=surface(a,b,kind,max_shift=12)
        for dx,dy in [(0,0),(7,-3),(-9,5),(12,0),(-2,-10)]:
            h,w=a.shape;x0=max(0,-dx);x1=min(w,w-dx);y0=max(0,-dy);y1=min(h,h-dy);num=0.;va=0.;vb=0.
            for aa,bb in zip(features(a,kind),features(b,kind)):
                x=aa[y0:y1,x0:x1].copy();y=bb[y0+dy:y1+dy,x0+dx:x1+dx].copy();x-=x.mean();y-=y.mean();num+=np.sum(x*y);va+=np.sum(x*x);vb+=np.sum(y*y)
            direct=num/np.sqrt(va*vb);observed=value[np.where(shifts==dy)[0][0],np.where(shifts==dx)[0][0]];numerical.append(abs(float(direct-observed)))
    check(max(numerical)<1e-11,'finite correlation agrees with independent direct dot products')
    panel=json.loads((R125/'results/real_panel_v2/frozen_panel.json').read_text());byseq={x['sequence']:x for x in panel['motion_pairs']};full=json.loads((ROOT/'results/fullfield_motion/measurements.json').read_text());vf=json.loads((ROOT/'results/fullfield_motion/verification.json').read_text());check(len(full['outputs'])==48 and len(full['rows'])==24,'all48full images and24pairs present')
    parity=[]
    for item in full['outputs']:
        check(sha(item['source']['path'])==item['source']['sha256'],'full source unchanged')
        check(sha(item['checkpoint']['path'])==item['checkpoint']['sha256'],'frozen checkpoint unchanged')
        check(sha(item['output']['path'])==item['output']['sha256'],'full output digest')
        spec=byseq[item['sequence']];x0,y0,x1,y1=spec['core_xyxy'];lx,ly,ux,uy=spec['core_in_context_xyxy'];old=R126/'results'/f'real_{item["arm"]}_s{item["seed"]}_step0128'/'motion'/item['sequence']/f'frame{item["frame"]}/output_float.npz'
        with np.load(item['output']['path']) as a,np.load(old) as b:err=float(np.max(np.abs(a['output'][y0:y1,x0:x1]-b['output'][ly:uy,lx:ux])))
        parity.append(err)
    check(max(parity)==0,'all48old core outputs bitwise reproduced')
    differences=[]
    for row in full['rows']:
        a=row['measurement']['forward'];b=row['source_Raw']['forward'];delta=np.hypot(a['dx']-b['dx'],a['dy']-b['dy']);differences.append(float(delta));check(abs(delta-row['fullfield_change_vs_Raw'])<1e-12,'fullfield paired difference recomputed')
    check(max(differences)==vf['maximum_accepted_Raw_difference'] and vf['accepted_pairs']==24,'all24fullfield reportable with retained qualification limits')
    native=json.loads((ROOT/'results/sem_native_v2/summary.json').read_text());arr=np.load(ROOT/'results/sem_native_v2/native_references.npz');oc=arr['optical_centers'].reshape(6,6,2);pitches=np.r_[np.linalg.norm(np.diff(oc,axis=0),axis=2).ravel(),np.linalg.norm(np.diff(oc,axis=1),axis=2).ravel()];sp=pd.read_csv(ROOT/'results/sem_native_v2/native_scale.csv');factor=np.median(pitches)/sp.native_SEM_pitch.median()*3.23;check(abs(factor-native['relative_factor_to_historical'])<1e-12,'native source scale independently recomputed')
    for source in native['sources']:check(sha(source['path'])==source['sha256'],'native SEM/Raw source unchanged')
    sizes=pd.read_csv(ROOT/'results/native_size_comparison/measurements.csv');check(len(sizes)==360 and not sizes.duplicated(['exposure','pillar','method']).any(),'complete common native-size comparison')
    for _,r in sizes.iterrows():
        x,b,lo,hi=r.optical_diameter_pitch_ratio,r.Raw_diameter_pitch_ratio,r.SEM_inner_ratio,r.SEM_outer_ratio;v=np.array([lo,hi,np.clip(x,lo,hi),np.clip(b,lo,hi)]);d=np.abs(x-v)-np.abs(b-v);check(abs(d.min()-r.paired_change_lower)<2e-15 and abs(d.max()-r.paired_change_upper)<2e-15,'definition-band effect bounds recomputed')
    guard=json.loads((ROOT/'results/preservation_verification.json').read_text());check(guard['passed'] and guard['arbitrary_inputs_passed']==100 and guard['weights_unchanged'] and guard['optimizer_updates']==0,'conditional preservation verified without weight changes')
    check(all(r['guard_mae']==0 and r['bitwise_raw_equal'] for r in guard['rows'] if r['category']=='clean_identity'),'all6known identity parents exact')
    check(guard['noisy_identity']['output_mae']<guard['noisy_identity']['Raw_mae'] and guard['noiseless_blur']['output_mae']<guard['noiseless_blur']['Raw_mae'],'nontrivial restoration retained')
    check(all(x['base_equal'] and not x['status']['exact_preservation_guaranteed'] for x in guard['real_checks']),'unknown real inputs never falsely certified clean')
    old=verify_old();check(old['unchanged'],'all older protected sources unchanged')
    for p in (ROOT/'scripts').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
    size=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file());check(size<3*2**30,'registered3GiBbudget')
    result=dict(verification_passed=not failures,failures=failures,checks=checks,old_sources=old,numerical_correlation_max_error=max(numerical),fullfield_output_count=48,fullfield_pair_count=24,old_core_max_difference=max(parity),maximum_fullfield_Raw_difference=max(differences),native_SEM_scale_factor=factor,native_size_rows=len(sizes),new_optimizer_updates=0,absolute_physical_accuracy_qualified=False,universal_real_clean_detection_claimed=False,model_promoted=False,size_gib=size/2**30)
    save(ROOT/'results/repair_verification.json',result);print(json.dumps({k:v for k,v in result.items() if k!='checks'}),flush=True)
    if failures:raise RuntimeError('Repair verification failed; preserve and resolve discrepancy')

if __name__=='__main__':main()
