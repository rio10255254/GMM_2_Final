"""Prepare writing materials from preserved sources. No model or Word editing."""
from pathlib import Path
import hashlib,json,shutil,sys,re,zipfile,xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import cv2

sys.stdout.reconfigure(encoding='utf-8')
REPO=Path(r'D:\GMM_2_Final')
EXP=REPO/'Experiments/R129_OpticalPriorHybrid'
PKG=REPO/'Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/R129_OpticalHybrid_Standalone_20260912'
HANDOFF=REPO/'Deliverables/R129_Corrected_Corner9_Thesis_Handoff_20260920'
OUT=REPO/'Deliverables/R129_Thesis_Rewrite_Ready_20260920'
DOC=Path(r'C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文_v34_SEM與不利論述_完整標註版.docx')
RUN=PKG/'results/training/r129_long_01'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
copies=[]
def cp(src,rel):
    src=Path(src);dst=OUT/rel;dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst);h=sha(src);assert sha(dst)==h
    copies.append(dict(source=str(src),destination=str(dst.relative_to(OUT)),sha256=h))
    return dst
def figsave(fig,name):
    for ext in ['png','svg']:fig.savefig(OUT/'05_Paper_Figures'/f'{name}.{ext}',dpi=200,bbox_inches='tight')
    plt.close(fig)

assert not OUT.exists(),'Use a new destination; do not overwrite a published material package.'
for d in ['00_Plan','01_Original_Thesis','02_Method_and_Training','03_Dataset','04_Results','05_Paper_Figures','06_Internal_Sources','07_Checks']:(OUT/d).mkdir(parents=True)
assert sha(DOC)=='d85a7987bbea8f5f58585334104f9d0425f3a42a92e51bbbb187cca2c5a9fc12'
cp(DOC,'01_Original_Thesis/thesis_v34_original_unchanged.docx')

for item in load(HANDOFF/'MANIFEST.json'):assert sha(HANDOFF/item['path'])==item['sha256'],item['path']
for src in sorted(HANDOFF.rglob('*')):
    if src.is_file():cp(src,Path('04_Results/R129_Handoff')/src.relative_to(HANDOFF))
print('Original thesis and R129 result package copied and verified.',flush=True)

for name in ['training.json']:cp(PKG/'config'/name,'02_Method_and_Training/'+name)
for name in ['run_plan.json','completion.json','latest_checkpoint.json']:cp(RUN/name,'02_Method_and_Training/records/'+name)
for src in RUN.glob('updates*.jsonl'):cp(src,'02_Method_and_Training/records/'+src.name)
for src in (PKG/'model').glob('*.py'):cp(src,'06_Internal_Sources/model/'+src.name)
for name in ['data.py','engine.py','objectives.py','runtime.py','PROVENANCE.json','ENVIRONMENT.json']:
    cp(PKG/name,'06_Internal_Sources/training/'+name)
cp(PKG/'calibration/measured_psf_bank.npz','02_Method_and_Training/measured_psf_bank.npz')
cp(RUN/'checkpoints/step08192.pth','02_Method_and_Training/final_model_step08192.pth')
assert sha(OUT/'02_Method_and_Training/final_model_step08192.pth')=='086608339c6418b9dfd650f6809b1f7b45e65b6eb11452afe7df45c5b24ff1fd'
for name in ['R129_ARCHITECTURE.md','R129_LONG_TRAINING_RESULTS.md']:
    cp(EXP/'reports'/name,'06_Internal_Sources/research_reports/'+name)
for name in ['R128_METHODOLOGY.md','R128_FINAL_AUDIT.md']:
    cp(REPO/'Experiments/R128_SourceOnlyFullTraining/reports'/name,'06_Internal_Sources/initialization_history/'+name)
