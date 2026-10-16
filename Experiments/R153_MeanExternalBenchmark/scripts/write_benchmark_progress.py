"""Generate an honest progress report from verified receipts, without inference."""
from pathlib import Path
import datetime
import json
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from study import read, sha
from scripts.monitor_training import completion, ORDER


def main():
    final_path = ROOT / 'results/full_benchmark/handoff_verified.json'
    review_path = ROOT / 'results/full_benchmark/delivery_verified.json'
    if final_path.exists() and review_path.exists():
        final = read(final_path)
        review = read(review_path)
        assert final['state'] == review['state'] == 'passed'
        assert review['visual_review_complete'] and review['runtime_samples'] == 150
        assert review['archive_sha256'] == final['archive_sha256'] == sha(final['archive'])
        assert len(final['completed_scope']) == 10
        text = '''# 外部模型比較結果與完成狀態

本次十種可執行方法的訓練、完整實拍驗證、效率量測、數字重算及圖表核對已完成。另兩個方法的官方後端阻礙如實保留，未列入已驗證方法。原論文、MOSR與既有保存量測未修改；已交付的九方法資料包保留原樣。

可直接交給網頁對話修改論文的資料：[完整論文交接](FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)、[修改位置指南](FINAL_BENCHMARK_THESIS_HANDOFF/PAPER_UPDATE_GUIDE.md)、[全部圖表與數據包](FINAL_BENCHMARK_THESIS_HANDOFF.zip)。以下為已核對的完整結果；更多模型架構、原訓練目標與設定、全部合成測試及未四捨五入資料見交接文件。

'''
        text += (ROOT / 'reports/FINAL_BENCHMARK_RESULTS.md').read_text(encoding='utf-8').replace('# 已完成模型之完整實拍驗證與效率比較', '## 完整結果', 1)
        text += '\n## 最終交付核對\n\n每方法930張、8370讀值、30完整有效趟次，量測失敗0。150次相同條件效率、162組完整掃描配對區間已核對；原九方法數字、區間及135次效率保持一致。SwinIR新增1800筆位移與18組區間獨立重算通過，同區域原生像素、灰階圖、附件及所有連結亦已核對。未變更實際訓練輪數，不宣稱全部充分收斂、相同訓練時間或單一模組的因果效果。全部可執行範圍已完成；原論文尚未修改，監看在交付後停止。\n'
        destination = ROOT / 'reports/BENCHMARK_RESULTS.md'
        destination.write_text(text, encoding='utf-8')
        print(json.dumps({'report': str(destination), 'sha256': sha(destination), 'benchmark_complete': True}, ensure_ascii=False))
        return
    snapshot = read(ROOT / 'runs/launcher_logs/monitor_snapshot.json')
    rows = []
    synthetic = []
    for method in ORDER:
        record = completion(method)
        if record:
            rows.append(f"| {method} | 訓練完成；實拍比較待完成 | {record['epochs_trained']} | {record['selected_epoch']} |")
            # Completion checks validate the selected weight and test receipt.
            test = read(ROOT / 'runs' / method / 'training_complete.json')['synthetic_test']
            synthetic.append((method, test))
        else:
            actual=next((x for x in snapshot.get('methods',[]) if x['method']==method),{})
            state = '使用者已暫停，不自動續訓' if actual.get('state')=='user_paused' else '訓練中' if actual.get('state')=='active' else '等待接續'
            rows.append(f'| {method} | {state} | — | — |')
    blocked = read(ROOT / 'config/blocked_models.json')
    for method in blocked:
        rows.append(f'| {method} | 官方執行環境受阻 | 0 | — |')
    for method in ('RAW', 'Wiener', 'MOSR'):
        path = ROOT / 'results/synthetic' / f'{method}.json'
        if path.exists():
            synthetic.append((method, read(path)['mean']))
    test_rows = '\n'.join(
        f"| {method} | {values['PSNR_core_dB']:.6f} | {values['SSIM_core']:.6f} | {values['PSNR_full_dB']:.6f} |"
        for method, values in synthetic
    )
    text = f'''# 外部模型比較結果與完成狀態

更新時間：{datetime.datetime.now(datetime.timezone.utc).isoformat()}。

本文件是持續更新的結果紀錄，目前尚未完成全部比較。訓練完成與完整實拍驗證分開記錄；不以合成影像分數推定實拍位移或輪廓排名。

## 一、比較規則

全部外部神經網路從零訓練，不使用公開預訓練權重。固定同一批TIFF合成影像、場景分組、共同有效監督區域及驗證規則；各模型使用各自常用的重建目標與最佳化設定。每輪看過2048組影像，至少8輪，連續5輪沒有0.02 dB的驗證改善即可停止，最多32輪。只用合成驗證分數選權重，實拍、PI與SEM不參與設定或選擇。

EDSR-x1、RDN-x1與RCAN-x1採L1與Adam；NAFNet採作者PSNR目標與AdamW；Restormer採L1與AdamW；SwinIR採作者Charbonnier目標、Adam及移動平均權重；USRNet-x1採L1與Adam。具體設定保存在訓練規則及各模型完成紀錄。USRNet-x1訓練使用已知的合成PSF及噪聲，驗證、測試與實拍使用固定平均PSF及固定噪聲設定；這項資訊差異須在比較中保留說明。

全部神經網路採FP32。原MOSR與既有RAW/MOSR量測資料維持原樣，未重新訓練MOSR，未重擬合既有圓心或輪廓。

## 二、訓練進度

| 方法 | 狀態 | 實際訓練輪數 | 選用輪數 |
| --- | --- | ---: | ---: |
{chr(10).join(rows)}

達到32輪上限只代表完成預先設定的訓練範圍，不代表已證明完全收斂。完整訓練與驗證曲線、選用權重身分及停止原因均保留在各方法紀錄。

## 三、已完成的合成測試

使用固定128個測試場景，每個場景4張影像。核心指標使用共同96×96有效區域，整張指標使用384×384影像，兩者不能混為同一指標。此處只列完成紀錄已核對的結果。

| 方法 | 核心PSNR (dB) | 核心SSIM | 整張PSNR (dB) |
| --- | ---: | ---: | ---: |
{test_rows}

合成測試有已知清楚影像；实拍沒有同區域清楚真值，不能把RAW當作真值計算重建PSNR。核心與整張分數的差異需另行檢視邊界與輸出行為，不能只依核心分數宣稱全面改善。

## 四、實拍比較

共同資料為30次掃描、每次31张，共930張；固定九顆柱體及量測設定。所有位移先對九個二維位移向量取算術平均，再投影至固定方向。每次掃描以30步的樣本標準差表示單趟波動，再以30次掃描之方差平均開根號得到合併標準差。配對區間以整次掃描作抽樣單位。

已核對的RAW/MOSR基準：合併單趟波動標準差8.780826／4.272773 nm；相鄰PI平均絕對差6.969175／3.598341 nm。30次掃描均改善單趟波動，逐次改善範圍34.6%至67.2%。完整計算、敏感度與逐次資料見[平均數與中位數分析](MEAN_MEDIAN_RESULTS.md)。

外部模型的930張重建、固定量測、完整掃描配對區間、輪廓及尺寸結果尚未全部完成。本節不填推估值，不預先排列勝負。量測失敗必須保留，不能只挑成功影像或剔除不利掃描。

## 五、效率與限制

新的同GPU、FP32、batch=1時間及記憶體測試尚待完成。須區分原生整張推論、MOSR原有分塊策略，以及因整張記憶體不足而採用的固定替代分塊。具有全域運算的模型使用替代分塊時，須說明其影像上下文已改變，不直接宣稱與整張結果相同。時間只計同步完成的模型前向，讀檔、儲存及CPU量測另列。

U-Net目前缺少可用的作者Caffe/Linux後端；MambaIRv2的官方CUDA運算建置失敗。原始來源與失敗紀錄已保留，未拿簡化或其他模型冒充完成比較。

MOSR在原尺寸參照比較中有較大的直徑誤差，這項不利結果仍須保留。短步波動改善不等於已證明長距離誤差或絕對尺寸改善。

## 六、尚待完成與交付條件

各模型訓練與選用权重核對、共同930張實拍驗證、全部固定量測與失敗紀錄、完整掃描配對區間、新效率量測及完整報告完成後，才可宣布比較工作完成。論文修改位置與已確認平均數結果見[論文修改對照表](THESIS_UPDATE_MAP.md)。原論文尚未修改。
'''
    budget_path = ROOT / 'config/TIME_BUDGET_OVERRIDE.json'
    if budget_path.exists():
        text = text.replace('每輪看過2048組影像，至少8輪，連續5輪沒有0.02 dB的驗證改善即可停止，最多32輪。',
            '每輪看過2048組影像。原規則至少8輪、連續5輪沒有0.02 dB改善停止、最多32輪。使用者後來因時間限制，改為尚未開始的RCAN-x1、Restormer、USRNet-x1、SwinIR最多8輪；EDSR-x1與NAFNet原32輪結果保留，RDN-x1保留已完成輪數及保存的最佳合成驗證結果並結束。此為較短訓練比較，實際輪數不同，不能宣稱相同訓練時間或所有模型均充分收斂。資料、有效區域、模型、訓練目標、最佳化方式及驗證選擇保持原規則。')
    stage_receipt = ROOT / 'results/available_real/complete.json'
    if stage_receipt.exists() and read(stage_receipt)['state'] == 'complete':
        import pandas as pd
        frame = pd.read_csv(ROOT/'reports/data/available_real/summary.csv')
        rows = ['| 方法 | 單趟波動合併SD nm | 相鄰PI MAE nm | 輪廓重複SD nm |', '| --- | ---: | ---: | ---: |']
        rows += [f'| {r.method} | {r.pooled_within_scan_sd_nm:.3f} | {r.adjacent_mae_nm:.3f} | {r.contour_repeat_sd_nm:.3f} |' for r in frame.itertuples()]
        text = text.replace('外部模型的930張重建、固定量測、完整掃描配對區間、輪廓及尺寸結果尚未全部完成。本節不填推估值，不預先排列勝負。量測失敗必須保留，不能只挑成功影像或剔除不利掃描。',
            'RAW、Wiener、EDSR-x1、NAFNet、RDN-x1、RCAN-x1、MOSR七方法已完成每方法930張、30趟完整量測；所有趟次有效、沒有量測失敗。保存RAW/MOSR讀值直接重用；四個完成外部模型與Wiener共4650份新原生重建、41850筆新讀值。全掃描配對區間共108組，新效率量測共105次。Restormer、USRNet-x1、SwinIR的訓練／實拍結果仍待完成，不能將本階段視為全部benchmark完成。\n\n'+'\n'.join(rows)+
            '\n\n完整結果、形狀／尺寸／SEM、速度與記憶體、配對區間及不利結果見[七方法完整階段報告](AVAILABLE_MODELS_REAL_RESULTS.md)，可上傳網頁對話的完整文件見[階段論文交接](AVAILABLE_MODELS_STAGE_COMPLETE/REPORT.md)。MOSR位移波動及相鄰PI MAE在此七方法最低；輪廓重複SD與EDSR差值區間跨零，不宣稱確定較好。NAFNet與EDSR的去尺寸形狀波動較低，RAW之SEM直徑差較小，速度與記憶體指標各自保留。')
        text = text.replace('新的同GPU、FP32、batch=1時間及記憶體測試尚待完成。',
            '上述七方法的新同GPU、FP32、batch=1時間及記憶體測試已完成，全部使用相同三張影像、各五次前向，訓練釋放GPU。後續三個方法仍待完成同條件測試。')
    complete_scope=ROOT/'results/completed_models/complete.json'
    if complete_scope.exists() and read(complete_scope).get('completed_models_user_scope_complete'):
        text=text.replace('本文件是持續更新的結果紀錄，目前尚未完成全部比較。','使用者指定的已完成模型範圍已完整彙整：六個外部模型加RAW、Wiener、MOSR共九方法；SwinIR依使用者要求保持暫停，不列入比較且不自動續訓。')
        text=text.replace('Restormer、USRNet-x1、SwinIR的訓練／實拍結果仍待完成，不能將本階段視為全部benchmark完成。','Restormer與USRNet-x1已完成新增實拍驗證，最新九方法完整結果見下節；SwinIR依使用者要求暫停，不列入結果或排名。')
        text=text.replace('後續三個方法仍待完成同條件測試。','新增Restormer與USRNet-x1同條件30次測試已完成；九方法合計135次，SwinIR未測且保持暫停。')
        frame=pd.read_csv(ROOT/'reports/data/completed_models/summary.csv')
        rows=['| 方法 | 單趟波動合併SD nm | 相鄰PI MAE nm | 輪廓重複SD nm |','| --- | ---: | ---: | ---: |']
        rows += [f'| {r.method} | {r.pooled_within_scan_sd_nm:.3f} | {r.adjacent_mae_nm:.3f} | {r.contour_repeat_sd_nm:.3f} |' for r in frame.itertuples()]
        text+='\n## 最新完成：使用者指定九方法論文交付\n\n'+ '\n'.join(rows)+'\n\n每方法930張、8370筆讀值、全部30趟有效、无失敗。全部144組配對區間、135次效率、尺寸／形狀／SEM、詳細模型設定及資料見[完整論文交接](COMPLETED_MODELS_THESIS_HANDOFF/REPORT.md)與[附件ZIP](COMPLETED_MODELS_THESIS_HANDOFF.zip)。原模型與原論文未修改，SwinIR保存step256且不自動續訓；兩個官方後端阻礙另外保留。MOSR位移目標最低，輪廓與EDSR區間跨零；形狀NAFNet／EDSR／Restormer較好、SEM尺寸RAW較好，速度與配置／保留峰值各自判讀，不宣稱全指標最佳。\n'
        text=text.replace('无失敗','無失敗')
    for old, new in [('实拍', '實拍'), ('31张', '31張'), ('权重', '權重')]:
        text = text.replace(old, new)
    destination = ROOT / 'reports/BENCHMARK_RESULTS.md'
    destination.write_text(text, encoding='utf-8')
    print(json.dumps({'report': str(destination), 'sha256': sha(destination), 'benchmark_complete': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
