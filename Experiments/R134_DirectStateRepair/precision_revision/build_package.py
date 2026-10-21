"""A separate manually operable package for the qualified precision revision only."""
from common import *
import shutil,ast
def main():
    admission=load(P/'results/admission.json');assert admission['eligible'];protected()
    for k in ['motion','sem','protocol']:assert sha(admission[k]['path'])==admission[k]['sha256']
    for group in ['motion','sem']:
        for r in load(admission[group]['path'])['sources']:assert sha(r['path'])==r['sha256']
    source=E.parent.parent/'Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/R129_OpticalHybrid_Standalone_20260912';pkg=source.parent/'R134_DirectState_Precision_Standalone_20260915'
    for path,h in load(source/'PACKAGE_MANIFEST.json')['files'].items():assert sha(source/path)==h
    if pkg.exists():raise FileExistsError('Preserve existing package; no automatic hash rebaseline')
    registry=E.parent.parent/'docs/operations/PROJECT_STORAGE_REGISTRY.json';reg=load(registry);assert not any(e['id']=='r134_precision_package' for e in reg['entries']);save(P/'results/storage_before_package.json',reg);reg['entries'].append(dict(id='r134_precision_package',path=pkg.relative_to(E.parent.parent).as_posix(),tier='active',state='building_qualified_precision_revision',budget_gib=12,action='protect',priority=0,keep='One R134 C precision-preserved standalone generation; original models and negative8bitqualification retained',blocked_by=[]));atomic(registry,reg)
    pkg.mkdir();[ (pkg/d).mkdir() for d in ['config','weights','calibration','validation','model','verification','sample_inputs','results'] ]
    for name in ['runtime.py','data.py','engine.py','objectives.py','requirements.txt','ENVIRONMENT.json']:shutil.copy2(source/name,pkg/name)
    for name in ['train_r129.py','control.py','START_R129.cmd']:
        text=(source/name).read_text(encoding='utf-8-sig').replace('R129_OpticalHybrid_LongTraining','R134_Precision_LongTraining').replace('r129','r134p').replace('R129','R134P');(pkg/name.replace('r129','r134p').replace('R129','R134P')).write_text(text,encoding='utf-8')
    runtime=pkg/'runtime.py';text=runtime.read_text(encoding='utf-8-sig').replace('initial_r129.pth','initial_r134p.pth');start=text.index('def save(');end=text.index('def setup(',start);text=text[:start]+'from serialization import save,atomic\n\n'+text[end:];runtime.write_text(text,encoding='utf-8')
    src=(P/'common.py').read_text(encoding='utf-8');tree=ast.parse(src);parts=['import json,os,time\nfrom pathlib import Path\nimport numpy as np']+[ast.get_source_segment(src,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['plain','save','atomic']];(pkg/'serialization.py').write_text('\n\n'.join(parts),encoding='utf-8')
    for p in (E/'net').glob('*.py'):shutil.copy2(p,pkg/'model'/p.name)
    shutil.copy2(E/'tiled.py',pkg/'model/staged.py')
    (pkg/'model/__init__.py').write_text('''from .network import Network
from .staged import tiled_prior
class Hybrid(Network):
    def __init__(self,mean,candidates):super().__init__(mean,candidates,'C')
    def forward(self,raw):
        runner=(lambda p,f:tiled_prior(p,f,512,16)) if not self.training and max(raw.shape[-2:])>1024 else None
        return Network.forward(self,raw,prior_runner=runner)
    def forward_details(self,*args,**kwargs):raise NotImplementedError('Legacy diagnostics do not describe the direct-state output')
''',encoding='utf-8')
    path=pkg/'model/inference_policy.py';text=path.read_text();assert '(d - 80) / 16' in text;path.write_text(text.replace('(d - 80) / 16','(d - 16) / 16'),encoding='utf-8')
    for a,b in [('package_evaluate.py','evaluate_real.py'),('package_infer.py','infer_r134p.py'),('package_preflight.py','preflight.py'),('precision_io.py','precision_io.py'),('sem_metrics.py','sem_metrics.py'),('readout.py','readout.py')]:shutil.copy2(P/a,pkg/b)
    shutil.copy2(E/'package_templates/verify_package.py',pkg/'verify_package.py')
    for p in (P/'validation').iterdir():
        if p.is_file():shutil.copy2(p,pkg/'validation'/p.name)
    cp=Path(admission['checkpoint']['path']);assert sha(cp)==admission['checkpoint']['sha256'];shutil.copy2(cp,pkg/'weights/initial_r134p.pth');shutil.copy2(E/'calibration/measured_psf_bank.npz',pkg/'calibration/measured_psf_bank.npz');shutil.copytree(Path(load(E/'config/study.json')['data_root']),pkg/'training_data')
    cfg=load(source/'config/training.json');cfg.update(model_name='R134_Precision_LongTraining',seed=1342001,order_seed=1349002,noise_seed=1349003,initial_weights='weights/initial_r134p.pth',continuation='Same R134 C after512updates;8192additionalupdates, optimizerreset; no inherited legacy neural weights',training_target_note='Unchanged native image+0.2gradient+0.2paired residual; no new geometric objective',readout='Exact float32npy reloaded for motion; normalized optical SEM cells retained asdouble;8bitpreviews never measurement inputs',architecture_changes=False);save(pkg/'config/training.json',cfg)
    panel=load(E/'config/motion_panel.json');configuration=load(panel['configuration']['path']);items=[]
    for e in [13,14,15]:
        src=E/f'validation/inputs/sem{e}.png';dest=pkg/f'validation/inputs/sem{e}.png';dest.parent.mkdir(exist_ok=True);shutil.copy2(src,dest);items.append(dict(name=f'sem{e}',kind='sem',path=dest.relative_to(pkg).as_posix(),sha256=sha(dest),original_source=record(src)))
    for f in panel['frames']:
        name=f"{f['sequence']}_{f['frame_index']:04d}";dest=pkg/f'validation/inputs/{name}.bmp';shutil.copy2(f['source']['path'],dest);items.append(dict(name=name,kind='motion',sequence=f['sequence'],frame_index=f['frame_index'],path=dest.relative_to(pkg).as_posix(),sha256=sha(dest),original_source=f['source']))
    sequences={k:{a:b for a,b in v.items() if a!='raw_dir'} for k,v in configuration['sequences'].items()};save(pkg/'validation/panel.json',dict(images=items,sequences=sequences,motion_pairs=panel['pairs'],scope='Reused24fullframes/12pairs and3SEMfields'))
    plan=load(panel['source_plan']['path']);first=plan['frames'][0];gold=[]
    for name,source_image,expected in [('SEM14',E/'validation/inputs/sem14.png',P/'results/sem/C_s1342001/sem14.npy'),('full_field',Path(first['source']['path']),P/f"results/motion/C_s1342001/{first['sequence']}/frame_{first['frame_index']:04d}/reconstruction.npy")]:
        a=pkg/'sample_inputs'/(name+source_image.suffix);b=pkg/'verification'/(name+'.npy');shutil.copy2(source_image,a);shutil.copy2(expected,b);gold.append(dict(name=name,input=a.relative_to(pkg).as_posix(),expected=b.relative_to(pkg).as_posix()))
    save(pkg/'verification/golden.json',dict(cases=gold));save(pkg/'PROVENANCE.json',dict(generation='R134_C_P1',admission=admission,original8bitnegative_admission=record(E/'results/long_admission.json'),source_checkpoint=record(cp),source_data_manifest=record(Path(load(E/'config/study.json')['data_root'])/'manifest.json'),B_D_not_implemented=True,physical_material_edge_calibration_qualified=False,initial_prior_updates=512,planned_additional_updates=8192,no_automatic_promotion=True))
    (pkg/'README_TW.md').write_text('''# R134 保留量測精度的獨立長訓練包

雙擊START_R134P.cmd，可開始、查看、安全暫停、續訓或重建範例。關閉選單不會停止背景訓練。這包只有R134 C這一代；原始模型與資料保留。

起始是已訓練512次且通過本次精度流程完整驗證的C模型；再延續8192次，共16次遍歷512個訓練來源，優化器重新開始。資料每輪重新加入預定噪聲；不是8192個獨立物體。所有模型、資料、校準及驗證輸入在包內。本機仍須安裝Python、CUDA及有影像處理工具箱的MATLAB。

重建會輸出三份：.npy保留模型計算值供量測；_view16.png供需要圖片格式的外部程式使用；_preview8.png只供看圖。量測程式會拒絕把看圖副本當正式輸入，SEM內部也保留精細數值。保留數值不代表增加實際光學資訊。

每512次檢查全部128個開發來源；0/512/2048/4096/8192檢查固定3張正常SEM及12對完整視野；結束檢查128個生成測試来源。這些實拍均是既有開發資料，不是未知樣品。全部201張的最終比較由實驗工作流程另存。完成訓練不自動採用最後模型，預設重建仍使用包內起始模型；可明確指定本包綁定的訓練權重。

新的材料／光學獨立校準B/D仍未完成；沒有宣稱絕對尺寸或真實側移已認證。任何資格、資料或程式核對失敗均保留記錄並停止，不自動接受新的原始檔案雜湊值。
''',encoding='utf-8')
    files={p.relative_to(pkg).as_posix():sha(p) for p in pkg.rglob('*') if p.is_file() and 'results' not in p.relative_to(pkg).parts};save(pkg/'PACKAGE_MANIFEST.json',dict(generation='R134_C_P1',created_utc=now(),files=files));save(P/'results/package_built.json',dict(path=str(pkg),preflight_pending=True,admission=record(P/'results/admission.json')));print('Built distinct precision package',pkg,flush=True)
if __name__=='__main__':main()
