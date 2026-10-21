"""R152正式訓練影像檔獨立包。

現在正式訓練直接讀取TIFF影像，清楚與模糊影像分開存放：
  data/train/clear、blur、geometry     512個母場景／2048組視圖
  data/dev/clear、blur、geometry       128個母場景／512組視圖
  data/test/clear、blur、geometry      128個母場景／512組視圖

clear與blur內都是TIFF影像，相同檔名對應同一視圖的清楚／模糊配對。
TIFF保存正式訓練的完整原數值，沒有另外附PNG或使用NPZ作訓練影像。
geometry為原邊界距離影像，保留正／負值。有效性、位移、PSF編號與加噪設定在data_index.py。
訓練資料夾沒有NPZ；PSF、已訓練權重和推論原生輸出仍使用必要的資料格式。

所有程式、設定、索引、說明及檢查都用.py。
models/是完整R152；core/是資料、損失、訓練工具；settings.py集中設定及包內路徑。
weights/內附原版已驗證權重；input/附真實灰階示例；outputs/交付時空白。
需要numpy、PyTorch、Pillow、scipy。整個資料夾可搬走，不讀取原實驗資料夾。

重新製作全部訓練影像：直接執行generate_data.py。
它從固定種子產生全部清楚場景，用同一25顆PSF製作模糊影像，並重建幾何標記。
不需要額外清楚照片、SEM檔或原實驗資料夾，完成後核對全部9216張TIFF的像素。
預設新資料放在outputs/generated_data；train.py --data-dir outputs/generated_data可直接讀取。
如中斷，generate_data.py --resume會核對已有影像後繼續。
generate_data.py --verify-only可重新核對完整輸出。
generation/內包含固定配方、可獨立執行的生成工具與五份未修改的當初原始程式。
原始程式放在original_sources作對照；直接操作使用根目錄的generate_data.py。
版本核對資料在generation/recipe.py，完整操作說明在generation_guide.py。

直接執行train.py，照原配方使用包內已訓練主體，訓練R152擴充8192次。
train.py --from-scratch，完整從零重做兩階段，各8192次。
train.py --resume 某次訓練/extension/last.pth，繼續未完成訓練。
--updates是累計更新總數；--max-updates和--assessment-limit僅供短測。
正式訓練不填--assessment-limit。Ctrl+C會在完成當前更新後保存。
新訓練及推論結果寫入outputs，附帶的正式權重不覆寫。

直接執行infer.py，以原版R152權重重建input資料夾的8／16位元灰階影像。
"""
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parent
    print(__doc__)
    print('目前獨立包：',root)
    print('\n可手動執行：')
    for name in ('check_package.py','generate_data.py','train.py','infer.py'):
        print(f'  & "{sys.executable}" "{root/name}"')
    print('\n完整從零重做：')
    print(f'  & "{sys.executable}" "{root/"train.py"}" --from-scratch')
    print('\n使用剛生成的完整影像：')
    print(f'  & "{sys.executable}" "{root/"train.py"}" --data-dir outputs/generated_data')
    print('\n清楚訓練影像：',root/'data/train/clear')
    print('模糊訓練影像：',root/'data/train/blur')
    print('設定：',root/'settings.py')


if __name__ == '__main__':
    main()
