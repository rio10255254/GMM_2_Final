from common import *
import ast,shutil
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
def main():
    for d in ['config','results','validation']:(P/d).mkdir(exist_ok=True)
    oldpanel=load(E/'config/motion_panel.json');plan=load(str(PROJECT_ROOT / oldpanel['source_plan']['path']));seed=load(E/'results/screening_decision.json')['selected_seed_by_dev_only'];assert seed==1342001
    sources=[record(E/'results/long_admission.json'),record(E/'config/full_motion_admission.json'),record(E/'config/study.json'),*load(E/'config/packaging_source_binding.json')['sources']]
    sources += [record(E/f'runs/R134_{a}_s{s}/step0512.pth') for a in ['A','C'] for s in [1342001,1342002]]
    sources += [record(Path(PROJECT_ROOT / oldpanel[k]['path'])) for k in ['source_plan','configuration','sessions']]
    save(P/'config/protocol.json',dict(revision='R134_P1_precision_preserved',created_utc=now(),origin='User-authorized post-diagnosis development revalidation; not unseen confirmation',model_changed=False,training_changed=False,selected_seed=seed,measurement='Reload exact float32 model values from lossless npy; uint8 preview not admitted as measurement input',motion='All201 Cselected frames plus original24fullframes each for matchedAseed1,Aseed2,Cseed2; same12pairs and all original120/194/3populations',sem='Both A/C seeds and Raw, all3normalexposures/36pillars; preserve values through crop normalization, all arms same extraction; fixed existingSEMreference remains unchanged',rules=load(E/'config/full_motion_admission.json'),original_stage1=load(E/'config/study.json')['screens'],reuse_generated_validation='Network and training objective unchanged, retain all original two-seed generated/clean results and dev-based seed choice',long_training='Only if both-seed SEM/12pair and selected full201 pass same thresholds; independent precision-aware package and actual package tests before8192additionalupdates',B_D='unexecuted pending independent calibration',protected=sources))
    for name in ['reference_circle_core.py','readout_helpers.py','sem_reference.mat','__init__.py']:shutil.copy2(E/'validation'/name,P/'validation'/name)
    shutil.copy2(str(PROJECT_ROOT / oldpanel['sessions']['path']),P/'validation/sessions.csv')
    old=(E/'validation/extract_sem.m').read_text(encoding='utf-8-sig');new=old.replace('function extract_sem(out)','function extract_sem_precise(out)').replace("cells=zeros(104,104,36,3,'uint8')","cells=zeros(104,104,36,3,'double')").replace("im=imread(fullfile(out,sprintf('sem%d.png',exposures(k))));","payload=load(fullfile(out,sprintf('sem%d_values.mat',exposures(k)))); im=double(payload.image); assert(all(isfinite(im),'all') && min(im,[],'all')>=0 && max(im,[],'all')<=1);").replace('im2uint8(mat2gray(cellim))','mat2gray(cellim)')
    assert 'im2uint8(mat2gray(cellim))' not in new and "'double'" in new
    (P/'validation/extract_sem_precise.m').write_text(new,encoding='utf-8')
    repo=E.parent.parent;parts=['import numpy as np,pandas as pd\nimport skimage.segmentation.morphsnakes as morphsnakes\nfrom pathlib import Path\nSESSION_TABLE=Path(__file__).parent/"validation/sessions.csv"\n']
    for path,names in [(repo/'Experiments/R128_SourceOnlyFullTraining/analysis/lsc_comparison/measure.py',['measure_frame','pair_table']),(repo/'Experiments/R80_InflectionReferenceCircleSEMValidation/scripts/run_displacement_lsc.py',['session_prediction','summarize_pairs']),(repo/'Experiments/R116_CoherentGeometryAnchorScratch/validation/run_lsc_e42.py',['reset_curvature_cycle'])]:
        text=path.read_text(encoding='utf-8-sig');tree=ast.parse(text)
        for name in names:parts.append(ast.get_source_segment(text,next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)))
    (P/'readout.py').write_text('\n\n'.join(parts),encoding='utf-8')
    reg=repo/'docs/operations/PROJECT_STORAGE_REGISTRY.json';v=load(reg);save(P/'results/storage_before.json',v);entry=next(x for x in v['entries'] if x['id']=='r134_direct_state');entry['budget_gib']=12;entry['precision_revision']='active_user_authorized_revalidation';atomic(reg,v)
    save(P/'results/prepared.json',dict(protocol=record(P/'config/protocol.json'),no_old_artifact_modified=True));print('Prepared independent precision revision')
if __name__=='__main__':main()
