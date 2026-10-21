"""Find research files added or changed during a long GitHub preservation run.

Previously fully hashed files may reuse that result only while size and precise
last-write time remain unchanged. New/changed files are read and hashed again.
This is a final-delta check, not a replacement for the full content audit. No
source, directory reference, training process or research verdict is modified.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat

from project_reproducibility_audit import classify, dependency_directory
from research_recovery import write_json
from research_preservation_exclusions import load_exclusions,excluded as private_excluded


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def compare_file(path, relative, previous, repository_record):
    before = path.stat()
    if previous and (before.st_size, before.st_mtime_ns) == (previous['bytes'], previous['mtime_ns']):
        return 'unchanged_since_full_content_audit', None
    digest = checksum(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        return 'changed_while_reading', {'path': relative, 'bytes': after.st_size}
    if repository_record and (after.st_size, digest) == (repository_record['bytes'], repository_record['sha256']):
        return 'current_source_catalog_content', None
    if previous and (after.st_size, digest) == (previous['bytes'], previous['sha256']):
        return 'metadata_only_change', None
    return 'new_or_changed_research_content', {
        'path': relative, 'source': str(path), 'bytes': after.st_size,
        'mtime_ns': after.st_mtime_ns, 'sha256': digest,
        'previous_sha256': previous['sha256'] if previous else None,
        'kind': classify(relative),
    }


def missing_captured_files(remaining, excluded_directories, unreadable_directories, private_policy):
    """Distinguish absent originals from deliberately unscanned dependency trees."""
    missing, skipped = [], {}
    def ancestor_in(relative, prefixes):
        if '' in prefixes or '.' in prefixes:
            return True
        parts = relative.casefold().split('/')
        return any('/'.join(parts[:index]) in prefixes for index in range(1, len(parts)))
    for key, previous in remaining.items():
        relative = previous['path']
        if private_excluded({'path': relative, **previous}, private_policy) or classify(relative) == 'private_excluded':
            reason = 'private_nonresearch_source_excluded'
        elif ancestor_in(key, excluded_directories):
            reason = 'captured_source_inside_currently_excluded_or_referenced_directory'
        elif ancestor_in(key, unreadable_directories):
            reason = 'captured_source_not_rechecked_due_directory_read_error'
        else:
            missing.append({'path': relative, 'previous_sha256': previous['sha256'], 'bytes': previous['bytes'],
                            'kind': classify(relative), 'state': 'missing_from_current_D_tree',
                            'archived_original_not_removed_or_replaced_by_this_check': True})
            continue
        skipped[reason] = skipped.get(reason, 0) + 1
    return missing, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--operation', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError('Keep the preceding delta check')
    if not (args.operation / 'ALL_RESEARCH_CONTENT_HASHED.json').exists():
        raise ValueError('Finish the original full content audit before the final delta check')
    root = args.root.resolve()
    private_policy=load_exclusions(root)
    baseline = {}
    for family in ['context', 'models', 'numeric', 'images', 'packages']:
        with gzip.open(args.operation / ('HASHED_' + family.upper() + '_FILES.jsonl.gz'), 'rt', encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                if row['origin'] == 'D_worktree':
                    baseline[row['logical_path'].casefold()] = {
                        key: row[key] for key in ['bytes', 'mtime_ns', 'sha256']}
                    baseline[row['logical_path'].casefold()]['path'] = row['logical_path']
    with gzip.open(root / 'docs/reproducibility/REPOSITORY_FILES.json.gz', 'rt', encoding='utf-8') as stream:
        source_catalog = json.load(stream)
    repository = {r['path'].casefold(): r for r in source_catalog['files']}
    source_catalog_relative = 'docs/reproducibility/REPOSITORY_FILES.json.gz'
    counts = {}
    findings, errors, edges = [], [], []
    remaining = dict(baseline)
    excluded_directories, unreadable_directories = set(), set()
    stack = [root]
    while stack:
        folder = stack.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError as error:
            errors.append({'path': str(folder), 'error': type(error).__name__})
            unreadable_directories.add(folder.relative_to(root).as_posix().casefold())
            continue
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            if private_excluded({'path':relative},private_policy):
                counts['private_nonresearch_backup_excluded']=counts.get('private_nonresearch_backup_excluded',0)+1
                excluded_directories.add(relative.casefold())
                continue
            try:
                info = entry.stat(follow_symlinks=False)
                reparse = bool(getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
                if entry.is_dir(follow_symlinks=False) or (reparse and path.is_dir()):
                    if 'portable_runtime' in {part.casefold() for part in Path(relative).parts}:
                        counts['generic_portable_runtime_excluded']=counts.get('generic_portable_runtime_excluded',0)+1
                        excluded_directories.add(relative.casefold())
                        continue
                    if dependency_directory(path, entry.name):
                        excluded_directories.add(relative.casefold())
                        continue
                    if reparse:
                        edges.append({'path': relative, 'target': str(path.resolve())})
                        excluded_directories.add(relative.casefold())
                    else:
                        stack.append(path)
                    continue
                remaining.pop(relative.casefold(), None)
                if reparse:
                    errors.append({'path': relative, 'error': 'new_reparse_file_requires_review'})
                    continue
                if classify(relative) == 'private_excluded':
                    counts['private_or_generic_certificate_excluded'] = counts.get('private_or_generic_certificate_excluded', 0) + 1
                    continue
                if relative == source_catalog_relative:
                    counts['source_catalog_self_excluded'] = 1
                    continue
                state, finding = compare_file(path, relative, baseline.get(relative.casefold()), repository.get(relative.casefold()))
                counts[state] = counts.get(state, 0) + 1
                if finding:
                    findings.append(finding)
            except OSError as error:
                errors.append({'path': relative, 'error': type(error).__name__})
    expected_edges = json.loads((root / 'docs/reproducibility/project_completion/REGISTERED_DIRECTORY_REFERENCES.json').read_text(encoding='utf-8'))['edges']
    prior = {r['logical_path'].casefold(): os.path.normcase(r['target']) for r in expected_edges if Path(r['source']).is_relative_to(root)}
    current = {r['path'].casefold(): os.path.normcase(r['target']) for r in edges}
    edge_changes = [{'path': key, 'previous': prior.get(key), 'current': current.get(key)}
                    for key in sorted(set(prior) | set(current)) if prior.get(key) != current.get(key)]
    missing, skipped_missing = missing_captured_files(remaining, excluded_directories, unreadable_directories, private_policy)
    write_json(args.report, {
        'status': 'NO_UNPRESERVED_RESEARCH_DELTA' if not findings and not missing and not errors and not edge_changes else 'DELTA_REQUIRES_PRESERVATION_REVIEW',
        'file_states': counts, 'new_or_changed_contents': findings, 'read_errors': errors,
        'captured_sources_missing_from_current_D_tree': missing,
        'captured_sources_in_currently_excluded_or_unreadable_trees': skipped_missing,
        'directory_reference_changes': edge_changes,
        'full_previous_content_hashes_reused_only_with_unchanged_metadata': True,
        'registered_H_payloads_not_rescanned_by_this_D_delta_check': True,
        'sources_or_processes_modified': False,
    })
    print('FINAL_RESEARCH_DELTA_CHECK', len(findings), len(missing), len(errors), len(edge_changes), flush=True)


if __name__ == '__main__':
    main()
