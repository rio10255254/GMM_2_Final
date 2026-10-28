from pathlib import Path
import json, platform
import numpy, pandas as pd, scipy, skimage, torch

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT.parents[1]
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def table(frame):
    lines=['| 條件 | 方法 | 配對數 | 步距波動 nm | 名義步距平均差 nm | 九顆差異中位數 nm |','|---|---|---:|---:|---:|---:|']
    for r in frame.itertuples():lines.append(f'| {r.sequence} | {r.method} | {r.n_pairs} | {r.step_sd_nm:.6f} | {r.nominal_mae_nm:.6f} | {r.median_within_grid_sd_nm:.6f} |')
    return '\n'.join(lines)

def main():
    full=ROOT/'results/full120/complete.json'
    if full.exists() and load(full).get('state')=='complete_objective_calibrated_full120':
        from finalize_full120 import main as finalize_current
        return finalize_current()
    done=load(ROOT/'results/20x/complete.json'); assert done['state']=='complete_20x_only'
    replay=load(ROOT/'results/submission_replay_check.json');assert replay['passed']
    summary=pd.read_csv(ROOT/'results/20x/summary.csv')
    combined=summary[summary.sequence=='20x_only_two_conditions'].set_index('method')
    changes=[]
    for baseline in ['Raw','Wiener']:
        b=combined.loc[baseline];r=combined.loc['R152'];cols=['step_sd_nm','nominal_mae_nm','median_within_grid_sd_nm']
        changes.append({'baseline':baseline,**{c:float((r[c]-b[c])/b[c]*100) for c in cols}})
    save(ROOT/'results/20x/change_percent.json',dict(sign='R152 minus baseline / baseline; positive is worse',values=changes))
    env=dict(python=platform.python_version(),numpy=numpy.__version__,pandas=pd.__version__,scipy=scipy.__version__,skimage=skimage.__version__,torch=torch.__version__,device=torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu')
    save(ROOT/'results/environment.json',env)
    status=load(ROOT/'results/preflight_status.json');status.update(status='PARTIAL_20X_COMPLETE_50X_BLOCKED',partial_20x_complete=True,partial_20x_images=80,partial_20x_pairs_per_method=60,native_20x_bank_confirmed_by_user=True,full_r152_inference_started=False,full_four_condition_result_available=False)
    save(ROOT/'results/preflight_status.json',status)
    save(ROOT/'results/20x/status.json',done)
    report='''# R152 IMPACT2026 來源與協議核對

## 判定

已找回原四組120配對、166張不同原始影像、原量測程式，以及原Wiener使用的20×／50×校正資料。原投稿三項統計與完整量測重播通過。使用者進一步指定20×採用R152原生光學資料，這部分已完成80張推論、60配對的三方法共同量測。

**整個跨倍率工作尚未完成：R152可直接使用的50×整組光學資料及已驗證接法未找到。** 原50× Wiener校正核存在，不能把「已有Wiener校正核」等同「已有R152相容資料」。未重新訓練、未修改D槽既有正式基準、未替换数据或補造結果。

使用者已澄清對話訊息本身就是執行指令；沒有缺少的獨立指令文件。兩頁投稿PDF已逐頁閱讀與檢視；全文與原頁面渲染保存在sources和qa。

## 找回的四組配對

| 原条件 | 配對數 | 不同影像數 | 比例 μm/px |
|---|---:|---:|---:|
| 50×，0.5 μm | 30 | 44 | 0.0690 |
| 50×，1.0 μm | 30 | 42 | 0.0690 |
| 20×，0.5 μm | 30 | 39 | 0.1725 |
| 20×，1.0 μm | 30 | 41 | 0.1725 |

來源為R80的 `displacement_raw_locked_selection_all.csv`，逐組對應投稿讀值表與原Raw eligibility表均相符。這不是新選的配對。原選擇規則是先通過平台可用性門檻，再按Raw名義步距差、九顆差異及影格編號排序取30組；不是隨機抽取或全序列無條件納入。每對影像相鄰，但部分配對共用影像，不宜寫成120次完全獨立重拍。

已核對每張原圖存在、格式與SHA-256；小型來源和程式逐位元保存。完整來源位置與核對值見 `results/source_manifest.json`，原圖明細見 `results/raw_frame_manifest.csv`。

## 投稿量測及三項統計是否一致

一致。使用原 `reference_circle_core.py` 和 `run_displacement_lsc.py`，保留原九顆身分、原預測裁切、暗柱方向、原取邊方法和幾何最小平方法。

- 配對步距：先算九顆各自的有號水平位移，再取中位數的絕對值。不是二維移動長度。
- Step SD：每組30個步距的樣本標準差（ddof=1），四組平均。
- Nominal MAE：對名義0.5／1.0 μm步距的平均絕對差，四組平均；等量30配對時與120配對合併平均相等。沒有改用PI回授。
- Median within-grid SD：每對九顆有號水平位移的樣本標準差，再對120對取中位數。
- 20×局部粗輪廓取64點，50×取96點；這是原投稿程式設定，非通用720方向的另一條序列量測路線。本次依使用者要求保持投稿讀法，不自行改成720點。
- 原名義位移僅用於搜尋窗口及後續誤差比較；圓擬合初值取邊界點平均，圓擬合目標不含指令位移。這不等於完全取消裁切初始化的影響。

## 原稿完整重播證據

在本獨立工作區實際讀取原圖與舊MOSR影像，重新執行四組Raw、Fixed Wiener與歷史MOSR量測。共4482筆圓心、360筆配對，全部與原表相符；圓心最大差約4.55e-13像素，三項配對讀值最大差約3.55e-15（依欄位單位）。詳見 `results/submission_replay_check.json`。

原稿表格重現如下；歷史MOSR是V42，絕不能改名為R152：

| 方法 | Step SD nm | Nominal MAE nm | Median within-grid SD nm |
|---|---:|---:|---:|
| Raw | 8.884944 | 7.001601 | 12.547376 |
| Fixed Wiener | 7.906361 | 6.417996 | 5.983640 |
| 歷史MOSR／V42 | 7.292303 | 5.742972 | 4.885544 |

## 光學來源與缺項

R152交付銀行位於原R152資料夾的 `calibration/measured_psf_bank.npz`，25顆101×101核，鎖定比例0.1725 μm/px。使用者本次確認這就是20×應使用的資料；20×推論保持它不變。原Frozen R148v2與新增支路的光學狀態也保持交付時原樣。

原Wiener分別讀取 `PSF_Fitting/tests/artifacts/cd_verification_20260714/20x_deconvolution_sweep.mat` 與50x同名資料。它們各只有1顆101×101核，分別追溯到 `PSF_Fitting/output/pillar_via_junction_psf_20260713/{20x,50x}/fit_result/PSF_fitted_2D_FOVstack.mat`。逐元素核對兩段來源一致，倍率與物方尺度由相應 `selected_frame.json` 證實。Wiener固定正規量0.0565，完整保留原背景／對比處理及裁切方式。

R152的原生介面要求25顆核，並從交付保存點載入原光學狀態。**不能僅把單顆50×核換檔，就宣稱模型用了正確的50×校正。** 需要可追溯的50×整組25顆校正資料、核的排列／尺度／中心約定，以及不改學得權重但正確更換原主體與新增支路光學內容的已驗證接法。未找到這份交付物；不複製單核25次、不放大20×核、不借用20×核。

## R152身分檢查

32項交付來源鎖通過；完整紀錄的29個連結與關鍵數值核對通過。交付保存點SHA-256為 `17bf7c63f070520a5ef8d4428010340686f465bf1fa03ef8225c0a2eadad4a61`，倍率1。原R148v2的192項權重／固定狀態逐項相等。詳細紀錄見 `results/r152_model_identity.json`。

## 下一步唯一必要缺項

提供或指定已完成、可直接接入目前R152的50×相容光學資料及既定接法。取得後先核對來源、尺度、模型接線和同權重條件，才補跑原50×兩組、合併四組統計及完成跨倍率海報。若需要另做光學校正或更動模型，屬目前「不自行改模型或換資料」限制之外的新增工作，不能自行當成本輪已獲授權的替代方案。
'''
    (ROOT/'reports/R152_AUDIT.md').write_text(report,encoding='utf-8')
    text='''# R152 IMPACT2026：20×部分結果

## 完成範圍

只完成20×原0.5與1.0 μm條件、60個鎖定配對、80張不同影像。Raw、Fixed Wiener與R152共2160筆圓心、180筆配對。50×未完成，因此沒有四組120配對的R152總結果。

R152使用原生20×銀行與已交付模型，倍率1；FP32、關閉TF32、原512/24分塊方式。量測直接使用原生浮點輸出；沒有再銳化、量化、移動或尺寸修正。所有模型權重與固定狀態在推論前後逐項相等。Wiener採原投稿20×單顆校正核及原固定設定，沒有為新結果調參。

## 結果

'''+table(summary)+'''

兩組合併時，前兩項取兩條件平均；最後一項取60配對的中位數。不是原稿四組平均。

## 驗證

- 所有80張重建各有原圖、模型、光學銀行與輸出的核對值；可依收據續跑，不能覆寫不相符檔案。
- 本次20×流程中Raw和Wiener重新量測後，再對照投稿原表，120列配對全部一致。
- 交付驗證另從存下的2160筆圓心重新計算180筆配對與九列摘要。
- 配對未重選；未新增排除影格或方法專用的邊界清理。
- 全部三项数字分别呈现，不用可調總分掩蓋取捨；本次沒有新增顯著性宣稱。

## 海報素材

- `poster_assets/results_20x_only.png` / `.svg`：60配對三項主結果。
- `poster_assets/representative_20x_only.png` / `.svg`：兩組各取原第一個鎖定配對的起始影像，三方法相同顯示範圍，2 μm比例尺。
- `poster_assets/RESULTS_20X_TEXT.md`：結果表、英文圖說及適用範圍。
- `poster_assets/method_protocol_pending.png` / `.svg`：全實驗方法圖，明確標示50×尚缺。
- `poster_assets/POSTER_TEXT.md`：方法段落和不能沿用的舊結果主張。

未完成完整跨倍率海報；上述20×結果可使用，但必須保留範圍標示。詳見 `R152_AUDIT.md` 的50×缺項。
'''
    (ROOT/'reports/R152_RESULTS.md').write_text(text,encoding='utf-8')
    # Notes stay in this isolated worktree; formal baseline values must remain unchanged.
    policy_path=WORK/'ESTIMATOR_POLICY.json';policy=load(policy_path);baseline=json.dumps(policy['formal_baseline'],sort_keys=True)
    policy['r152_impact2026_worktree_note']=dict(status='20x_partial_complete_50x_blocked',formal_baseline_unchanged=True,external_compare='Not external GMF; original IMPACT maximum-gradient/LSC nominal-step protocol.',notes='20x uses delivered native R152 optical bank as explicitly requested; 50x requires compatible calibration. No promotion.',report='Experiments/R152_IMPACT2026Validation/reports/R152_RESULTS.md')
    assert json.dumps(policy['formal_baseline'],sort_keys=True)==baseline
    save(policy_path,policy)
    statepath=WORK/'PROJECT_STATE.md';state=statepath.read_text(encoding='utf-8')
    marker='<!-- R152_IMPACT2026_WORKTREE_ONLY -->'
    if marker not in state:
        note=marker+'\n2026-09-29 本獨立工作區完成R152原生20×的60配對共同量測；原四組120配對與投稿量測已找回並重播核對。50×相容光學資料及接法未找到，完整跨倍率結果未成立。正式基準不變。[部分結果](Experiments/R152_IMPACT2026Validation/reports/R152_RESULTS.md)\n'
        state=state.replace('<!-- QUICK_HANDOFF_START -->','<!-- QUICK_HANDOFF_START -->\n'+note,1)
        state+='\n## R152 IMPACT2026 獨立工作區補充\n\n'+note+'\n本工作區根層其餘內容源自較早的Git提交；當次D槽現況快照保存在本驗證資料夾sources中。未向D槽同步這些治理註記。\n'
        statepath.write_text(state,encoding='utf-8')
    indexpath=WORK/'Experiments/INDEX.md';index=indexpath.read_text(encoding='utf-8')
    if marker not in index:indexpath.write_text(index+'\n'+marker+'\n## 本獨立工作區的R152投稿跟進\n\n[R152 IMPACT2026部分結果](R152_IMPACT2026Validation/reports/R152_RESULTS.md)：20×60配對完成，50×相容光學缺項待補；沒有重訓或更換正式基準。\n',encoding='utf-8')
    print(json.dumps(changes,indent=2))

if __name__=='__main__':main()
