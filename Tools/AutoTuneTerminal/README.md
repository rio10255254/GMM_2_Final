# AutoTune 終端機前景顯示

靜態工具集中放在：

```text
D:\GMM_2_Final\Tools\AutoTuneTerminal\
```

根目錄只保留一個最常用入口：

```powershell
D:\GMM_2_Final\OPEN_AUTOTUNE_MONITORS.cmd
```

它會同時打開：
- raw output 視窗
- status 視窗
- 如果舊的 monitor 視窗還留著，會先自動關掉再重開

## 1. 看狀態摘要

如果背景 autotune / supervisor 正在跑，你可以在任一個終端機直接執行：

```powershell
D:\GMM_2_Final\Tools\AutoTuneTerminal\WATCH_AUTOTUNE_STATUS.cmd
```

如果你想直接跳出一個獨立終端機視窗顯示前景狀態，可以執行：

```powershell
D:\GMM_2_Final\Tools\AutoTuneTerminal\OPEN_AUTOTUNE_STATUS_WINDOW.cmd
```

它會每 5 秒刷新一次，顯示：

- `state`
- `notify_codex`
- `active_pid`
- `active_out_log`
- `plan_total / plan_remaining`
- 最新狀態行

## 2. 看訓練程式原始輸出

如果你要看目前正在跑的 autotune / train 原始輸出，可以在任一個終端機直接執行：

```powershell
D:\GMM_2_Final\Tools\AutoTuneTerminal\WATCH_AUTOTUNE_OUTPUT.cmd
```

如果你想直接跳出一個獨立終端機視窗顯示原始輸出，可以執行：

```powershell
D:\GMM_2_Final\Tools\AutoTuneTerminal\OPEN_AUTOTUNE_OUTPUT_WINDOW.cmd
```

這個輸出視窗會根據 `000_AUTOTUNE_STATUS.json` 裡的 `active_out_log` 自動切到目前正在跑的 log，
所以即使 supervisor 進入下一輪 chain，也會跟著換。

如果你不想清畫面，可以改成：

```powershell
python D:\GMM_2_Final\Model\GeoEdgeAlignSR_v1_AutoTuneStatusWatch.py --no-clear --interval-sec 5
```

## 重要限制

- `WATCH_AUTOTUNE_STATUS.cmd` 是摘要狀態
- `WATCH_AUTOTUNE_OUTPUT.cmd` 是訓練/自動化程式原始輸出
- 已經在背景跑的訓練程序，本身仍然是寫到 log 檔，不會直接附著回 VSCode 既有 terminal session
- 但你現在已經可以用 `WATCH_AUTOTUNE_OUTPUT.cmd` 在前景終端機看它的原始輸出
- `OPEN_AUTOTUNE_MONITORS.cmd` 只是打開監看視窗，不會啟動新的訓練
- 之後如果是我替你啟動新的背景流程，我可以同時幫你打開這兩個視窗，不需要你手動開
