"""Copy the authorized standalone payload without altering source experiments."""
import sys,shutil,ast,json,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from common import *
import numpy as np,cv2

def main():
    target=REPO/'Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/R129_OpticalHybrid_Standalone_20260912'
    if target.exists():raise FileExistsError(target)
    registry=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';before=load(registry)
    save(ROOT/'config/standalone_storage_before.json',before)
    before['entries'].append(dict(id='r129_standalone_long_training',path=target.relative_to(REPO).as_posix(),tier='active',state='building_standalone_and_preflight',budget_gib=12,action='protect',priority=0,keep='User-requested independent package copy of all R128 source data, organized R129 D, fixed calibration and real development panel; one8192-update continuation; retain originals and all adverse results',blocked_by=[]))
    registry.write_text(json.dumps(before,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    target.mkdir();copied=[]
    def copy(source,relative):
        destination=target/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
        a=sha(source);b=sha(destination)
        if a!=b:raise RuntimeError('Copy mismatch')
        copied.append(dict(source=str(source),destination=relative,sha256=a))
    for p in (ROOT/'package_source').glob('*.py'):copy(p,p.name)
    for p in (ROOT/'model/organized').glob('*.py'):copy(p,'model/'+p.name)
    copy(ROOT/'runs/D/step24.pth','weights/initial_r129.pth')
    copy(ROOT/'data/measured_psf_bank.npz','calibration/measured_psf_bank.npz')
    copy(ROOT/'data/PSF_PROVENANCE.json','docs/PSF_PROVENANCE.json')
    cfg=dict(model_name='R129_OpticalHybrid_LongTraining',seed=1299001,order_seed=1299002,noise_seed=1299003,splits={'train':512,'dev':128,'test':128},updates=8192,epochs=16,save_every=128,optimizer=dict(name='AdamW',peak_lr=.0001,minimum_lr=.00001,warmup_updates=128,weight_decay=.00001,gradient_clip=5),dev_steps=list(range(0,8193,512)),real_steps=[0,512,2048,4096,8192],loss=dict(image=1.,gradient=.2,pair=.2),initial_weights='weights/initial_r129.pth',training_inputs='Source images only plus fixed inherited optical calibration buffers',continuation='Same D prototype, all existing learnable parameters enabled; optimizer reset, not from-scratch',physical_calibration_qualified=False,real_panel_is_reused_development=True,generated_test_is_historical_not_new_holdout=True,selection='All scheduled checkpoints reported; final8192 is planned endpoint, no automatic deployment change',source_data_note='512 procedural parent pairs; new independent noise every epoch, not8192independentgeometries',training_target_note='Native output objective matches R129 short pilot; no latent/observation loss or absent branch claimed',data_fit_limits='Fixed measured prior is not the true per-scene PSF; diverse source blur is robustness training, not proof of instrument fit',architecture_changes=False)
    def write(relative,value):
        p=target/relative;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('x',encoding='utf-8') as f:f.write(value)
    write('config/training.json',json.dumps(cfg,ensure_ascii=False,indent=2))
    manifest=load(R128/'data/package/manifest.json')
    for i,e in enumerate(manifest['entries']):
        for key in ['arrays_path','metadata_path']:copy(R128/'data/package'/e[key],'training_data/'+e[key].replace('\\','/'))
        if (i+1)%128==0:print('Copied source parents',i+1,'/',len(manifest['entries']),flush=True)
    copy(R128/'data/package/manifest.json','training_data/manifest.json')
    copy(R128/'data/package/plan.json','docs/original_data_plan.json')
    for p in ['R129_RESULTS.md','R129_ARCHITECTURE.md']:copy(ROOT/'reports'/p,'docs/'+p)
    for p in (ROOT/'reports/figures').glob('R129_organized_architecture.*'):copy(p,'docs/figures/'+p.name)
    for p in ['summary.csv','per_pillar.csv','per_measurement.csv']:copy(ROOT/'results/sem'/p,'validation/baseline/sem_'+p)
    copy(ROOT/'results/motion_centers.csv','validation/baseline/motion_centers.csv')
    copy(ROOT/'results/motion_pairs.csv','validation/baseline/motion_pairs.csv')
    copy(REPO/'Experiments/R70_V42ACMContourSEMValidation/results/masks/acm_primary_masks.mat','validation/sem_reference.mat')
    copy(REPO/'Experiments/R80_InflectionReferenceCircleSEMValidation/scripts/reference_circle_core.py','validation/reference_circle_core.py')
    write('validation/__init__.py','')
    def extract(path,names):
        nodes={n.name:n for n in ast.parse(path.read_text(encoding='utf-8-sig')).body if isinstance(n,ast.FunctionDef)}
        return '\n\n'.join(ast.unparse(nodes[n]) for n in names)
    helpers=extract(REPO/'Experiments/R80_InflectionReferenceCircleSEMValidation/scripts/run_sem36_contour_validation.py',['mask_center_radius','radial_signature'])
    helpers+='\n\n'+extract(REPO/'Experiments/R116_CoherentGeometryAnchorScratch/validation/run_lsc_e42.py',['reset_curvature_cycle'])
    write('validation/readout_helpers.py','import numpy as np\nimport skimage.segmentation.morphsnakes as morphsnakes\n\n'+helpers+'\n')
    write('objectives.py','import math\nimport torch\n\n'+extract(R128/'training/objectives.py',['robust_gray','translated'])+'\n')
    panel=load(ROOT/'config/real_panel.json');sequences=load(panel['sequence_config']['path'])['sequences']
    sys.path.insert(0,str(R128/'analysis/lsc_comparison'));from measure import reader
    _,scope=reader(load(R128/'results/lsc_comparison/plan.json'));images=[]
    for item in panel['sem']:
        name=f"sem{item['exposure']}";relative='validation/inputs/'+name+'.png';raw=cv2.imread(item['source']['path'],0)
        p=target/relative;p.parent.mkdir(parents=True,exist_ok=True);assert cv2.imwrite(str(p),raw)
        images.append(dict(name=name,kind='sem',path=relative,sha256=sha(p),original_source=item['source']))
        copy(ROOT/'results/real/D_24'/(name+'.png'),'validation/baseline/'+name+'.png')
        if item['exposure']==14:copy(item['source']['path'],'sample_inputs/pillar_normal.bmp')
    for item in panel['motion']:
        s=sequences[item['sequence']];x0,y0,x1,y1=item['box'];raw=cv2.imread(item['source']['path'],0)[y0:y1,x0:x1]
        name=f"{item['sequence']}_{item['frame_index']:04d}";relative='validation/inputs/'+name+'.png';p=target/relative;assert cv2.imwrite(str(p),raw)
        prediction=scope['session_prediction'](item['sequence'],item['frame_index'],np.asarray(s['centers'],float),s['expected_signed_dx_px'])
        centers=[[int(pid),float(x-x0),float(y-y0)] for pid,x,y in prediction]
        images.append(dict(name=name,kind='motion',path=relative,sha256=sha(p),sequence=item['sequence'],frame_index=item['frame_index'],global_origin=[x0,y0],centers_local=centers,original_source=item['source']))
        copy(ROOT/'results/real/D_24'/(name+'.png'),'validation/baseline/'+name+'.png')
    keys=['pitch_px','radius_px','magnification','object_um_per_px','nominal_step_um']
    write('validation/panel.json',json.dumps(dict(images=images,motion_pairs=panel['motion_plan'],sequences={k:{j:v[j] for j in keys} for k,v in sequences.items() if k in {x['sequence'] for x in panel['motion_plan']}},scope='Same three full SEM fields and four fixed ROI motion pairs as R129 pilot; no temporal SD or full-thesis qualification'),ensure_ascii=False,indent=2))
    old=(ROOT/'scripts/extract_sem.m').read_text(encoding='utf-8-sig');helper=old[old.index('function centers = sort_grid_centers'):]
    wrapper="""function extract_sem(out)
root=fileparts(fileparts(mfilename('fullpath')));
old=load(fullfile(root,'validation','sem_reference.mat'));
exposures=[13 14 15];masks=false(104,104,36,3);cells=zeros(104,104,36,3,'uint8');valid=true(36,3);
for k=1:3
 im=imread(fullfile(out,sprintf('sem%d.png',exposures(k))));
 for gy=1:6
  for gx=1:6
   id=double(old.global_index(gy,gx));center=old.opt_centers((gy-1)*6+gx,:);
   cellim=extract_padded_cell(im,center,52);cells(:,:,id,k)=im2uint8(mat2gray(cellim));
   try
    masks(:,:,id,k)=segment_acm(cellim,40,200,1.0,45);
   catch ME
    valid(id,k)=false;fprintf('Failed pillar %d: %s\\n',id,ME.message);
   end
  end
 end
end
save(fullfile(out,'sem_masks.mat'),'masks','cells','valid','-v7');
if ~all(valid,'all'),error('Invalid SEM cases retained');end
end

"""
    write('validation/extract_sem.m',wrapper+helper)
    # Host interpreter discovery is environment setup, not a dependency on the research checkout.
    write('START_R129.cmd','@echo off\r\ncd /d "%~dp0"\r\nif defined R129_PYTHON (\r\n  "%R129_PYTHON%" -B control.py menu\r\n) else if exist "%USERPROFILE%\\anaconda3\\python.exe" (\r\n  "%USERPROFILE%\\anaconda3\\python.exe" -B control.py menu\r\n) else (\r\n  python -B control.py menu\r\n)\r\npause\r\n')
    write('requirements.txt','numpy\nscipy\npandas\nopencv-python\nscikit-image\npsutil\ntorch==2.3.0\n')
    write('results/README.md','# Results\n\npreflight: bounded real checks and resume tests. training: long runs, immutable checkpoints, attempt ledgers and scheduled evaluations. inference: manually requested image outputs. launcher_logs: mutable process logs. No run is complete merely because its process stopped.\n')
    write('PROVENANCE.json',json.dumps(dict(created_utc=now(),copied_files=copied,source_R129=str(ROOT),data_copy_reason='User explicitly requested a package usable independently of the source project',runtime_uses_package_local_payload=True,no_original_files_modified=True),ensure_ascii=False,indent=2))
    save(ROOT/'config/standalone_build.json',dict(created_utc=now(),path=str(target),source=record(__file__),copied_files=len(copied),planned_updates=8192))
    print('Standalone payload created:',target,flush=True)

if __name__=='__main__':main()
