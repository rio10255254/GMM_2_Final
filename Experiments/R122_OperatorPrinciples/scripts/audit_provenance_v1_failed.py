"""Read-only V42 final-run lineage audit; all outputs go under R122."""
import csv, hashlib, json, pathlib, collections
import numpy as np
import cv2
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]

ROOT = pathlib.Path(str(PROJECT_ROOT))
E = ROOT/'Experiments/R122_OperatorPrinciples'
V = ROOT/'Deliverables/Standalone_Models/V42_SoftLabelSNR_FullStandalone_20260709'
D = V/'training_data'
fingerprints = {}
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest()
def protect(p):
    p=pathlib.Path(p); fingerprints[str(p)]=sha(p); return p
def read(p): return json.loads(protect(p).read_text(encoding='utf-8-sig'))
def table(name,rows):
    if not rows:return
    with (E/'results'/name).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    m=read(D/'manifest.json'); sd=D/'splits/grouped_seed1337_val120';s=read(sd/'split_meta.json')
    split={k:np.load(protect(sd/(k+'_idx.npy'))).tolist() for k in ['train','val']}
    assert not set(split['train']) & set(split['val'])
    assert sorted(split['train']+split['val'])==list(range(len(s['source_paths_sorted'])))
    paths=s['source_paths_sorted']; bypath={p['package_src']:p for p in m['pairs']}
    assert len(bypath)==len(paths)==11254
    # Reproduce the lexical source ordering used by collect_image_paths.
    disk=sorted(str(p.relative_to(D)).replace('\\','/') for p in (D/'src').rglob('*.bmp'))
    assert disk==paths, 'Split ancestry cannot be bound to current source ordering'
    ps={k:[bypath[paths[i]] for i in indices] for k,indices in split.items()}
    roles=[]
    for role in sorted(set(p['role'] for p in m['pairs'])):
        roles.append({'role':role,**{k:sum(p['role']==role for p in pp) for k,pp in ps.items()}})
    table('v42_split_roles.csv',roles)
    cfg=read(ROOT/'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/config/sequence_center9_50x20x.json')
    selection=protect(ROOT/'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/tables/top30_raw_motion_selection.csv')
    selected=list(csv.DictReader(selection.open(encoding='utf-8-sig')))
    # Actual frame ancestry supersedes role-specific group names.
    key=lambda p:(p.get('target_dataset'),p.get('target_sequence'),p.get('source_frame_name'))
    aset={k:{key(p) for p in pp if all(key(p))} for k,pp in ps.items()}
    shared=aset['train']&aset['val']
    table('v42_shared_frame_ancestry.csv',[dict(zip(['dataset','sequence','frame'],k)) for k in sorted(shared)])
    seqrows=[]; matches=[]; pixel_checks=[]
    for name,c in cfg['sequences'].items():
        train=[p for p in ps['train'] if p.get('target_dataset')==c['dataset'] and p.get('target_sequence')==c['group']]
        evalnames={p.name for p in pathlib.Path(ROOT / c['raw_dir']).glob('*.bmp')}
        trainnames={p.get('source_frame_name') for p in train}
        selected_pairs=[int(r['end_frame_index']) for r in selected if r['sequence']==name and r['top30_raw_motion_selected']=='1']
        both=sum(f'frame_{i-1:04d}.bmp' in trainnames and f'frame_{i:04d}.bmp' in trainnames for i in selected_pairs)
        seqrows.append({'sequence':name,'evaluation_frames':len(evalnames),'train_eligible_rows':len(train),'evaluation_frames_with_train_ancestry':len(evalnames&trainnames),'selected_pairs':len(selected_pairs),'selected_pairs_both_frames_have_train_ancestry':both})
        for p in train:
            if p.get('source_frame_name') in evalnames:
                matches.append({'sequence':name,'role':p['role'],'frame':p['source_frame_name'],'package_src':p['package_src'],'label_source':p.get('label_source'),'crop_x':p.get('crop_x'),'crop_y':p.get('crop_y'),'crop_size':p.get('crop_size')})
        # Pixel-level lineage checks for all unshifted pseudo-boundary crops.
        rawcache={}
        for p in train:
            if p['role']!='target_real_pseudo_boundary':continue
            f=p['source_frame_name'];src=pathlib.Path(ROOT / c['raw_dir'])/f
            if f not in rawcache:rawcache[f]=cv2.imread(str(protect(src)),cv2.IMREAD_GRAYSCALE)
            raw=rawcache[f]; x,y,n=(p[k] for k in ['crop_x','crop_y','crop_size'])
            patch=cv2.imread(str(protect(D/p['package_src'])),cv2.IMREAD_GRAYSCALE)
            expected=raw[y:y+n,x:x+n]
            same_shape=expected.shape==patch.shape
            err=float(np.max(np.abs(expected.astype(float)-patch))) if same_shape else None
            pixel_checks.append({'sequence':name,'frame':f,'package_src':p['package_src'],'shape_match':same_shape,'max_abs_gray':err,'exact_pixels':same_shape and err==0})
    table('v42_evaluation_overlap.csv',seqrows);table('v42_training_evaluation_ancestry.csv',matches);table('v42_source_pixel_checks.csv',pixel_checks)
    r60=ROOT/'LabSystem_MOSR/Training_Data/r60_sem_truth_boundary/hs100mg_basler/r60_sem_truth_realcrop_anchor_train'
    r60m=read(r60/'manifest.json');sem=[p for p in ps['train'] if p['role']=='sem_truth_anchor']
    # Bind inherited paired payload to its original R60 source by exact relative name/hash.
    semchecks=[]
    for p in sem:
        rel=pathlib.Path(p['package_src']).relative_to('src/stage_36_r61_sem_truth_anchor')
        for side in ['src','lbl']:
            origin=r60/side/rel; current=D/p['package_'+side]
            semchecks.append({'package_path':p['package_'+side],'source_path':str(origin),'origin_exists':origin.exists(),'same_hash':sha(protect(origin))==sha(protect(current)) if origin.exists() else False})
    table('v42_sem_anchor_lineage.csv',semchecks)
    static=ROOT/'Thesis_MOSR_Evidence/20260618_100MG/Image__2026-06-18__17-10-31.bmp'
    semref=pathlib.Path(ROOT / r60m['sem_reference_csv']);protect(semref);protect(static)
    run=V/'results/training_results/training_progress_V42_SoftLabelSNR_full_training_20260709_202710_20260709_202713'
    runmeta=read(run/'run_meta.json');ck=protect(run/'epoch_120.pth.tar')
    logp=protect(V/'results/run_logs/full_training_20260709_202710/train_stdout.log');log=logp.read_text(encoding='utf-8',errors='replace')
    protect(V/'train_v42.py');protect(V/'model_v42.py');protect(V/'weights/base_v41_standalone_best_tradeoff.pth.tar')
    assert 'samples=9857->12321' in log and 'Starting Epoch 120/120' in log
    assert str(sd) in log
    summary={'run_id':runmeta['run_tag'],'checkpoint_sha256':fingerprints[str(ck)],'image_split_counts':{k:len(v) for k,v in ps.items()},'role_counts':roles,'train_val_common_source_frames':len(shared),'train_val_unique_frame_counts':{k:len(v) for k,v in aset.items()},'evaluation_overlap':seqrows,'pixel_checks':{'count':len(pixel_checks),'exact':sum(x['exact_pixels'] for x in pixel_checks),'maximum_abs_gray':max(x['max_abs_gray'] or 0 for x in pixel_checks)},'sem_anchor':{'train_rows':len(sem),'real_crop_rows':sum(p.get('domain')=='real_microscope_crop' for p in sem),'sem_answer_rows':sum(p.get('label_source')=='sem_truth' for p in sem),'payload_checks':len(semchecks),'matching_source_hashes':sum(x['same_hash'] for x in semchecks),'original_microscope_image':str(ROOT / r60m['microscope_image']),'same_static_evaluation_image':pathlib.Path(ROOT / r60m['microscope_image'])==static,'sem_reference_csv':str(semref)},'limitations':['Membership records establish eligibility, not per-example weighted-sampler consumption.','Auxiliary sequence and motion samplers access the same package separately; image split is a conservative lower bound on training access.','V42 starts from V41 and uses teacher outputs. Full ancestor pretraining contamination was not reconstructed.','No conclusion about intent or whether historical same-sample adaptation was disclosed in every thesis passage.','Supervised truth is legitimate in training; these reused samples cannot establish unseen evaluation.']}
    (E/'results/v42_provenance_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    (E/'results/protected_inputs.json').write_text(json.dumps(fingerprints,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['role_counts','limitations']},indent=2))
if __name__=='__main__':main()
