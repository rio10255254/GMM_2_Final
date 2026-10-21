"""A source scan must report removed evidence without mislabeling dependencies."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_research_preservation_delta import missing_captured_files

POLICY = {'excluded_path_prefixes': [], 'excluded_content_objects': []}


def record(path):
    return {'path': path, 'bytes': 15, 'sha256': 'a' * 64}


def test_missing_real_results_are_reported_without_touching_originals():
    pending = {'results/data.npy': record('results/data.npy')}
    missing, skipped = missing_captured_files(pending, set(), set(), POLICY)
    assert len(missing) == 1 and missing[0]['path'] == 'results/data.npy'
    assert missing[0]['state'] == 'missing_from_current_D_tree'
    assert pending['results/data.npy']['sha256'] == 'a' * 64 and skipped == {}


def test_explicit_dependency_exclusion_does_not_hide_similarly_named_research():
    pending = {p: record(p) for p in ['portable_runtime/tools.py', 'portable_runtime_research/output.npy', 'run/runtime/custom.py']}
    missing, skipped = missing_captured_files(pending, {'portable_runtime'}, set(), POLICY)
    assert {row['path'] for row in missing} == {'portable_runtime_research/output.npy', 'run/runtime/custom.py'}
    assert skipped['captured_source_inside_currently_excluded_or_referenced_directory'] == 1


def test_read_failure_is_distinguished_from_an_absent_original():
    pending = {'blocked/result.npy': record('blocked/result.npy')}
    missing, skipped = missing_captured_files(pending, set(), {'blocked'}, POLICY)
    assert not missing
    assert skipped['captured_source_not_rechecked_due_directory_read_error'] == 1


def test_unreadable_root_does_not_claim_all_originals_are_missing():
    pending = {'reports/final.csv': record('reports/final.csv')}
    missing, skipped = missing_captured_files(pending, set(), {'.'}, POLICY)
    assert not missing and skipped['captured_source_not_rechecked_due_directory_read_error'] == 1
