"""Exercise original-path preservation, especially relocated current results."""
import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("master_builder", TOOLS / "build_project_restore_index.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            json.dump(value, stream)
    else:
        path.write_text(json.dumps(value), encoding="utf-8")


def item(path, content, **extra):
    value = content.encode()
    return {"path": path, "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest(), **extra}


def fixture(tmp_path, monkeypatch, conflicting_git_source=False):
    root, op, out = tmp_path / "source", tmp_path / "operation", tmp_path / "master"
    current = item("README.md", "current guide")
    old_guide = item("README.md", "earlier guide")
    older_guide = item("README.md", "oldest guide")
    old_array = item("data/fixed.npy", "old array")
    current_array = item("__archive_objects__/new_array", "current array")
    old_image = item("results/centers/image.bmp", "old image")
    current_image = item("__archive_objects__/new_image", "current image")
    files = [old_guide, older_guide, old_array, current_array, old_image, current_image]
    for row in files:
        row["asset"] = "fixture.zip"
    archive_manifest = {"state": "complete", "files": files, "assets": [{"name": "fixture.zip", "sha256": "f" * 64, "bytes": 100}]}
    dump(op / "training_history_bundle/RESEARCH_ASSETS.json.gz", archive_manifest)
    dump(op / "context_batch_001_bundle/RESEARCH_ASSETS.json.gz", {"state": "complete", "files": [], "assets": []})
    dump(op / "GITHUB_CONTEXT_FAST_ISOLATED_GUARD.json", {"status": "PASS"})
    dump(op / "FIRST_SOURCE_COMMIT.json", {"files": []})
    dump(root / "docs/reproducibility/REPOSITORY_FILES.json.gz", {"source_snapshot_commit": "fixture", "files": [current]})
    dump(root / "docs/reproducibility/experiment_index.json", [])
    archive = Path(r"H:\GMM_2_Final_Archive")
    target = archive / "active_runs/test_current/centers"
    dump(root / "docs/reproducibility/project_completion/HISTORICAL_PATH_PROJECTIONS.json", {"projections": [{
        "archive_relative_prefix": "active_runs/test_current/centers", "project_prefix": "results/centers",
        "scope": "test", "projection_role": "current_registered_H_reference"}]})

    def captured(original, logical, source, origin):
        return {**original, "logical_path": logical, "source": str(source), "origin": origin,
                "scope": "test", "kind": "result_numeric"}

    rows = {
        "context": [captured(old_guide, "README.md", root / "README.md", "D_worktree")] if conflicting_git_source else [],
        "models": [],
        # A later current H reference must win over older archived contents,
        # while retaining that older content at a distinct historical path.
        "numeric": [captured(old_array, "data/fixed.npy", archive / "experiments/old/snapshot/fixed.npy", "H_snapshot"),
                    captured(current_array, "data/fixed.npy", archive / "active_runs/test_current/fixed.npy", "registered_H_reference")],
        # One physical H target is used through two original result paths.
        "images": [captured(current_image, "results_local/centers/image.bmp", target / "image.bmp", "registered_H_reference")],
        "packages": [],
    }
    for family, values in rows.items():
        with gzip.open(op / ("HASHED_" + family.upper() + "_FILES.jsonl.gz"), "wt", encoding="utf-8") as stream:
            for value in values:
                stream.write(json.dumps(value) + "\n")
    dump(op / "ALL_RESEARCH_CONTENT_HASHED.json", {"status": "ALL_REQUESTED_FAMILIES_CONTENT_CHECKED",
         "families": [{"family": family, "files": len(values)} for family, values in rows.items()]})
    for family in ["model", "numeric", "image", "package"]:
        dump(op / (family + "_batches") / "PLAN.json", {"tag": "fixture-" + family, "batches": []})
    monkeypatch.setattr(builder, "known_manifests", lambda root, archive: [])
    monkeypatch.setattr(builder, "git_tree", lambda root, ref: {"README.md": "a" * 40})
    monkeypatch.setattr(builder.subprocess, "check_output", lambda *args, **kwargs: gzip.compress(json.dumps({"source_snapshot_commit": "fixture-old", "files": [old_guide]}).encode()))
    monkeypatch.setattr(sys, "argv", ["builder", "--root", str(root), "--operation", str(op), "--output", str(out)])
    return out, current_array, current_image, old_guide, older_guide


def test_current_relocated_results_and_both_older_source_versions_survive(tmp_path, monkeypatch):
    out, array, image, old_guide, older_guide = fixture(tmp_path, monkeypatch)
    builder.main()
    rows = []
    for path in out.glob("RESTORE_*.json.gz"):
        rows.extend(builder.read(path)["files"])
    aliases = builder.read(out / "REPOSITORY_CONTENT_ALIASES.json.gz")["files"]
    locations = {row["path"]: row["sha256"] for row in rows + aliases}
    assert locations["data/fixed.npy"] == array["sha256"]
    assert locations["results/centers/image.bmp"] == image["sha256"]
    assert locations["results_local/centers/image.bmp"] == image["sha256"]
    assert {old_guide["sha256"], older_guide["sha256"]} <= {
        sha for path, sha in locations.items() if path.startswith("Historical_Publications/") and path.endswith("README.md")
    }
    assert not any(path.startswith("__archive_objects__/") for path in locations)


def test_changed_current_source_requires_review(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch, conflicting_git_source=True)
    with pytest.raises(ValueError, match="Current Git source differs"):
        builder.main()


def test_receipt_from_a_different_object_set_cannot_approve_a_component():
    row = item("data/original.npy", "original observation")
    part = {"name": "original.zip", "bytes": 123, "sha256": "a" * 64}
    manifest = {"files": [row], "assets": [part]}
    valid = {"status": "PASS_FILE_IDENTITY_AND_RESTORATION", "assets": [part],
             "checks": [{**row, "exact_file_bytes_restored": True}]}
    builder.verify_exact_batch_receipt(manifest, valid)
    wrong = {**valid, "checks": [{**item("data/other.npy", "different observation"), "exact_file_bytes_restored": True}]}
    with pytest.raises(ValueError, match="exact declared objects"):
        builder.verify_exact_batch_receipt(manifest, wrong)


def test_batch_release_shards_keep_their_exact_object_providers(tmp_path, monkeypatch):
    out, array, image, _, _ = fixture(tmp_path, monkeypatch)
    batches = []
    for number, (row, tag) in enumerate([(array, 'fixture-images'), (image, 'fixture-images-02')], 1):
        folder = tmp_path / 'operation/image_batches' / f'B{number}'
        part = {'name': 'same-part-name.zip', 'bytes': number * 100, 'sha256': str(number) * 64}
        saved = {**row, 'asset': part['name']}
        dump(folder / 'bundle/RESEARCH_ASSETS.json.gz', {'state': 'complete', 'files': [saved], 'assets': [part]})
        dump(folder / 'BATCH_GITHUB_RESTORE_VERIFIED.json', {
            'status': 'PASS_FILE_IDENTITY_AND_RESTORATION', 'assets': [part],
            'checks': [{**saved, 'exact_file_bytes_restored': True}]})
        batches.append({'batch': f'B{number}', 'folder': str(folder), 'tag': tag})
    dump(tmp_path / 'operation/image_batches/PLAN.json', {'tag': 'fixture-images', 'batches': batches})
    builder.main()
    master = builder.read(out / 'MASTER_RESTORE_INDEX.json')
    components = {row['tag']: builder.read(out / row['restore_manifest']) for row in master['components']}
    assert next(row for row in components['fixture-images']['files'] if row['path'] == 'data/fixed.npy')['sha256'] == array['sha256']
    assert next(row for row in components['fixture-images-02']['files'] if row['path'] == 'results/centers/image.bmp')['sha256'] == image['sha256']
    assert components['fixture-images']['assets'][0]['sha256'] != components['fixture-images-02']['assets'][0]['sha256']


def test_captured_old_task_catalog_cannot_replace_fixed_clone_catalog(tmp_path, monkeypatch):
    out, _, _, _, _ = fixture(tmp_path, monkeypatch)
    op=tmp_path/'operation';root=tmp_path/'source'
    relative='docs/reproducibility/REPOSITORY_FILES.json.gz'
    frozen=item(relative,'earlier self-excluding task catalog',asset='fixture.zip')
    original_catalog=(root/relative).read_bytes()
    manifest=builder.read(op/'training_history_bundle/RESEARCH_ASSETS.json.gz')
    manifest['files'].append(frozen)
    dump(op/'training_history_bundle/RESEARCH_ASSETS.json.gz',manifest)
    captured={**frozen,'logical_path':relative,'source':str(root/relative),
              'origin':'D_worktree','scope':'research','kind':'other_review'}
    with gzip.open(op/'HASHED_PACKAGES_FILES.jsonl.gz','wt',encoding='utf-8') as stream:
        stream.write(json.dumps(captured)+'\n')
    check=builder.read(op/'ALL_RESEARCH_CONTENT_HASHED.json')
    next(row for row in check['families'] if row['family']=='packages')['files']=1
    dump(op/'ALL_RESEARCH_CONTENT_HASHED.json',check)
    builder.main()
    rows=[]
    for component in out.glob('RESTORE_*.json.gz'):
        rows.extend(builder.read(component)['files'])
    assert all(row['path'].casefold()!=relative.casefold() for row in rows)
    saved=next(row for row in rows if row['sha256']==frozen['sha256'])
    assert saved['path']=='Historical_Preservation_Metadata/'+frozen['sha256'][:16]+'/'+relative
    assert (root/relative).read_bytes()==original_catalog


def test_pending_batch_path_review_never_creates_a_restorable_master(tmp_path, monkeypatch):
    out, _, _, _, _ = fixture(tmp_path, monkeypatch)
    op=tmp_path/'operation';folder=op/'numeric_batches/B001'
    pending=item('__archive_objects__/only_planned.npy','not yet on GitHub')
    dump(folder/'SELECTION.json',{'files':[pending]})
    export=op/'HASHED_NUMERIC_FILES.jsonl.gz'
    with gzip.open(export,'rt',encoding='utf-8') as stream:rows=[json.loads(line) for line in stream]
    rows.append({**pending,'logical_path':'data/only_planned.npy','source':str(tmp_path/'source/data/only_planned.npy'),
                 'origin':'D_worktree','scope':'test','kind':'result_numeric'})
    with gzip.open(export,'wt',encoding='utf-8') as stream:
        for row in rows:stream.write(json.dumps(row)+'\n')
    check=builder.read(op/'ALL_RESEARCH_CONTENT_HASHED.json')
    next(row for row in check['families'] if row['family']=='numeric')['files']=len(rows)
    dump(op/'ALL_RESEARCH_CONTENT_HASHED.json',check)
    dump(op/'numeric_batches/PLAN.json',{'tag':'pending-fixture','batches':[
        {'batch':'B001','folder':str(folder)}]})
    sys.argv.append('--review-paths-only')
    builder.main()
    review=builder.read(out/'PATH_PROVIDER_REVIEW.json')
    assert review['state']=='review_only_not_restorable'
    assert review['publication_complete'] is False
    assert review['pending_actual_GitHub_verification']['B001']=={'locations':1,'unique_objects':1}
    assert not (out/'MASTER_RESTORE_INDEX.json').exists()


def test_final_index_still_rejects_a_pending_batch(tmp_path, monkeypatch):
    _, array, _, _, _ = fixture(tmp_path, monkeypatch)
    op=tmp_path/'operation';folder=op/'numeric_batches/B001'
    dump(folder/'SELECTION.json',{'files':[array]})
    dump(op/'numeric_batches/PLAN.json',{'tag':'pending-fixture','batches':[
        {'batch':'B001','folder':str(folder)}]})
    with pytest.raises(ValueError,match='not been actually retrieved'):
        builder.main()


def test_image_role_uses_exact_evidence_without_relabeling_an_older_version(tmp_path, monkeypatch):
    out, _, image, _, _=fixture(tmp_path,monkeypatch)
    dump(tmp_path/'source/docs/reproducibility/project_completion/IMAGE_ROLE_EVIDENCE_20261021.json',
         {'files':[{'path':'results/centers/image.bmp','sha256':image['sha256'],'bytes':image['bytes'],
                    'role':'mathematical_translation_test_input','evidence':'original locked input manifest'}]})
    builder.main()
    rows=[]
    for path in out.glob('RESTORE_*.json.gz'):rows.extend(builder.read(path)['files'])
    current=next(row for row in rows if row['path']=='results/centers/image.bmp')
    assert current['role']=='mathematical_translation_test_input'
    historical=[row for row in rows if row['path'].startswith('Historical_Publications/') and row['path'].endswith('results/centers/image.bmp')]
    assert historical and all(row['role']!='mathematical_translation_test_input' for row in historical)


def test_current_image_cannot_inherit_a_stale_scientific_role(tmp_path, monkeypatch):
    fixture(tmp_path,monkeypatch)
    dump(tmp_path/'source/docs/reproducibility/project_completion/IMAGE_ROLE_EVIDENCE_20261021.json',
         {'files':[{'path':'results/centers/image.bmp','sha256':'b'*64,'bytes':1,
                    'role':'camera_original','evidence':'different file'}]})
    with pytest.raises(ValueError,match='reviewed role evidence'):
        builder.main()
