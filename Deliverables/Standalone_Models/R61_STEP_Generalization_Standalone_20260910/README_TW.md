# R61 STEP Generalization Standalone Model Package

這是一個整理後的 R61 v16 獨立模型包。訓練、重建、PSF、權重、完整訓練資料和代表性驗證結果都放在同一個資料夾內；正常使用時不需要再回頭尋找原專案的 Model、Traing_Progress 或 R61 實驗資料夾。

## 包內主要內容

- train_r61.py：包內訓練入口，預設使用 r61_motion_texture_stepguard_v16_dualgate_boundary_focus。
- infer_r61.py：包內重建入口，預設使用 weights/best_tradeoff.pth.tar。
- model_r61.py、utils_r61.py、train_core_r61.py：R61 使用的模型本體、工具和訓練核心。
- scripts/：R61 訓練設定、資料準備、幻影驗證、雙重／三重門檻和動態檢查程式。
- training_data/：完整 v16 七角色資料，共 20,296 組、114,284 個檔案，約 11.16 GB。
- weights/：v16 目前權重、訓練可用的 v14 起始權重、R39 a970 教師權重、R60 起始權重和 R61 各輪候選權重。
- results/：v16 完整訓練紀錄與 matched 96-case 驗證結果。
- docs/：R61 原始整理索引、進度、v16 handoff 和本次包裝來源紀錄。
- verify_package.py：檢查包內資料、權重、核心程式和路徑是否完整。

## 先做完整性檢查

在這個資料夾中執行：

~~~powershell
python .\verify_package.py
~~~

## 直接重建

包內已放三張測試圖，先用 CPU 可驗證整條流程：

~~~powershell
python .\infer_r61.py --device cpu --output-name smoke_verify --print-model-config
~~~

輸出會放在：

results\inference_results\

實際資料重建時，可指定自己的輸入資料夾：

~~~powershell
python .\infer_r61.py --device cuda:0 --input-dir D:\your_input --output-name your_run
~~~

## 直接訓練

先做不訓練的路徑和資料檢查：

~~~powershell
python .\train_r61.py --dry-run --device cpu
~~~

若要跑包內預設的 R61 v16 設定：

~~~powershell
python .\train_r61.py --device cuda:0 --num-epoch 8
~~~

訓練結果會放在：

results\training_results\

也可以直接執行完整設定檔：

~~~powershell
python .\scripts\launch_r61.py --candidate r61_motion_texture_stepguard_v16_dualgate_boundary_focus --dry-run --device cpu
~~~

## 驗證工具

~~~powershell
python .\scripts\run_diverse_phantom_validation.py --device cpu --skip-reconstruct
~~~

它會把測試結果放到 results\validation\diverse_phantom_validation\。要實際產生重建圖時，移除 --skip-reconstruct，並改用 GPU。

## 權重選擇

平常重建使用：

weights\best_tradeoff.pth.tar

若要從 v16 的原始訓練狀態繼續，可查看：

- weights\latest.pth.tar
- weights\epoch_008.pth.tar

重新執行 v16 訓練時，包內已保留：

- weights\base_v14_motion_texture_best_tradeoff.pth.tar
- weights\teacher_r39_best_latest_a970.pth.tar

## 範圍和限制

這個包保存的是 R61 v16 的模型與可重跑資料，不代表 R61 已取代正式 baseline。R61 仍是論文相關候選，正式 baseline 仍以專案狀態文件為準。

prepare_r61_universal_dataset.py 的產生程式也一併保留；目前完整資料已經封存於包內。若要從最上游來源重新產生 legacy、sequence 和 SEM anchor 三類資料，仍需另外提供那些上游資料包。

