"""Create a new self-contained generation package only after measured admission."""
from pathlib import Path
import sys,shutil,ast
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from rt import *
from motion134 import load_reader
import cv2
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def main():
    admission=load(ROOT/'results/long_admission.json');assert admission['eligible'],'No long-training package for an unqualified candidate'
    for key in ['stage1','motion12','motion201']:assert sha(admission[key]['path'])==admission[key]['sha256']
    assert load(ROOT/'results/motion_audit.json')['passed']
    for item in load(ROOT/'config/packaging_source_binding.json')['sources']:
        assert sha(str(PROJECT_ROOT / item['path']))==item['sha256'],str(PROJECT_ROOT / item['path'])
    seed=admission['selected_seed'];checkpoint_source=Path(admission['checkpoint']['path']);assert sha(checkpoint_source)==admission['checkpoint']['sha256']
    source=ROOT.parent.parent/'Deliverables/Standalone_Models/R129_OpticalHybrid_Standalone_20260912'
    for rel,expected in load(source/'PACKAGE_MANIFEST.json')['files'].items():
        assert sha(source/rel)==expected,'Original source package changed: '+rel
    pkg=source.parent/'R134_DirectState_Standalone_20260915'
    registry=ROOT.parent.parent/'docs/operations/PROJECT_STORAGE_REGISTRY.json';reg=load(registry)
    assert not any(e['id']=='r134_standalone_long_training' for e in reg['entries'])
    save(ROOT/'results/storage_before_package.json',reg)
    reg['entries'].append(dict(id='r134_standalone_long_training',path=pkg.relative_to(ROOT.parent.parent).as_posix(),tier='active',state='building_after_admission',budget_gib=12,action='protect',priority=0,keep='Independent R134 C long-training package; preserve every source and adverse outcome',blocked_by=[]))
    atomic(registry,reg);pkg.mkdir(exist_ok=False)
    for name in ['config','model','weights','calibration','validation','sample_inputs','verification','results']:(pkg/name).mkdir()
    for name in ['runtime.py','data.py','engine.py','objectives.py','evaluate_real.py','requirements.txt','ENVIRONMENT.json']:shutil.copy2(source/name,pkg/name)
    for name in ['train_r129.py','infer_r129.py','control.py','START_R129.cmd']:
        txt=(source/name).read_text(encoding='utf-8-sig').replace('R129_OpticalHybrid_LongTraining','R134_DirectState_LongTraining').replace('R129','R134').replace('r129','r134')
        (pkg/name.replace('R129','R134').replace('r129','r134')).write_text(txt,encoding='utf-8')
    for p in (ROOT/'net').glob('*.py'):shutil.copy2(p,pkg/'model'/p.name)
    shutil.copy2(ROOT/'tiled.py',pkg/'model/staged.py')
    wrapper='''from .network import Network
from .staged import tiled_prior
class Hybrid(Network):
    def __init__(self,mean,candidates):super().__init__(mean,candidates,'C')
    def forward_details(self,*args,**kwargs):
        raise NotImplementedError('Legacy output diagnostics do not represent R134 C. Use forward for reconstruction.')
    def forward(self,raw):
        runner=(lambda p,f:tiled_prior(p,f,512,16)) if not self.training and max(raw.shape[-2:])>1024 else None
        return Network.forward(self,raw,prior_runner=runner)
'''
    (pkg/'model/__init__.py').write_text(wrapper,encoding='utf-8')
    p=pkg/'model/inference_policy.py';p.write_text(p.read_text().replace('(d - 80) / 16','(d - 16) / 16'),encoding='utf-8')
    p=pkg/'runtime.py';text=p.read_text(encoding='utf-8-sig').replace('initial_r129.pth','initial_r134.pth');text=text.replace('import os,json,hashlib,datetime,random,math','import os,json,hashlib,datetime,random,math,time')
    # Preserve trained mathematics; replace only transient Windows state IO with
    # bounded retries, before this new package is frozen.
    start=text.index('def atomic(');end=text.index('\ndef setup(',start)
    text=text[:start]+'''def atomic(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.writing')
    for attempt in range(30):
        try:
            with tmp.open('w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
            os.replace(tmp,p);return
        except PermissionError:time.sleep(.1)
    raise RuntimeError('State write remained locked')
'''+text[end:]
    p.write_text(text,encoding='utf-8')
    p=pkg/'infer_r134.py';text=p.read_text(encoding='utf-8-sig')
    needle="m,_=create(a.device);state=torch.load(a.checkpoint,map_location=a.device);m.load_state_dict(state['model'],strict=True);m.eval()"
    assert needle in text
    text=text.replace(needle,"from verify_package import verify\n    verify(False)\n    m,_=create(a.device);state=torch.load(a.checkpoint,map_location=a.device)\n    if 'binding' in state:verify_binding(state['binding'])\n    elif sha(a.checkpoint)!=sha(ROOT/'weights/initial_r134.pth'):raise RuntimeError('Checkpoint is not the packaged generation or a bound run')\n    m.load_state_dict(state['model'],strict=True);m.eval()")
    p.write_text(text,encoding='utf-8')
    shutil.copy2(checkpoint_source,pkg/'weights/initial_r134.pth');shutil.copy2(ROOT/'calibration/measured_psf_bank.npz',pkg/'calibration/measured_psf_bank.npz')
    shutil.copytree(Path(PROJECT_ROOT / load(ROOT/'config/study.json')['data_root']),pkg/'training_data')
    cfg=load(source/'config/training.json');cfg.update(model_name='R134_DirectState_LongTraining',seed=seed,order_seed=1349002,noise_seed=1349003,initial_weights='weights/initial_r134.pth',continuation='Same-generation C512 checkpoint; optimizer reset;8192additionalupdates, not fresh-from-zero and not legacy neural inheritance',training_target_note='Native image+0.2gradient+0.2paired residual; direct image state; geometry requirement NOT added',architecture_changes=False)
    save(pkg/'config/training.json',cfg)
    for name in ['extract_sem.m','sem_reference.mat','reference_circle_core.py','readout_helpers.py','__init__.py']:shutil.copy2(ROOT/'validation'/name,pkg/'validation'/name)
    mp=load(ROOT/'config/motion_panel.json');oldplan=load(str(PROJECT_ROOT / mp['source_plan']['path']));scfg=load(str(PROJECT_ROOT / mp['configuration']['path']));_,scope=load_reader()(oldplan);images=[]
    for e in [13,14,15]:
        src=ROOT/f'validation/inputs/sem{e}.png';dest=pkg/f'validation/inputs/sem{e}.png';dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);images.append(dict(name=f'sem{e}',kind='sem',path=dest.relative_to(pkg).as_posix(),sha256=sha(dest),original_source=record(src)))
    for frame in mp['frames']:
        seq=frame['sequence'];index=frame['frame_index'];src=Path(PROJECT_ROOT / frame['source']['path']);dest=pkg/f'validation/inputs/{seq}_{index:04d}.bmp';shutil.copy2(src,dest);spec=scfg['sequences'][seq];centers=scope['session_prediction'](seq,index,np.asarray(spec['centers'],float),spec['expected_signed_dx_px'])
        images.append(dict(name=f'{seq}_{index:04d}',kind='motion',path=dest.relative_to(pkg).as_posix(),sha256=sha(dest),sequence=seq,frame_index=index,global_origin=[0,0],centers_local=centers.tolist(),original_source=frame['source']))
    seqs={k:{a:b for a,b in s.items() if a!='raw_dir'} for k,s in scfg['sequences'].items()}
    save(pkg/'validation/panel.json',dict(images=images,sequences=seqs,motion_pairs=mp['pairs'],scope='Full native fields,12fixedpairs; not full201long-end qualification'))
    p=pkg/'evaluate_real.py';text=p.read_text(encoding='utf-8-sig');old="details=model.forward_details(x,trace=True);value=guard(x,details.output)";assert old in text;text=text.replace(old,"prediction=model(x);value=guard(x,prediction)")
    old="quality=float(details.quality[0]),optical_weights=details.optical['weights'].cpu().tolist()";assert old in text;text=text.replace(old,"optical_weights=model.optics.last_weights.cpu().tolist(),quality_gate_applied=False")
    text=text.replace('motion_pairs=4,temporal_SD_not_available=True','motion_pairs=len(panel[\'motion_pairs\']),temporal_SD_not_reported=True');p.write_text(text,encoding='utf-8')
    # Golden outputs from the admitted same checkpoint, not new chosen examples.
    case=oldplan['frames'][0];full_input=Path(case['source']['path']);full_expected=ROOT/f'results/full_motion/{case["sequence"]}/frame_{case["frame_index"]:04d}/reconstruction.png'
    pairs=[('SEM14',ROOT/'validation/inputs/sem14.png',ROOT/f'results/real/C_s{seed}_p0512/sem14.png'),('full_field',full_input,full_expected)];gold=[]
    for name,src,expected in pairs:
        inp=pkg/'sample_inputs'/(name+src.suffix);exp=pkg/'verification'/(name+'.png');shutil.copy2(src,inp);shutil.copy2(expected,exp);gold.append(dict(name=name,input=inp.relative_to(pkg).as_posix(),expected=exp.relative_to(pkg).as_posix()))
    save(pkg/'verification/golden.json',dict(cases=gold))
    for name in ['verify_package.py','preflight.py']:shutil.copy2(ROOT/'package_templates'/name,pkg/name)
    save(pkg/'PROVENANCE.json',dict(generation='R134_C',admission=admission,source_checkpoint=record(checkpoint_source),source_data_manifest=record(Path(PROJECT_ROOT / load(ROOT/'config/study.json')['data_root'])/'manifest.json'),B_D_not_implemented=True,calibration_not_material_edge_qualified=True,initial_prior_updates=512,planned_additional_updates=8192,originals_unchanged=True))
    (pkg/'README_TW.md').write_text('# R134 直接影像模型獨立長訓練包\n\n操作入口：START_R134.cmd。只有R134 C這一代；起始為已通過短測及位移條件的512次模型，另做8192次延續訓練，優化器重新開始。原R129不變。\n\n可開始、查看、安全暫停、續訓與重建範例。關閉選單不會停止背景訓練。所有資料／模型／校準／驗證程式在包內；Python、CUDA與MATLAB須由本機提供。\n\n每512次驗證全部128開發來源，0/512/2048/4096/8192檢查3張正常SEM及12對完整視野影像，終點檢查128生成測試。這些是既有開發資料，不是新未知樣品。完成训练不自动采用最后权重。\n\n目前仅新接口C，独立材料校准B/D尚未完成；没有新增几何要求或物理尺寸认证。初始与最终结果分开，默认重建仍保留包内起始模型。\n',encoding='utf-8')
    files={p.relative_to(pkg).as_posix():sha(p) for p in pkg.rglob('*') if p.is_file() and 'results' not in p.relative_to(pkg).parts}
    save(pkg/'PACKAGE_MANIFEST.json',dict(generation='R134_C',files=files,created_utc=now()))
    save(ROOT/'results/package_built.json',dict(path=str(pkg),generation='R134_C',preflight_pending=True,source=record(__file__)));print('Built package awaiting its own actual preflight',pkg,flush=True)
if __name__=='__main__':main()
