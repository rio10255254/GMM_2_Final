"""Phase 4 hand fix: early batches joined onto the training-output root.

Old code set one root, `PROJECT_ROOT / "Traing_Progress"`, and joined both kinds of
folder onto it: `training_progress_*` runs (now Experiments/Training_Runs) and the
early `organized_*` batches (now Experiments/Legacy). The decision for that root sent
it to Training_Runs, which is right for the runs but leaves every
`ROOT / "organized_..."` pointing at Experiments/Training_Runs/organized_..., a
folder that does not exist.

For each Python file that joins `organized_*` or `auto_tune_reports` onto a
Training_Runs root, this adds `LEGACY_ROOT` on the line below the root and moves
those joins onto it. Rerunning changes nothing.
"""
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
EARLY = r'(?:organized_|auto_tune_reports)'
ASSIGN = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*(.*?"Training_Runs"\)?)[ \t]*(?:#.*)?$', re.M)


def fix(text: str) -> str:
    for m in list(ASSIGN.finditer(text)):
        var, expr = m.group(1), m.group(2)
        join = re.compile(r'(?<![\w.])' + re.escape(var) + r'(\s*/\s*f?["\']' + EARLY + r')')
        if not join.search(text):
            continue
        text = join.sub(r'LEGACY_ROOT\1', text)
        legacy = 'LEGACY_ROOT = ' + expr.replace('"Training_Runs"', '"Legacy"')
        if legacy not in text:
            end = text.index('\n', text.index(m.group(0))) + 1
            text = text[:end] + legacy + '  # early organized_* batches\n' + text[end:]
    return text


def main() -> None:
    out = subprocess.run(['git', '-c', 'core.quotepath=false', '-C', str(REPO), 'ls-files', '-z', '--', '*.py'],
                         capture_output=True, check=True).stdout.decode('utf-8')
    changed = 0
    for rel in filter(None, out.split('\0')):
        p = REPO / rel
        raw = p.read_bytes()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            continue
        if '"Training_Runs"' not in text:
            continue
        crlf = '\r\n' in text
        new = fix(text.replace('\r\n', '\n'))
        if crlf:
            new = new.replace('\n', '\r\n')
        if new != text:
            p.write_bytes(new.encode('utf-8'))
            changed += 1
    print(f'{changed} files changed')


if __name__ == '__main__':
    main()
