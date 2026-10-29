"""Read-only R61 training/evaluation provenance audit, separate from model scores."""
from r135_common import *
import pandas as pd,cv2,re,collections
from openpyxl import load_workbook
from scipy.io import loadmat
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[6]

def main():
    out=ROOT/'results/r61_training_audit';out.mkdir(exist_ok=False);plan=load(ROOT/'config/plan.json');cp=Path(plan['models']['R61']['checkpoint']['path']);assert sha(cp)==plan['models']['R61']['checkpoint']['sha256']
    lab=REPO/'Thesis_MOSR_Evidence/LabSystem_MOSR';exp=lab/'Experiments/R61_BoundaryGeneralizationUniversal';data=lab/'Training_Data/r61_universal_boundary_generalization/hs100mg_basler/r61_universal_boundary_train_motion_texture_step_guard_v16';manifest=load(data/'manifest.json');split=data/'splits/grouped_seed1337_val100';meta=load(split/'split_meta.json');train=np.load(split/'train_idx.npy');val=np.load(split/'val_idx.npy');paths=meta['source_paths_sorted'];assert len(paths)==20296 and len(set(paths))==20296;assert len(train)==18266 and len(val)==2030 and not set(train)&set(val)
    normalize=lambda p:str(p).replace('\\','/');by_path={normalize(r['package_src']):r for r in manifest['pairs']};assert set(map(normalize,paths))==set(by_path);partition={normalize(paths[int(i)]):'train' for i in train};partition.update({normalize(paths[int(i)]):'val' for i in val});rows=[]
    for path in paths:
        r=by_path[normalize(path)];rows.append(dict(split=partition[normalize(path)],path=normalize(path),role=r['role'],domain=r.get('domain',''),feature=r.get('feature',''),sem_reference_id=r.get('sem_reference_id'),sem_radius_nm=r.get('sem_radius_nm'),target_radius_nm=r.get('target_radius_nm')))
    roster=pd.DataFrame(rows);roster.to_csv(out/'training_roster.csv',index=False);counts=roster.groupby(['role','split']).size().unstack(fill_value=0);counts.to_csv(out/'role_counts.csv')
    r60=data.parent.parent.parent/'r60_sem_truth_boundary/hs100mg_basler/r60_sem_truth_realcrop_anchor_train';r60manifest=load(r60/'manifest.json');parent=Path(r60manifest['microscope_image']);csv=Path(r60manifest['sem_reference_csv']);csvdata=pd.read_csv(csv);workbook=Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/20260618_100MG/SEM_data/via_pilar.xlsx'));w=load_workbook(workbook,read_only=True,data_only=True);sheet=w['SEM data'];reference=[]
    for row in sheet.iter_rows(min_row=3,max_row=38,values_only=True):reference.append([int(row[16]),float(row[17]),float(row[18])])
    ref=pd.DataFrame(reference,columns=['index','via','pillar']).set_index('index');c=csvdata.set_index(csvdata.columns[0]);assert len(ref)==len(c)==36;diff=float(np.abs(ref[['via','pillar']].values-c.values).max());assert diff<1e-9;ref.to_csv(out/'SEM_reference_values.csv')
    # Reference layout used for the current SEM comparison is exactly the same
    # indexed36value grid in the source workbook; this is reference reuse, not
    # a claim that current optical photos have identical pixels.
    gt=loadmat(ROOT/'validation/sem_reference.mat',variable_names=['global_index']);grid=gt['global_index'];workgrid=np.asarray([[sheet.cell(row,column).value for column in range(10,16)] for row in range(5,11)],float);expected=np.array([[ref.loc[int(i),'pillar'] for i in rr] for rr in grid]);assert np.allclose(workgrid,expected,rtol=0,atol=1e-9)
    semrows=roster[roster.role=='sem_truth_anchor'];checks=[]
    for r in semrows.itertuples():
        assert r.feature in ['pillar','via'];expected=float(ref.loc[int(r.sem_reference_id),r.feature]);assert abs(r.sem_radius_nm-expected)<1e-9 and abs(r.target_radius_nm-expected)<1e-9;checks.append(dict(split=r.split,feature=r.feature,sem_id=int(r.sem_reference_id),value_nm=expected,domain=r.domain))
    pd.DataFrame(checks).to_csv(out/'SEM_target_matches.csv',index=False)
    # Recreate actual retained real-source crops and their SEM-derived target
    # images using pure helpers, never invoking the destructive dataset builder.
    generator=module('r61_audit_r60_generator',lab/'Experiments/R60_SEMTruthBoundaryTraining/scripts/prepare_r60_sem_truth_dataset.py');image=generator._read_gray(parent);template=generator._template_rows(Path(r60manifest['template_csv']),'原圖');refs=generator.read_sem_reference(csv);by_id={(r['feature'],r['id']):r for r in template};replay=[];seen={}
    for r in manifest['pairs']:
        if r.get('domain')!='real_microscope_crop':continue
        key=r['feature'],int(r['template_id']);src=data/r['package_src'];lbl=data/r['package_lbl'];stored_src=generator._read_gray(src);stored_lbl=generator._read_gray(lbl)
        if key not in seen:
            row=by_id[key];crop=generator._extract_centered_crop(image,row['x_px'],row['y_px'],stored_src.shape[0]);target,n=generator._draw_sem_field_label(crop=crop,center_row=row,all_rows=template,refs=refs,crop_size=stored_src.shape[0]);seen[key]=(crop,target)
        a,b=seen[key];assert np.array_equal(a,stored_src) and np.array_equal(b,stored_lbl);replay.append(dict(path=r['package_src'],split=partition[normalize(r['package_src'])],feature=key[0],template_id=key[1],source_exact=True,target_exact=True))
    pd.DataFrame(replay).to_csv(out/'real_crop_and_target_replay.csv',index=False)
    # Exact full-image pixel identities, not filenames or acquisition-folder dates.
    def pixels(p):
        a=cv2.imdecode(np.fromfile(p,np.uint8),cv2.IMREAD_GRAYSCALE);assert a is not None;return a,hashlib.sha256(str(a.shape).encode()+a.tobytes()).hexdigest()
    _,parenthash=pixels(parent);identities=[]
    for f in plan['frames']:
        a,h=pixels(f['source']['path']);identities.append(dict(role='motion',sequence=f['sequence'],frame=f['frame_index'],same_as_training_parent=h==parenthash,shape=str(a.shape),pixel_sha256=h))
    for e,s in plan['SEM_sources'].items():
        a,h=pixels(s['path']);identities.append(dict(role='SEM_optical',frame=int(e),same_as_training_parent=h==parenthash,shape=str(a.shape),pixel_sha256=h))
    pd.DataFrame(identities).to_csv(out/'evaluation_full_image_identity.csv',index=False)
    # Final-stage group split does not necessarily separate allSEM identities.
    ids={s:set((r['feature'],r['sem_id']) for r in checks if r['split']==s) for s in ['train','val']};shared=sorted(ids['train']&ids['val'])
    # Resolve the actual continuation chain from training log headers and RUN paths.
    logs={}
    for f in (exp/'reports/training_logs').glob('*.out.log'):
        text=f.read_text(encoding='utf-8-sig',errors='replace')
        try:header,_=json.JSONDecoder().raw_decode(text.lstrip())
        except ValueError:continue
        found=re.search(r'^\[RUN\] progress_dir=(.+)$',text,re.M)
        if found:logs[str(Path(found.group(1).strip()).resolve()).casefold()]=(f,header,text)
    lineage=[];current=cp;visited=set()
    for _ in range(12):
        directory=current.parent.parent if current.parent.name=='weights' else current.parent;key=str(directory.resolve()).casefold()
        if key in visited or key not in logs:break
        visited.add(key);f,h,text=logs[key];lineage.append(dict(checkpoint=record(current),log=record(f),candidate=h.get('candidate'),data_dir=h.get('data_dir'),base_checkpoint=h.get('base_checkpoint'),scratch_training=h.get('scratch_training'),num_epoch=h.get('num_epoch'),lr=h.get('lr'),finetune_lines=[s for s in text.splitlines() if s.startswith('[FINETUNE]')],split_lines=[s for s in text.splitlines() if '[DATA][SPLIT]' in s]))
        base=h.get('base_checkpoint')
        if not base or not Path(base).exists():break
        current=Path(base)
    assert lineage and 'load external fixed split' in '\n'.join(lineage[0]['split_lines']);save(out/'lineage.json',dict(chain=lineage,unresolved_older_checkpoint=str(current)))
    final=torch.load(cp,map_location='cpu')['state_dict'];base=torch.load(lineage[0]['base_checkpoint'],map_location='cpu')['state_dict'];changed=[k for k in final if k in base and not torch.equal(final[k],base[k])];unchanged=[k for k in final if k in base and torch.equal(final[k],base[k])];save(out/'inherited_tensor_comparison.json',dict(changed=changed,unchanged_count=len(unchanged),missing_in_parent=[k for k in final if k not in base]))
    # Decode role information for training-vs-validation counts without printing
    # the large manifest. Existing labels are the inspected artifacts, not claims.
    inputs=[cp,data/'manifest.json',split/'split_meta.json',split/'train_idx.npy',split/'val_idx.npy',r60/'manifest.json',csv,workbook,parent,Path(generator.__file__),exp/'scripts/launch_r61.py',ROOT/'config/plan.json']
    verdict=dict(checkpoint=record(cp),train_count=len(train),val_count=len(val),role_counts=counts.to_dict(),sem_target_rows=len(checks),sem_target_train=sum(r['split']=='train' for r in checks),real_crop_replayed=len(replay),real_crop_train=sum(r['split']=='train' for r in replay),unique_real_crop_features=len(seen),training_parent=record(parent),exact_same_parent_in_current204=sum(r['same_as_training_parent'] for r in identities),SEM_csv_matches_workbook_max_error_nm=diff,SEM_grid_ids_match_current_reference=True,shared_SEM_id_between_train_val=len(shared),shared_SEM_ids=shared,changed_from_immediate_parent=changed,lineage_runs=len(lineage),inherited_training_not_fully_audited=True,scope='Positive proof of reused SEM size supervision and same static-photo crop/target training. No direct current201photo inclusion established by this full-parent hash check; arbitrary transformed crops and earlier ancestor data remain outside this negative result.',inputs=[record(p) for p in inputs]);save(out/'summary.json',verdict)
    assert sha(cp)==plan['models']['R61']['checkpoint']['sha256'];print(json.dumps({k:v for k,v in verdict.items() if k not in ['inputs','shared_SEM_ids','checkpoint','training_parent','role_counts','changed_from_immediate_parent']},ensure_ascii=False,indent=2));print(counts.to_string());print('Changed parent tensors',changed)
if __name__=='__main__':main()
