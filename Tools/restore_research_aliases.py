"""Restore verified within-project shared-data references after downloading sources.

Only new directory references are created. Existing ordinary folders, user
files and historical links to an external H archive are never replaced.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess

from research_recovery import digest, safe_relative, write_json


def identical_directory(first, second, root):
    def inventory(folder):
        rows = {}
        for path in folder.rglob('*'):
            if not path.resolve().is_relative_to(root):
                raise ValueError('Existing shared data redirects outside the workspace')
            if path.is_file():
                rows[path.relative_to(folder).as_posix()] = path
        return rows
    left, right = inventory(first), inventory(second)
    return (set(left) == set(right) and
            all(left[name].stat().st_size == right[name].stat().st_size and
                digest(left[name]) == digest(right[name]) for name in left))


def restore_aliases(root, manifest, report):
    root = root.resolve(strict=True)
    if report.exists():
        raise FileExistsError('Alias receipt already exists')
    plan = json.loads(manifest.read_text(encoding='utf-8-sig'))
    pending = []; present = []; identical = []; seen = set()
    for item in plan['links']:
        if item['kind'] != 'inside_project':
            continue
        relative = safe_relative(item['path']); target_relative = safe_relative(item['portable_target'])
        alias = root / relative; target = root / target_relative
        key = str(relative).casefold()
        if key in seen:
            raise ValueError('Duplicate shared-source reference')
        seen.add(key)
        if alias == target or target.is_relative_to(alias):
            raise ValueError('Recursive shared-source reference')
        if not alias.resolve().is_relative_to(root) or not target.resolve().is_relative_to(root):
            raise ValueError('Shared source must stay within the downloaded workspace')
        if not target.is_dir():
            raise FileNotFoundError('Restore the source data first: ' + target_relative.as_posix())
        row = {'path': relative.as_posix(), 'target': target_relative.as_posix()}
        if os.path.lexists(alias):
            if alias.resolve() == target.resolve():
                present.append(row)
            elif alias.is_dir() and identical_directory(alias, target, root):
                # Some frozen packages already contain the complete logical
                # path. Keep that verified copy without replacing anything.
                identical.append(row)
            else:
                raise FileExistsError('Existing folder or reference is not replaced: ' + relative.as_posix())
        else:
            pending.append((alias, target, row))
    # All references are checked before any new one is created.
    created = []
    for alias, target, row in pending:
        alias.parent.mkdir(parents=True, exist_ok=True)
        if os.name == 'nt':
            quote = lambda value: "'" + str(value).replace("'", "''") + "'"
            script = "$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path " + quote(alias) + ' -Target ' + quote(target) + ' | Out-Null'
            subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                           check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            alias.symlink_to(os.path.relpath(target, alias.parent), target_is_directory=True)
        if alias.resolve() != target.resolve():
            raise OSError('Shared-data reference was not created correctly')
        created.append(row)
    receipt = {'status': 'PASS', 'created': created, 'already_correct': present,
               'already_identical_directory': identical,
               'external_H_archive_references_created': 0, 'existing_files_replaced': 0}
    write_json(report, receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    print(json.dumps(restore_aliases(args.root,
        args.manifest or args.root / 'docs/reproducibility/research_path_aliases.json',
        args.report or args.root / 'SHARED_SOURCE_REFERENCES_VERIFIED.json'), ensure_ascii=False))
