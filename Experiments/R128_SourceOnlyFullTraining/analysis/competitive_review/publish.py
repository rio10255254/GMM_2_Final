"""Create a supplemental report and scientific comparison figure from verified rows."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from common import load, save, record, sha, now
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager


def table_text(data, columns, formats=None):
    formats = formats or {}
    rows = ['| '+' | '.join(columns.values())+' |', '| '+' | '.join(['---']*len(columns))+' |']
    for _, row in data.iterrows():
        rows.append('| '+' | '.join(format(row[k], formats[k]) if k in formats else str(row[k]) for k in columns)+' |')
    return '\n'.join(rows)


def main():
    out = ROOT/'results/competitive_review'
    verification = load(out/'verification.json')
    assert verification['all_1080_contour_rows_recomputed'] and verification['sources_unchanged']
    summary = pd.read_csv(out/'summary.csv')
    paired = pd.read_csv(out/'paired_comparisons.csv')
    lsc = pd.read_csv(out/'LSC_recomputed.csv')
    t = pd.read_csv(out/'measurements.csv')
    plan = load(out/'plan.json')
    methods = plan['methods']
    labels = ['原圖', 'R61v16', 'R109', 'R119', 'R128']
    display = dict(zip(methods, labels))
    font_manager.fontManager.addfont('C:/Windows/Fonts/msjh.ttc')
    plt.rcParams['font.family'] = 'Microsoft JhengHei'
    fig, axes = plt.subplots(2, 2, figsize=(11.4, 8.4))
    refs = ['historical', 'global_pitch_matched']
    ref_labels = ['既有尺度參考', '依柱距統一尺度的參考']
    colors = ['#969FA8', '#A4A9AE', '#44779B', '#9AABB8', '#D58236']
    for ri, ref in enumerate(refs):
        group = summary[(summary.scope == 'all_36') & (summary.reference == ref)].set_index('method').loc[methods]
        for ci, metric in enumerate(['mean_boundary_px', 'circularity_error']):
            ax = axes[ri, ci]
            values = group[metric].to_numpy()
            bars = ax.bar(labels, values, color=colors, width=.65)
            ax.set_ylim(0, 1.03 if ci == 0 else .061)
            ax.set_title(ref_labels[ri], fontsize=12, pad=10)
            ax.set_ylabel('輪廓差距（像素；越小越好）' if ci == 0 else '圓度與 SEM 的差距（越小越好）', fontsize=10)
            ax.grid(axis='y', alpha=.2)
            ax.set_axisbelow(True)
            ax.spines[['top', 'right']].set_visible(False)
            for bar, value in zip(bars, values):
                ax.text(bar.get_x()+bar.get_width()/2, value+(0.015 if ci == 0 else .0009), f'{value:.3f}' if ci == 0 else f'{value:.4f}', ha='center', fontsize=10)
    fig.suptitle('同一批實拍與 SEM：R128 輪廓領先，圓度仍未全面改善', fontsize=17, y=.98)
    fig.text(.5, .035, '36 顆柱體，各取 3 次拍攝的中間值再彙整；同一試片，並非 108 個獨立樣本。\n圓度比較的是接近實際 SEM 的程度；兩種參考的結果都保留。', ha='center', fontsize=10, linespacing=1.6)
    fig.tight_layout(rect=[0, .09, 1, .95], h_pad=2.4, w_pad=2.2)
    image_path = ROOT/'reports/figures/competitive_contour_circularity.png'
    assert not image_path.exists()
    fig.savefig(image_path, dpi=150)
    plt.close(fig)

    lines = [
        '# R128 與近期模型：LSC、完整輪廓與圓度的同條件盤點', '',
        '2026-09-10。結論：R128 是值得繼續驗證的單一候選。在目前正常拍攝的配對柱體上，它的整體外輪廓、面積、周長比所列舊候選更接近既有 SEM 參考；但圓度改善會隨參考輪廓改變，局部最差距離也未全面改善，而且尚無相同正式流程的 R128 LSC 成績。因此不能宣稱它已是全能量測冠軍。', '',
        '正式專案基準仍是 COMBO；V42 是歷史論文結果模型，R61v16 是另一個歷史重建候選，兩者不能混為同一份權重。R109 E48 是有既有 LSC 成績的研究比較對手；R119 B E42 的因果審查修正仍優先於舊完成宣稱；R128 P_s1285002 step8192 仍是唯一保留的研究試用候選。此次不修改模型、訓練資料或舊預期雜湊。', '',
        '## 比較怎麼做', '',
        '使用同一試片的 36 顆配對柱體、正常拍攝照片 13/14/15。各方法都沿用既有完整外輪廓，使用同一個由原圖決定的平移，不各自重新對齊，也不為任何模型調整尺寸。原圖輪廓、SEM 輪廓及柱體對應在三個來源間完全相同。這是已有資料的回顧比較，不是新試片或未見確認集。', '',
        '以下先對每顆柱體取三張照片的中間值，再對 36 顆柱體彙整。改善顆數也按這 36 顆計算；不能理解成每次拍攝都改善。所有照片逐項結果、每顆結果及不利結果均保留。兩種 SEM 尺度參考同時呈現，不選擇對模型較有利的一種。', '',
        'R128 表示既有實際試用輸出，包含原本的影像外圍保留機制；中央 16 顆完全由模型重建的柱體另行比較，整體輪廓的優勢仍成立。', '',
        '## 完整外輪廓與形狀', '',
        '表內除了重疊程度，其他指標皆越小越好。圓度差距是與 SEM 柱體圓度之差，並非與完美圓的差距。', '',
    ]
    cols = {'method':'方法', 'mean_boundary_px':'輪廓差距（像素）', 'area_error_pct':'面積差距（%）', 'perimeter_error_pct':'周長差距（%）', 'circularity_error':'圓度差距', 'iou':'重疊程度'}
    fmt = {'mean_boundary_px':'.4f', 'area_error_pct':'.3f', 'perimeter_error_pct':'.3f', 'circularity_error':'.5f', 'iou':'.5f'}
    for ref, label in zip(refs, ref_labels):
        g = summary[(summary.reference == ref) & (summary.scope == 'all_36')].set_index('method').loc[methods].reset_index()
        lines += ['### '+label, '', table_text(g, cols, fmt), '']
        cur, raw, old = [g[g.method == m].iloc[0] for m in ['R128_P_s1285002', 'Raw', 'R109_E48']]
        lines += [f'相對原圖，R128 的輪廓差距降低 {(1-cur.mean_boundary_px/raw.mean_boundary_px)*100:.2f}%，面積差距降低 {(1-cur.area_error_pct/raw.area_error_pct)*100:.2f}%，周長差距降低 {(1-cur.perimeter_error_pct/raw.perimeter_error_pct)*100:.2f}%。相對 R109，輪廓差距降低 {(1-cur.mean_boundary_px/old.mean_boundary_px)*100:.2f}%。這些百分比是上述整體中間值之比，不是每顆都進步同樣百分比。', '']
        q = paired[(paired.reference == ref) & (paired.scope == 'all_36') & (paired.method == 'R128_P_s1285002') & paired.metric.isin(['mean_boundary_px','perimeter_error_pct','circularity_error'])]
        lines += [table_text(q, {'baseline':'比較對象','metric':'指標','improved':'改善顆數','worsened':'退步顆數','tied':'持平顆數'}), '']
    lines += ['![相同條件的輪廓與圓度比較](figures/competitive_contour_circularity.png)', '',
        'R128 兩種參考下皆有 33/36 顆的外輪廓比 R109 更接近 SEM。相對 R61v16 則為 26/36 與 25/36 顆。不能把整體排名第一說成所有柱體、所有位置都勝出。', '',
        '## 圓度與局部輪廓為何不能宣稱已過關', '',
        '既有尺度下，R128 圓度差距的整體值從原圖 0.01619 降到 0.01249；但按柱距統一尺度後，從 0.01177 升到 0.01506，36 顆中 19 顆退步。中央 16 顆的相同問題也存在，不能歸因於外圍保留原圖。', '',
        '兩個參考來自同一批 SEM；另一尺度的流程會重新縮放 SEM 照片並抽取輪廓。確認模型本身的圓度在兩個參考間完全相同，但每顆 SEM 參考圓度的絕對差異中間值約 0.01459，已與欲宣稱的模型改善量同級甚至更大。這支持「目前的圓度判斷對參考輪廓建立方式敏感」，不支持實物圓度已得到可靠改善。幾何上的等比例縮放不應改變圓度；此處含有影像重取樣、像素輪廓與輪廓抽取的影響，尚未完成物理參考資格確認。', '',
        '整體貼合更好也不代表每段輪廓更好：依柱距統一尺度的所有觀察中，最差局部距離由原圖 2.236 像素增至 R128 的 2.828 像素；既有尺度下是 3.000 → 3.162 像素。這些不利值均保留。', '',
        '## LSC：舊模型確實有進步，R128 尚未同規則測量', '',
        '以下重新由原始逐對紀錄計算：四組真實 20×/50× 位移序列，每組同樣 30 對原圖事先選定的影格，總計 120 對。各模型沿用相同影格，並未重新挑對自己有利的影格。原始選法偏向原圖較穩定的 30 對，故也不是所有場景的無條件成績。', '',
        '「位移波動」是先計算每組量到步距的波動，再平均四組；「柱體間不一致」是同一對影格中九顆柱體量出位移的分散程度。越小代表越穩，但不能等同於獨立位置真值證明的準確度。', '',
    ]
    combined = lsc[lsc.scope == 'all_four_sequences'].copy()
    lines += [table_text(combined, {'method':'方法','n_pairs':'相同影格對數','step_sd_nm':'位移波動（奈米）','mean_nominal_abs_error_nm':'與設定步距差距（奈米）','median_within_grid_sd_nm':'柱體間不一致（奈米）','median_cross_axis_abs_nm':'橫向偏移（奈米）'}, {k:'.3f' for k in ['step_sd_nm','mean_nominal_abs_error_nm','median_within_grid_sd_nm','median_cross_axis_abs_nm']}), '',
        'R109 的位移波動相對原圖約減少 28%，柱體間不一致約減少 69%；R119 的位移波動約減少 25%。R119 在四組中的三組波動略低於 R109，但在 20×、1 微米那组較差，整體未勝過 R109。傳統 Wiener 處理已有 7.392 奈米的位移波動，R109 相對它的整體改善約 5.3%，所以它也必須留在後續比較中。', '',
        'V42 的表內數字保留以維持歷史完整性，但先前已查明其訓練資料含這批評估影像的衍生資料與 SEM 半徑答案；這些是同來源適應成績，不能當未見資料的公平冠軍證據。此處不推斷動機，也不將該特定重疊稽核擴大套到其他權重。', '',
        'R128 目前沒有這套 LSC 的結果。前次約 0.01319 像素是原圖與重建之間，另一套整幅影像位移讀法的變動；不能換算後塞入本表，更不能當作 LSC 提升成績。', '',
        '## 下一個有意義的判斷', '',
        '保留現在這一個 R128，先讓它走與原圖、Wiener、R109 相同的 120 對影格、同樣柱體、同樣 LSC 計算，逐組檢查位移波動、柱體間一致性、橫向偏移和最差案例。此項本次未啟動，不能寫成已完成。無需為此再訓練四個模型。', '',
        '若 R128 的 LSC 能接近或超過 R109，且不以不合理改形狀換穩定，它才具備「輪廓更好、量測也更好」的直接支持。圓度則先確定同一實物邊界及參考建立方式的穩定性，再決定是否需要針對模型改善；不能直接把柱體強行修圓。最終仍是一個模型。', '',
        '## 這次核對的範圍與重現資料', '',
        '獨立逐筆重算全部 1,080 筆輪廓比較，距離與面積等數值和原流程相符；432 筆原圖與 R128 既有結果重現。圓度採用同一版本的既有輪廓量測函式，另核对與 SEM 圓度相減的定義。舊 LSC 的 25 列摘要皆由逐對紀錄重現，未重新運行舊模型、訓練或讀取舊封閉確認影像。這是計算與比較資格核對，不是新的訓練因果審核或物理準確度資格確認。', '',
        '- [比較規則與來源](../results/competitive_review/plan.json)',
        '- [完整核對記錄](../results/competitive_review/verification.json)',
        '- [逐顆、跨三張照片的結果](../results/competitive_review/per_pillar.csv)',
        '- [逐張照片彙整](../results/competitive_review/per_exposure.csv)',
        '- [每顆勝負比較](../results/competitive_review/paired_comparisons.csv)',
        '- [LSC 重新彙整的結果](../results/competitive_review/LSC_recomputed.csv)',
        '- [先前完整輪廓疊圖與限制](R128_FULL_CONTOUR_SEM.md)', '',
    ]
    report_path = ROOT/'reports/R128_COMPETITIVE_REVIEW.md'
    with report_path.open('x', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    save(out/'report_record.json', dict(created_utc=now(), report=record(report_path), figure=record(image_path), generator=record(__file__), verification=record(out/'verification.json')))
    print(str(report_path))
    print(str(image_path))


if __name__ == '__main__':
    main()
