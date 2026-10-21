"""Check only the registered current H targets for late research changes.

The original full SHA-256 inventory remains authoritative for unchanged files.
New or changed files are hashed again. No research source or reference is edited,
and unregistered directory redirects are never followed into another data tree.
"""
import argparse
import gzip
import json
import os
from pathlib import Path
import stat
import time

from audit_research_preservation_delta import compare_file
from project_reproducibility_audit import classify,dependency_directory
from research_preservation_exclusions import load_exclusions,excluded
from research_recovery import write_json


def key(path):
    return os.path.normcase(os.path.abspath(path))


def inside(path,prefix):
    return path==prefix or path.startswith(prefix+os.sep)


def scoped_roots(edges,archive,operation):
    archive=archive.resolve();operation=operation.resolve();roots={}
    for edge in edges:
        target=Path(edge['target'])
        if not target.is_relative_to(archive):continue
        if target==archive or operation.is_relative_to(target) or target.is_relative_to(operation):
            raise ValueError('A registered target would include operation staging or the whole archive')
        if target.resolve()!=target or Path(edge['source']).resolve()!=target:
            raise ValueError('A registered source no longer resolves to its captured H target')
        roots[key(target)]=target
    ordered=sorted(roots.values(),key=lambda path:len(path.parts));selected=[]
    for target in ordered:
        if not any(target.is_relative_to(parent) for parent in selected):selected.append(target)
    return selected


def inspect_roots(roots,baseline,edges,repository,private_policy,progress=None):
    remaining=dict(baseline);findings=[];errors=[];references=[];states={};checked=0
    expected_edges={key(row['source']):key(row['target']) for row in edges}
    def locations(path):
        values=[]
        for edge in edges:
            target=Path(edge['target'])
            try:tail=path.relative_to(target)
            except ValueError:continue
            values.append((Path(edge['logical_path'])/tail).as_posix())
        return sorted(set(values))
    stack=list(roots)
    while stack:
        directory=stack.pop()
        try:entries=list(os.scandir(directory))
        except OSError as error:
            errors.append({'path':str(directory),'error':type(error).__name__});continue
        for entry in entries:
            path=Path(entry.path);physical=key(path)
            try:
                info=entry.stat(follow_symlinks=False)
                reparse=bool(getattr(info,'st_file_attributes',0)&stat.FILE_ATTRIBUTE_REPARSE_POINT)
                if entry.is_dir(follow_symlinks=False) or (reparse and path.is_dir()):
                    if dependency_directory(path,entry.name) or 'portable_runtime' in {p.casefold() for p in path.parts}:continue
                    if reparse:
                        actual=key(path.resolve());references.append({'path':str(path),'target':str(path.resolve())})
                        if expected_edges.get(physical)!=actual:
                            errors.append({'path':str(path),'error':'new_or_changed_unfollowed_directory_reference'})
                    else:stack.append(path)
                    continue
                if reparse:
                    errors.append({'path':str(path),'error':'unfollowed_reparse_file_requires_review'});continue
                previous=remaining.pop(physical,None)
                if previous is None and physical in baseline:
                    raise ValueError('A current file was visited twice through overlapping roots')
                relative=previous['logical_path'] if previous else locations(path)[0]
                if classify(relative)=='private_excluded' or excluded(previous or {'path':relative},private_policy):
                    states['private_excluded']=states.get('private_excluded',0)+1;continue
                state,finding=compare_file(path,relative,previous,repository.get(relative.casefold()))
                states[state]=states.get(state,0)+1;checked+=1
                if finding:
                    findings.append({**finding,'origin':'registered_H_reference','logical_aliases':locations(path)})
                if progress and checked%10000==0:progress(checked,states,len(findings),len(errors))
            except OSError as error:
                errors.append({'path':str(path),'error':type(error).__name__})
    for physical,previous in remaining.items():
        findings.append({'source':previous['source'],'path':previous['logical_path'],
                         'previous_sha256':previous['sha256'],'kind':previous['kind'],
                         'state':'previously_captured_H_file_now_missing','origin':'registered_H_reference'})
    return {'file_states':states,'files_checked':checked,'new_changed_or_missing_contents':findings,
            'read_or_reference_errors':errors,'nested_directory_references':references}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--operation',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve();op=args.operation.resolve()
    if args.report.exists():raise FileExistsError('Keep the preceding registered-target check')
    if not (op/'ALL_RESEARCH_CONTENT_HASHED.json').exists():raise ValueError('Finish the complete content hash audit first')
    edges=json.loads((root/'docs/reproducibility/project_completion/REGISTERED_DIRECTORY_REFERENCES.json').read_text(encoding='utf-8'))['edges']
    archive=Path(r'H:\GMM_2_Final_Archive');roots=scoped_roots(edges,archive,op)
    if not roots:raise ValueError('No current registered archive targets were selected')
    prefixes=tuple(key(path)+os.sep for path in roots);baseline={};started=time.time()
    for family in ['context','models','numeric','images','packages']:
        with gzip.open(op/('HASHED_'+family.upper()+'_FILES.jsonl.gz'),'rt',encoding='utf-8') as stream:
            for line in stream:
                row=json.loads(line);physical=key(row['source'])
                if not physical.startswith(prefixes):continue
                previous=baseline.get(physical)
                if previous and any(previous[field]!=row[field] for field in ['bytes','mtime_ns','sha256']):
                    raise ValueError('Two frozen records disagree about one current physical H file')
                baseline[physical]={field:row[field] for field in ['source','logical_path','bytes','mtime_ns','sha256','kind']}
        print('REGISTERED_H_BASELINE_LOADED',family,len(baseline),flush=True)
    with gzip.open(root/'docs/reproducibility/REPOSITORY_FILES.json.gz','rt',encoding='utf-8') as stream:
        repository={row['path'].casefold():row for row in json.load(stream)['files']}
    def progress(checked,states,findings,errors):
        write_json(args.report.with_name(args.report.stem+'_PROGRESS.json'),{
            'state':'running_not_completion','files_checked':checked,'states':states,
            'findings':findings,'errors':errors,'seconds':time.time()-started})
        print('REGISTERED_H_CURRENT_FILES_CHECKED',checked,findings,errors,flush=True)
    result=inspect_roots(roots,baseline,edges,repository,load_exclusions(root),progress)
    passed=not result['new_changed_or_missing_contents'] and not result['read_or_reference_errors']
    write_json(args.report,{'status':'NO_UNPRESERVED_REGISTERED_H_DELTA' if passed else 'REGISTERED_H_DELTA_REQUIRES_REVIEW',
        'current_roots':[str(path) for path in roots],'frozen_current_physical_files':len(baseline),
        **result,'whole_archive_or_operation_staging_scanned':False,'sources_or_training_modified':False,
        'seconds':time.time()-started,'whole_project_complete':False})
    print('REGISTERED_H_LATE_DELTA_AUDIT_FINISHED',passed,result['files_checked'],len(result['new_changed_or_missing_contents']),flush=True)


if __name__=='__main__':main()
