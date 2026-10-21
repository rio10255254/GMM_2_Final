"""Compact annotations and make figure contact sheets for read-only review."""
import json,math,re
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'results/thesis_v34_review_20260912';P=BASE/'extraction_v2'
def main():
    blocks=json.loads((P/'blocks.json').read_text(encoding='utf-8'));parts=json.loads((P/'other_parts.json').read_text(encoding='utf-8'))
    comments=parts['word/comments.xml'];w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    for start in range(0,len(comments),50):
        lines=[]
        for c in comments[start:start+50]:
            a=c['attributes'];cid=a.get('{'+w+'}id');anchors=[b['index'] for b in blocks if cid in b['comments']]
            lines.append(f"ID {cid} | {a.get('{'+w+'}author')} | blocks {anchors}\n{c['text']}")
        (P/f'compact_comments_{start//50+1}.txt').write_text('\n\n'.join(lines),encoding='utf-8')
    figs=[]
    for b in blocks:
        for im in b['images']:
            member=im.get('Target','');path=P/'media'/Path(member).name
            if not path.is_file():continue
            captions=[x for x in blocks if b['index']<x['index']<=b['index']+3 and 'Caption' in x['style']]
            figs.append(dict(file=str(path),block=b['index'],caption=captions[0]['text'] if captions else 'caption not adjacent'))
    # Some floating drawings sit in neighboring text; every media file still receives a view.
    seen={x['file'] for x in figs}
    for path in sorted((P/'media').iterdir()):
        if str(path) not in seen:figs.append(dict(file=str(path),block=None,caption='Floating or fallback image'))
    (BASE/'figure_reading_manifest.json').write_text(json.dumps(figs,ensure_ascii=False,indent=2),encoding='utf-8')
    folder=BASE/'figure_sheets';folder.mkdir(exist_ok=False);font=ImageFont.truetype('C:/Windows/Fonts/msjh.ttc',18)
    for start in range(0,len(figs),6):
        sheet=Image.new('RGB',(1440,1140),'#eeeeee');draw=ImageDraw.Draw(sheet)
        for j,item in enumerate(figs[start:start+6]):
            x=(j%2)*720;y=(j//2)*380;im=Image.open(item['file']).convert('RGB');im.thumbnail((690,305))
            sheet.paste(im,(x+(720-im.width)//2,y+50+(305-im.height)//2));label=f"{start+j+1}. {Path(item['file']).name} / block {item['block']}"
            draw.text((x+12,y+8),label,font=font,fill='black');draw.text((x+12,y+32),item['caption'][:36],font=font,fill='black')
        sheet.save(folder/f'figures_{start+1:02d}_{min(start+6,len(figs)):02d}.png')
    # Summarize appendix structure and compare it against actual annotation IDs.
    index=[b for b in blocks if b['index']>=1291]
    (BASE/'tail_structure.txt').write_text('\n'.join(f"[{b['index']}] {b['text'][:150]}" for b in index),encoding='utf-8')
    print('Prepared',len(comments),'comments and',len(figs),'figure placements.')
if __name__=='__main__':main()
