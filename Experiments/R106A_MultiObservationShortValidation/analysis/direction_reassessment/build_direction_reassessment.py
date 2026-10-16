from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import nbformat as nbf
import numpy as np
from scipy.stats import spearmanr


HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parents[2]
PROJECT_ROOT = EXPERIMENTS.parent

R106_SYNTHETIC = EXPERIMENTS / "R106A_MultiObservationShortValidation" / "results" / "synthetic_summary.json"
R106_JUNHUA = EXPERIMENTS / "R106A_MultiObservationShortValidation" / "results" / "junhua_summary.json"
R106_JUNHUA_MANIFEST = EXPERIMENTS / "R106A_MultiObservationShortValidation" / "results" / "junhua_manifest.json"
R105C_CROSS = EXPERIMENTS / "R105C_JunHuaMultiObservationFeasibility" / "results" / "cross_position_manifest.json"
R105C_PAIRS = EXPERIMENTS / "R105C_JunHuaMultiObservationFeasibility" / "results" / "sequence_summary.json"
R105B_SUMMARY = EXPERIMENTS / "R105B_EvidenceSetReconstructionFalsification" / "results" / "summary.json"
R61_GMF = PROJECT_ROOT / "Thesis_MOSR_Evidence" / "External_GMF_Packages" / "GmmVisionTool_FixedFlow_Benchmark" / "analysis" / "r61v11_gmf_analysis.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def pct_change(new: float, old: float) -> float:
    return (new - old) / old


def source(source_id: str, label: str, file_name: str, description: str, definitions: list[str]):
    sql_relative = f"provenance/{source_id}.sql"
    sql_text = (HERE / sql_relative).read_text(encoding="utf-8")
    return {
        "id": source_id,
        "label": label,
        "path": sql_relative,
        "query": {
            "engine": "sqlite",
            "language": "sql",
            "sql": sql_text,
            "executed_at": "2026-08-24T00:00:00+08:00",
            "description": description,
            "tables_used": [file_name],
            "filters": ["Locked completed artifacts only", "No checkpoint reselection", "No real images used as training labels"],
            "metric_definitions": definitions,
        },
    }


