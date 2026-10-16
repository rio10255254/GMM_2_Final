# R88 原始研究與設計對照

這裡只列直接影響 R88 的原始研究。論文證明的是各自方法在其資料上的效果；把它們組合到 MOSR 是本專案的設計推論，仍須由 R88 自己的鎖定實驗驗證。

## 真實紋理不能靠平坦標準答案學出來

[CARE](https://www.nature.com/articles/s41592-018-0216-7) 使用低訊噪觀察與高訊噪真值來訓練顯微影像復原，展示成對的低、高品質成像能把模型目標放在實際可觀測訊號，而不是理想化圖形。[Noise2Noise](https://proceedings.mlr.press/v80/lehtinen18a) 進一步證明，在噪聲條件成立時，彼此獨立的受污染觀察也能用來學習底層訊號。

R88 採用的部分：每個程式生成場景保留一張帶紋理的潛在真值，再產生四個獨立觀察。將來若允許補拍，可另外建立同位置多張對齊平均的真實高訊噪外部驗證，但不把 SEM 灰階或樣品結構當成訓練答案。

## 邊界要直接量，不能只靠整張像素或梯度

[Boundary Loss](https://proceedings.mlr.press/v102/kervadec19a.html) 將距離轉換加入訓練，直接處理輪廓而非只累加區域誤差。[Hausdorff 距離損失](https://pubmed.ncbi.nlm.nih.gov/31329113/) 專門降低最差邊界偏離；[Boundary IoU](https://openaccess.thecvf.com/content/CVPR2021/html/Cheng_Boundary_IoU_Improving_Object-Centric_Image_Segmentation_Evaluation_CVPR_2021_paper.html) 則顯示一般 IoU 對大型物體的邊界誤差不夠敏感。

R88 採用的部分：在有精確程式幾何的資料上，同時使用距離式輪廓限制、最差邊界與 Boundary IoU；ACM 驗證仍以固定外部抽取流程執行，避免模型自己報自己的輪廓分數。

## 孔洞與斷裂要當成拓撲錯誤

[Topology-Preserving Deep Image Segmentation](https://proceedings.neurips.cc/paper/2019/hash/2d95666e2649fcfc6e3af75e09f5adb9-Abstract.html) 用可微分拓撲損失讓輸出與真值有相同的連通數與孔洞數。

R88 採用的部分：只在具有精確幾何真值的合成資料啟用拓撲限制；驗證時任何新增或遺失的孔洞、連通區塊都是硬失敗，不能被較好的平均 IoU 抵銷。

## 頻率損失只能保護已知存在的細節

[Focal Frequency Loss](https://openaccess.thecvf.com/content/ICCV2021/html/Jiang_Focal_Frequency_Loss_for_Image_Reconstruction_and_Synthesis_ICCV_2021_paper.html) 指出一般重建損失容易留下頻域落差，並將訓練重點放在較難重建的頻率。

R88 採用的部分：頻率限制只比較標準答案中已知存在、且成像模型仍保留訊息的頻帶。對被 PSF 與噪聲完全抹除的頻帶不要求生成，並禁止對抗式或生成式紋理損失，避免「看起來像」取代「真的存在」。

## 分塊一致性要從取樣與模型運算處理

[Making Convolutional Networks Shift-Invariant Again](https://proceedings.mlr.press/v97/zhang19a.html) 說明步進卷積與池化若在降採樣前沒有低通，微小位移可能造成輸出劇烈改變。[EDSR](https://openaccess.thecvf.com/content_cvpr_2017_workshops/w12/papers/Lim_Enhanced_Deep_Residual_CVPR_2017_paper.pdf) 在超解析模型中移除正規化層，以避免限制輸出值域並降低不必要記憶體成本。

R88 採用的部分：降採樣前固定低通、上採樣後固定低通；不用任何跨高度與寬度的正規化，也不用全圖 FFT、全局池化或切片依賴的 SNR。完整影像與分塊走完全相同的局部路徑。

## 位移要以等變性與次像素量測直接約束

[Equivariant Imaging](https://openaccess.thecvf.com/content/ICCV2021/html/Chen_Equivariant_Imaging_Learning_Beyond_the_Range_Space_ICCV_2021_paper.html) 利用已知轉換後，重建結果也應以相同方式轉換的條件來限制影像反問題。[Guizar-Sicairos 等人的次像素配準](https://opg.optica.org/ol/abstract.cfm?URI=ol-33-2-156) 使用矩陣乘法 DFT 在較低成本下達到小數像素配準精度。

R88 採用的部分：同一場景建立正負方向與零位移對；訓練同時限制「先位移再重建」與「先重建再位移」的一致性，並用可微分的局部相位相關估計位移誤差。最終評估另用固定 DFT 配準量測斜率、截距、方向偏差、MAE 與重複性。

## 不採用的做法

- 不使用 GAN、擴散或感知模型產生看似自然但無量測依據的紋理。
- 不用單一 PSNR、SSIM 或平均訓練誤差決定模型。
- 不把 SEM 的灰階紋理搬到光學顯微影像。
- 不把大圖切片後再用羽化混合當成架構根治。
- 不因 GPU 顯存大就無限制增加參數；大 patch 用來看跨區域結構，batch 用來穩定正負位移與各類資料比例。

