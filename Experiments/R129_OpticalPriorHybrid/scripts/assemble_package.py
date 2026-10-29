"""Finish user-facing manual controls and freeze the first package release."""
import sys,shutil,json,importlib.metadata,platform
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
PROJECT_ROOT = Path(__file__).resolve().parents[3]
def main():
    pkg=Path(PROJECT_ROOT / load(ROOT/'config/standalone_build.json')['path'])
    shutil.copy2(ROOT/'package_source/preflight.py',pkg/'preflight.py')
    launcher=(pkg/'START_R129.cmd').read_text(encoding='utf-8').replace('\r','')
    (pkg/'START_R129.cmd').write_bytes(launcher.replace('\n','\r\n').encode('ascii'))
    readme='''# R129 獨立訓練與重建套件

這一包使用目前整理完成的 R129 D 架構，包含全部訓練資料、光學資料、起始模型、真實驗證影像與工具。正常操作不依賴原本的 R128、R129 或 R61 實驗資料夾。原專案與舊模型完整保留。

## 最容易的操作方式

雙擊 **START_R129.cmd** 開啟操作選單：

| 選項 | 用途 |
|---|---|
| 1 Start long training | 開始新訓練，預設名稱 r129_long_01 |
| 2 Resume | 從同一個訓練最近的保存點續跑 |
| 3 Status | 查看已完成次數、目前工作和最近保存位置 |
| 4 Pause safely | 要求安全暫停；當次更新或驗證結束後會保存並停止 |
| 5 Reconstruct sample images | 用包內起始模型處理範例影像 |
| 6 Verify package | 核對程式、模型及全部資料 |
| 0 Exit | 關閉選單；背景訓練會繼續 |

同一個名稱不能重複開始；已存在的訓練請用 Resume。若顯示 evaluating_real 或 evaluating_development，表示正在驗證而不是卡住。請用 Pause safely 暫停；突然斷電或強制終止後只能回到最近保存點，之後重做的更新會保留在不同嘗試紀錄，不能重複算成新進度。

## 本次長訓練的內容

- **只訓練一個 R129 模型**，由包內既有 D 第24次權重開始，重新建立優化器；不是重新隨機訓練，也不是四組並行。
- 16 個完整資料循環，每循環512組影像對，總共 **8,192 次新更新**。每組有兩張影像；每循環產生新的雜訊，幾何仍是同一批512個來源，不能說成8192個獨立場景。
- 保留現有光學融合、四次共享修正、改善上取樣、原圖參照與品質調整。沒有偷偷新增方向分支或每步物理校正。
- 前128次逐步提高學習速率，最高0.0001，之後逐步降至0.00001。全部既有可學習部分參與；固定光學核和固定濾波器不當作可學習參數。
- 使用與 R129 短測一致的影像、邊緣與影像對修正要求。新架構尚未完整實作的訓練要求不宣稱已存在。
- 每128次保存一次。每512次對128組開發資料完整驗證；第0、512、2048、4096、8192次對固定真實光學／SEM影像做驗證。結尾才報告128組既有合成測試資料。
- 不按看過的成績偷偷換成另一個訓練長度或挑有利影格。預定終點是8192；全部指定結果都保留。

## 資料是否適合

資料是既有 R128 的完整合成來源：512訓練、128開發、128測試；涵蓋不規則曲線、尖角／線條、密集結構、帶紋理邊緣、乾淨／有雜訊影像及空白情況。訓練標籤没有取用實拍或SEM影像答案，三個分組的幾何來源不重疊。

固定光學資料仍繼承自 V42 校準，因此不能把整個系統稱為與舊SEM來源完全無關。合成模糊也不是逐場景匹配這份固定光學資料；它可用來研究對不同成像情況的適應，尚不能保證指定儀器的準確度。真實驗證與合成測試都是既有資料，不是新未知樣本。

訓練中的真實驗證使用三張正常拍攝影像、36顆SEM柱子和四對固定位移區域，與原R129短測讀法一致。它不能替代完整的時間位移波動或跨樣品驗證。後續是否可用，以真實輪廓、非圓細節、位移和最差案例決定。

## 輸出在哪裡

- `weights/initial_r129.pth`：目前已驗證的起始模型，永不覆寫。
- `results/training/r129_long_01/`：這次長訓練的所有保存點、逐次紀錄、驗證表和重建圖。
- `status.json`：該次訓練目前狀態；`latest_checkpoint.json`：最近可續訓的位置。
- `completion.json`：只有8192次更新及所有指定驗證均完成後才建立。
- `results/launcher_logs/`：背景執行訊息。啟動成功不代表訓練完成，需核對狀態與完成紀錄。
- `results/preflight/`：套件試跑、實際續訓一致性與真實量測重現結果。

## 自己的影像重建

在套件資料夾開終端機，使用同一個可用的 Python 環境：

```powershell
python infer_r129.py --input-dir "D:\\your_images" --output-name trial_01
```

預設仍使用起始模型，**長訓練完成不會自動取代它**。要試指定保存點：

```powershell
python infer_r129.py --input-dir "D:\\your_images" --output-name trained_trial --checkpoint results/training/r129_long_01/checkpoints/step08192.pth
```

輸入為8-bit灰階，至少193×193；輸出與原圖同尺寸，放在 `results/inference/`。資料夾名稱不能重複。完整大圖需足夠顯示卡記憶體；沒有偷偷用近似分塊改變結果。

## 終端機操作與環境

```powershell
python verify_package.py
python train_r129.py --dry-run --device cpu
python control.py start
python control.py status
python control.py pause
python control.py resume
```

套件不內藏整份 Python 或 MATLAB 安裝。這台電腦使用既有 Anaconda、PyTorch 與 RTX A6000；精確版本在 `ENVIRONMENT.json`。選單會先用環境變數 `R129_PYTHON` 指定的 Python，其次找使用者的 Anaconda，最後使用系統 Python。重建與訓練可不依賴原專案，但本套真實SEM粗輪廓驗證仍需要 MATLAB 與 Image Processing Toolbox；程式會尋找本機安裝，或用 `MATLAB_EXE` 指定。沒有MATLAB時不能假裝完成這個既定真實驗證流程。

新電腦請先準備相容的Python、PyTorch及GPU驅動，參照 `requirements.txt` 與 `ENVIRONMENT.json`，再核對套件並試跑。所有模型／資料路徑依套件位置解析，整包搬動後仍可使用。設定已固定在 `config/training.json`；直接改動會被偵測並停止，避免續訓悄悄變成另一種實驗。若要另訂方案，應另存配置與重新試跑，而不是覆寫正在執行的設定。

`PROVENANCE.json`、`docs/` 與原資料清單保留歷史路徑供追溯，它們不是程式必須回頭讀取的資料位置。原始報告中的舊實驗連結也屬歷史來源；操作以本說明為準。

這是一個可獨立操作的研究訓練套件，不代表R129已優於既有模型，也不代表論文可以省略後續驗證。
'''
    (pkg/'README_TW.md').write_text(readme,encoding='utf-8')
    (pkg/'MANIFEST.md').write_text('# R129 standalone manifest\n\nProfile: standalone payload, explicitly requested by user. One8192-update continuation of the organized R129 D prototype; preserved initial weights, local768-parent data, fixed calibration, real development fixtures and locked readers. All immutable resources are listed in PACKAGE_MANIFEST.json; active results are excluded. No original experiment input or result is overwritten. This package uses host Python/CUDA and MATLAB for identical SEM extraction. It is not production promotion or a guarantee of improvement.\n',encoding='utf-8')
    versions={}
    for name in ['torch','numpy','scipy','pandas','opencv-python','scikit-image','psutil']:
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]='not found'
    (pkg/'ENVIRONMENT.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),packages=versions,interpreter_used=sys.executable,external_validation_requirement='MATLAB with Image Processing Toolbox; discovered from host'),indent=2),encoding='utf-8')
    # Freeze sources before any preflight output; failures are retained, not auto-rebaselined.
    files={p.relative_to(pkg).as_posix():sha(p) for p in pkg.rglob('*') if p.is_file() and p.relative_to(pkg).parts[0]!='results' and '__pycache__' not in p.parts}
    payload=dict(created_utc=now(),model='R129_OpticalHybrid_LongTraining',files=files,scope='Immutable package input/source resources; runtime results are separate',count=len(files))
    with (pkg/'PACKAGE_MANIFEST.json').open('x',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,indent=2)
    print('Package release frozen:',len(files),'files')

if __name__=='__main__':main()
