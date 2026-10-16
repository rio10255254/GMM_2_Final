# GeoEdge R39R40 a025 ONNX 公司測試包

這是 `R39R40_avg_a025 / r39r40_complementary_avg_a025` 的 ONNX 交付包，格式沿用之前的 COMBO ONNX 公司測試包。

## 這版是誰

`a025` 是目前已核准的 balanced full-spectrum alternate。白話說，它不是正式 COMBO baseline，但它是在「外部 GMF 不要離 COMBO 太遠」的前提下，同時補強形狀泛化與顯微特徵重建的那一版。

核心紀錄：

- 外部 8px：`0.146505`，比 COMBO 好 `5.18%`
- 外部 0.8px：`0.133546`，比 COMBO 退 `1.51%`
- 外部 0.08px：`0.100400`，比 COMBO 退 `0.51%`
- 顯微/形狀測試：12 類 PSNR 都勝過 COMBO 與 R39 a030

## 內容

- `model/geoedge_r39r40_a025_body.onnx`：ONNX 模型主體。
- `assets/preprocess_config.json`：推論前處理設定。
- `assets/psf_mean.npy`：固定 PSF 前處理資料。
- `run_a025_onnx.py`：單張或整個資料夾推論入口。
- `samples/sample_input.bmp`：範例輸入。
- `samples/sample_output_onnx.bmp`：此包產生的 ONNX 範例輸出。
- `samples/sample_output_reference_pytorch.bmp`：用完整 PyTorch checkpoint 產生的參考輸出。
- `verification_report.json`：本機驗證紀錄。

## 安裝

```bash
python -m pip install -r requirements.txt
```

## 執行

單張影像：

```bash
python run_a025_onnx.py --input samples/sample_input.bmp --output outputs
```

整個資料夾：

```bash
python run_a025_onnx.py --input path/to/images --output outputs
```

輸入可為灰階或彩色影像；彩色會轉成灰階。輸出會保留輸入影像大小與整數格式。

## 模型身分

- 候選：`R39R40_avg_a025 / r39r40_complementary_avg_a025`
- 角色：balanced full-spectrum approved alternate
- 來源：R39 a030 與 R40 a043 跨輪權重平均，a025 表示 75% a030 + 25% a043
- 原始 checkpoint：`D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\checkpoints\a025\best_tradeoff.pth.tar`

## 驗證結果

ONNX 檔已通過 checker，並已用 CPU ONNX Runtime 跑過 sample。

ONNX sample 與完整 PyTorch 參考輸出的差異：

- 平均灰階差：`0.030815`
- 最大灰階差：`1.0`
- PSNR：`77.34 dB`

注意：這個包和之前 COMBO ONNX 包一樣，ONNX 內放主要網路主體，固定 PSF 前處理放在 Python runner 裡。checkpoint 裡的 weak PSF 小模組沒有放進 ONNX；sample 差異已寫在 `verification_report.json`。
