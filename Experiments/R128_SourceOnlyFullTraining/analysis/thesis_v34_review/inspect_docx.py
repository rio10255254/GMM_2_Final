"""Read-only capture of the user-specified annotated thesis, including all XML content."""
import json,hashlib,shutil,re,datetime,posixpath
from pathlib import Path
from zipfile import ZipFile
from lxml import etree

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path('C:/Users/Rio/OneDrive/學業/碩班/論文/可用/論文_v34_SEM與不利論述_完整標註版.docx')
BASE=ROOT/'results/thesis_v34_review_20260912'
OUT=BASE/'extraction_v2'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','a':'http://schemas.openxmlformats.org/drawingml/2006/main','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def local(e):return etree.QName(e).localname
def txt(e,deleted=False):
    if local(e)=='del' and not deleted:return ''
    if local(e) in ['t','delText']:return e.text or ''
    if local(e)=='tab':return '\t'
    if local(e) in ['br','cr']:return '\n'
    return ''.join(txt(c,deleted) for c in e)
def save(name,data):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    capture=json.loads((BASE/'source_capture.json').read_text(encoding='utf-8-sig'));before=capture['source_sha256'];assert sha(BASE/'source_annotated_v34.docx')==before
    with ZipFile(BASE/'source_annotated_v34.docx') as z:
        body=etree.fromstring(z.read('word/document.xml'));styles=etree.fromstring(z.read('word/styles.xml'))
        style_names={s.get('{'+NS['w']+'}styleId'):s.find('w:name',NS).get('{'+NS['w']+'}val') for s in styles.findall('w:style',NS) if s.find('w:name',NS) is not None}
        rels=etree.fromstring(z.read('word/_rels/document.xml.rels'));relmap={r.get('Id'):dict(r.attrib) for r in rels}
        blocks=[];table_count=0
        for i,e in enumerate(body.find('w:body',NS)):
            kind=local(e)
            if kind=='sectPr':continue
            text=txt(e);style=e.find('w:pPr/w:pStyle',NS);sid=style.get('{'+NS['w']+'}val') if style is not None else ''
            item=dict(index=i,kind=kind,style_id=sid,style=style_names.get(sid,sid),text=text,all_revision_text=txt(e,True),equations=[etree.tostring(x,encoding='unicode') for x in e.findall('.//m:oMath',NS)],images=[],comments=[])
            for b in e.findall('.//a:blip',NS):
                rid=b.get('{'+NS['r']+'}embed') or b.get('{'+NS['r']+'}link');item['images'].append(relmap.get(rid,{'Id':rid}))
            for c in e.findall('.//w:commentReference',NS):item['comments'].append(c.get('{'+NS['w']+'}id'))
            item['highlights']=[x.get('{'+NS['w']+'}val') for x in e.findall('.//w:highlight',NS)]
            if kind=='tbl':
                table_count+=1;item['table_index']=table_count;item['rows']=[[txt(c) for c in row.findall('w:tc',NS)] for row in e.findall('w:tr',NS)]
            blocks.append(item)
        parts={}
        for name in z.namelist():
            if re.fullmatch(r'word/(comments\d*|footnotes|endnotes|header\d+|footer\d+)\.xml',name):
                r=etree.fromstring(z.read(name));parts[name]=[dict(kind=local(e),attributes=dict(e.attrib),text=txt(e,True)) for e in r]
        media=[];(OUT/'media').mkdir()
        for name in z.namelist():
            if name.startswith('word/media/'):
                dest=OUT/'media'/Path(name).name;dest.write_bytes(z.read(name));media.append(dict(member=name,file=str(dest),sha256=sha(dest),bytes=dest.stat().st_size))
        for name in ['docProps/core.xml','docProps/app.xml']:
            if name in z.namelist():parts[name]=z.read(name).decode('utf-8')
        save('blocks.json',blocks);save('other_parts.json',parts);save('media_manifest.json',media)
        with (OUT/'full_text.md').open('x',encoding='utf-8') as f:
            for b in blocks:
                f.write(f"\n\n[BLOCK {b['index']:04d} {b['kind']} {b['style']}]\n")
                if b['kind']=='tbl':
                    for row in b['rows']:f.write(' | '.join(row)+'\n')
                else:f.write(b['text']+'\n')
                if b['images']:f.write('[IMAGES: '+', '.join(x.get('Target','?') for x in b['images'])+']\n')
                if b['equations']:f.write('[EQUATIONS: '+str(len(b['equations']))+']\n')
                if b['comments']:f.write('[COMMENTS: '+','.join(b['comments'])+']\n')
                if b['all_revision_text']!=b['text']:f.write('[INCLUDING DELETED TEXT]\n'+b['all_revision_text']+'\n')
        outline=[dict(index=b['index'],style=b['style'],text=b['text'][:350]) for b in blocks if ('heading' in b['style'].lower() or re.match(r'^第[一二三四五六七八九十0-9]+章',b['text']) or re.match(r'^\d+\.\d+\s',b['text']))]
        save('outline.json',outline)
        inventory=dict(source=str(SOURCE),source_sha256=before,snapshot=str(BASE/'source_annotated_v34.docx'),created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),body_blocks=len(blocks),paragraphs=len(body.findall('.//w:p',NS)),tables=table_count,equations=len(body.findall('.//m:oMath',NS)),insertions=len(body.findall('.//w:ins',NS)),deletions=len(body.findall('.//w:del',NS)),comment_references=len(body.findall('.//w:commentReference',NS)),media=len(media),text_characters=sum(len(b['text']) for b in blocks),other_parts=list(parts),source_unchanged_during_capture=capture['source_unchanged_during_capture'])
        save('inventory.json',inventory);print(json.dumps(inventory,ensure_ascii=True,indent=2));print('Outline blocks:',len(outline))

if __name__=='__main__':main()
