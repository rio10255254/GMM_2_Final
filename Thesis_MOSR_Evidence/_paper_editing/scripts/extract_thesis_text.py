"""Extract docx XML to plain text with heading markers + paragraph numbers.

Used to locate exact paragraph boundaries for tracked-change editing.
"""
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
}
W = '{%s}' % NS['w']
A = '{%s}' % NS['a']
R = '{%s}' % NS['r']
WP = '{%s}' % NS['wp']


def para_text(p):
    bits = []
    for t in p.iter(W + 't'):
        if t.text:
            bits.append(t.text)
    for _ in p.iter(W + 'tab'):
        bits.append('\t')
    return ''.join(bits).strip()


def main(xml_path, out_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    body = root.find(W + 'body') or root
    out_lines = []
    paragraph_count = 0
    for p in body.iter(W + 'p'):
        paragraph_count += 1
        text = para_text(p)
        # Check for image
        has_img = any(True for _ in p.iter(WP + 'inline')) or any(True for _ in p.iter(WP + 'anchor'))
        prefix = f"[P{paragraph_count:04d}]"
        if has_img:
            out_lines.append(f"{prefix} [IMG] {text}")
        elif text:
            out_lines.append(f"{prefix} {text}")
        else:
            out_lines.append(f"{prefix}")
    Path(out_path).write_text('\n'.join(out_lines), encoding='utf-8')
    print(f"wrote {out_path} ({paragraph_count} paragraphs)")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
