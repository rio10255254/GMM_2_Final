# Final Continuation Fix 2026-03-10

## 這次修了什麼

1. `final` 不再從舊 seed 重新開始。
   - 位置：
     `D:\GMM_2_Final\Model\GeoEdgeAlignSR_v1_AutoTuneTrain.py`
   - 現在 `final` 會直接從 `sweep` 的 `best_tradeoff.pth.tar` 接續。

2. `final` 進場時會重置 optimizer 與 epoch 計數。
   - 位置：
     `D:\GMM_2_Final\Model\GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py`
   - 新增：
     - `LOAD_RESET_OPTIMIZER`
     - `LOAD_RESET_EPOCH`

3. monitor reference 初始化時序修正。
   - 之前：先建 monitor reference，再 resume checkpoint。
   - 現在：先 resume checkpoint，再建 monitor reference。
   - 這樣 guard/reference 才會對齊實際載入的模型。

4. `short final` 改成真正對齊主任務的節奏。
   - `EqGeom` 直接在 final 前期啟動，不再沿用長訓練 schedule。
   - `physics / weak-PSF` 在 short final 內明確關閉，不再掛著永遠進不來的 schedule。
   - `self-band / rescue` 延後到 final 長度之外，避免在短 final 內過早干擾。
   - final 全程維持 micro-epoch 形式，避免剛進 final 後半段又切回 full epoch。

5. autotune report 現在會寫出建議部署候選。
   - 欄位：
     - `best_candidate.best_checkpoint_path`
     - `final_run.init_checkpoint_path`
     - `final_run.best_checkpoint_path`
     - `recommended_deploy`

6. LongRun manifest 會優先採用 `recommended_deploy`。
   - 位置：
     `D:\GMM_2_Final\Model\GeoEdgeAlignSR_v1_LongRunSupervisor.py`

## 這次修正的核心判斷

- 之前的 `final` 破壞 `sweep best`，主因不是單一 loss 權重，而是流程設計本身錯位：
  - `final` 不是 continuation，而是 restart
  - monitor reference 對錯模型
  - short final 沿用 long schedule
  - guard / rescue 在 short final 太早、太敏感

## 最直接的行為改變

- 未來 autotune 跑完後，如果 `final` 沒有明顯贏過 `sweep best`，report 會直接建議部署 `sweep` 權重。
- 如果 `final` 真的贏了，LongRun/manifest 也能正確記錄它，而不是只看 sweep。

## 本地 smoke test

- 驗證方式：stub `run_one_seed`，只檢查 `final` 進場時的實際 CFG。
- 驗證結果：
  - `PRETRAINED_PATH` 已切到 sweep best checkpoint
  - `LOAD_RESET_OPTIMIZER = True`
  - `LOAD_RESET_EPOCH = True`
  - `EQ_WARMUP_OFF_E = 0`
  - `EQ_RAMP_START_E = 1`
  - `EQ_RAMP_END_E = 4`
  - `SELF_BAND_READY_EPOCH = 5`（對 4-epoch final 等效停用）
  - `RESCUE_START_EPOCH = 5`（對 4-epoch final 等效停用）

## 現在的建議

下一輪不要直接回到長 final。

比較合理的順序是：

1. 先用這次修過的流程重新跑一輪小規模 autotune
2. 觀察 `sweep best -> short final` 是否終於能出現正向 gain
3. 只有在 final 已證明穩定有幫助後，再考慮把它納回長時間自動化
