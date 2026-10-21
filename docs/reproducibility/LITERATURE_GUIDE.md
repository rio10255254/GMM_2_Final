# 文獻引用、設計推論與原方法來源

這裡整理本專案原本已保存的文獻連結、研究設計與官方程式版本，不下載整批論文或模型，也不把本次整理寫成重新讀完所有外部原文。原文獻、作者方法、本專案採用方式和本機實驗結果各自保留身分。

## 先從研究問題找原整理

| 想理解什麼 | 本專案原文件 | 閱讀界線 |
|---|---|---|
| 紋理答案、獨立雜訊、輪廓／孔洞、頻率、移動與分塊 | [R88原始研究與設計對照](<../../Experiments/R88_MeasurementFaithfulScratch/reports/R88_LITERATURE_SYNTHESIS.md>) | 原文獻只是設計依據；R88原87輪停止與未過項目仍保留，不因有文獻就改成成功。 |
| 序列條件與移動一致性 | [R119原因審查](<../../Experiments/R119_SequenceGeometryValidation/reports/R119_CAUSAL_AUDIT.md>) | 原控制與本專案失敗條件優先，不把抗混疊當成全面一致性的保證。 |
| 重建穩定性、錯誤結構與不確定性 | [R122原結果與限制](<../../Experiments/R122_OperatorPrinciples/reports/R122_RESULTS.md>)、[當時模型設計](<../../Experiments/R122_OperatorPrinciples/reports/MODEL_DESIGN.md>) | 設計推論不能借用其他顯微／醫學影像論文的成績當成本機驗證。 |
| 成像算子與學習更新如何接在一起 | [R123原設計](<../../Experiments/R123_RealFirstModelDesign/reports/R123_DESIGN.md>) | 方法家族的依據與本專案是否實際改善量測分開。 |
| 對整數移動、成像擾動與PSF的反應 | [R147原內部審查](<../../Experiments/R147_FullResPSFConsistency/reports/R147_INTERNAL_AUDIT.md>) | 文獻不取代本機實際位移、輪廓與不利讀值。 |
| 銳利外觀與量測是否能同時改善 | [R117當時設計審查](<../../Experiments/R117_CenterLockedSubpixelScratch/analysis/design_audit_20260905/FINDINGS.md>) | 保留實際反例；不從漂亮影像推論尺寸或定位更準。 |

## R88原文中實際引用的來源

下表沿用原文標示與連結，只幫助找原始來源。它不代表本次重新核實每篇內容，也不表示引用的方法已在MOSR通過。完整出處、原段落與原檔身分見[引用來源表](<project_completion/curated/LITERATURE_SOURCES.json>)。

