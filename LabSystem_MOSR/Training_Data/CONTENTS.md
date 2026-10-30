# Lab資料形成與固定來源

[Lab研究沿革](<../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [Lab實驗分區](<../../docs/reproducibility/routes/lab.md>) · [共用原拍](<../../Shared_Sources/README.md>)

stage01至33是資料類型，不是33輪獨立訓練。BADS光學與Gaussian對照、幾何答案及SEM來源要跟原設定配對。大影像不在這一層，不表示只靠種子就能恢復繼承來源。

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [Data_Simulaion.py](<Data_Simulaion.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [generated/](<generated>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [generated_convolved/](<generated_convolved>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [generated_convolved_gaussian_control/](<generated_convolved_gaussian_control>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | Training_Data Manifest |
| [PSF_Convolution.py](<PSF_Convolution.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [r39_shape_generalization/](<r39_shape_generalization>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [r40_microscopy_feature_coverage/](<r40_microscopy_feature_coverage>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [r48_real_corner_transfer/](<r48_real_corner_transfer>) | 2檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [r49_cad_anchor_real_geometry/](<r49_cad_anchor_real_geometry>) | 2檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [r49_cad_anchor_source/](<r49_cad_anchor_source>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [r55_source_style_rebuild/](<r55_source_style_rebuild>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [README.md](<README.md>) | 1檔 | Lab Training_Data |
| [reports/](<reports>) | 5檔 | 原報告、計畫、審查與各階段結論 |
| [scripts/](<scripts>) | 4檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 4檔 | 原檢查程式；不是研究結果本身 |

原README、MANIFEST與完成紀錄按各自日期閱讀；不能用早期bootstrap說明代替後續全部研究現況。