cp(REPO/'Experiments/R128_SourceOnlyFullTraining/config/study.json','06_Internal_Sources/initialization_history/study.json')
cp(REPO/'Experiments/R80_InflectionReferenceCircleSEMValidation/scripts/reference_circle_core.py','06_Internal_Sources/measurement/reference_circle_core.py')
cp(REPO/'Experiments/R136_PIRepeatability/scripts/lsc_core.py','06_Internal_Sources/measurement/lsc_core.py')

cfg=load(PKG/'config/training.json');manifest=load(PKG/'training_data/manifest.json')
cp(PKG/'training_data/manifest.json','03_Dataset/original_manifest.json')
entries=manifest['entries'];assert len(entries)==768
rows=[];metas={}
for i,e in enumerate(entries):
    ap=PKG/'training_data'/e['arrays_path'];mp=PKG/'training_data'/e['metadata_path']
    assert sha(ap)==e['arrays_sha256'] and sha(mp)==e['metadata_sha256'],e['parent_id']
    m=load(mp);metas[e['parent_id']]=m
    assert not m['external_source_inputs'] and not m['real_or_SEM_answers_used']
    cp(mp,Path('03_Dataset/all_parent_metadata')/e['metadata_path'])
    rows.append({k:e[k] for k in ['parent_id','split','index','category','geometry_sha256','arrays_sha256','metadata_sha256']}|dict(arrays_source_path=str(ap),metadata_source_path=str(mp),arrays_bytes=ap.stat().st_size))
    if (i+1)%128==0:print(f'Training source files verified: {i+1}/768',flush=True)
parents=pd.DataFrame(rows);parents.to_csv(OUT/'03_Dataset/all_768_parent_sources.csv',index=False,encoding='utf-8-sig')
counts=pd.crosstab(parents.category,parents.split).reindex(columns=['train','dev','test'])
assert counts.sum().to_dict()=={'train':512,'dev':128,'test':128}
counts.to_csv(OUT/'03_Dataset/category_counts.csv',encoding='utf-8-sig')
sets={s:set(parents[parents.split==s].geometry_sha256) for s in ['train','dev','test']}
overlap={f'{a}_{b}':len(sets[a]&sets[b]) for a,b in [('train','dev'),('train','test'),('dev','test')]}
assert not any(overlap.values())

