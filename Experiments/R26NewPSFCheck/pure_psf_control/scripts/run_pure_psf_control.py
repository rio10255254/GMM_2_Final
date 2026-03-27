from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pure_psf_control_lib as lib


ROOT = lib.EXPERIMENT_ROOT


def _prepare_dirs() -> dict[str, Path]:
    paths = {
        "root": ROOT,
        "scripts": ROOT / "scripts",
        "tests": ROOT / "tests",
        "reports": ROOT / "reports",
        "logs": ROOT / "logs",
        "tables": ROOT / "tables",
        "artifacts": ROOT / "artifacts",
        "reconstructions": ROOT / "reconstructions",
        "runs": ROOT / "runs",
    }
    for path in paths.values():
        lib.ensure_dir(path)
    return paths


def _write_restore_report(report_path: Path, payload: dict[str, object]) -> None:
    lines = [
        "# Official PSF Restore",
        "",
        f"- old archive: `{payload['old_psf_archive']}`",
        f"- root before: `{payload['root_formal_before']['sha256']}`",
        f"- package before: `{payload['package_formal_before']['sha256']}`",
        f"- root after: `{payload['root_formal_after']['sha256']}`",
        f"- package after: `{payload['package_formal_after']['sha256']}`",
        "",
        "正式預設已回到舊 package PSF；新 PSF 只保留在 experiment sandbox。",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _write_parity_report(report_path: Path, rows: list[dict[str, object]]) -> None:
    lines = [
        "# Pure PSF Control Parity Diff",
        "",
        "| field | old_psf | new_psf | status |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['field']} | {row['left']} | {row['right']} | {row['status']} |"
        )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _run_line(spec: dict[str, object], paths: dict[str, Path]) -> tuple[dict[str, object], list[dict[str, object]]]:
    run_dir = lib.find_latest_usable_run(Path(str(spec["output_root"])))
    if run_dir is None:
        result = lib.run_old_recipe_sweep(spec)
        run_dir = Path(str(result["progress_dir"]))
    else:
        result = {
            "candidate": str(spec["candidate_name"]),
            "model_name_base": str(spec["model_name_base"]),
            "progress_dir": str(run_dir),
            "best_checkpoint_path": str(run_dir / "weights" / "best_tradeoff.pth.tar"),
            "reused_existing_run": True,
        }
    recon_root = paths["reconstructions"] / str(spec["label"])
    rows = lib.collect_epoch_metrics(run_dir, recon_root)
    payload = {
        "spec": spec,
        "result": result,
        "epoch_metrics": rows,
    }
    lib.dump_json(paths["logs"] / f"{spec['label']}_run.json", payload)
    lib.write_epoch_metrics_csv(paths["tables"] / f"{spec['label']}_epoch_metrics.csv", rows)
    return result, rows


def _write_epoch_screen_report(
    report_path: Path,
    old_rows: list[dict[str, object]],
    new_rows: list[dict[str, object]],
    abort_verdict: dict[str, object],
) -> None:
    headers = [
        "line",
        "epoch",
        "edge_w_main",
        "slope_main",
        "CNR_main",
        "bg_std",
        "cb_ratio",
        "thickness_std",
    ]
    rows = lib.summarize_line("old_psf", old_rows) + lib.summarize_line("new_psf", new_rows)
    lines = [
        "# Epoch Screen",
        "",
        f"- evaluated_epochs: {abort_verdict['evaluated_epochs']}",
        f"- abort_after_40: {abort_verdict['abort']}",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    lines += [
        "",
        "主判定只看主邊界 width、max slope、CNR_main、background_std；若 new_psf 在 epoch 20 與 40 都同時更差，就視為不能直接接舊 recipe。",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _write_summary_report(
    report_path: Path,
    old_result: dict[str, object],
    new_result: dict[str, object],
    abort_verdict: dict[str, object],
) -> None:
    lines = [
        "# Pure PSF Control Summary",
        "",
        f"- old_psf progress_dir: `{old_result['progress_dir']}`",
        f"- new_psf progress_dir: `{new_result['progress_dir']}`",
        f"- abort_after_epoch40: `{abort_verdict['abort']}`",
        "",
    ]
    if abort_verdict["abort"]:
        lines += [
            "結論：在舊 R26 recipe 等價重跑下，new centered PSF 在 epoch 20 與 40 都未追回 old_psf 線，純 PSF 直接接軌失敗。",
            "下一步若仍要讓新 PSF 變好，應另開 `recipe adaptation`，而不是再宣稱它能無痛取代舊 PSF。",
        ]
    else:
        lines += [
            "結論：new centered PSF 至少通過了 pure-control 的 40 epoch screen，可再進一步跑完整 100 epoch。",
        ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run pure old-recipe old/new-PSF control.")
    parser.add_argument("--skip-restore", action="store_true")
    parser.add_argument("--sweep-epochs", type=int, default=40)
    args = parser.parse_args(argv)

    paths = _prepare_dirs()
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())

    if not args.skip_restore:
        restore_payload = lib.snapshot_and_restore_official_psf(
            backup_root=paths["artifacts"] / f"official_psf_restore_{ts}"
        )
        lib.dump_json(paths["logs"] / f"official_psf_restore_{ts}.json", restore_payload)
        _write_restore_report(paths["reports"] / f"official_psf_restore_{ts}.md", restore_payload)

    recipe = lib.load_round26_recipe(lib.AUTO_TUNE_R26_REPORT, candidate_name="r26_sm035")
    old_spec = lib.build_control_spec(
        recipe=recipe,
        label="old_psf",
        psf_path=lib.OLD_PSF_ARCHIVE,
        progress_root=paths["runs"] / "old_psf",
        sweep_epochs=int(args.sweep_epochs),
    )
    new_spec = lib.build_control_spec(
        recipe=recipe,
        label="new_psf",
        psf_path=lib.ROOT_FORMAL_PSF,
        progress_root=paths["runs"] / "new_psf",
        sweep_epochs=int(args.sweep_epochs),
    )
    parity_rows = lib.build_parity_rows(old_spec, new_spec)
    lib.dump_json(paths["logs"] / "parity_diff.json", {"rows": parity_rows})
    _write_parity_report(paths["reports"] / "parity_diff.md", parity_rows)
    manifest = {
        "recipe_source": recipe["source_report"],
        "old_spec": old_spec,
        "new_spec": new_spec,
        "observation_epochs": list(lib.OBS_EPOCHS),
    }
    lib.dump_json(paths["logs"] / "pure_control_manifest.json", manifest)

    old_result, old_rows = _run_line(old_spec, paths)
    new_result, new_rows = _run_line(new_spec, paths)

    abort_verdict = lib.should_abort_after_epoch40(old_rows, new_rows)
    lib.dump_json(paths["logs"] / "epoch40_abort_verdict.json", abort_verdict)
    _write_epoch_screen_report(paths["reports"] / "epoch_screen.md", old_rows, new_rows, abort_verdict)
    _write_summary_report(paths["reports"] / "PURE_PSF_CONTROL_SUMMARY.md", old_result, new_result, abort_verdict)

    combined_rows = []
    for row in old_rows:
        combined_rows.append({"line": "old_psf", **row})
    for row in new_rows:
        combined_rows.append({"line": "new_psf", **row})
    lib.write_epoch_metrics_csv(paths["tables"] / "combined_epoch_metrics.csv", combined_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
