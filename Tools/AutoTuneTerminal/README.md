# AutoTune 終端機前景顯示 / AutoTune Foreground Monitoring

靜態工具集中放在：  
Static helper tools are grouped under:

```text
Tools/AutoTuneTerminal
```

根目錄只保留一個最常用入口：  
The repo root keeps one common entry point:

```powershell
OPEN_AUTOTUNE_MONITORS.cmd
```

它會同時打開：  
It opens the following together:
- raw output 視窗 / raw output window
- status 視窗 / status window
- 如果舊的 monitor 視窗還留著，會先自動關掉再重開  
  If old monitor windows are still open, it closes them first and reopens clean ones.

## 1. 看狀態摘要 / Watch Status Summary

如果背景 autotune / supervisor 正在跑，你可以在任一個終端機直接執行：  
If a background autotune / supervisor process is already running, you can run:

```powershell
Tools/AutoTuneTerminal/WATCH_AUTOTUNE_STATUS.cmd
```

如果你想直接跳出一個獨立終端機視窗顯示前景狀態，可以執行：  
If you want a separate foreground terminal window for status, run:

```powershell
Tools/AutoTuneTerminal/OPEN_AUTOTUNE_STATUS_WINDOW.cmd
```

它會每 5 秒刷新一次，顯示：  
It refreshes every 5 seconds and shows:

- `state`
- `notify_codex`
- `active_pid`
- `active_out_log`
- `plan_total / plan_remaining`
- 最新狀態行 / the latest status line

## 2. 看訓練程式原始輸出 / Watch Raw Training Output

如果你要看目前正在跑的 autotune / train 原始輸出，可以在任一個終端機直接執行：  
To watch the raw output of the currently running autotune / training process, run:

```powershell
Tools/AutoTuneTerminal/WATCH_AUTOTUNE_OUTPUT.cmd
```

如果你想直接跳出一個獨立終端機視窗顯示原始輸出，可以執行：  
If you want a separate foreground terminal window for raw output, run:

```powershell
Tools/AutoTuneTerminal/OPEN_AUTOTUNE_OUTPUT_WINDOW.cmd
```

這個輸出視窗會根據 `000_AUTOTUNE_STATUS.json` 裡的 `active_out_log` 自動切到目前正在跑的 log，  
所以即使 supervisor 進入下一輪 chain，也會跟著換。  
This output window follows the `active_out_log` field in `000_AUTOTUNE_STATUS.json`, so it switches to the current log even if the supervisor moves on to the next chain.

如果你不想清畫面，可以改成：  
If you do not want the screen to clear between refreshes, use:

```powershell
python Model/GeoEdgeAlignSR_v1_AutoTuneStatusWatch.py --no-clear --interval-sec 5
```

## 重要限制 / Important Limits

- `WATCH_AUTOTUNE_STATUS.cmd` 是摘要狀態  
  `WATCH_AUTOTUNE_STATUS.cmd` shows the status summary.
- `WATCH_AUTOTUNE_OUTPUT.cmd` 是訓練/自動化程式原始輸出  
  `WATCH_AUTOTUNE_OUTPUT.cmd` shows raw training / automation output.
- 已經在背景跑的訓練程序，本身仍然是寫到 log 檔，不會直接附著回 VSCode 既有 terminal session  
  A background training process still writes to log files and does not automatically reattach itself to an existing VS Code terminal session.
- 但你現在已經可以用 `WATCH_AUTOTUNE_OUTPUT.cmd` 在前景終端機看它的原始輸出  
  You can now watch that raw output in the foreground with `WATCH_AUTOTUNE_OUTPUT.cmd`.
- `OPEN_AUTOTUNE_MONITORS.cmd` 只是打開監看視窗，不會啟動新的訓練  
  `OPEN_AUTOTUNE_MONITORS.cmd` opens monitor windows only; it does not start a new training run.
- 之後如果是我替你啟動新的背景流程，我可以同時幫你打開這兩個視窗，不需要你手動開  
  If I launch a new background process for you later, I can also open both monitor windows at the same time.
