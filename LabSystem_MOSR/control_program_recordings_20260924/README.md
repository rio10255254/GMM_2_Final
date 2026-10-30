# 控制程式效果錄影（2026-09-24）

實驗室系統新控制程式的效果錄影：Basler 相機（acA2040-120um）加 PI 平台，2026-09-24 下午連續錄的三支 MP4，共 124.9 MB。檔名照原樣保留，裡面有全形破折號和空白：

| 檔名 | 大小 |
|---|---|
| `Basler acA2040-120um (23153416) + PI Control — Optimized 2026-09-24 14-00-26.mp4` | 67.1 MB |
| `Basler acA2040-120um (23153416) + PI Control — Optimized 2026-09-24 14-02-28.mp4` | 34.2 MB |
| `Basler acA2040-120um (23153416) + PI Control — Optimized 2026-09-24 14-03-03.mp4` | 23.5 MB |

這是錄影，用來看控制程式跑起來的樣子；控制程式本身不在本專案。原本放在專案根目錄、只在原電腦上，2026-10-30 收進這裡並上傳。

錄影在發布附件 [labsystem-control-recordings-20261028](https://github.com/rio10255254/GMM_2_Final/releases/tag/labsystem-control-recordings-20261028)，Git 裡只有這份說明；恢復後就放在這個資料夾。上傳後已重新下載還原，三支 sha256 與原檔相同，檔名一字不差。

```powershell
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag labsystem-control-recordings-20261028 --output ../control-recordings --prefix LabSystem_MOSR/control_program_recordings_20260924
python Tools/research_asset_bundle.py restore --manifest ../control-recordings/RESEARCH_ASSETS.json.gz --assets ../control-recordings --destination . --prefix LabSystem_MOSR/control_program_recordings_20260924 --keep-identical-existing
```

返回：[LabSystem_MOSR](../README.md)。
