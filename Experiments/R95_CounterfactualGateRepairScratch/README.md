# R95：修復控制與學習動力

保留 R94 的成像分工與局部切片設計，改成清楚輸入確實為零的需求答案，對同一場景的清楚、無雜訊、含雜訊三種輸入直接監督控制；改用較中性的初始控制、逐步交接及早期自適應平均權重。保留跨目標不互相反向的更新方式。

seed 950041；2,303,717 參數。48 輪完成，四段原表共 49 列；從第 8 輪恢復後重新跑的第 9 輪取代舊列，形成 48 輪提交軌跡，兩筆原列都保留。

第一次因保護停止於未提交的第 10 輪，回到模型第 8 輪，且 optimizer_state_restored=false：模型與平均權重接續，但訓練更新狀態重新建立。後續由第 11、32 輪接續才有完整更新狀態。不能稱為三次完全連續或四次獨立訓練。第 40 輪診斷仍顯示清楚案例的誤改、邊界控制壓低與極弱紋理分支；48 輪已完成不等於這些機制全面解決。

- [方法、實際歷程、完整保存與限制](reports/R95_AUDIT.md)
- [四輪 GitHub 取回與重做入口](../../docs/reproducibility/four_rounds/README.md)
- [重要原圖與不利案例](../../docs/reproducibility/four_rounds/GALLERY.md#r95)
- [本輪全部模型、影像、數據與失敗紀錄](https://github.com/rio10255254/GMM_2_Final/releases/tag/r95-complete-record-20261021)

原指南完整保留於 `docs/history/R95_README_BEFORE_PROVENANCE_AUDIT_20261021.md`。`config/experiment_design.json` 是當年設計；實際完成以原表、模型與上述審查為準。不要直接在保存的歷史目錄開新訓練，重做請使用另外的工作目錄。
