import React from "react";
import {
  DataComponent, DataTable, EvidenceChart, MetricCard, ReportSection, RichNarrative, useDataApp,
} from "../../data-app-public.jsx";

const pct = (value, digits = 1) => value == null ? "—" : `${Number(value).toFixed(digits)}%`;
const num = (value, digits = 3) => value == null ? "—" : Number(value).toFixed(digits);
const categoryNames = {
  dense_close_structures: "極密集結構", corners_lines_junctions: "角點與線段",
  textured_edges: "紋理邊緣", noisy_identity: "帶雜訊原樣圖",
  clean_identity: "清楚原樣圖", irregular_curved: "不規則曲線", flat_negative: "平坦區域",
};
const componentNames = { image: "影像", gradient: "邊緣", pair_output: "位置一致", boundary: "邊界", observation: "成像一致" };
const periodNames = { early_first512: "最初512次", recent_last512: "最後512次" };

export function ReportContent() {
  const { reviewedRows, visible, canEdit, mode, appTitle, setAppTitle } = useDataApp();
  const status = reviewedRows("training_status")[0] ?? {};
  const dev = reviewedRows("dev_curve");
  const rawCategories = reviewedRows("dev_categories").sort((a, b) => b.loss_mean - a.loss_mean);
  const categories = rawCategories.map((row) => ({ ...row, display_category: categoryNames[row.category] ?? row.category }));
  const rawShares = reviewedRows("objective_share").filter((row) => row.period !== "all");
  const shares = rawShares.map((row) => ({ ...row, display_component: componentNames[row.component] ?? row.component, display_period: periodNames[row.period] ?? row.period }));
  const stages = reviewedRows("stage_audit");
  const ablations = reviewedRows("ablation_audit");
  const issues = reviewedRows("issues").sort((a, b) => a.priority - b.priority);
  const gradientRows = reviewedRows("gradient_norms");
  const realRows = reviewedRows("real_ranking");
  const realCurrent = realRows.find((row) => row.model === "R148v2-HybridContextNativePSF") ?? {};
  const realRaw = realRows.find((row) => row.model === "Raw") ?? {};
  const dense = categories.find((row) => row.category === "dense_close_structures");
  const context = ablations.find((row) => row.mode === "context_off");
  const psf = ablations.find((row) => row.mode === "actual_psf");
  const recentShare = Object.fromEntries(shares.filter((row) => row.period === "recent_last512").map((row) => [row.component, row.share_percent]));
  const recentDrops = [status.recent_dev_drop_1, status.recent_dev_drop_2, status.recent_dev_drop_3].map((value) => num(value));

  return <article className="report-content" aria-label="R148v2 training deep dive">
    <header className="report-hero">
      <h1 data-data-app-title contentEditable={canEdit && mode === "edit"} suppressContentEditableWarning
        onBlur={canEdit && mode === "edit" ? (event) => setAppTitle(event.currentTarget.textContent.trim() || appTitle) : undefined}>{appTitle}</h1>
      <RichNarrative id="report:deck" className="report-deck" label="編輯報告引言"
        value={`${status.formal_training_complete ? "正式訓練已完成" : "截至正式訓練"}第 ${Number(status.step ?? 0).toLocaleString()} 次；固定 930 張實拍與 8,370 顆圓${status.real930_complete ? "也已完成核對" : "仍待完成"}。報告分開回答短步位移、長距離、直徑、輪廓與模型內部問題。`} />
    </header>

    {visible("executive-summary") && <ReportSection id="executive-summary" title="結論摘要" queryId="training_status"
      queryIds={["training_status", "dev_categories", "ablation_audit", "issues"]}
      sourceRowsByQuery={{ training_status: [status], dev_categories: rawCategories, ablation_audit: ablations, issues }} showHeading={false}>
      <RichNarrative id="executive-summary:body" className="report-summary-lead" label="編輯結論摘要"
        value={`## 結論摘要

- **訓練本身健康，但已進入遞減期。** 固定開發誤差由 ${num(status.dev_initial)} 降至 ${num(status.dev_latest)}，改善 ${pct(status.dev_improvement_percent)}；最近三個 512 次區間只再下降 ${recentDrops.join("、")}。
- **目前最大的風險是資料幾何，不是訓練不收斂。** 密集結構約占五分之一場景，卻貢獻約 ${pct(dense?.latest_share_pct)} 的開發誤差；這批圖比實拍九圓擁擠很多。
- **多尺度脈絡確實被使用。** 凍結關閉後 14/14 抽測場景都變差，平均分數增加 ${num(context?.mean_score_change)}；保留它有證據。
- **PSF 提示仍需要簡化。** 換成生成時的正確個別 PSF，整體平均差異只有 ${num(Math.abs(psf?.mean_score_change), 5)} 分，方向接近零；兩個密集抽測平均關掉 PSF 提示反而更好。
- **實拍驗證已完成。** 相對 Raw，短步平均差由 ${num(realRaw.short_step_mae_nm)} 降至 ${num(realCurrent.short_step_mae_nm)} nm，長距離由 ${num(realRaw.long_distance_mae_nm)} 降至 ${num(realCurrent.long_distance_mae_nm)} nm；直徑重拍標準差由 ${num(realRaw.diameter_repeatability_nm)} 降至 ${num(realCurrent.diameter_repeatability_nm)} nm。
- **尺寸偏差仍是主要缺點。** 相對同九顆 SEM 的平均直徑差為 ${num(realCurrent.sem_mean_diameter_error_nm)} nm，高於 Raw 的 ${num(realRaw.sem_mean_diameter_error_nm)} nm；穩定不等於尺寸更接近參考。`} />
    </ReportSection>}

    <div className="report-facts" aria-label="關鍵數字">
      <MetricCard id="status-progress" title="正式訓練快照" queryId="training_status" sourceRows={[status]}
        value={`${Number(status.percent ?? 0).toFixed(1)}%`} comparison={`${status.step ?? 0} / ${status.expected_steps ?? 8192}`}
        description={status.formal_training_complete ? "正式權重與固定測試已完成並寫入收據。" : "建立報告時的連續正式更新；不是完成標記。"} />
      <MetricCard id="status-dev" title="固定開發誤差" queryId="dev_curve" sourceRows={dev}
        value={num(status.dev_latest)} comparison={`由 ${num(status.dev_initial)} 降低 ${pct(status.dev_improvement_percent)}`}
        description="128 個固定生成母場景的完整平均目標；越低越好。" trendValues={dev.map((row) => row.mean_loss)} />
      <MetricCard id="status-dense" title="密集圖誤差占比" queryId="dev_categories" sourceRows={categories}
        value={pct(dense?.latest_share_pct)} comparison={`密集圖平均 ${num(dense?.loss_mean)}`}
        description="這是總開發誤差的集中度，不是實拍族群占比。" />
      <MetricCard id="status-context" title="關掉脈絡的代價" queryId="ablation_audit" sourceRows={ablations}
        value={`+${num(context?.mean_score_change)}`} comparison="14 / 14 抽測場景變差"
        description="凍結開關結果；證明使用程度，不等於匹配重訓效果。" />
    </div>

    {status.real930_complete && <section className="report-section">
      <ReportSection id="real-text" title="930張實拍：相對Raw全面穩定，但用途排名不同" queryId="real_ranking" sourceRows={realRows} showHeading={false}>
        <RichNarrative id="real-text:body" className="report-analysis" label="編輯實拍判讀"
          value={`## 930張實拍：相對Raw全面穩定，但用途排名不同

R148v2 的短步平均差為 ${num(realCurrent.short_step_mae_nm)} nm，在12種方法中第 ${realCurrent.short_step_mae_rank}；比 Raw 改善約51%，也優於 R147，但仍落後 R140v2。長距離平均差 ${num(realCurrent.long_distance_mae_nm)} nm，與 R137、R140v2、R147 的差異很小。

直徑重拍標準差 ${num(realCurrent.diameter_repeatability_nm)} nm 是12種方法最低；輪廓重拍 ${num(realCurrent.contour_repeatability_nm)} nm 居中。SEM平均直徑差 ${num(realCurrent.sem_mean_diameter_error_nm)} nm，較 Raw 多約34.40 nm，所以這版適合描述重拍穩定改善，不適合宣稱尺寸更準。`} />
      </ReportSection>
      <DataComponent id="real-ranking-table" title="固定930張的用途分項比較" queryId="real_ranking" kind="table"
        displayRows={realRows} sourceRows={realRows} description="同一30趟、930張與8,370顆圓；數值越低越好。">
        <DataTable rows={realRows} searchable={false} columns={[
          { key: "model", label: "方法" }, { key: "short_step_mae_nm", label: "短步平均差 (nm)" },
          { key: "long_distance_mae_nm", label: "長距離平均差 (nm)" }, { key: "diameter_repeatability_nm", label: "直徑重拍 (nm)" },
          { key: "contour_repeatability_nm", label: "輪廓重拍 (nm)" }, { key: "sem_mean_diameter_error_nm", label: "SEM平均直徑差 (nm)" },
        ]} />
      </DataComponent>
    </section>}

    <section className="report-section">
      <ReportSection id="convergence-text" title="模型仍在進步，但延長訓練不會解決結構問題" queryId="dev_curve" sourceRows={dev} showHeading={false}>
        <RichNarrative id="convergence-text:body" className="report-analysis" label="編輯收斂判讀"
          value={`## 模型仍在進步，但延長訓練不會解決結構問題

16 個正式開發檢查點全部低於前一次，沒有過擬合反轉。下降幅度正在收斂，所以完成既定 8,192 次是合理終點；繼續加訓練次數只會小幅降低生成誤差，無法補上實拍幾何沒有覆蓋、邊界要求過度彙總或 PSF 身分不一致。`} />
      </ReportSection>
      <EvidenceChart id="dev-trend" queryId="dev_curve" title="固定開發誤差持續下降，但斜率逐步變小"
        spec={{ type: "line", x: "step", y: "mean_loss", xLabel: "Training update", yLabel: "Mean dev loss", valueDecimals: 3 }}
        rows={dev} sourceRows={dev} height={300} description="每 512 次更新，對同一 128 個生成開發母場景做完整評估。" />
    </section>

    <section className="report-section">
      <ReportSection id="category-text" title="極密集生成圖主導了總分" queryId="dev_categories" sourceRows={rawCategories} showHeading={false}>
        <RichNarrative id="category-text:body" className="report-analysis" label="編輯類別判讀"
          value={`## 極密集生成圖主導了總分

密集結構的最新平均誤差為 ${num(dense?.loss_mean)}，下一高的角點／線段為 ${num(categories.find((row) => row.category === "corners_lines_junctions")?.loss_mean)}。誤差與目標邊緣密度的相關約 0.973，表示總分很大部分在量「影像裡有多少邊」及模糊難度。

更重要的是，生成密集圖中心距只有 10.6–23.9 px、間隙 1.7–5.9 px；實拍九圓約為 28.9 px 與 12.3 px。正式模型可能花大量能力修復比實拍更擁擠的圖，而沒有看過真正相似的圓陣列。`} />
      </ReportSection>
      <EvidenceChart id="category-bars" queryId="dev_categories" title="最新開發誤差高度集中於密集結構"
        spec={{ type: "horizontalBar", x: "display_category", y: "loss_mean", xLabel: "場景類別", yLabel: "平均開發誤差", valueDecimals: 2 }}
        rows={categories} sourceRows={rawCategories} height={340} description="相同開發集；按場景類別平均。" />
      <DataComponent id="category-table" title="各類別從原圖到目前模型的改善" queryId="dev_categories" kind="table"
        displayRows={categories} sourceRows={rawCategories} description="初始權重輸出等於輸入；改善率反映生成開發集。">
        <DataTable rows={categories} searchable={false} columns={[
          { key: "display_category", label: "場景類別" }, { key: "count", label: "母場景" },
          { key: "initial_loss", label: "初始誤差" }, { key: "loss_mean", label: "目前平均" },
          { key: "loss_p90", label: "P90" }, { key: "improvement_percent", label: "改善 (%)" },
        ]} />
      </DataComponent>
    </section>

    <section className="report-section">
      <ReportSection id="objective-text" title="量測要求的標量占比仍很小" queryId="objective_share" sourceRows={rawShares} showHeading={false}>
        <RichNarrative id="objective-text:body" className="report-analysis" label="編輯目標判讀"
          value={`## 量測要求的標量占比仍很小

最近 512 次更新的加權標量平均中，影像與梯度合計約 ${pct((recentShare.image ?? 0) + (recentShare.gradient ?? 0))}，跨外觀位置一致約 ${pct(recentShare.pair_output, 2)}，邊界約 ${pct(recentShare.boundary, 2)}，成像一致約 ${pct(recentShare.observation, 2)}。

兩個固定場景的更新方向抽測也顯示不平衡：密集場景的影像重建影響約 81.59，邊界 2.34、位置一致 0.24；位置一致與影像方向約為 −0.44，邊界與成像一致約為 −0.70。這說明問題不只是權重小，幾項要求在困難圖上還可能互相拉扯。應先修幾何和局部量測定義，再做平衡；不能直接粗暴放大權重。`} />
      </ReportSection>
      <EvidenceChart id="objective-share" queryId="objective_share" title="訓練前後都由影像與梯度項主導"
        spec={{ type: "bar", x: "display_component", y: "share_percent", series: "display_period", stackable: false, yLabel: "加權值占比 (%)", valueDecimals: 1 }}
        rows={shares} sourceRows={rawShares} height={320} description="標量占比只描述目標值尺度；不是梯度貢獻率。" />
    </section>

    <section className="report-section">
      <ReportSection id="internal-text" title="三個階段與脈絡都在工作，PSF提示的價值較小" queryId="stage_audit"
        queryIds={["stage_audit", "ablation_audit", "parameter_groups"]}
        sourceRowsByQuery={{ stage_audit: stages, ablation_audit: ablations, parameter_groups: reviewedRows("parameter_groups") }} showHeading={false}>
        <RichNarrative id="internal-text:body" className="report-analysis" label="編輯內部判讀"
          value={`## 三個階段與脈絡都在工作，PSF提示的價值較小

在每類兩個固定開發場景上，三個原尺寸階段都讓 14/14 場景繼續改善；平均修正強度約 7.39、3.65、2.29 灰階。後段不是完全冗餘，但收益遞減。

關掉多尺度脈絡讓所有抽測場景變差，說明一次脈絡分支有實際價值。關掉 PSF 提示則 10/14 變差，但兩個密集場景平均反而改善；改用生成時的正確個別 PSF，整體平均差異幾乎為零。這支持保留平均 PSF 作弱提示，同時優先做「提示開／關」匹配重訓，不必先做逐張 PSF 選擇器。`} />
      </ReportSection>
      <div className="report-two-column">
        <EvidenceChart id="stage-trend" queryId="stage_audit" title="每個原尺寸階段都持續降低抽測分數"
          spec={{ type: "line", x: "stage", y: "combined_score", xLabel: "Stage", yLabel: "Combined generated score", valueDecimals: 3 }}
          rows={stages} sourceRows={stages} height={300} description="Stage 0 是輸入影像；不含最後成像一致項。" />
        <EvidenceChart id="ablation-bars" queryId="ablation_audit" title="脈絡是主要輔助，正確個別PSF只帶來極小差異"
          spec={{ type: "horizontalBar", x: "mode", y: "mean_score_change", xLabel: "Frozen switch", yLabel: "Score change vs normal", valueDecimals: 4 }}
          rows={ablations} sourceRows={ablations} height={300} description="正值代表關閉／切換後變差；凍結開關不是匹配重訓。" />
      </div>
    </section>

    <section className="report-section">
      <ReportSection id="recommendations-text" title="下一輪應先修資料與量測要求" queryId="issues" sourceRows={issues} showHeading={false}>
        <RichNarrative id="recommendations-text:body" className="report-analysis" label="編輯優化建議"
          value={`## 下一輪應先修資料與量測要求

優先順序不是增加模型深度或延長訓練，而是先補實拍相似圓陣列、讓邊界要求變成局部逐圓量測，並消除已知PSF／平均PSF的訓練推論落差。任何改動都應保持目前模型、資料順序和 930 張協議不變，做單因素匹配對照。`} />
      </ReportSection>
      <DataComponent id="issue-table" title="建議的優化優先順序" queryId="issues" kind="table"
        displayRows={issues} sourceRows={issues} description="優先序綜合證據強度、對實拍轉移的影響與可隔離程度。">
        <DataTable rows={issues} rowKey="priority" searchable={false} columns={[
          { key: "priority", label: "優先" }, { key: "issue", label: "問題" },
          { key: "evidence", label: "目前證據" }, { key: "recommendation", label: "建議" },
          { key: "confidence", label: "信心" },
        ]} />
      </DataComponent>
    </section>

    {gradientRows.length > 0 && <section className="report-section">
      <DataComponent id="gradient-table" title="兩個固定場景的加權目標梯度" queryId="gradient_norms" kind="table"
        displayRows={gradientRows} sourceRows={gradientRows} description="僅用來檢查標量占比是否也反映參數更新；不是完整訓練統計。">
        <DataTable rows={gradientRows} searchable={false} columns={[
          { key: "category", label: "場景" }, { key: "component", label: "目標" },
          { key: "weighted_value", label: "加權值" }, { key: "gradient_L2", label: "梯度 L2" },
        ]} />
      </DataComponent>
    </section>}

    <ReportSection id="limits" title="判讀界線" queryId="training_status" sourceRows={[status]} showHeading={false}>
      <RichNarrative id="limits:body" className="report-disclosure" label="編輯判讀界線"
        value={`## 判讀界線

本報告的訓練曲線使用所有連續正式更新與固定128母場景開發集；凍結內部拆解每類只抽兩個母場景。開關實驗不能代替重新訓練。實拍比較已完成同一30趟、930張與8,370顆圓，並以完整掃描為重抽樣單位。SEM尺寸來自同九顆樣品，也參與PSF擬合，因此只作同條件尺寸差比較，不作獨立絕對準確度宣稱。`} />
    </ReportSection>
  </article>;
}