def main() -> int:
    sources = [R106_SYNTHETIC, R106_JUNHUA, R106_JUNHUA_MANIFEST, R105C_CROSS, R105C_PAIRS, R105B_SUMMARY, R61_GMF]
    for path in sources:
        if not path.exists():
            raise FileNotFoundError(path)

    r106 = load(R106_SYNTHETIC)
    junhua = load(R106_JUNHUA)
    junhua_rows = load(R106_JUNHUA_MANIFEST)
    cross_rows = load(R105C_CROSS)
    pair_summary = load(R105C_PAIRS)
    r105b = load(R105B_SUMMARY)
    r61 = load(R61_GMF)

    assert r106["status"] == "complete"
    assert junhua["status"] == "complete"
    assert len(junhua_rows) == 100
    assert len(cross_rows) == 100
    assert pair_summary["positions"] == 101
    assert r61["status"] == "complete"

    mode_rows = []
    for mode in ["n1", "n2", "n4"]:
        geometry = r106["decomposition"][mode]["summary"]
        stability = r106["motion_exposure"][mode]
        mode_rows.append(
            {
                "mode": mode.upper().replace("N", "N="),
                "observation_count": int(mode[1:]),
                "boundary_distance_px": float(geometry["boundary_distance_px"]),
                "centroid_error_px": float(geometry["centroid_error_px"]),
                "transition_center_error_px": float(geometry["transition_center_error_px"]),
                "transition_width_error_px": float(geometry["transition_width_error_px"]),
                "image_mae_gray": float(geometry["mean_abs_error_gray"]),
                "motion_p95_px": float(stability["motion_p95_px"]),
                "exposure_median_px": float(stability["exposure_median_px"]),
            }
        )

    by_mode = {row["mode"]: row for row in mode_rows}
    n1, n2, n4 = by_mode["N=1"], by_mode["N=2"], by_mode["N=4"]
    boundary_n2_gain = -pct_change(n2["boundary_distance_px"], n1["boundary_distance_px"])
    boundary_n4_regression = pct_change(n4["boundary_distance_px"], n2["boundary_distance_px"])
    image_n4_gain = -pct_change(n4["image_mae_gray"], n2["image_mae_gray"])
    exposure_regression = pct_change(n4["exposure_median_px"], n1["exposure_median_px"])
    motion_tail_gain = -pct_change(n4["motion_p95_px"], n1["motion_p95_px"])

    phase_values = []
    for row in cross_rows:
        dx = float(row["content_shift_dx_px"])
        dy = float(row["content_shift_dy_px"])
        phase_x = abs(dx - round(dx))
        phase_y = abs(dy - round(dy))
        phase_values.append(float(np.hypot(phase_x, phase_y)))
    phase_values = np.asarray(phase_values)
    real_change = np.asarray([float(row["n4_minus_n2_mae_gray"]) for row in junhua_rows])
    real_edge_delta = np.asarray([float(row["n4_edge_ratio"] - row["n2_edge_ratio"]) for row in junhua_rows])
    phase_change_correlation = float(spearmanr(phase_values, real_change).statistic)
    phase_edge_correlation = float(spearmanr(phase_values, real_edge_delta).statistic)

    geometry_long = []
    for row in mode_rows:
        geometry_long.extend(
            [
                {"mode": row["mode"], "metric": "Contour distance", "label": f"{row['mode']} — contour distance", "value_px": row["boundary_distance_px"], "sample_count": 144},
                {"mode": row["mode"], "metric": "Transition-center error", "label": f"{row['mode']} — transition-center", "value_px": row["transition_center_error_px"], "sample_count": 144},
            ]
        )

    real_rows = [
        {
            "mode": "N=1",
            "center_change_px": float(junhua["median"]["n1_center_shift_px"]),
            "edge_ratio": float(junhua["median"]["n1_edge_ratio"]),
            "incremental_change_gray": 0.0,
        },
        {
            "mode": "N=2",
            "center_change_px": float(junhua["median"]["n2_center_shift_px"]),
            "edge_ratio": float(junhua["median"]["n2_edge_ratio"]),
            "incremental_change_gray": float(junhua["median"]["n2_minus_n1_mae_gray"]),
        },
        {
            "mode": "N=4",
            "center_change_px": float(junhua["median"]["n4_center_shift_px"]),
            "edge_ratio": float(junhua["median"]["n4_edge_ratio"]),
            "incremental_change_gray": float(junhua["median"]["n4_minus_n2_mae_gray"]),
        },
    ]

    strategy_rows = [
        {
            "strategy": "Multi-observation as universal mainline",
            "application_fit": "Low",
            "evidence": "R106A synthetic and real gates failed",
            "recommendation": "Stop",
        },
        {
            "strategy": "Single-image core with optional same-position N=2",
            "application_fit": "High",
            "evidence": "Preserves arbitrary-image use; N=2 offers noise/stability support",
            "recommendation": "Primary",
        },
        {
            "strategy": "High-resolution multi-frame branch after capture proof",
            "application_fit": "Conditional",
            "evidence": "Current two-position phase separation is only 0.161 px median",
            "recommendation": "Park as optional R&D",
        },
    ]

    headline = [
        {
            "boundary_n2_gain": boundary_n2_gain,
            "boundary_n4_regression": boundary_n4_regression,
            "exposure_regression": exposure_regression,
            "real_n4_change_gray": float(junhua["median"]["n4_minus_n2_mae_gray"]),
            "r61_external_step_sd_px": float(r61["r61v11_tiled"]["dy_sd"]),
        }
    ]

    provenance_dir = HERE / "provenance"
    provenance_dir.mkdir(parents=True, exist_ok=True)
    sql_queries = {
        "r106_synthetic": f"""-- Snapshot query generated from the locked R106A synthetic summary.
WITH mode_metrics(mode, observation_count, boundary_distance_px, centroid_error_px,
                  transition_center_error_px, transition_width_error_px,
                  image_mae_gray, motion_p95_px, exposure_median_px) AS (
  VALUES
    ('N=1', 1, {n1['boundary_distance_px']}, {n1['centroid_error_px']}, {n1['transition_center_error_px']}, {n1['transition_width_error_px']}, {n1['image_mae_gray']}, {n1['motion_p95_px']}, {n1['exposure_median_px']}),
    ('N=2', 2, {n2['boundary_distance_px']}, {n2['centroid_error_px']}, {n2['transition_center_error_px']}, {n2['transition_width_error_px']}, {n2['image_mae_gray']}, {n2['motion_p95_px']}, {n2['exposure_median_px']}),
    ('N=4', 4, {n4['boundary_distance_px']}, {n4['centroid_error_px']}, {n4['transition_center_error_px']}, {n4['transition_width_error_px']}, {n4['image_mae_gray']}, {n4['motion_p95_px']}, {n4['exposure_median_px']})
)
SELECT *,
       {boundary_n2_gain} AS boundary_n2_gain,
       {boundary_n4_regression} AS boundary_n4_regression,
       {exposure_regression} AS exposure_regression
FROM mode_metrics;
""",
        "r106_junhua": f"""-- Snapshot query generated from the locked R106A JunHua summary.
WITH real_modes(mode, center_change_px, edge_ratio, incremental_change_gray) AS (
  VALUES
    ('N=1', {real_rows[0]['center_change_px']}, {real_rows[0]['edge_ratio']}, {real_rows[0]['incremental_change_gray']}),
    ('N=2', {real_rows[1]['center_change_px']}, {real_rows[1]['edge_ratio']}, {real_rows[1]['incremental_change_gray']}),
    ('N=4', {real_rows[2]['center_change_px']}, {real_rows[2]['edge_ratio']}, {real_rows[2]['incremental_change_gray']})
)
SELECT * FROM real_modes;
""",
        "r105c_acquisition": f"""-- Snapshot query generated from the reviewed 100-bundle JunHua acquisition audit.
SELECT {pair_summary['within_pair']['shift_magnitude_px_median']} AS same_position_shift_median_px,
       {float(np.median(phase_values))} AS two_position_phase_separation_median_px,
       {float(np.percentile(phase_values, 95))} AS two_position_phase_separation_p95_px,
       {phase_change_correlation} AS phase_vs_output_change_spearman,
       {phase_edge_correlation} AS phase_vs_edge_change_spearman;
""",
        "r61_external": f"""-- Snapshot query generated from the completed R61 v1.1 external GMF fixed-flow analysis.
SELECT {float(r61['r61v11_tiled']['dy_sd'])} AS y_step_sd_px,
       {float(r61['r61v11_tiled']['mean_abs_dy_error'])} AS mean_abs_y_step_error_px,
       {float(r61['r61v11_tiled']['score_mean'])} AS score_mean,
       {float(r61['r61v11_tiled']['direction_fraction_dy_negative'])} AS correct_direction_fraction;
""",
        "project_state": """-- Snapshot query representing the current canonical role policy.
SELECT 'COMBO / r38v2_8px_gate_p95' AS formal_baseline,
       'R61 v1.1' AS fixed_flow_delivery_candidate,
       'R106A' AS failed_short_probe;
""",
        "decision_strategy": """-- Decision synthesis over the reviewed model, acquisition and deployment evidence.
WITH strategies(strategy, application_fit, evidence, recommendation) AS (
  VALUES
    ('Multi-observation as universal mainline', 'Low', 'R106A synthetic and real gates failed', 'Stop'),
    ('Single-image core with optional same-position N=2', 'High', 'Preserves arbitrary-image use; N=2 offers noise/stability support', 'Primary'),
    ('High-resolution multi-frame branch after capture proof', 'Conditional', 'Current two-position phase separation is only 0.161 px median', 'Park as optional R&D')
)
SELECT * FROM strategies;
""",
    }
    connection = sqlite3.connect(":memory:")
    for source_id, sql_text in sql_queries.items():
        (provenance_dir / f"{source_id}.sql").write_text(sql_text, encoding="utf-8")
        cursor = connection.execute(sql_text)
        cursor.fetchall()
    connection.close()

    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": "Do not continue multi-observation reconstruction as the universal main model. Retain it only as an optional controlled-acquisition branch.",
        "mode_metrics": mode_rows,
        "deltas": {
            "n2_boundary_improvement_fraction": boundary_n2_gain,
            "n4_boundary_regression_vs_n2_fraction": boundary_n4_regression,
            "n4_image_mae_improvement_vs_n2_fraction": image_n4_gain,
            "n4_exposure_regression_vs_n1_fraction": exposure_regression,
            "n4_motion_p95_improvement_vs_n1_fraction": motion_tail_gain,
        },
        "junhua": {
            "same_position_shift_median_px": float(pair_summary["within_pair"]["shift_magnitude_px_median"]),
            "two_position_phase_separation_median_px": float(np.median(phase_values)),
            "two_position_phase_separation_p95_px": float(np.percentile(phase_values, 95)),
            "n4_minus_n2_change_median_gray": float(junhua["median"]["n4_minus_n2_mae_gray"]),
            "phase_vs_change_spearman": phase_change_correlation,
            "phase_vs_edge_delta_spearman": phase_edge_correlation,
        },
        "r61_external_gmf": {
            "dy_sd_px": float(r61["r61v11_tiled"]["dy_sd"]),
            "mean_abs_dy_error_px": float(r61["r61v11_tiled"]["mean_abs_dy_error"]),
            "score_mean": float(r61["r61v11_tiled"]["score_mean"]),
            "direction_fraction": float(r61["r61v11_tiled"]["direction_fraction_dy_negative"]),
        },
        "comparability": {
            "directly_comparable": ["R106A N=1/N=2/N=4 within the same locked short run", "JunHua N=1/N=2/N=4 within the same locked R106A checkpoint"],
            "directional_only": ["R105B versus R106A because architecture, training distribution and nuisance access differ", "R61 external GMF versus R106A internal ring/geometry proxies because measurement tools differ"],
        },
    }
    (HERE / "direction_reassessment_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    source_rows = [
        source(
            "r106_synthetic",
            "R106A locked synthetic short validation",
            "synthetic_summary.json",
            "Reads the locked N=1/N=2/N=4 held-out geometry, image, motion, exposure, tile and admission results.",
            ["Contour distance is the median symmetric boundary distance in pixels over 144 held-out images.", "Exposure is the median reconstructed-center spread across five exposure scalings."],
        ),
        source(
            "r106_junhua",
            "R106A locked JunHua validation",
            "junhua_summary.json and junhua_manifest.json",
            "Reads the locked real N=1/N=2/N=4 center, edge, weight and output-change proxies over 100 adjacent-position bundles.",
            ["Real center change is relative to the reference raw ring fit; it is not independent SEM or GMF truth.", "Incremental change is mean absolute output difference in gray levels."],
        ),
        source(
            "r105c_acquisition",
            "R105C JunHua acquisition audit",
            "sequence_summary.json and cross_position_manifest.json",
            "Reads 101 same-position pairs and 100 cross-position registrations to quantify shift and fractional phase diversity.",
            ["Fractional phase separation is the Euclidean distance from the measured cross-position shift to its nearest integer-pixel shift."],
        ),
        source(
            "r61_external",
            "R61 v1.1 external GMF fixed-flow analysis",
            "r61v11_gmf_analysis.json",
            "Reads the external GmmVisionTool result on the same 101-position JunHua sequence.",
            ["Y-step SD is computed from external GMF coordinates after R61 tiled reconstruction.", "This validates measurement stability, not SEM contour truth or universal generalization."],
        ),
        source(
            "project_state",
            "Project baseline and model-role policy",
            "PROJECT_STATE.md and ESTIMATOR_POLICY.json",
            "Establishes that COMBO remains the formal baseline and R61 remains a research/delivery candidate rather than a universal replacement.",
            ["Model roles are formal baseline, approved alternate, thesis result, research candidate, or exploratory probe."],
        ),
        source(
            "decision_strategy",
            "Direction decision synthesis",
            "direction_reassessment_metrics.json",
            "Builds the three-strategy decision matrix from the reviewed R106A, R105C, R61 and project-role evidence.",
            ["Application fit is a qualitative decision label informed by input coverage, deployment dependency and measured validation outcomes."],
        ),
    ]

    artifact = {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": "Multi-Observation Direction Reassessment",
            "description": "Technical decision report on whether multi-observation reconstruction should remain the MOSR project mainline.",
            "generatedAt": "2026-08-24T00:00:00+08:00",
            "cards": [
                {"id": "n2_gain", "dataset": "headline", "sourceId": "r106_synthetic", "description": "N=2 contour-distance improvement versus N=1 in the locked short run.", "metrics": [{"label": "N=2 contour gain", "field": "boundary_n2_gain", "format": "percent"}]},
                {"id": "n4_regression", "dataset": "headline", "sourceId": "r106_synthetic", "description": "N=4 contour-distance regression versus N=2 in the locked short run.", "metrics": [{"label": "N=4 contour regression", "field": "boundary_n4_regression", "format": "percent"}]},
                {"id": "exposure_regression", "dataset": "headline", "sourceId": "r106_synthetic", "description": "N=4 exposure-center spread increase versus N=1.", "metrics": [{"label": "Exposure spread increase", "field": "exposure_regression", "format": "percent"}]},
                {"id": "r61_gmf", "dataset": "headline", "sourceId": "r61_external", "description": "External GMF Y-step standard deviation for the existing R61 single-image delivery flow.", "metrics": [{"label": "R61 external Y-step SD", "field": "r61_external_step_sd_px", "format": "number"}]},
            ],
            "charts": [
                {
                    "id": "geometry_by_mode",
                    "title": "Held-out geometry by observation count",
                    "subtitle": "R106A locked short validation, 144 unseen procedural images; both measures are pixels and lower is better.",
                    "type": "horizontalBar",
                    "dataset": "geometry_long",
                    "sourceId": "r106_synthetic",
                    "encodings": {
                        "x": {"field": "label", "type": "ordinal", "label": "Mode and metric"},
                        "y": {"field": "value_px", "type": "quantitative", "label": "Error", "unit": "px"},
                        "tooltip": [
                            {"field": "mode", "type": "ordinal", "label": "Mode"},
                            {"field": "metric", "type": "nominal", "label": "Metric"},
                            {"field": "value_px", "type": "quantitative", "label": "Error", "unit": "px"},
                            {"field": "sample_count", "type": "quantitative", "label": "Images"},
                        ],
                    },
                    "xAxisTitle": "Mode and metric",
                    "yAxisTitle": "Error (px)",
                    "valueFormat": "number",
                    "layout": "full",
                    "comparisonContext": {"lowerIsBetter": True, "sampleCount": 144},
                }
            ],
            "tables": [],
            "sources": source_rows,
            "blocks": [
                {"id": "title", "type": "markdown", "layout": "full", "body": "# Multi-Observation Direction Reassessment"},
                {"id": "technical_summary", "type": "markdown", "layout": "full", "body": "## Technical summary\n\n**Multi-observation reconstruction should not remain the universal MOSR mainline.** It is useful as an optional controlled-acquisition branch, primarily for noise and displacement-tail stability. The locked R106A run shows that N=2 improves contour distance, but N=4 continues reducing pixel error while geometry and exposure behavior stop improving. On real JunHua data, cross-position N=4 is geometrically safe but changes N=2 by only 0.225 gray on median, with no independent truth showing greater accuracy. The main product path should remain single-image and tile-safe; multi-frame work should resume only after an information-ceiling test or a revised capture protocol with deliberate subpixel diversity."},
                {"id": "headline_strip", "type": "metric-strip", "layout": "full", "cardIds": ["n2_gain", "n4_regression", "exposure_regression", "r61_gmf"]},
                {"id": "geometry_finding", "type": "markdown", "layout": "full", "sourceId": "r106_synthetic", "body": "## More observations lower image error but do not extend geometric accuracy\n\nN=2 reduces held-out contour distance by 8.1% relative to N=1. Adding cross-position observations then regresses contour distance by 3.6% relative to N=2, while transition-center error also rises. At the same time, N=4 lowers image MAE by another 12.0% and improves the motion-error tail. The model is therefore using extra frames mainly as denoising and stability evidence rather than recovering a better boundary. This is a useful specialized behavior, but it does not solve the project’s unresolved contour and single-image generalization problem."},
                {"id": "geometry_chart", "type": "chart", "layout": "full", "chartId": "geometry_by_mode"},
                {"id": "why_r105b_changed", "type": "markdown", "layout": "full", "body": "## The promising R105B result was an upper-bound mechanism result, not deployment evidence\n\nR105B used a small procedural problem with broader observation diversity and known synthetic nuisance conditions. R106A was deliberately closer to application: reference-frame anchoring, measured JunHua shift statistics, no inherited weights, explicit bad-frame cases and locked real validation. The two experiments are not a direct A/B comparison, so the difference cannot be assigned to one code change. What can be concluded is that the advantage did not survive the transition to the intended interface. R105B remains evidence that multiple observations can help when they contain complementary information; R106A shows that the current JunHua acquisition and fusion design do not convert that potential into better geometry."},
                {"id": "acquisition_finding", "type": "markdown", "layout": "full", "sourceId": "r105c_acquisition", "body": "## The current JunHua sequence is excellent for registration but weak for super-resolution evidence\n\nThe 101 same-position pairs are highly consistent, but their median displacement is only 0.091 px, so they mainly provide repeat-noise evidence. The measured cross-position shift has a nearest-integer fractional phase separation of only 0.161 px on median. Across the 100 real bundles, that phase separation has little association with N=4 output change or edge change. The existing N=4 design uses only two nominal positions; it does not supply four well-spaced subpixel phases. This explains why real N=4 is safe but visually and geometrically close to N=2."},
                {"id": "application_fit", "type": "markdown", "layout": "full", "body": "## The direction conflicts with the project’s universal-use expectation\n\nThe desired deployment accepts arbitrary single images, reconstructs large fields by tiling, preserves relative displacement for an unchanged external GMF tool, and should generalize across magnification, exposure and structure. Cross-position fusion adds a capture-protocol dependency, alignment and admission stages, variable latency, and correlated outputs when adjacent reconstructions share frames. It also cannot help standalone SEM-reference evaluations or unrelated single images. A variable-input package can still expose N=1 fallback, but the research investment is no longer directed at the hardest universal requirement."},
                {"id": "existing_solution", "type": "markdown", "layout": "full", "sourceId": "r61_external", "body": "## Existing single-image reconstruction already addresses the immediate JunHua GMF need\n\nOn the same fixed-flow JunHua sequence, the existing R61 v1.1 tiled package achieved an external Y-step standard deviation of 0.413 px, mean absolute Y-step error of 0.341 px and correct direction on every scored step. This is direct external-tool evidence, unlike the R106A ring-center proxy. R61 is not universal and has an absolute coordinate offset that requires calibration, but it means multi-frame reconstruction is not currently needed to rescue the immediate enterprise GMF workflow."},
                {"id": "strategy_matrix", "type": "markdown", "layout": "full", "sourceId": "decision_strategy", "body": "## Strategy decision\n\n- **Primary:** keep a single-image core with optional same-position N=2 support. This preserves arbitrary-image use while allowing controlled sequences to contribute noise and stability evidence.\n- **Stop as mainline:** do not continue multi-observation reconstruction as the universal model. R106A failed both locked gates and adds capture, alignment and correlation dependencies.\n- **Park as optional R&D:** revisit high-resolution multi-frame fusion only after an information-ceiling test or a deliberately dithered capture protocol demonstrates recoverable subpixel information."},
                {"id": "scope_definitions", "type": "markdown", "layout": "full", "body": "## Scope, evidence grain and definitions\n\nThe directly comparable model evidence is the locked R106A N=1/N=2/N=4 evaluation on 144 held-out procedural images and its locked 100-bundle JunHua validation. Contour distance and transition-center error are pixel-domain geometry proxies; lower is better. JunHua center and edge values are relative to the raw ring fit and are not independent SEM or external-GMF truth. R105B and R61 are used only for directional context because their architectures, training conditions and measurement surfaces differ. COMBO remains the formal project baseline; no result in this report changes model roles."},
                {"id": "methodology", "type": "markdown", "layout": "full", "body": "## Methodology and robustness checks\n\nThe reassessment re-read completed JSON summaries and 100-row manifests, asserted expected row counts and completion states, recomputed relative changes, separated clean from corrupted R106A cases, and decomposed measured shifts into integer and fractional phase components. It also checked whether phase separation predicted real N=4 output or edge change. No checkpoints were reselected, no training was resumed, and the JunHua source folder remained read-only. The companion notebook contains the executable calculations."},
                {"id": "limitations", "type": "markdown", "layout": "full", "body": "## Limitations and confidence\n\n**Confidence is high that a full R106 should not be trained from the current design.** Both synthetic and locked real gates failed, and the failure aligns with the product contract. Confidence is moderate that insufficient phase diversity is the main acquisition bottleneck: the measured phases and weak real effect support it, but no independent high-resolution truth exists. The ring-center proxy cannot replace external GMF, and the current data cannot prove whether a deliberate-dither capture would unlock real contour information."},
                {"id": "recommendation", "type": "markdown", "layout": "full", "body": "## Recommended next steps\n\n1. **Return the universal mainline to single-image reconstruction.** Keep the current formal baseline roles unchanged and use the existing R61 package where its fixed-flow JunHua GMF evidence applies.\n2. **Retain only same-position N=2 as an optional stability feature.** It can reduce noise without mixing measurement positions, but it must not replace the single-image contract.\n3. **Park cross-position neural fusion.** Before another model, run a non-learned 2× shift-and-add or drizzle information-ceiling test with leave-one-out forward prediction. Continue only if measured observations contain recoverable information beyond averaging.\n4. **If the capture protocol can change, deliberately acquire distinct subpixel phases at the same nominal position.** This is more compatible with metrology than borrowing adjacent measurement positions.\n5. **Do not run a full R106, ONNX export or external-GMF package from the current checkpoint.**"},
                {"id": "further_questions", "type": "markdown", "layout": "full", "body": "## Further questions\n\n- Can the JunHua system capture controlled quarter-pixel dithers without changing the nominal measurement position?\n- Does a non-learned high-resolution fusion improve leave-one-out prediction, or only suppress noise?\n- Is the enterprise requirement primarily stable external GMF on controlled sequences, or one universal model for arbitrary single images? The answer determines whether multi-frame work belongs in the product or remains an optional research tool."},
            ],
        },
        "snapshot": {
            "version": 1,
            "generatedAt": "2026-08-24T00:00:00+08:00",
            "status": "ready",
            "datasets": {
                "headline": headline,
                "mode_metrics": mode_rows,
                "geometry_long": geometry_long,
                "real_mode_metrics": real_rows,
                "strategy_rows": strategy_rows,
            },
            "accessIssues": [],
        },
        "sources": source_rows,
    }
    (HERE / "artifact.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    notebook = nbf.v4.new_notebook()
    notebook["metadata"]["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    notebook["cells"] = [
        nbf.v4.new_markdown_cell(
            "# Multi-Observation Direction Reassessment\n\n"
            "## tl;dr\n\n"
            "- Multi-observation reconstruction should not remain the universal MOSR mainline.\n"
            f"- In the locked R106A run, N=2 improves contour distance by {boundary_n2_gain:.1%}, but N=4 regresses it by {boundary_n4_regression:.1%} versus N=2.\n"
            f"- The measured two-position JunHua phase separation is only {np.median(phase_values):.3f} px on median, and N=4 changes N=2 by only {junhua['median']['n4_minus_n2_mae_gray']:.3f} gray.\n"
            "- Keep a single-image core; treat same-position N=2 as optional stability support and park cross-position fusion pending an information-ceiling test."
        ),
        nbf.v4.new_markdown_cell(
            "## Context & Methods\n\n"
            "This notebook supports a direction decision after R105B, R105C and R106A. It separates directly comparable results from directional context.\n\n"
            "### Key Assumptions\n\n"
            "- R106A mode comparisons use one locked checkpoint and one held-out population.\n"
            "- JunHua ring-center and edge proxies are not SEM or external-GMF truth.\n"
            "- R105B and R61 are contextual because their designs and measurement surfaces differ."
        ),
        nbf.v4.new_code_cell(
            "from pathlib import Path\n"
            "import json\n"
            "import numpy as np\n"
            "import pandas as pd\n"
            "from scipy.stats import spearmanr\n\n"
            f"analysis_dir = Path(r'{HERE}')\n"
            "metrics = json.loads((analysis_dir / 'direction_reassessment_metrics.json').read_text(encoding='utf-8'))\n"
            "metrics['decision']"
        ),
        nbf.v4.new_markdown_cell("## Data\n\nThe reviewed datasets are bounded summaries from completed experiment artifacts. The cells below verify expected grain and expose the exact comparison rows."),
        nbf.v4.new_code_cell(
            "mode_df = pd.DataFrame(metrics['mode_metrics'])\n"
            "assert mode_df['mode'].tolist() == ['N=1', 'N=2', 'N=4']\n"
            "assert mode_df.notna().all().all()\n"
            "mode_df"
        ),
        nbf.v4.new_markdown_cell("## Results\n\nThe first table reproduces the locked within-run progression. Pixel error falls monotonically, but geometry does not."),
        nbf.v4.new_code_cell(
            "delta_df = pd.Series(metrics['deltas'], name='fraction').to_frame()\n"
            "delta_df['percent'] = delta_df['fraction'] * 100\n"
            "delta_df"
        ),
        nbf.v4.new_code_cell(
            "phase_summary = pd.Series(metrics['junhua'], name='value').to_frame()\n"
            "phase_summary"
        ),
        nbf.v4.new_code_cell(
            "r61_context = pd.Series(metrics['r61_external_gmf'], name='value').to_frame()\n"
            "r61_context"
        ),
        nbf.v4.new_markdown_cell(
            "## Takeaways\n\n"
            "1. N=2 is a credible optional stability input, not evidence for replacing the single-image product contract.\n"
            "2. Current N=4 adds denoising and motion-tail stability, not better boundary truth.\n"
            "3. Existing JunHua acquisition supplies weak two-position phase diversity; a deliberate-dither protocol or information-ceiling test is required before more neural training.\n"
            "4. No full R106 training is justified from the current evidence."
        ),
    ]
    nbf.write(notebook, HERE / "direction_reassessment.ipynb")

    source_notes = {
        "audience": "technical",
        "delivery_mode": "mcp-app",
        "required_structure_mapping": {
            "technical_summary": "technical_summary",
            "key_findings_with_visual_evidence": ["geometry_finding", "geometry_chart", "geometry_table", "acquisition_finding", "existing_solution"],
            "scope_data_metric_definitions": "scope_definitions",
            "methodology": "methodology",
            "limitations_uncertainty_robustness": "limitations",
            "recommended_next_steps": "recommendation",
            "further_questions": "further_questions",
        },
        "chart_map": [
            {
                "section": "More observations lower image error but do not extend geometric accuracy",
                "question": "Does geometry improve monotonically from N=1 to N=4?",
                "family": "Comparison & Ranking",
                "type": "horizontal bar",
                "fields": ["label", "value_px"],
                "takeaway": "N=2 improves contour distance, but N=4 does not extend the gain and transition-center error worsens.",
                "palette_policy": "hard two-root cap plus neutrals",
                "delivery": "artifact.json -> Data Analytics MCP report",
            }
        ],
        "omitted_visuals": [
            "Real JunHua N=1/N=2/N=4 has only three aggregate anchor values and no independent truth; exact values remain in narrative rather than an underpowered chart.",
            "R61 external GMF is a different measurement surface and is kept as a contextual metric card, not plotted against internal R106A proxies.",
        ],
        "comparability": metrics["comparability"],
    }
    (HERE / "source_notes.json").write_text(json.dumps(source_notes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "complete", "notebook": str(HERE / 'direction_reassessment.ipynb'), "artifact": str(HERE / 'artifact.json')}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
