"""Add a separately versioned full-field entry without editing the frozen package."""
import sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
def main():
    pkg=Path(load(ROOT/'config/standalone_build.json')['path']);dest=pkg/'addons/full_field';dest.mkdir(parents=True,exist_ok=False)
    shutil.copy2(ROOT/'scripts/sequence_inference.py',dest/'sequence_inference.py')
    script='''"""Full-field trained R129 inference using global optics and context-preserving local computation."""
import os,sys,argparse,time
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(PACKAGE))
import runtime as rt
import torch,numpy as np,cv2
from model.inference_policy import guard
from sequence_inference import predict
def main():
    p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,default=PACKAGE/'sample_inputs');p.add_argument('--output-name',default='full_'+str(time.time_ns()));p.add_argument('--checkpoint',type=Path,default=PACKAGE/'results/training/r129_long_01/checkpoints/step08192.pth');a=p.parse_args()
    if not a.output_name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in a.output_name):p.error('Use a simple new output name')
    manifest=rt.load(Path(__file__).parent/'ADDON_MANIFEST.json')
    for name,h in manifest['files'].items():
        if rt.sha(Path(__file__).parent/name)!=h:raise RuntimeError('Addon source changed')
    model,_=rt.create('cuda');state=torch.load(a.checkpoint,map_location='cuda');model.load_state_dict(state['model'],strict=True);model.eval()
    out=PACKAGE/'results/inference'/a.output_name;out.mkdir(parents=True,exist_ok=False)
    paths=sorted(x for x in a.input_dir.iterdir() if x.suffix.lower() in ['.bmp','.png','.tif','.tiff'])
    if not paths:raise ValueError('No input images')
    if len({x.stem.lower() for x in paths})!=len(paths):raise ValueError('Input names collide')
    for path in paths:
        raw=cv2.imdecode(np.fromfile(path,np.uint8),cv2.IMREAD_UNCHANGED)
        if raw is None or raw.ndim!=2 or raw.dtype!=np.uint8 or min(raw.shape)<193:raise ValueError('Use native 8-bit grayscale at least193x193')
        x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
        with torch.no_grad():result=guard(x,predict(model,x,512))[0,0].cpu().numpy()
        value=np.rint(result*255).clip(0,255).astype(np.uint8);ok,data=cv2.imencode('.png',value);assert ok
        output=out/(path.stem+'.png')
        with output.open('xb') as f:f.write(data.tobytes())
        rt.save(out/(path.stem+'.json'),dict(input_path=str(path.resolve()),input_sha256=rt.sha(path),output=rt.record(output),checkpoint_path=str(a.checkpoint.resolve()),checkpoint_sha256=rt.sha(a.checkpoint),full_native_shape=list(raw.shape),core=512,halo=16,global_optics_and_quality=True,addon_manifest_sha256=rt.sha(Path(__file__).parent/'ADDON_MANIFEST.json'),model_promoted=False))
        print('Reconstructed',path.name,flush=True)
if __name__=='__main__':main()
'''
    (dest/'infer_fullfield.py').write_text(script,encoding='utf-8')
    (dest/'README_TW.md').write_text('''# 完整影像重建入口

此附加入口使用已訓練完成的R129第8192次權重。原始套件程式、起始模型及舊清單保持不變。它處理完整原生影像，光學與品質統計使用全圖，只有局部重建計算分段，解決直接放大完整2048×1536影像時的運算索引限制。

在套件資料夾使用：

```powershell
python addons/full_field/infer_fullfield.py --input-dir "D:\\your_images" --output-name full_trial_01
```

需相同Python/CUDA環境；輸入8-bit灰階、至少193×193。输出存於results/inference/full_trial_01，保留原寬高；名稱不可重複。可用--checkpoint指定另一份相容R129權重；本次驗證的是第8192次，其他權重的效能不由此保證。

這是新的推論入口，不是重新訓練或正式採用模型。完整連續LSC分析與所有影像保存在Experiments/R129_OpticalPriorHybrid/results/continuous_lsc，對應報告另行產出。初版完整圖失敗與分段等價檢查均保留。
''',encoding='utf-8')
    save(dest/'ADDON_MANIFEST.json',dict(created_utc=now(),files={p.name:sha(p) for p in dest.iterdir() if p.is_file()},mathematical_operator_unchanged=True,validated_checkpoint=load(ROOT/'results/continuous_lsc/plan.json')['checkpoint'],original_package_manifest_sha256=sha(pkg/'PACKAGE_MANIFEST.json'),verification=record(ROOT/'results/continuous_lsc/staged_inference_verification.json')))
    save(ROOT/'results/continuous_lsc/fullfield_addon.json',dict(created_utc=now(),source=record(__file__),path=str(dest),manifest=record(dest/'ADDON_MANIFEST.json')))
    print('Added a separate full-field entry; no original package source or hash modified')
if __name__=='__main__':main()
