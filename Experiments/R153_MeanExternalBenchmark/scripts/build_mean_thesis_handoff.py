"""Portable first-part thesis handoff: verified means, complete tables, grayscale figures."""
from pathlib import Path
import hashlib, json, shutil, sys, zipfile
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from study import read, sha
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

DEST = ROOT / 'reports/MOSR_MEAN_THESIS_HANDOFF_20261005'


def table(frame, digits=6):
    lines = ['| ' + ' | '.join(map(str, frame.columns)) + ' |',
             '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |']
    for row in frame.itertuples(index=False, name=None):
        values = [f'{x:.{digits}f}' if isinstance(x, (float, np.floating)) else str(x) for x in row]
        lines.append('| ' + ' | '.join(values) + ' |')
    return '\n'.join(lines)


def figures():
    plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Times New Roman', 'DejaVu Serif'],
        'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'svg.fonttype': 'none'})
    positions = pd.read_csv(DEST / 'data/per_step_across_scan_statistics.csv')
    pairs = pd.read_csv(DEST / 'data/paired_30_scan_comparison.csv')
    records = []
    designs = [
        ('Fig6_12_within_scan_SD', 'scan', None, 'Within-scan step SD (nm)', 'Repeated scan number'),
        ('Fig6_13_adjacent_displacement', 'adjacent', 'displacement', 'Mean step displacement (nm)', 'Step number'),
        ('Fig6_14_start_relative_PI_error', 'start', 'error', 'Start-relative displacement minus PI (nm)', 'Position number'),
        ('Supplement_adjacent_PI_error', 'adjacent', 'error', 'Step displacement minus PI (nm)', 'Step number')]
    for filename, kind, value, ylabel, xlabel in designs:
        fig, ax = plt.subplots(figsize=(7.2, 3.7))
        for method, color, marker, style in [('RAW', '0.55', 'o', '--'), ('MOSR', '0.05', 's', '-')]:
            if kind == 'scan':
                y = pairs[f'{method}_mean_SD_nm'].to_numpy()
                mean, sd = y.mean(), y.std(ddof=1)
                ax.axhspan(mean - sd, mean + sd, color=color, alpha=.12)
                label = f'{method}: {mean:.3f} ± {sd:.3f} nm'
            else:
                data = positions[(positions.method == method) & (positions.aggregation == 'mean') & (positions.kind == kind)].sort_values('step')
                assert data.step.tolist() == list(range(1, 31))
                y = data[f'mean_{value}_nm'].to_numpy()
                sd = data[f'{value}_sd_nm'].to_numpy()
                ax.fill_between(np.arange(1, 31), y - sd, y + sd, color=color, alpha=.18)
                label = method + ': mean ± 1 SD'
            ax.plot(np.arange(1, 31), y, color=color, marker=marker, linestyle=style,
                    linewidth=1.1, markersize=3, markerfacecolor='white', label=label)
        if value == 'error':
            ax.axhline(0, color='0.7', linewidth=.7, linestyle=':')
        ax.set(xlabel=xlabel, ylabel=ylabel, xlim=(.7, 30.3))
        ax.set_xticks([1, 5, 10, 15, 20, 25, 30])
        ax.grid(axis='y', color='0.9', linewidth=.5)
        ax.legend(loc='best', fontsize=9, frameon=False)
        fig.tight_layout()
        for ext in ['png', 'svg', 'pdf']:
            fig.savefig(DEST / 'figures' / (filename + '.' + ext), dpi=300, bbox_inches='tight')
        plt.close(fig)
        records.append(filename)
    for ext in ['png', 'svg']:
        shutil.copy2(ROOT / 'reports/figures' / ('mean_median_sensitivity.' + ext),
                     DEST / 'figures' / ('Supplement_mean_median_sensitivity.' + ext))
    return records


