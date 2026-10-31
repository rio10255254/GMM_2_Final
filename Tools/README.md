# 工具

全專案共用的程式：檢查專案狀態、量位移、從 Releases 取回資料、維護 repo。這裡不是一份要從頭跑到尾的流程，先想清楚要做什麼，再挑對應的工具。

| 我想… | 用這個 |
|---|---|
| 看專案整體狀態、跑健康檢查 | `python Tools/project_control_center.py`，搭配[目前狀態](../PROJECT_STATE.md) |
| 檢查資料夾結構和規則文件有沒有走樣 | `python Tools/validate_project_structure.py`（提交前的檢查也會跑它） |
| 查某個檔案在雲端哪裡、該下載哪個附件 | `python Tools/cloud_locator.py build`，再 `python Tools/cloud_locator.py where <專案內路徑>` |
| 下載並還原 Releases 裡的資料 | `download_research_assets.py` 下載、`research_asset_bundle.py restore` 還原；各份資料的 README 都寫了完整指令 |
| 取回相機原拍 | [930 張位移重拍的說明](../Shared_Sources/PI_Repeatability_20260903/README.md) |
| 取回某個模型或來源 | [按用途取得](../docs/reproducibility/ASSET_GUIDE.md)、[模型指南](../docs/reproducibility/MODEL_GUIDE.md) |
| 從原始數表重算結果 | [按用途取得](../docs/reproducibility/ASSET_GUIDE.md)：R93、四輪比較、Lab、光學、十種方法各有自己的入口 |
| 用不依賴廠商工具的方法量位移 | [位移演算法](Displacement_Algorithms/README.md) |
| 維護資料與硬碟容量 | [維護說明](../docs/operations/README.md) |

## 幾類比較特別的程式

- **保存用的上傳程式**（`plan_research_*`、`publish_research_batch.py`、`publish_research_assets.py`、`assemble_verified_archive_collection.py` 等）：當初把資料傳上 Releases 用的，留著可以看當時怎麼做。整批上傳整個專案的計畫已經停了，不要整批重跑。這個 repo 是公開的，所以上傳到它時要加 `--public-ok`，表示你知道附件會公開。
- **`restructure_*.py`**：2026-10-28 那次資料夾整理用的工具，怎麼用寫在[整理紀錄](../docs/operations/TREE_RESTRUCTURE_20261028.md)。
- **`tests/`**：這些工具自己的測試，`python -m pytest Tools/tests` 可以全部跑一次。

研究結果、模型和資料來源，以各輪的正式報告和清單為準，不以這裡的程式為準。跟研究無關的個人小工具，不算重做研究需要的東西。