| 原設計段落 | 原引用連結 |
|---|---|
| 真實紋理不能靠平坦標準答案學出來 | [CARE](https://www.nature.com/articles/s41592-018-0216-7) |
| 真實紋理不能靠平坦標準答案學出來 | [Noise2Noise](https://proceedings.mlr.press/v80/lehtinen18a) |
| 邊界要直接量，不能只靠整張像素或梯度 | [Boundary Loss](https://proceedings.mlr.press/v102/kervadec19a.html) |
| 邊界要直接量，不能只靠整張像素或梯度 | [Hausdorff 距離損失](https://pubmed.ncbi.nlm.nih.gov/31329113/) |
| 邊界要直接量，不能只靠整張像素或梯度 | [Boundary IoU](https://openaccess.thecvf.com/content/CVPR2021/html/Cheng_Boundary_IoU_Improving_Object-Centric_Image_Segmentation_Evaluation_CVPR_2021_paper.html) |
| 孔洞與斷裂要當成拓撲錯誤 | [Topology-Preserving Deep Image Segmentation](https://proceedings.neurips.cc/paper/2019/hash/2d95666e2649fcfc6e3af75e09f5adb9-Abstract.html) |
| 頻率損失只能保護已知存在的細節 | [Focal Frequency Loss](https://openaccess.thecvf.com/content/ICCV2021/html/Jiang_Focal_Frequency_Loss_for_Image_Reconstruction_and_Synthesis_ICCV_2021_paper.html) |
| 分塊一致性要從取樣與模型運算處理 | [Making Convolutional Networks Shift-Invariant Again](https://proceedings.mlr.press/v97/zhang19a.html) |
| 分塊一致性要從取樣與模型運算處理 | [EDSR](https://openaccess.thecvf.com/content_cvpr_2017_workshops/w12/papers/Lim_Enhanced_Deep_Residual_CVPR_2017_paper.pdf) |
| 位移要以等變性與次像素量測直接約束 | [Equivariant Imaging](https://openaccess.thecvf.com/content/ICCV2021/html/Chen_Equivariant_Imaging_Learning_Beyond_the_Range_Space_ICCV_2021_paper.html) |
| 位移要以等變性與次像素量測直接約束 | [Guizar-Sicairos 等人的次像素配準](https://opg.optica.org/ol/abstract.cfm?URI=ol-33-2-156) |

## R153外部方法的官方程式與本專案版本

官方原碼只是來源；本專案的單倍率配置、訓練資料、實際輪數、選模與量測讀法仍要讀本地紀錄。原始來源固定在下列版本，不自動追最新版；沒有下載官方預訓練模型冒充本地訓練。

| 方法 | 本專案保存的官方版本 | 本地完成狀態 |
|---|---|---|
| EDSR | [sanghyun-son/EDSR-PyTorch @ 8dba5581a750](https://github.com/sanghyun-son/EDSR-PyTorch/tree/8dba5581a7502b92de9641eb431130d6c8ca5d7f) | 列入原R153已完成比較 |
| RDN | [yulunzhang/RDN @ 83b0a4336d73](https://github.com/yulunzhang/RDN/tree/83b0a4336d7394bce8b4a4201806a2dcbfe29ec6) | 列入原R153已完成比較 |
| RCAN | [yulunzhang/RCAN @ f722e5d0e1ef](https://github.com/yulunzhang/RCAN/tree/f722e5d0e1eff45148bfaefd9bc85c6f0f26ce02) | 列入原R153已完成比較 |
| NAFNet | [megvii-research/NAFNet @ 2b4af71ebe09](https://github.com/megvii-research/NAFNet/tree/2b4af71ebe098a92a75910c233a3965a3e93ede4) | 列入原R153已完成比較 |
| SwinIR | [JingyunLiang/SwinIR @ 6545850fbf8d](https://github.com/JingyunLiang/SwinIR/tree/6545850fbf8df298df73d81f3e8cba638787c8bd) | 列入原R153已完成比較 |
| Restormer | [swz30/Restormer @ 68dc6ac472db](https://github.com/swz30/Restormer/tree/68dc6ac472db26f16361150cb7a96a1bc87da93f) | 列入原R153已完成比較 |
| MambaIRv2 | [csguoh/MambaIR @ 33d7b3460c46](https://github.com/csguoh/MambaIR/tree/33d7b3460c4665229334cc8de38c7f4c766ed3be) | 官方後端受阻，未完成；不混入已完成名單 |
| USRNet | [cszn/USRNet @ 7e4338ff33d8](https://github.com/cszn/USRNet/tree/7e4338ff33d8e897c4229dcc224c1f3ecb12d8e6) | 列入原R153已完成比較 |
| UNet | [lmb-freiburg/Unet-Segmentation @ 870e50366fcd](https://github.com/lmb-freiburg/Unet-Segmentation/tree/870e50366fcdabd7401e7936d1f2a6294dba488d) | 官方後端受阻，未完成；不混入已完成名單 |

精確原碼檔案與取得紀錄見[原官方來源清單](<../../Experiments/R153_MeanExternalBenchmark/config/official_sources.json>)；實際訓練使用的版本另見[原訓練來源](<../../Experiments/R153_MeanExternalBenchmark/config/official_training_sources.json>)及[原KAIR訓練來源](<../../Experiments/R153_MeanExternalBenchmark/config/official_KAIR_training_sources.json>)。原第三方授權隨已保存的原碼保留。

模型原始論文的其他資料集分數不當成本專案結果；已完成的十方法完整比較、SEM尺寸與速度代價仍回到[R153原論文交接](<../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md>)。

## 從文獻接到可重做的實驗

- [每輪問題、方法、完整結果與失敗](<EXPERIMENTS.md>)
- [原資料生產程式、真正設定及必要來源](<GENERATION_GUIDE.md>)
- [R88到後續修復的原數據與限制](<project_completion/curated/FAILURE_LINEAGE_READING.md>)
- [原拍、人工來源、生成資料與影像取捨](<SOURCE_AND_IMAGE_DECISIONS.md>)

本索引保留原引用連結與已存在文件，沒有宣稱每個連結都另存成論文PDF，也沒有替缺少全文的文獻補造內容。