logs=[json.loads(line) for p in sorted(RUN.glob('updates*.jsonl')) for line in p.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
assert len(logs)==8192 and sorted(x['step'] for x in logs)==list(range(1,8193))
logs=sorted(logs,key=lambda x:x['step']);trainids=set(parents[parents.split=='train'].parent_id)
assert {x['parent_id'] for x in logs}==trainids
for ep in range(16):assert {x['parent_id'] for x in logs if x['epoch']==ep}==trainids
error=max(abs(x['loss']-(x['terms']['image']+.2*x['terms']['gradient']+.2*x['terms']['pair'])) for x in logs)
assert error<1e-5
pd.DataFrame([dict(step=x['step'],epoch=x['epoch'],loss=x['loss'],learning_rate=x['learning_rate'],**x['terms']) for x in logs]).to_csv(OUT/'02_Method_and_Training/training_curve_all_steps.csv',index=False,encoding='utf-8-sig')
dev=[]
for step in cfg['dev_steps']:
    p=RUN/f'evaluations/step{step:05d}/dev.json';o=load(p);assert len(o['rows'])==128
    cp(p,f'02_Method_and_Training/records/dev_step{step:05d}.json');dev.append(dict(step=step,mean_loss=o['mean_loss']))
pd.DataFrame(dev).to_csv(OUT/'02_Method_and_Training/development_curve.csv',index=False,encoding='utf-8-sig')
cp(RUN/'evaluations/step08192/test.json','02_Method_and_Training/records/historical_generated_test.json')
plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,axs=plt.subplots(1,2,figsize=(11,4),layout='constrained')
loss=np.array([x['loss'] for x in logs]);axs[0].plot(np.arange(128,8193,128),loss.reshape(-1,128).mean(1),color='#147e9d')
axs[0].set(title='Training: 128-update block means',xlabel='Additional update',ylabel='Weighted training objective')
axs[1].plot([x['step'] for x in dev],[x['mean_loss'] for x in dev],marker='o',markersize=3,color='#147e9d')
axs[1].set(title='Development: same 128 parent scenes',xlabel='Additional update',ylabel='Mean development objective')
figsave(fig,'F03_training_and_development')

categories=['irregular_curved','corners_lines_junctions','dense_close_structures','textured_edges','clean_identity','noisy_identity','flat_negative']
labels=['Irregular curved boundaries','Lines, corners and junctions','Dense adjacent structures','Textured edges','Clean-image control','Noisy-image control','Flat-field control']
fig,axs=plt.subplots(7,3,figsize=(10,17),layout='constrained');examples=[]
for ri,cat in enumerate(categories):
    e=next(x for x in sorted(entries,key=lambda x:x['index']) if x['split']=='train' and x['category']==cat)
    m=metas[e['parent_id']];ap=PKG/'training_data'/e['arrays_path']
    with np.load(ap) as z:
        rng=np.random.default_rng(np.random.SeedSequence([cfg['noise_seed'],0,e['index']]))
        obs=np.rint(np.clip(z['noiseless'].astype(float)+rng.normal(0,m['noise_sigma_gray']/255,z['noiseless'].shape),0,1)*255).astype('uint8')
        norm=np.ascontiguousarray(obs[:,None,32:352,32:352].astype('float32')/np.float32(255))
        h=hashlib.sha256(norm.tobytes()).hexdigest();log=next(x for x in logs if x['epoch']==0 and x['parent_id']==e['parent_id']);assert h==log['actual_input_sha256']
        target=z['target'].copy()
    arrays=[obs[0,128:256,128:256]/255,target[0,128:256,128:256],obs[1,128:256,128:256]/255]
    for ci,a in enumerate(arrays):
        axs[ri,ci].imshow(a,cmap='gray',vmin=0,vmax=1,interpolation='nearest');axs[ri,ci].set_xticks([]);axs[ri,ci].set_yticks([])
        if ri==0:axs[ri,ci].set_title(['Observed image A','Clean target A','Observed shifted image B'][ci])
    axs[ri,0].set_ylabel(labels[ri],fontsize=10)
    sample=OUT/f'03_Dataset/examples/{cat}.npz';sample.parent.mkdir(exist_ok=True)
    np.savez_compressed(sample,epoch0_observed_uint8=obs,target=target)
    examples.append(dict(category=cat,parent_id=e['parent_id'],selection='first training parent by index within category',epoch=0,logged_step=log['step'],consumed_input_sha256=h,shift_xy=m['shift_xy'],source_file=str(ap),display_core=[128,256,128,256]))
figsave(fig,'F02_training_examples');save(OUT/'03_Dataset/example_sources.json',examples)

# Method-only flowchart, verified against package-local composition.
fig,ax=plt.subplots(figsize=(13,5.4));ax.set_xlim(0,13);ax.set_ylim(0,5.4);ax.axis('off')
boxes=[(.2,3.3,1.7,'Observed\nimage'),(2.25,3.3,2.1,'Measured optical\nconditioning'),(4.75,3.3,2.7,'Four shared\nreconstruction updates\nwith filtered upsampling'),(7.9,3.3,2.65,'Bounded detail addition\nto the original image'),(10.95,3.3,1.8,'Native-size\noutput')]
for x,y,w,txt in boxes:
    ax.add_patch(FancyBboxPatch((x,y),w,1.1,boxstyle='round,pad=0.03',facecolor='#edf5f8',edgecolor='#426777'));ax.text(x+w/2,y+.55,txt,ha='center',va='center',fontsize=10)
for left,right in zip(boxes,boxes[1:]):
    ax.annotate('',xy=(right[0]-.06,3.85),xytext=(left[0]+left[2]+.06,3.85),arrowprops=dict(arrowstyle='->',color='#333333',lw=1.4))
ax.plot([1.05,1.05,9.22],[3.25,2.45,2.45],color='#555555',lw=1.3);ax.annotate('',xy=(9.22,3.25),xytext=(9.22,2.45),arrowprops=dict(arrowstyle='->',color='#555555'))
ax.text(5.1,2.58,'Original-image reference and image-statistic strength control',ha='center',fontsize=10)
ax.text(6.5,4.9,'MOSR: image reconstruction and common measurement',ha='center',fontsize=15)
ax.text(6.5,1.75,'Global edge retention: 80 pixels + 16-pixel transition for this real-data result',ha='center',fontsize=10)
ax.text(6.5,1.1,'Same measurement for Raw and MOSR: ACM coarse contour → final edge points → circles / displacement',ha='center',fontsize=11)
ax.text(6.5,.4,'SEM and stage readouts are external references; they are not reconstruction inputs.',ha='center',fontsize=10)
figsave(fig,'F01_model_and_measurement')

# Actual saved image pair and measured coarse/final boundaries; first scan/frame/target, no outcome selection.
plan=load(HANDOFF/'04_Verification_and_Sources/config/plan.json');frame=plan['frames'][0];rawpath=Path(frame['source']['path']);assert sha(rawpath)==frame['source']['sha256']
record=load(REPO/'Experiments/R136_PIRepeatability/results/R129'/frame['run']/'01.json');rp=Path(record['values']['path']);assert sha(rp)==record['values']['sha256']
cp(rawpath,'05_Paper_Figures/example_source/first_raw.bmp');cp(rp,'05_Paper_Figures/example_source/first_reconstruction.npz')
raw=cv2.imread(str(rawpath),0).astype(float)/255
with np.load(rp) as z:recon=z['output'].astype(float)
fig,axs=plt.subplots(2,2,figsize=(8,8),layout='constrained');x0,x1,y0,y1=1576,1608,710,742
for col,(model,img) in enumerate([('Raw',raw),('R129',recon)]):
    f=HANDOFF/f'04_Verification_and_Sources/centers/{model}/{frame["run"]}.npz'
    with np.load(f) as z:coarse=z['coarse'][0,0];pts=z['points'][0,0]
    for row in range(2):
        axs[row,col].imshow(img[y0:y1,x0:x1],cmap='gray',vmin=0,vmax=1,interpolation='nearest',extent=(x0-.5,x1-.5,y1-.5,y0-.5))
        axs[row,col].set_xticks([]);axs[row,col].set_yticks([])
    axs[0,col].set_title('Raw' if model=='Raw' else 'MOSR reconstruction')
    cc=np.vstack([coarse,coarse[0]]);pp=np.vstack([pts,pts[0]])
    axs[1,col].plot(cc[:,0],cc[:,1],'--',color='#f1bb31',lw=1.5,label='ACM coarse contour')
    axs[1,col].plot(pp[:,0],pp[:,1],color='#14b4e0',lw=1.4,label='Final edge points')
    axs[1,col].set_xlim(x0-.5,x1-.5);axs[1,col].set_ylim(y1-.5,y0-.5)
axs[1,1].legend(loc='lower center',bbox_to_anchor=(.5,-.18),fontsize=9)
fig.suptitle('Same target and readout: coarse contour and final boundary',fontsize=13)
figsave(fig,'F04_ACM_and_final_boundary')
save(OUT/'05_Paper_Figures/example_source/provenance.json',dict(frame=frame,reconstruction=record,local_pillar=1,crop_xyxy=[x0,y0,x1,y1],display='same 0..1 grey range, no separate contrast normalization',scope='illustration from stored data, no new model inference or boundary extraction'))

# Curate existing figures: source images are copied, not altered.
existing={
 'F05_selected_nine.png':'03_Sampling_and_SEM/selected_nine.png',
 'F06_displacement_mean_sd.png':'01_Raw_R129_Comparison/figures/09_mean_error_sd_overlay.png',
 'F06_displacement_mean_sd.svg':'01_Raw_R129_Comparison/figures/09_mean_error_sd_overlay.svg',
 'F07_contours_start.png':'01_Raw_R129_Comparison/figures/03_contours_position00.png',
 'F08_contours_end.png':'01_Raw_R129_Comparison/figures/03_contours_position30.png',
 'F09_diameter_and_SEM.png':'01_Raw_R129_Comparison/figures/04_diameter_and_SEM.png',
 'F10_SEM_contours_inferred.png':'01_Raw_R129_Comparison/figures/08_SEM_inferred_comparison.png'}
for name,rel in existing.items():cp(HANDOFF/rel,'05_Paper_Figures/'+name)

# Current thesis map, with all ablation requirements removed.
heads=load(EXP/'results/thesis_revision_20260918/headings.json');mapped=[]
for h in heads:
    t=h['text'];m=re.match(r'(\d+(?:\.\d+)*)',t);n=m.group(1) if m else ''
    action='保留；引用與術語隨新版核對';target=t
    if t in ['摘要','Abstract'] or n.startswith(('1.2','1.3','1.4','7.')):action='依單一MOSR及新九顆結果改寫'
    if n.startswith('3.6'):action='改為共享多次修正的神經重建背景，舊U-Net僅作背景'
    if n.startswith(('4.4','4.5','4.6','5.4')):action='整段換成實际R129方法、資料及訓練；不沿用V42圖表與數字'
    if n.startswith('4.7'):action='保留ACM粗輪廓→最大梯度邊界→圓心／尺寸／位移；與現用讀法一致'
    if n.startswith('6.2'):action='用原圖與R129新九顆證據替換；核對舊模型圖片與數字'
    if n in ['5.4.5','5.4.6','6.2.7']:action='刪除舊多模型配置／排行；必要新資料配置併入鄰近節'
    if n in ['5.4.7','6.2.6']:action='刪除消融文字、圖表及所有回指；本次不補做'
    if n=='6.2.4':action='輪廓正文重點：ACM取邊示意、30次疊圖、SEM形狀與尺寸對照'
    if n=='6.2.8':action='改為單一MOSR處理時間與使用條件，不作速度排行'
    if n=='6.2.5.1':action='保留必要LSC／MZC選擇理由；舊模型數字不可改名沿用'
    mapped.append(dict(**h,action=action))
pd.DataFrame(mapped).to_csv(OUT/'00_Plan/section_action_map.csv',index=False,encoding='utf-8-sig')
save(OUT/'00_Plan/section_action_map.json',mapped)

# Archive original paragraphs for targeted replacement search without editing Word.
cp(EXP/'results/thesis_revision_20260918/paragraphs.json','01_Original_Thesis/paragraphs.json')
cp(EXP/'results/thesis_revision_20260918/headings.json','01_Original_Thesis/headings.json')
cp(Path(__file__),'07_Checks/prepare_materials.py')
save(OUT/'07_Checks/source_copies.json',copies)
save(OUT/'07_Checks/preparation_checks.json',dict(original_word_sha256=sha(DOC),result_manifest_payloads_verified=len(load(HANDOFF/'MANIFEST.json')),parents_verified=768,split_counts=counts.sum().to_dict(),geometry_cross_split_overlap=overlap,metadata_real_sem_flags_all_false=True,unique_training_updates=8192,epochs_with_all_512_parents=16,loss_arithmetic_max_abs_difference=error,development_evaluations=len(dev),actual_epoch0_example_inputs_verified=7,thesis_headings_mapped=len(mapped),new_model_training=False,new_model_inference=False,word_edited=False,semantic_note='Declared sources and hash lineage checked; this is not a new independent measurement or blanket physical accuracy certification.'))
print('Writing materials generated:',OUT,flush=True)