def main():
    for directory in ['data', 'figures', 'verification']:
        (DEST / directory).mkdir(parents=True, exist_ok=True)
    for path in (ROOT / 'reports/data').glob('*.csv'):
        shutil.copy2(path, DEST / 'data' / path.name)
    for name in ['mean_median_complete.json', 'fixed_center_reaggregation.npz', 'verified_fixed_measurement_sources.csv']:
        shutil.copy2(ROOT / 'results/analysis' / name, DEST / 'verification' / name)
    shutil.copy2(ROOT/'scripts/verify_mean_handoff.py', DEST/'verification/recalculate_and_verify.py')
    audit = read(DEST / 'verification/mean_median_complete.json')
    assert audit['status'] == 'passed' and audit['source_files_verified'] == 154
    assert audit['optical_circle_refits'] == audit['MOSR_reconstructions'] == 0
    figures()
    full = (ROOT / 'reports/MEAN_MEDIAN_RESULTS.md').read_text(encoding='utf-8')
    full = full.replace('# 九顆柱體平均位移與中位數位移比較', '## 九顆柱體平均位移與中位數位移比較', 1)
    full = full.replace('figures/mean_within_scan_sd.png', 'figures/Fig6_12_within_scan_SD.png')
    full = full.replace('figures/mean_median_sensitivity.png', 'figures/Supplement_mean_median_sensitivity.png')
    full = full.replace('| |偏態|中位數 | |偏態|>1的步數 |', '| 絕對偏態中位數 | 絕對偏態>1的步數 |')
    full = full.replace('後續外部模型以相同規則比較。', '此份文件只處理已完成的RAW／MOSR平均數重算。')
    mapping = (ROOT / 'reports/THESIS_UPDATE_MAP.md').read_text(encoding='utf-8').split('## 四、')[0]
    mapping = mapping.replace('# 最新版論文修改對照表', '### 最新版論文修改對照表', 1)
    mapping = '\n'.join(line for line in mapping.splitlines() if '表6-9及摘要推論秒數' not in line)
    mapping = mapping.replace('平均數分析已完成並核對。外部模型目前仍在訓練；外部模型排名、全部實拍指標及新效率數字須待完整驗證後填入，本文不以短測或舊日期數據代替。',
        '本次只修改九顆位移彙整與其結果；不新增尚未完成的外部模型比較。')
    mapping = mapping.replace('figures/mean_within_scan_sd', 'figures/Fig6_12_within_scan_SD')
    means = pd.read_csv(DEST / 'data/all_aggregated_displacements.csv')
    groups = []
    for lower, upper in [(1, 6), (7, 30)]:
        row = {'掃描範圍': f'{lower}–{upper}', '掃描數': upper - lower + 1}
        values = []
        for method in ['RAW', 'MOSR']:
            data = means[(means.method == method) & (means.aggregation == 'mean') &
                         (means.kind == 'adjacent') & means.scan.between(lower, upper)]
            sd = data.groupby('scan').displacement_nm.std(ddof=1).to_numpy()
            pooled = float(np.sqrt(np.mean(sd ** 2)))
            row[method + '合併SD nm'] = pooled
            row[method + ' PI MAE nm'] = float(data.error_nm.abs().mean())
            values.append(pooled)
        row['合併SD降低%'] = 100 * (1 - values[1] / values[0])
        groups.append(row)
    group_frame = pd.DataFrame(groups)
    group_frame.to_csv(DEST / 'data/mean_first6_last24_summary.csv', index=False, encoding='utf-8-sig')
    positions = pd.read_csv(DEST / 'data/per_step_across_scan_statistics.csv')
    detailed = []
    for kind, title in [('adjacent', '相鄰步距'), ('start', '直接相對起點')]:
        r = positions[(positions.method == 'RAW') & (positions.aggregation == 'mean') & (positions.kind == kind)].sort_values('step')
        m = positions[(positions.method == 'MOSR') & (positions.aggregation == 'mean') & (positions.kind == kind)].sort_values('step')
        frame = pd.DataFrame({'位置／步': r.step.to_numpy(), 'RAW位移平均 nm': r.mean_displacement_nm.to_numpy(),
            'RAW位移SD nm': r.displacement_sd_nm.to_numpy(), 'MOSR位移平均 nm': m.mean_displacement_nm.to_numpy(),
            'MOSR位移SD nm': m.displacement_sd_nm.to_numpy(), 'RAW PI差平均 nm': r.mean_error_nm.to_numpy(),
            'RAW PI差SD nm': r.error_sd_nm.to_numpy(), 'MOSR PI差平均 nm': m.mean_error_nm.to_numpy(),
            'MOSR PI差SD nm': m.error_sd_nm.to_numpy()})
        detailed.append('### ' + title + '\n\n' + table(frame))
    preamble = '''# MOSR論文修改交接：九顆平均位移之完整驗證結果

日期：2026-10-05。此份是可獨立閱讀的第一部分交接；全部數字已由同一批保存量測資料重算，不需等待外部模型訓練。

## 給網頁版對話的修改指令

請先完整閱讀本文件與我同時提供的最新版論文，再修改原論文。這次只將九顆柱體位移的彙整從「x、y分量中位數」改成「九個二維位移向量的算術平均，再投影至固定方向」，並一致更新相關公式、摘要、研究貢獻、表格、圖說、討論與結論。依下列位置對照核查原文，不要只替換百分比。

使用RAW與MOSR名稱，不放內部開發編號。模型、訓練、PSF校正、影像重建、圓心與輪廓量測方式、尺度、方向、PI回授、物件對應、所有30次掃描與九顆柱體均維持原設定。本次沒有新模型結果、沒有重新訓練或重建MOSR，也沒有重新擬合RAW/MOSR的LSC。

相對起點PI平均絕對差的95%配對區間已跨零，請改為「點估計略降，但尚不能確認改善」，不能沿用舊版的肯定結論。約30 μm終點的平均有號差也沒有改善證據。輪廓與尺寸數字並不因位移彙整改變；MOSR的SEM直徑差仍比RAW大，必須保留。不要將重複性改善写成已證明絕對準確度或完整量測不確定度降低。

圖表採簡單研討會／論文格式與灰階。請用附件的新圖替換對應舊圖，保留各圖統計量與灰帶定義。最後提供修改後論文，以及逐處修改對照表，核查全文的數字、公式、圖說與結論是否一致。

## 閱讀順序與本次範圍

本文件依序包含完整驗證分析、三張主圖與圖說、前6／後24趟分析、30位置完整摘要、未變動結果、論文修改位置與可直接使用文字。data資料夾是完整數據；verification資料夾保存已核對的圓心與PI陣列及可獨立重算的程式。只上传本MD與論文即可理解結果；要實際替換圖，請同時提供ZIP解壓後的figures或個別PNG／PDF。

來源論文為《MOSR_論文_格式與正式用語校訂版_20261004.pdf》，共144個PDF頁；對照表使用原論文印刷頁碼，括號內為PDF頁。來源檔案識別及數據檔案雜湊保存於verification，原論文檔案未被改寫。

---

'''
    captions = '''
## 新主圖與可直接使用的圖說

### 圖6-12：每趟30步的波動

![圖6-12 平均向量版單趟步距波動](figures/Fig6_12_within_scan_SD.png)

圖6-12　RAW與MOSR於30次重複掃描之掃描內步距樣本標準差。每趟先計算30個相鄰影格間的九顆平均位移，再以分母29求該趟標準差。水平灰帶分別為30個單趟標準差的算術平均±其樣本標準差：RAW為8.679±1.354 nm，MOSR為4.188±0.861 nm。此灰帶描述趟次間的變動，不是每點的信賴區間。主要合併標準差另為8.781與4.273 nm，兩者不可混用。

### 圖6-13：同一步跨30次重拍

![圖6-13 平均向量版逐步位移與重拍範圍](figures/Fig6_13_adjacent_displacement.png)

圖6-13　每一步影像位移於30次掃描之平均±1個樣本標準差。每趟的單步位移先取固定九顆二維位移向量之平均，再投影至固定方向。橫軸為步數，線為同一步跨30趟的平均位移，灰带為平均±樣本SD，並非標準誤或95%區間。圖6-12描述趟內步距波動，本圖描述同一步在不同趟之重拍分散，兩者不可互換。此圖並未把每步強制設成1000 nm。

### 圖6-14：長距離與PI的差

![圖6-14 平均向量版相對起點PI差](figures/Fig6_14_start_relative_PI_error.png)

圖6-14　各位置相對起點的影像位移與對應PI回授差之平均±1個樣本標準差。每趟以當前與起點的九顆圓心差向量直接平均及投影，再扣同一影格對PI_Y回授差；跨30趟計算平均與樣本SD。零位置的位移與PI差依定義均為零，本圖畫其後30位置。正值表示影像量得位移大於PI回授。算術平均版本的直接相對起點與逐步位移累加等價；圖說不可再寫成分量中位數累加。此處SD是扣PI後誤差的跨趟散布，不是單趟30步SD。

### 補充圖：單步PI差

![補充 平均向量版相鄰PI差](figures/Supplement_adjacent_PI_error.png)

補充圖　各相鄰步之影像位移減PI回授差，線與灰帶分別為跨30次掃描之平均與±1個樣本SD。只作單步偏差分布補充，不替代PI MAE或掃描內波動主指標。

所有圖提供300 dpi PNG、SVG及PDF；敏感度補充圖提供PNG及SVG。圖上只有RAW與MOSR名稱，沒有彩色線條。
'''
    unchanged = '''
## 未因平均數彙整改變的幾何結果

| 指標（nm） | RAW | MOSR | 判讀 |
| --- | ---: | ---: | --- |
| 平均直徑 | 2799.620660 | 2834.017939 | MOSR平均大34.397279 nm |
| 直徑重複量測SD | 32.750251 | 13.251720 | 重複性改善 |
| 完整輪廓重複量測SD | 63.758024 | 18.599990 | 重複性改善約70.8% |
| 去平均半徑之形狀SD | 61.666738 | 17.400551 | 描述去尺寸後之形狀重複性 |
| SEM工作表平均逐顆直徑絕對差 | 169.883278 | 204.280557 | MOSR較大，不是尺寸更準 |
| SEM輪廓點參照平均逐顆直徑絕對差 | 185.182117 | 219.579396 | MOSR較大 |

直徑SD先在同一位置、同一顆物體跨30次掃描求樣本SD，再合併31位置及九顆之方差。完整輪廓先以保存LSC圓心平移對齊，將64個邊界點插值至720固定方向，在同一位置／物件／方向跨30趟求SD，再合併；不自由旋轉、縮放或配準。去尺寸形狀則先各自扣除輪廓平均半徑。SEM直徑差先對每顆的30×31個光學直徑平均，再與對應SEM直徑比較，最後平均九顆絕對差。

SEM工作表的平均直徑2629.737382 nm，SEM輪廓點參照為2614.438543 nm，兩種讀法相差15.298839 nm，不可混用。此處沿用已核對的原幾何結果，本次只重算位移，不重做SEM擬合或校正。

## 統計判讀與限制

所有配對區間取完整掃描為抽樣單位，20000次重抽樣，固定種子20261002，相同掃描名單同時用於RAW與MOSR。逐次SD降低34.6%至67.2%是本批30趟觀察到的範圍；合併降低率95%區間48.40%至54.26%是全掃描重抽樣的估計區間，两者不可混用。圖的±1SD又是另一個描述量。

30趟来自同批同時段，可能存在時間漂移；整趟重抽樣保留趟內相依，但仍假設趟次可交換。前6／後24趟作預先已有的敏感度分析，不能事後據此捨棄某一組。區間不含完整PI誤差預算、像素尺度校準不確定度、SEM參照誤差或跨樣品變異。PI相符程度可作準度相關參照，但不是已建立完整絕對真值。900步、九顆物件或720方向不能充當900／8100／更多次獨立重拍。
'''
    texts = '''
## 可直接使用的摘要、結果與結論文字

### 中文摘要與研究貢獻的數據句

在30次重複掃描中，以固定九顆柱體之平均位移向量彙整後，RAW與MOSR的掃描內步距合併標準差分別為8.781 nm與4.273 nm，降低51.3%，全部30次掃描均改善，逐次降低範圍為34.6%至67.2%。相鄰位移相對PI回授的平均絕對差由6.969 nm降至3.598 nm，降低48.4%。完整輪廓重複量測標準差仍由63.758 nm降至18.600 nm；惟SEM平均直徑差較大，尺寸準度未同步改善。

### 英文摘要的對應數據句

Across 30 repeated scans, displacement was aggregated by averaging the two-dimensional displacement vectors of nine fixed pillars and projecting the mean vector onto the fixed motion direction. The pooled within-scan step standard deviation decreased from 8.781 nm for RAW to 4.273 nm for MOSR (51.3%). All 30 scans improved, with individual reductions ranging from 34.6% to 67.2%. The mean absolute difference between adjacent image displacements and PI feedback decreased from 6.969 nm to 3.598 nm (48.4%). These results support improved short-step repeatability and agreement with PI feedback for this dataset, without establishing improved absolute dimensional accuracy or reduced long-distance bias.

### 長距離討論與結論

相對起點位移之PI平均絕對差由18.405 nm變為17.874 nm，點估計降低2.9%，但MOSR減RAW差值的95%完整掃描配對估計區間為−1.149至+0.090 nm，跨越零。約30 μm終點的平均有號PI差由+41.726 nm變為+42.678 nm，其差值區間亦跨越零。因此，本批資料的主要位移效益為掃描內步距穩定性與相鄰位移對PI回授的相符程度；不能將短步改善直接延伸為長距離偏差或絕對尺寸準度的確定改善。

## 修改後全文檢查清單

1. 九顆位移主公式使用向量平均；分量中位數僅留在敏感度分析或歷史對照。
2. 摘要、英文摘要、貢獻、主結果、結論的位移SD均為8.781／4.273 nm、降低51.3%；相鄰PI MAE均為6.969／3.598 nm、降低48.4%。
3. 全部30趟、每趟30步、九顆與930張保留，不因診斷旗標刪除資料。
4. 區分單趟SD、合併SD、30個SD之平均±SD、同一步跨趟SD、PI誤差SD；不以標準誤或900步混算取代。
5. 相對起點改善區間跨零；終點偏差不宣稱改善；尺寸與SEM不利結果保留。
6. 圖6-12至6-14、表6-4至6-6及表7-1數字、圖說與正文章節一致。這次不加入未完成外部模型排名，也不修改模型或PSF。
7. 表内至少保留3位小數，百分比正文通常1位，原始CSV保存完整精度。最終文字修改以原論文實際排版與公式編號為準。
'''
    data_rows = [{'檔案': p.name, '資料列數': len(pd.read_csv(p))} for p in sorted((DEST / 'data').glob('*.csv'))]
    dictionary = '\n## 附件資料索引\n\n' + table(pd.DataFrame(data_rows), 0) + '''

aggregation=mean為主要版本，median為敏感度版本；kind=adjacent為相鄰影格，start為當前對起點。所有_nm欄位單位為nm；dx_px、dy_px為像素；百分比是0至100尺度。mean_median_paired_intervals.csv中MSE欄位及其差值／區間單位為nm²，不能標成nm或誤認RMSE。diagnostic旗標與leave_one_out為補充檢查，不是主分析刪點規則。

all_aggregated_displacements.csv共7200列，涵蓋兩方法×兩彙整×兩位移定義×900；其中主要mean版本3600列，每方法1800列。all_pillar_displacements.csv共16200列，為兩方法×30趟×30步×九顆，均是相鄰位移。per_scan_metrics.csv每方法／彙整／位移定義有30趟摘要；start的within_scan_sd留空，因不以相對起點曲線之散布代替主單趟步距波動。per_step_across_scan_statistics.csv每組30列，用於新圖6-13與6-14。
'''
    definitions = '''
## 統一公式與符號（可供論文排版）

r=1,…,30為掃描，j=1,…,30為相鄰步或相對起點之非零位置，k=1,…,9為固定柱體。c_(r,j,k)是保存的二維LSC圓心，單位pixel；a=j−1為相鄰步，a=0為直接相對起點。

Δc̄_(r,j;a) = (1/9) Σ_(k=1)^9 [c_(r,j,k) − c_(r,a,k)]

d_(r,j;a) = 172.5 uᵀ Δc̄_(r,j;a)　[nm]

p_(r,j;a) = 1000 [PI_Y(r,j) − PI_Y(r,a)]　[nm]

e_(r,j;a) = d_(r,j;a) − p_(r,j;a)　[nm]

d̄_r = (1/30) Σ_(j=1)^30 d_(r,j;j−1)

s_r = sqrt{ (1/29) Σ_(j=1)^30 [d_(r,j;j−1) − d̄_r]² }

s_pooled = sqrt{ (1/30) Σ_(r=1)^30 s_r² }

MAE = (1/900) Σ_r Σ_j |e_(r,j;a)|；RMSE = sqrt{(1/900) Σ_r Σ_j e_(r,j;a)²}；有號偏差 = (1/900) Σ_r Σ_j e_(r,j;a)；最大絕對差 = max_(r,j)|e_(r,j;a)|。

約30 μm終點摘要只取j=30，因此MAE、RMSE與偏差分母為30；終點跨趟SD分母29。各位置跨趟均值μ_j=(1/30)Σ_r d_(r,j;a)，SD_j=sqrt{(1/29)Σ_r[d_(r,j;a)−μ_j]²}；PI誤差灰帶以e代d同樣計算。主要s_r針對量得步距d，不是PI差e的SD；二者不可偷換。

降低率=100×(1−MOSR指標/RAW指標)。逐次降低率使用各趟s_r；合併降低率使用s_pooled，而不是30個降低率的平均。比較方向一律MOSR−RAW，對非負誤差或波動指標，負差值代表降低；有號偏差需另看距零遠近。
'''
    doc = preamble + definitions + full + captions + '\n## 前6／後24次掃描敏感度（平均向量版）\n\n' + table(group_frame) + \
        '\n\n兩組使用同一計算方式，完整保留。前6趟及後24趟均顯示MOSR的合併單趟波動較低；不能因此刪除後24趟或將其解讀為另一次獨立樣品驗證。\n' + \
        '\n## 30位置完整摘要（每列均跨30趟）\n\n' + '\n\n'.join(detailed) + unchanged + \
        '\n## 論文逐處修改位置\n\n' + mapping + texts + dictionary
    for old, new in [('上传', '上傳'), ('写成', '寫成'), ('灰带', '灰帶'), ('两者', '兩者'), ('来自', '來自'), ('表内', '表內')]:
        doc = doc.replace(old, new)
    assert not __import__('re').search(r'\bR(?:140|148|150|152|153)\b', doc)
    (DEST / 'MOSR_MEAN_THESIS_HANDOFF.md').write_text(doc, encoding='utf-8')
    (DEST / 'UPLOAD_INSTRUCTIONS.txt').write_text('先上傳 MOSR_MEAN_THESIS_HANDOFF.md 與最新版論文。若網頁對話不能解壓ZIP，請自行解壓後提供figures內Fig6_12、Fig6_13、Fig6_14的PNG或PDF。data是完整CSV；verification可重算核對，不必逐檔先讀。這次只修改平均數版本，不加入外部模型結果。\n', encoding='utf-8')
    from scripts.verify_mean_handoff import verify
    verify(DEST)
    import re
    from PIL import Image
    for link in re.findall(r'\]\(([^)]+)\)', doc):
        assert (DEST / link).is_file(), link
    lengths = []
    for line in doc.splitlines():
        if line.startswith('|'):
            count = len(line.split('|'))
            if lengths:
                assert count == lengths[-1], ('table column mismatch', line)
            lengths.append(count)
        else:
            lengths = []
    for path in (DEST / 'figures').glob('*.png'):
        pixels = np.asarray(Image.open(path).convert('RGB')).astype(np.int16)
        assert np.max(abs(pixels[..., 0] - pixels[..., 1])) == 0
        assert np.max(abs(pixels[..., 1] - pixels[..., 2])) == 0
    locked = read(ROOT / 'config/source_lock.json')['files']
    for row in locked:
        assert sha(row['path']) == row['sha256'], row['path']
    provenance = {'source_files': locked, 'original_optical_measurement_files': 'verified_fixed_measurement_sources.csv',
        'builder_sha256': sha(__file__), 'main_MD_sha256': sha(DEST / 'MOSR_MEAN_THESIS_HANDOFF.md'),
        'original_sources_modified': False, 'new_model_training_results_included': False,
        'figures_visual_review': 'three main PNGs viewed; no clipped labels or colored data',
        'all_png_pixels_verified_grayscale': True}
    (DEST / 'verification/source_provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding='utf-8')
    manifest = [{'file': str(p.relative_to(DEST)).replace('\\', '/'), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                for p in sorted(DEST.rglob('*')) if p.is_file() and p.name != 'PACKAGE_MANIFEST.json']
    (DEST / 'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    archive = DEST.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(DEST.rglob('*')):
            if path.is_file():
                z.write(path, str(path.relative_to(DEST.parent)))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for row in manifest:
            payload = z.read(DEST.name + '/' + row['file'])
            assert hashlib.sha256(payload).hexdigest() == row['sha256']
    receipt = {'status': 'passed', 'files': len(manifest) + 1, 'ZIP': str(archive), 'ZIP_bytes': archive.stat().st_size,
        'ZIP_sha256': sha(archive), 'independent_recalculation': read(DEST/'verification/independent_recalculation.json'),
        'all_MD_links_present': True, 'all_MD_tables_consistent': True, 'all_png_grayscale': True,
        'protected_source_files_unchanged': True, 'complete_first_part_only': True, 'full_external_benchmark_complete': False}
    (ROOT / 'results/analysis/mean_thesis_handoff_delivery_verified.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Handoff built:', DEST, flush=True)
    print('ZIP verified:', archive, archive.stat().st_size, 'bytes', flush=True)


if __name__ == '__main__':
    main()
