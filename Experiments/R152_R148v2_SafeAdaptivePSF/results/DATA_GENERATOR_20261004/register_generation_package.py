"""Record the completed independent image generator without changing model roles."""
from copy import deepcopy
import json
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[4]
ROOT=PROJECT/'Experiments/R152_R148v2_SafeAdaptivePSF'
OUT=Path(__file__).resolve().parent


def main():
    receipt=json.loads((OUT/'package_receipt.json').read_text(encoding='utf-8'))
    assert receipt['status']=='passed' and receipt['all_archive_files_verified']
    g=receipt['generation']
    mb=receipt['package_bytes']/1e6
    zipmb=receipt['archive_bytes']/1e6
    report=ROOT/'reports/R152_DATA_GENERATION_REPRODUCTION_20261004.md'
    report.write_text(f'''# R152完整訓練影像生成程式與重新生成核對

日期：2026-10-04。使用者要求把當初生成全部訓練影像的程式加入最新獨立包，讓其他人不用重新實作也能生成同一份資料。本交付在既有TIFF版補齊生成來源與可執行入口，不改模型或正式資料的值。

## 交付與操作

- [完整最新獨立包](../../../Deliverables/R152_Standalone_ImageFiles_20261004.zip)
- [完整影像生成入口](../../../Deliverables/R152_Standalone_ImageFiles_20261004/generate_data.py)
- [純PY操作說明](../../../Deliverables/R152_Standalone_ImageFiles_20261004/generation_guide.py)
- [固定場景配方](../../../Deliverables/R152_Standalone_ImageFiles_20261004/generation/recipe.py)
- [五份原始程式身分](../../../Deliverables/R152_Standalone_ImageFiles_20261004/generation/source_history.py)

直接執行generate_data.py，會生成全部768母場景、每個四視圖，輸出到包內outputs/generated_data。重新生成影像可以由train.py --data-dir outputs/generated_data直接讀取；完整兩階段可加--from-scratch。如原data資料夾已不存在，可指定--output-dir data重建。既有非空資料夾不默默覆寫；--resume會核對已完成影像後接續，--verify-only則重新核對完整生成資料。

所有程式、配方、索引、說明、狀態與生成完成紀錄一律PY。清楚／模糊／幾何標記一律TIFF；沒有訓練PNG、NPZ，沒有新增MATLAB需求。生成只需包內程式與原25PSF銀行，不需要外部清楚影像、原實驗資料夾、SEM檔或原NPZ訓練資料。

## 找回的原始流程

1. R125 geometry helper定義連續形狀、座標與面積平均。
2. R128 source generator用固定種子生成清楚場景；R152所需的是其第一視图的4倍清楚latent。原資料後續雖經R129等版本保存，清楚來源仍是這套R128程式。
3. R148 prepare_data從這份清楚latent生成四視圖。位移、亮度、對比、PSF編號與噪聲規則按固定split和index決定，使用當時實際25PSF。
4. R148v2 prepare_geometry依相同形狀與位移重建中央96×96邊界標記。
5. R152原本讀取R148v2的共同payload；TIFF版保存相同讀入值。正式訓練再按輪次的固定種子加噪並轉八位元。

generation/original_sources中完整保存五份未改動程式：r125_geometry_helper.py、r128_scene_generation.py、r128_build_all.py、r148_physical_views.py、r148v2_geometry_labels.py。它們供追查當初實作；直接執行用generate_data.py及generation中的可獨立運作版本，已消除原環境路徑依賴。原始檔逐位元相同，對應hash保存於source_history.py。

## 固定參數與輸出

| 項目 | 原配方 |
| --- | --- |
| 母場景 | train 512、dev 128、test 128 |
| 場景種子基底 | 128100000、128200000、128300000，另加場景index |
| 七類比例 | 不規則曲線0.20、角線交接0.20、密集結構0.20、紋理邊界0.20、清潔等同0.05、含噪等同0.05、平坦0.10 |
| 清楚形成 | 8倍細格連續光度→2×2平均→4倍latent，保留原float32捨入 |
| 原尺寸 | 384×384 |
| 每母場景 | 四個視圖 |
| 小位移 | 0.25、0.5、0.75像素 |
| 大位移 | 2、4、6、8像素 |
| 對比候選 | 0.85、0.95、1、1.15，依原规则保留光度餘裕 |
| 亮度候選 | −5、0、3、5灰階，依原规则避免截斷 |
| 噪聲候選 | 0.5、1、1.5、3灰階標準差 |
| PSF規則 | (index×4+view+split offset) mod 25；train/dev/test offset=0/7/13；等同控制第一視圖不卷積 |
| PSF細格 | 原101×101核三次插值至401×401，負值歸零再正規化 |
| 位移與卷積邊界 | 原40格反射位移、200格反射卷積 |
| 最終數值 | 原native float32→float16儲存捨入→訓練float32；TIFF保留最後這些值 |
| 幾何標記 | 原score／梯度距離、±8像素截斷、float16→float32，中央96×96 |

清楚與模糊TIFF各3072張，另有3072張幾何TIFF，合計9216。總清楚／模糊像素905,969,664，加上幾何28,311,552，共934,281,216個像素值。TIFF亮度0～1，幾何保留正負距離。模糊TIFF刻意是原無噪聲結果；每輪noise_seed=1481003、split id、epoch、index、view再決定實際噪聲，不能把某一輪的加噪結果寫死取代它。

本入口只省略R152沒有消費的R128舊高斯模糊、第二視圖及診斷陣列。清楚渲染改以分段列降低暫存記憶體，取樣座標、原公式、面積平均與數值捨入保持相同。未以原TIFF複製或讀回充當生成。

## 實際驗證

- 768個场景從種子重建的全部參數，與當初母場景metadata摘要完全相同。
- 七類代表的4倍清楚latent，逐像素等於原R129包內實際保存的起始latent；其最終清楚、模糊、幾何與有效性也相同。
- 完整新生成768母場景／3072視圖／9216張TIFF，所有934,281,216個像素與固定metadata核對通過。9216個TIFF檔案內容也與既有交付逐位元相同。
- 完整生成時，審計掛鉤直接阻擋舊Experiments、Thesis_MOSR_Evidence、舊NPZ包及現成TIFF資料的檔案讀取；只有生成驗證輸出目錄例外。子程序也啟用同一阻擋。完整生成成功，證明不讀原影像仍可重做。
- 生成工具搬到另址，只帶程式及PSF，不帶訓練影像；由不同工作目錄執行並阻擋舊包讀取，train/dev/test三個場景均逐檔相同。核對後續跑可重用已完成正確影像；改動一張TIFF會被拒絕。
- 全部3072個實際模型輸入、答案、幾何、位移、PSF／算子編號與原R152讀法完全相同，第八輪代表資料的噪聲與算子也相同。
- 用新資料透過正式--data-dir入口實際做CUDA前四次更新，八個損失項與當初8192正式紀錄最大差0；所有第四次模型張量也等於上一TIFF交付的四次短測。
- 原模型程式、權重、PSF、損失與訓練迴圈逐檔不變。僅補生成工具及可指定生成資料夾的入口，沒有重新完成8192正式訓練或更換已验证部署權重。

生成實測使用4個工作程序，耗時{g['seconds']:.3f}秒，約{g['seconds']/60:.2f}分鐘，含写檔與再次讀回核對。本機Python {g['environment']['Python']}、numpy {g['environment']['numpy']}、scipy {g['environment']['scipy']}、Pillow {g['environment']['Pillow']}。其他環境速度可不同；不同套件版本若影響數值，像素檢查會拒絕，不能把未通過的輸出稱為同一份資料。

## 完成交付

更新後獨立包{receipt['file_count']}個檔案，含{receipt['python_files']}個PY與9216個TIFF，約{mb:.3f} MB；ZIP約{zipmb:.3f} MB。交付outputs空白，没有測試資料或快取；全部ZIP檔案已逐檔核對。

ZIP SHA-256：`{receipt['archive_sha256']}`。

所有實跑紀錄、生成資料及短測權重保留在results/DATA_GENERATOR_20261004；它們是驗證證據，不塞進交付包。
''',encoding='utf-8')
    text=report.read_text(encoding='utf-8')
    for old,new in [('視图','視圖'),('规则','規則'),('场景','場景'),('验证','驗證'),('写檔','寫檔'),('没有','沒有')]:
        text=text.replace(old,new)
    report.write_text(text,encoding='utf-8')
    tiff_report=ROOT/'reports/R152_TIFF_TRAINING_PACKAGE_20261004.md'
    text=tiff_report.read_text(encoding='utf-8')
    old='完整包9242個檔案，其中20個PY、9216個TIFF，約476.2 MB；ZIP約457.4 MB。'
    new=f"完整包目前{receipt['file_count']}個檔案，其中{receipt['python_files']}個PY、9216個TIFF，約{mb:.1f} MB；ZIP約{zipmb:.1f} MB。"
    if old in text:text=text.replace(old,new)
    text+='\n## 同日補齊完整影像生成來源\n\n已加入五份未修改的原始生成程式，以及獨立generate_data.py入口。全部768母場景／3072視圖／9216 TIFF已從固定種子重新製作，阻擋舊來源及現成TIFF讀取仍通過；全部像素及檔案內容相同。新資料透過--data-dir正式入口的全部實際輸入及前四次CUDA更新亦精確相同。完整來源、固定參數與實跑紀錄見[R152重新生成核對](R152_DATA_GENERATION_REPRODUCTION_20261004.md)。\n'
    tiff_report.write_text(text,encoding='utf-8')
    policy_path=PROJECT/'ESTIMATOR_POLICY.json'
    before=policy_path.read_bytes()
    policy=json.loads(before.decode('utf-8-sig'))
    baseline=deepcopy(policy['formal_baseline']);alternates=deepcopy(policy['approved_alternates'])
    item=policy['artifact_index']['R152_TIFF_training_standalone_20261004']
    item.update(generation_entry='Deliverables/R152_Standalone_ImageFiles_20261004/generate_data.py',
                generation_guide='Deliverables/R152_Standalone_ImageFiles_20261004/generation_guide.py',
                generation_report=str(report.relative_to(PROJECT)).replace('\\','/'),
                original_generation_sources_preserved=5,complete_generation_from_fixed_seeds_verified=True,
                regenerated_TIFFs_exact=9216,regenerated_inputs_and_first4_losses_exact=True,
                no_external_training_images_needed=True,archive_sha256=receipt['archive_sha256'])
    policy['notes'].append('2026-10-04 R152 TIFF package now includes five unchanged historical image-generation programs and a portable Python entry. All 768 parents and 9216 TIFFs were regenerated from original seeds with old-source/bundled-TIFF reads denied; all pixels and TIFF bytes match. Moved no-image-source generation, all actual training inputs and first-four CUDA update losses passed. Model/weights/PSF and formal baseline roles are unchanged.')
    assert policy_path.read_bytes()==before
    policy_path.write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    saved=json.loads(policy_path.read_text(encoding='utf-8'))
    assert saved['formal_baseline']==baseline and saved['approved_alternates']==alternates
    state_path=PROJECT/'PROJECT_STATE.md'
    state=state_path.read_text(encoding='utf-8-sig')
    state=state.replace('Last updated: 2026-10-04（R152正式訓練改讀TIFF影像檔，獨立版完成）',
                        'Last updated: 2026-10-04（R152完整影像生成程式補齊，從頭重新生成核對完成）',1)
    anchor='2026-10-04 TIFF影像版：'
    i=state.index(anchor);end=state.index('\n',i)
    state=state[:end]+' 同日補齊五份原始生成程式及[完整生成入口](Deliverables/R152_Standalone_ImageFiles_20261004/generate_data.py)；阻擋舊資料讀取仍從頭生成全部9216 TIFF且逐檔相同，新資料前四次CUDA更新也完全相同。'+state[end:]
    anchor='### R152 formal TIFF-image training package (2026-10-04)\n'
    addition=f'\n同日新增generate_data.py及generation/五份當初原始程式，從固定種子重新生成全部768母場景／9216 TIFF，阻擋舊實驗及現成影像讀取仍通過；所有像素、TIFF內容、完整實際輸入及前四次CUDA更新均相同。另址無訓練影像時可生成，--data-dir可直接正式訓練新資料。最新包{receipt["python_files"]}個PY、{receipt["file_count"]}檔約{mb:.1f}MB，ZIP約{zipmb:.1f}MB，outputs空白。[完整生成與驗證紀錄](Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_DATA_GENERATION_REPRODUCTION_20261004.md)。\n'
    assert anchor in state
    state=state.replace(anchor,anchor+addition,1)
    # Retain the earlier conversion evidence, update only current inventory figures.
    state=state.replace('20個PY、9242檔約476.2MB，ZIP約457.4MB',f'{receipt["python_files"]}個PY、{receipt["file_count"]}檔約{mb:.1f}MB，ZIP約{zipmb:.1f}MB')
    state_path.write_text(state,encoding='utf-8')
    index_path=PROJECT/'Experiments/INDEX.md'
    index=index_path.read_text(encoding='utf-8-sig')
    index=index.replace('Last updated: 2026-10-04（R152正式訓練TIFF影像檔獨立版完成）',
                        'Last updated: 2026-10-04（R152完整影像生成程式及從頭重做核對完成）',1)
    anchor='R152最新正式訓練TIFF影像版：'
    i=index.index(anchor);end=index.index('\n',i)
    index=index[:end]+' 已補[全部影像生成入口](../Deliverables/R152_Standalone_ImageFiles_20261004/generate_data.py)／[原始流程與核對](R152_R148v2_SafeAdaptivePSF/reports/R152_DATA_GENERATION_REPRODUCTION_20261004.md)，無原影像可從固定種子重做全部9216 TIFF，像素與檔案完全相同。'+index[end:]
    index_path.write_text(index,encoding='utf-8')
    for key in ('package','archive','generation_entry','generation_guide','generation_report'):
        assert (PROJECT/item[key]).exists(),key
    print('Canonical generation report, latest delivery registry and project handoff updated.',flush=True)


if __name__=='__main__':main()
