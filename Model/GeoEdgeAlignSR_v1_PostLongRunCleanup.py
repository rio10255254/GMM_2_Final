import json
import shutil
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TP_ROOT = PROJECT_ROOT / "Traing_Progress"
ORG_ROOT = TP_ROOT / "organized_20260311"
STATUS_MD = PROJECT_ROOT / "000_LONGRUN_UNIVERSAL_STATUS.md"
RUN_FLAG = PROJECT_ROOT / "000_LONGRUN_UNIVERSAL_RUNNING.txt"
CLEANUP_STATUS_MD = PROJECT_ROOT / "000_POST_CLEANUP_STATUS.md"
CLEANUP_STATUS_JSON = PROJECT_ROOT / "000_POST_CLEANUP_STATUS.json"
TRASH_ROOT = PROJECT_ROOT / "Trash_20260311_project_cleanup"


def _write_status(state: str, note: str, moved: dict | None = None) -> None:
    payload = {
        "state": state,
        "note": note,
        "moved": moved or {},
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
    CLEANUP_STATUS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    CLEANUP_STATUS_MD.write_text(
        "\n".join(
            [
                f"state: {payload['state']}",
                f"note: {payload['note']}",
                f"updated_at: {payload['updated_at']}",
            ]
        ),
        encoding="utf-8",
    )


def _safe_move(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return False
    shutil.move(str(src), str(dst))
    return True


def _latest_file(glob_pat: str, root: Path) -> Path | None:
    items = list(root.glob(glob_pat))
    if not items:
        return None
    items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return items[0]


def _wait_for_longrun_completion(timeout_sec: int = 8 * 3600) -> None:
    start = time.time()
    while time.time() - start < timeout_sec:
        if not RUN_FLAG.exists() and STATUS_MD.exists():
            txt = STATUS_MD.read_text(encoding="utf-8", errors="replace")
            if "state: completed" in txt or "state: error" in txt:
                return
        time.sleep(15)
    raise TimeoutError("Timed out waiting for longrun universal completion.")


def _collect_round12_runs_from_summary(summary_json: Path) -> tuple[list[Path], str]:
    data = json.loads(summary_json.read_text(encoding="utf-8"))
    selected_ckpt = str(data.get("selected_checkpoint") or "")
    run_dirs: list[Path] = []
    for report_path in data.get("report_paths", []):
        rp = Path(str(report_path))
        if not rp.exists():
            continue
        report = json.loads(rp.read_text(encoding="utf-8"))
        for cand in report.get("candidates", []):
            progress_dir = cand.get("progress_dir")
            if progress_dir:
                run_dirs.append(Path(str(progress_dir)))
    dedup = []
    seen = set()
    for p in run_dirs:
        s = str(p)
        if s in seen:
            continue
        seen.add(s)
        dedup.append(p)
    return dedup, selected_ckpt


def _write_readme(moved: dict, summary_json: Path | None, summary_md: Path | None) -> None:
    readme = ORG_ROOT / "README.md"
    lines = [
        "# organized_20260311",
        "",
        "目前用途：round12 universal multiscale 長跑、外部驗證重建、以及本輪歸檔。",
        "",
        "## 主要位置",
        f"- selected runs: {ORG_ROOT / 'selected' / 'runs'}",
        f"- selected reports: {ORG_ROOT / 'selected' / 'reports'}",
        f"- archive runs: {ORG_ROOT / 'archive' / 'runs' / 'round12_universal_longrun'}",
        f"- archive root status: {ORG_ROOT / 'archive' / 'root_status_legacy'}",
        f"- external validation: {ORG_ROOT / 'external_validation'}",
        f"- trash: {TRASH_ROOT}",
        "",
    ]
    if summary_json is not None:
        lines.append(f"- universal summary json: {summary_json}")
    if summary_md is not None:
        lines.append(f"- universal summary md: {summary_md}")
    lines.extend(
        [
            "",
            "## 本次整理",
            f"- moved_root_status_files: {len(moved.get('root_status', []))}",
            f"- moved_root_launchers_to_trash: {len(moved.get('launchers', []))}",
            f"- moved_round12_runs_selected: {len(moved.get('selected_runs', []))}",
            f"- moved_round12_runs_archive: {len(moved.get('archived_runs', []))}",
            f"- moved_root_legacy_runs_archive: {len(moved.get('root_legacy_runs', []))}",
            f"- moved_reconstruct_progress: {len(moved.get('legacy_reconstruct', []))}",
            f"- moved_old_trash: {len(moved.get('legacy_trash', []))}",
        ]
    )
    readme.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    _write_status("waiting", "waiting for longrun universal completion")
    _wait_for_longrun_completion()
    moved: dict[str, list[str]] = {
        "root_status": [],
        "launchers": [],
        "selected_runs": [],
        "archived_runs": [],
        "root_legacy_runs": [],
        "legacy_reconstruct": [],
        "legacy_trash": [],
    }
    _write_status("running", "longrun completed, starting cleanup")

    # 1) Move obsolete root status files, keep only current universal status in root.
    root_status_archive = ORG_ROOT / "archive" / "root_status_legacy"
    for name in [
        "000_AUTOTUNE_STATUS.json",
        "000_AUTOTUNE_STATUS.md",
        "000_LONGRUN_ROUND9_STATUS.json",
        "000_LONGRUN_ROUND9_STATUS.md",
        "000_LONGRUN_STATUS.json",
        "000_LONGRUN_STATUS.md",
        "000_ROUND6_PIPELINE_STATUS.json",
        "000_ROUND6_PIPELINE_STATUS.md",
    ]:
        src = PROJECT_ROOT / name
        dst = root_status_archive / name
        if _safe_move(src, dst):
            moved["root_status"].append(str(dst))

    # 2) Move obsolete root launcher helpers to trash.
    launchers_trash = TRASH_ROOT / "root_launchers"
    for name in [
        "OPEN_AUTOTUNE_MONITORS.cmd",
        "OPEN_ROUND6_MONITORS.cmd",
    ]:
        src = PROJECT_ROOT / name
        dst = launchers_trash / name
        if _safe_move(src, dst):
            moved["launchers"].append(str(dst))

    # 3) Move current round12 run dirs into selected/archive according to summary.
    summary_json = _latest_file("ROUND12_UNIVERSAL_MULTISCALE_SUMMARY_*.json", ORG_ROOT / "selected" / "reports")
    summary_md = _latest_file("ROUND12_UNIVERSAL_MULTISCALE_SUMMARY_*.md", ORG_ROOT / "selected" / "reports")
    if summary_json is not None:
        run_dirs, selected_ckpt = _collect_round12_runs_from_summary(summary_json)
        selected_run_dir = Path(selected_ckpt).parents[1] if selected_ckpt else None
        selected_target_root = ORG_ROOT / "selected" / "runs"
        archive_target_root = ORG_ROOT / "archive" / "runs" / "round12_universal_longrun"
        selected_new_ckpt = None
        for run_dir in run_dirs:
            if not run_dir.exists():
                continue
            if selected_run_dir is not None and run_dir.resolve() == selected_run_dir.resolve():
                dst = selected_target_root / run_dir.name
                if _safe_move(run_dir, dst):
                    moved["selected_runs"].append(str(dst))
                    if selected_ckpt:
                        selected_new_ckpt = dst / "weights" / Path(selected_ckpt).name
            else:
                dst = archive_target_root / run_dir.name
                if _safe_move(run_dir, dst):
                    moved["archived_runs"].append(str(dst))
        if selected_new_ckpt is not None:
            manifest_path = ORG_ROOT / "selected" / "current_universal_seed.json"
            manifest = {
                "weights_path": str(selected_new_ckpt),
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "source_summary": str(summary_json),
            }
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # 4) Move remaining root-level training_progress_* runs into archive.
    root_legacy_run_root = ORG_ROOT / "archive" / "runs" / "root_legacy"
    for run_dir in sorted(TP_ROOT.glob("training_progress_*")):
        if not run_dir.exists():
            continue
        dst = root_legacy_run_root / run_dir.name
        if _safe_move(run_dir, dst):
            moved["root_legacy_runs"].append(str(dst))

    # 5) Move legacy reconstruction root into archive.
    legacy_reconstruct = PROJECT_ROOT / "Reconstruct_Progress"
    if legacy_reconstruct.exists():
        dst = ORG_ROOT / "archive" / "legacy_root" / "Reconstruct_Progress"
        if _safe_move(legacy_reconstruct, dst):
            moved["legacy_reconstruct"].append(str(dst))

    # 6) Consolidate older trash into current trash root.
    old_trash = PROJECT_ROOT / "Trash_20260309_workflow_audit"
    if old_trash.exists():
        dst = TRASH_ROOT / "legacy" / old_trash.name
        if _safe_move(old_trash, dst):
            moved["legacy_trash"].append(str(dst))

    _write_readme(moved, summary_json, summary_md)
    _write_status("completed", "cleanup completed", moved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
