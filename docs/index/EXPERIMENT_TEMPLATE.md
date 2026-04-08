# 實驗模板 / Experiment Template

Last updated: 2026-04-08

新實驗建立時，複製此結構作為起點。
Copy this structure when creating a new experiment.

---

## 目錄結構

```
Experiments/R##_Description/
├── README.md                         # [必備] 見下方模板
├── scripts/
│   └── launch_r##.py                # [建議] 訓練啟動器
├── reports/
│   └── R##_RESULTS.md               # [必備] 完整結果報告
└── results/
    ├── external_gmf/                 # [如果送了外部驗證]
    │   ├── pitch0p8px/GMF_score.txt
    │   ├── pitch0p08px/GMF_score.txt
    │   └── pitch8px/GMF_score.txt
    ├── sequence_analysis/            # [建議] 720-angle 內部分析
    └── *_recon/                      # [如果有推理輸出]
        ├── pitch0p1um_y_60_odd/
        ├── pitch0p01um_y_40_odd/
        └── pitch1um_y_100_odd/
```

## README.md 模板

```markdown
# Round ## — [實驗名稱]

## 假說

[一句話描述這個實驗要驗證什麼]

## 設計

[核心機制、和先前 Round 的差異、為什麼這樣設計]

## 候選

| Tag | 關鍵參數 | 說明 |
|-----|---------|------|
| `r##_candidate_name` | PARAM=VALUE | 主候選 |

## 結果

[簡要結果摘要，詳見 reports/R##_RESULTS.md]

## 資料

- Checkpoint: `Traing_Progress/..._YYYYMMDD_HHMMSS/weights/best_tradeoff.pth.tar`
- External GMF: `results/external_gmf/`

## 分支

`sandbox/r##`
```

## Launcher 模板

```python
"""Round ## — [Description] Launcher"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "Model"))

CANDIDATES = {
    "r##_candidate_name": {
        # config overrides
    },
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, choices=list(CANDIDATES.keys()))
    parser.add_argument("--num-epoch", type=int, default=100)
    parser.add_argument("--device", type=str, default="cuda:0")
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0]] + remaining

    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer
    CFG = trainer.CFG
    for key, val in CANDIDATES[args.candidate].items():
        setattr(CFG, key, val)
    CFG.MODEL_NAME = f"GESR_v1_v5_ST0p8_SWP_{args.candidate}"
    trainer.MODEL_NAME_BASE = CFG.MODEL_NAME  # ensure artifact identity
    CFG.NUM_EPOCH = args.num_epoch
    CFG.DEVICE = args.device
    trainer.main()

if __name__ == "__main__":
    main()
```

## 檢查清單

新實驗建立後確認：
- [ ] README.md 寫了假說和設計
- [ ] Launcher 有 `trainer.MODEL_NAME_BASE = CFG.MODEL_NAME`
- [ ] 分支命名 `sandbox/r##`
- [ ] 報告用 `R##_RESULTS.md` 格式
- [ ] 送外部 GMF 後有 `results/external_gmf/` 三尺度
