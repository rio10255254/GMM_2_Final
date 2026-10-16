# 包裝修訂記錄

第一階段建立後，在獨立暫存副本測試了合成 100 顆銀行安裝、四次訓練更新及正式推論拒絕。依測試結果，補上銀行來源鎖與測試銀行不可用於正式推論的保護。第一階段來源清單保留在 `config/history/INTEGRITY_STAGE0.json`；以下是本次定向變更，其餘訓練資料、評估參照與模型來源均未修改。

| 檔案 | 原 SHA256 | 完成 SHA256 |
|---|---|---|
| `utils.py` | `3ee8cbc311a70712fe25ec0fda34d4e034d21470822bbe3f945baaaccd149e09` | `b3587981c06ff44ad013aa1a1b21bc6018898696253303038ab5b703597fcc12` |
| `train.py` | `583404a3ed3d71384a8bd20769d4c7257d17ce01e2ae4cd3325e6221e7d4e537` | `ace212429ebc9c5d89a4879922f3d240258511113af4490334b4e728994baf10` |
| `infer.py` | `19d9c61f26dfe6254a9c30dd91b2def2731260bf60847c4d3a08f58502bb6d73` | `d3f01350c48be43c0b9b01655e292ff314a0b0573230e4223c3d972b67972eeb` |
| `verify_package.py` | `866166505636782d8dc3fc7e20d589a0c33ab7097e388f4b3283fdbcdbc45e68` | `d4a5694692d9e60ec0717697f1c630560a960b1b481eab419c6f39cc8edc27e2` |
| `install_bank.py` | `d4fc3bc9d61e709965309012f9a7bb591d94e8e2ba56b974dea0244b0fea4c15` | `5742c832ec62c8c24ff77aab2fa5af3acd8e16bc71d3962a99e6b9e39e946589` |

正式長訓練與實測 PSF 自適應能力尚未由此包裝測試證明。

完整性清單排除 10 個 Python 可再生快取；程式、資料與權重沒有改動。

第二階段補上包外 `--data-root` 訓練入口，避免為加上 PSF 真值而改寫已鎖定的原始合成資料。已在獨立資料根目錄跑四次更新、以暫存標記讀入 `psf_index`，並確認來源原件未變。前一階段清單保留為 `config/history/INTEGRITY_STAGE1.json`。

- `dataset.py`：`4e92eaf3b2e728d5f1d88412ca00c2781f345a72213c9c667a00998c155e24c5` → `dabbabe476c81e654b3fb9b1d215f5571bb9600bc232052cdaa4373b64a587ad`
- `train.py`：`ace212429ebc9c5d89a4879922f3d240258511113af4490334b4e728994baf10` → `09a337c9350a87fbd7fcf11c9f4d5fd31920a7c6d72cd8933b2346480459371d`
- `MODEL_CARD.md`：`8ae90d6509ee12a8346c81c65954e327df45e1e1cb642cf4994147be884070ef` → `179cbb14c58db3dbd531145563d463ead2e84efe9f006aba66d78f31f255895b`
- `tests/VALIDATION.md`：`4d067e8d7e887fd749bdea4a2bb438d977cfe58223050234b0ae88d6db109e2a` → `ed5216914957e079ad79a8aa617a10f091d088cafa1dc97ce84929c55c0d1e8c`
- `README.md`：`9ee0554902913c428aaaac9ed7ec6c3542357b0a9669a69c531861c0884f20e8` → `c4c97553efad39d5635db1b24338f318d320cb12df08bf3fdbf1432365b4cb6f`
- 新測試 `tests/probe_external_labeled_data.py`：`a3e4fb0eb241bbce2c96e3a7ece8c5cd863f2a88326f46af4b7f87b0d17c2d8f`
