"""R152獨立包使用說明。執行此檔會顯示訓練、推論與完整性檢查的實際路徑。

資料夾結構：
  models/       最新R152完整模型，包括原主體與25PSF融合。
  core/         包內資料讀取、損失、訓練與保存工具。
  data/         完整768母場景、3072視圖；train512/dev128/test128。
  calibration/  本版真正使用的25顆PSF。
  weights/      已訓練主體、R152訓練保存點、R152部署權重。
  input/        放待重建影像；附一張已驗證的示例。
  reference/    示例對應的原版浮點輸出，供比對。
  outputs/      手動訓練及推論的新結果。

程式與設定一律.py；資料及權重為必要的NPZ/PTH/BMP格式。
全部程式由本資料夾定位，不依賴原Experiments或其他資料夾。
需要numpy、PyTorch、Pillow；settings.py可修改參數和預設路徑。

直接執行train.py會照最新R152配方訓練8192次擴充，使用包內已訓練主體。
若要整個模型從零重做，使用train.py --from-scratch：先8192次主體，再8192次擴充。
正式執行不填--assessment-limit；它只供短暫功能檢查。
Ctrl+C會在完成當前更新後保存last.pth。--updates代表累計更新總數。
若最後更新已完成但評估尚未結束，可續跑last.pth完成評估；已完成的正式權重要續訓則提高累計總數。
短測或新訓練結果存入outputs，不會覆寫附帶的已驗證权重。

直接執行infer.py會讀input中的灰階影像，用已驗證R152權重輸出原生NPZ和顯示PNG。
請搬動整個資料夾，以維持程式、完整資料與權重一起存在。
"""
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parent
    print(__doc__.replace('权重', '權重'))
    print('目前獨立包：', root)
    print('目前Python：', sys.executable)
    print('\n可直接手動執行：')
    for file in ('check_package.py', 'train.py', 'infer.py'):
        print(f'  & "{sys.executable}" "{root/file}"')
    print('\n完整兩階段重做：')
    print(f'  & "{sys.executable}" "{root/"train.py"}" --from-scratch')
    print('\n訓練資料：', root/'data')
    print('設定：', root/'settings.py')
    print('新訓練結果：', root/'outputs/training')
    print('新重建影像：', root/'outputs/inference')


if __name__ == '__main__':
    main()
