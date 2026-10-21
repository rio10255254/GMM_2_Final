"""Explicit private nonresearch backup exclusions; original files stay local."""
import json
from pathlib import Path


def load_exclusions(root):
    path=Path(root)/'docs/reproducibility/project_completion/EXCLUDED_PRIVATE_TOOL_BACKUPS.json'
    if not path.exists():
        return {'excluded_path_prefixes':[],'excluded_content_objects':[]}
    value=json.loads(path.read_text(encoding='utf-8'))
    for row in value['excluded_content_objects']:
        if len(row['sha256'])!=64 or row['bytes']<0:
            raise ValueError('Invalid explicit private backup identity')
    return value


def excluded(row,policy):
    relative=row.get('original_project_path',row.get('logical_path',row.get('path',''))).replace('\\','/').casefold()
    if any(relative.startswith(prefix.replace('\\','/').casefold().rstrip('/')+'/')
           for prefix in policy['excluded_path_prefixes']):
        return True
    return any((row.get('sha256'),row.get('bytes'))==(item['sha256'],item['bytes'])
               for item in policy['excluded_content_objects'])
