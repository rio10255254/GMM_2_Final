from pathlib import Path
import json, math
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
PROJECT_ROOT = Path(__file__).resolve().parents[3]

OUT = Path(__file__).resolve().parent
ROOT = Path(str(PROJECT_ROOT / 'Experiments'))
R140 = ROOT / "R140v2_StableUNet"
R148 = ROOT / "R148v2_HybridContextNativePSF"
R150 = ROOT / "R150_MatchedGeometryMeanPSF"
COMP = R150 / "results/comparison"
WITHIN = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Model_Comparison_Reports/WithinScan_30Step_16Models_20260930'))
EFF = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Efficiency_Validation_R140v2_R148v2_20260928'))
DOCX = OUT / "R140v2_R148v2_R150_Conference_Report_20260928.docx"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

MODELS = ["R140v2-StableUNet", "R148v2-HybridContextNativePSF", "R150-MatchedGeometryMeanPSF"]
SHORT = ["R140v2", "R148v2", "R150"]
GRAY = [55, 135, 205]

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def font(size, bold=False, serif=False):
    candidates = [
        r"C:\Windows\Fonts\mingliub.ttc" if bold and serif else r"C:\Windows\Fonts\mingliu.ttc" if serif else "",
        r"C:\Windows\Fonts\msjhbd.ttc" if bold else r"C:\Windows\Fonts\msjh.ttc",
        r"C:\Windows\Fonts\msjhl.ttc",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for p in candidates:
        if p and Path(p).exists(): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

F16, F20, F24, F28, FB22, FB28 = font(16), font(20), font(24), font(28), font(22, True), font(28, True)
FS18, FS20, FS22, FSB20, FSB24 = font(18, serif=True), font(20, serif=True), font(22, serif=True), font(20, True, True), font(24, True, True)

def text_center(draw, box, text, fnt, fill=0):
    x0,y0,x1,y1=box; b=draw.multiline_textbbox((0,0),text,font=fnt,align="center",spacing=4); w=b[2]-b[0]; h=b[3]-b[1]
    draw.multiline_text(((x0+x1-w)/2,(y0+y1-h)/2),text,font=fnt,fill=fill,align="center",spacing=4)

def architecture_figure():
    img=Image.new("L",(2100,980),255);d=ImageDraw.Draw(img)
    titles=["R140v2\n共享反覆 U-Net", "R148v2\n一次脈絡加獨立原尺寸階段", "R150\nR148v2 架構加資料與 PSF 政策"]
    for i,title in enumerate(titles):
        x=40+i*690; text_center(d,(x+10,45,x+640,145),title,FB28)
        if i<2:d.line((x+670,45,x+670,915),fill=170,width=2)
    # R140
    x=70
    blocks=[(180,"輸入與原圖特徵",230),(305,"共享 U-Net\n32 64 96 128",390),(500,"半尺寸 PSF 模組\n末次啟用 八候選",590),(700,"有界殘差輸出",750)]
    for y,t,y2 in blocks:d.rectangle((x,y,x+590,y2),fill=255,outline=0,width=2);text_center(d,(x,y,x+590,y2),t,F24)
    for y in (245,405,605):d.line((x+295,y,x+295,y+48),fill=0,width=3);d.polygon([(x+286,y+42),(x+304,y+42),(x+295,y+55)],fill=0)
    text_center(d,(x,790,x+590,895),"同一 U-Net 共用四次\n抗混疊降採樣與升採樣",F20)
    # R148
    x=760; d.rectangle((x,180,x+590,275),fill=255,outline=0,width=2);text_center(d,(x,180,x+590,275),"輸入與全解析 PSF 提示",F24)
    d.rectangle((x,330,x+590,440),fill=255,outline=0,width=2);text_center(d,(x,330,x+590,440),"抗混疊 U-Net 脈絡\n只執行一次",F24)
    d.line((x+295,275,x+295,325),fill=0,width=3)
    for j in range(3):
        bx=x+20+j*195;d.rectangle((bx,520,bx+170,645),fill=255,outline=0,width=2);text_center(d,(bx,520,bx+170,645),f"原尺寸階段 {j+1}\n獨立參數",F20)
        if j<2:d.line((bx+170,582,bx+192,582),fill=0,width=3);d.polygon([(bx+187,574),(bx+187,590),(bx+198,582)],fill=0)
    d.line((x+295,440,x+295,510),fill=0,width=3)
    d.rectangle((x,710,x+590,775),fill=255,outline=0,width=2);text_center(d,(x,710,x+590,775),"原圖參考 有界累積殘差",F20)
    text_center(d,(x,805,x+590,895),"最新 25 PSF\n訓練 25% 已知 推論平均",F20)
    # R150
    x=1450; d.rectangle((x,180,x+590,275),fill=255,outline=0,width=2);text_center(d,(x,180,x+590,275),"輸入與平均 PSF 提示",F24)
    d.rectangle((x,330,x+590,440),fill=255,outline=0,width=2);text_center(d,(x,330,x+590,440),"抗混疊 U-Net 脈絡\n只執行一次",F24)
    d.line((x+295,275,x+295,325),fill=0,width=3)
    for j in range(3):
        bx=x+20+j*195;d.rectangle((bx,520,bx+170,645),fill=255,outline=0,width=2);text_center(d,(bx,520,bx+170,645),f"原尺寸階段 {j+1}\n獨立參數",F20)
        if j<2:d.line((bx+170,582,bx+192,582),fill=0,width=3);d.polygon([(bx+187,574),(bx+187,590),(bx+198,582)],fill=0)
    d.line((x+295,440,x+295,510),fill=0,width=3)
    d.rectangle((x,710,x+590,775),fill=255,outline=0,width=2);text_center(d,(x,710,x+590,775),"原圖參考 有界累積殘差",F20)
    text_center(d,(x,805,x+590,895),"最新 25 PSF\n訓練與推論皆使用平均",F20)
    p=FIG/"figure_1_architecture.png";img.save(p,dpi=(200,200));return p

def patterned_bar(draw, box, model_index):
    x0,y0,x1,y1=box
    if model_index==0:
        draw.rectangle(box,fill=238,outline=0,width=2)
        for yy in range(y0+12,y1,24):
            for xx in range(x0+12,x1,24):draw.ellipse((xx-3,yy-3,xx+3,yy+3),fill=0)
    elif model_index==1:
        draw.rectangle(box,fill=170,outline=0,width=2)
        h=max(1,y1-y0)
        for s in range(x0-h,x1+1,24):
            xa=max(x0,s);ya=y1-(xa-s)
            xb=min(x1,s+h);yb=y1-(xb-s)
            if xa<=xb:draw.line((xa,ya,xb,yb),fill=50,width=3)
    else:
        draw.rectangle(box,fill=30,outline=0,width=2)

def draw_legend(draw, y=20):
    labels=SHORT; item_w=355; total=item_w*3; start=(2100-total)//2
    for i,label in enumerate(labels):
        x=start+i*item_w; patterned_bar(draw,(x,y+6,x+72,y+40),i);draw.text((x+88,y),label,font=FS22,fill=0)

def nice_max(v):
    raw=max(v)*1.17
    if raw<=10:step=2
    elif raw<=30:step=5
    elif raw<=80:step=10
    elif raw<=160:step=20
    else:step=50
    return max(step,math.ceil(raw/step)*step),step

def grouped_axis(draw, box, panels, sublabel=None):
    x0,y0,x1,y1=box;left=x0+105;right=x1-22;top=y0+58;base=y1-112
    values=[v for _,vals,_ in panels for v in vals];vmax,tick=nice_max(values)
    for val in np.arange(0,vmax+0.01,tick):
        yy=base-int((base-top)*float(val)/vmax);draw.line((left,yy,right,yy),fill=218,width=2)
        lab=f"{val:g}";b=draw.textbbox((0,0),lab,font=FS18);draw.text((left-16-(b[2]-b[0]),yy-(b[3]-b[1])/2),lab,font=FS18,fill=0)
    draw.line((left,top,left,base),fill=0,width=3);draw.line((left,base,right,base),fill=0,width=3)
    n=len(panels);group_w=(right-left)/n;bar_w=min(80,int(group_w/4.5));bar_gap=max(6,int(bar_w*.12))
    for k,(name,vals,unit) in enumerate(panels):
        cx=left+(k+.5)*group_w;start=cx-(3*bar_w+2*bar_gap)/2
        for i,v in enumerate(vals):
            bx=int(start+i*(bar_w+bar_gap));by=base-int((base-top)*v/vmax);patterned_bar(draw,(bx,by,bx+bar_w,base),i)
            txt=f"{v:.2f}";b=draw.textbbox((0,0),txt,font=FS18);draw.text((bx+(bar_w-(b[2]-b[0]))/2,by-(b[3]-b[1])-7),txt,font=FS18,fill=0)
        text_center(draw,(int(cx-group_w*.46),base+12,int(cx+group_w*.46),base+78),name,FS20)
    unit=panels[0][2] if panels else 'nm';draw.text((x0+8,top-36),f"Value ({unit})",font=FS20,fill=0)
    if sublabel: text_center(draw,(x0,base+78,x1,y1),sublabel,FSB20)

def conference_bars(path, panels, title, split=None):
    W=2100
    if split is None:
        H=900;img=Image.new("L",(W,H),255);d=ImageDraw.Draw(img);draw_legend(d,18);grouped_axis(d,(35,70,W-35,H-20),panels)
    else:
        H=1030;img=Image.new("L",(W,H),255);d=ImageDraw.Draw(img);draw_legend(d,18);gap=55;pw=(W-90-gap)//2
        grouped_axis(d,(30,70,30+pw,H-15),panels[:split],"(a)")
        grouped_axis(d,(30+pw+gap,70,W-30,H-15),panels[split:],"(b)")
    img.save(path,dpi=(200,200));return path

def configure_doc(doc):
    sec=doc.sections[0];sec.top_margin=Inches(.65);sec.bottom_margin=Inches(.62);sec.left_margin=Inches(.72);sec.right_margin=Inches(.72)
    styles=doc.styles
    normal=styles['Normal'];normal.font.name='Microsoft JhengHei';normal._element.rPr.rFonts.set(qn('w:eastAsia'),'Microsoft JhengHei');normal.font.size=Pt(10.5);normal.font.color.rgb=RGBColor(0,0,0);normal.paragraph_format.space_after=Pt(5);normal.paragraph_format.line_spacing=1.12
    for name,size,before,after in [('Title',17,0,10),('Heading 1',14,12,6),('Heading 2',11.5,9,4),('Subtitle',11,0,8)]:
        s=styles[name];s.font.name='Microsoft JhengHei';s._element.rPr.rFonts.set(qn('w:eastAsia'),'Microsoft JhengHei');s.font.size=Pt(size);s.font.bold=name!='Subtitle';s.font.color.rgb=RGBColor(0,0,0);s.paragraph_format.space_before=Pt(before);s.paragraph_format.space_after=Pt(after);s.paragraph_format.keep_with_next=True
        s.font.italic=False
        ppr=s.element.get_or_add_pPr()
        for border in list(ppr.findall(qn('w:pBdr'))):ppr.remove(border)
    header=sec.header.paragraphs[0];header.text='MOSR 混合重建模型比較報告';header.alignment=WD_ALIGN_PARAGRAPH.RIGHT;header.runs[0].font.size=Pt(8);header.runs[0].font.color.rgb=RGBColor(80,80,80)
    footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER;run=footer.add_run('第 ');fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');run._r.addnext(fld);footer.add_run(' 頁');
    for r in footer.runs:r.font.size=Pt(8)

def set_repeat_header(row):
    trPr=row._tr.get_or_add_trPr();tblHeader=OxmlElement('w:tblHeader');tblHeader.set(qn('w:val'),'true');trPr.append(tblHeader)

def shade_cell(cell,fill):
    tcPr=cell._tc.get_or_add_tcPr();shd=tcPr.find(qn('w:shd'))
    if shd is None:shd=OxmlElement('w:shd');tcPr.append(shd)
    shd.set(qn('w:fill'),fill)

def rules(cell, top=None, bottom=None):
    tcPr=cell._tc.get_or_add_tcPr();old=tcPr.find(qn('w:tcBorders'))
    if old is not None:tcPr.remove(old)
    b=OxmlElement('w:tcBorders')
    for edge in ('left','right'):
        e=OxmlElement('w:'+edge);e.set(qn('w:val'),'nil');b.append(e)
    for edge,spec in (('top',top),('bottom',bottom)):
        e=OxmlElement('w:'+edge)
        if spec is None:e.set(qn('w:val'),'nil')
        else:
            color,size=spec;e.set(qn('w:val'),'single');e.set(qn('w:sz'),size);e.set(qn('w:color'),color)
        b.append(e)
    tcPr.append(b)

def table(doc, headers, rows, widths=None, font_size=8.5, header_dark=True):
    t=doc.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False;set_repeat_header(t.rows[0])
    for j,h in enumerate(headers):
        c=t.rows[0].cells[j];c.text=str(h);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER;rules(c,('000000','12'),('000000','6'))
        for p in c.paragraphs:
            p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_after=Pt(0)
            for rr in p.runs:rr.font.bold=True;rr.font.size=Pt(font_size);rr.font.color.rgb=RGBColor(0,0,0)
    for i,row in enumerate(rows):
        cells=t.add_row().cells
        for j,v in enumerate(row):
            c=cells[j];c.text=str(v);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            rules(c,None,('000000','12') if i==len(rows)-1 else ('BFBFBF','3'))
            for p in c.paragraphs:
                p.alignment=WD_ALIGN_PARAGRAPH.LEFT if j==0 else WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=1.0
                for rr in p.runs:rr.font.size=Pt(font_size);rr.font.color.rgb=RGBColor(0,0,0)
    if widths:
        for row in t.rows:
            for j,w in enumerate(widths):row.cells[j].width=Inches(w)
    doc.add_paragraph().paragraph_format.space_after=Pt(0)
    return t

def caption(doc,text):
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_before=Pt(2);p.paragraph_format.space_after=Pt(7);r=p.add_run(text);r.bold=True;r.font.size=Pt(9)

def add_figure(doc,path,cap,width=7.0):
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=True;p.add_run().add_picture(str(path),width=Inches(width));caption(doc,cap)

def main():
    disp=pd.read_csv(COMP/'displacement_summary.csv');geo=pd.read_csv(COMP/'shape_size_summary.csv');sem=pd.read_csv(COMP/'SEM_corrected_size_summary.csv');semmap=pd.read_csv(COMP/'SEM_comparison.csv');endpoint=pd.read_csv(COMP/'endpoint_30um.csv');paired150=pd.read_csv(COMP/'paired_scan_intervals.csv');paired148=pd.read_csv(R148/'results/comparison/paired_scan_intervals.csv')
    cfg140=load_json(R140/'config/model.json');tr140=load_json(R140/'config/TRAIN.json');prov140=load_json(R140/'config/INHERITED_PSF_PROVENANCE.json');cfg148=load_json(R148/'config/model.json');tr148=load_json(R148/'config/train.json');audit148=load_json(R148/'results/training_deep_dive/frozen_checkpoint_audit.json');cfg150=load_json(R150/'config/model.json');tr150=load_json(R150/'config/train.json');audit150=load_json(R150/'results/final_audit.json');within=load_json(WITHIN/'summary.json');within_by={r['display']:r for r in within['ranked_summary']}
    def dr(model,kind,key):return float(disp[(disp.model==model)&(disp.kind==kind)][key].iloc[0])
    def gr(model,key):return float(geo[geo.model==model][key].iloc[0])
    def sr(model,key):return float(sem[sem.model==model][key].iloc[0])
    arch=architecture_figure()
    displacement_panels=[('短步平均絕對差',[dr(m,'adjacent','mae_nm') for m in MODELS],'nm'),('短步跨趟同一步波動',[dr(m,'adjacent','repeatability_nm') for m in MODELS],'nm'),('長距離平均絕對差',[dr(m,'start','mae_nm') for m in MODELS],'nm'),('長距離跨趟同一步波動',[dr(m,'start','repeatability_nm') for m in MODELS],'nm')]
    fig2=conference_bars(FIG/'figure_2_displacement.png',displacement_panels,'位移準度與跨趟同一步波動 越低越好')
    size_panels=[('直徑重拍波動',[gr(m,'diameter_repeat_sd_nm') for m in MODELS],'nm'),('輪廓重拍波動',[gr(m,'contour_repeat_sd_nm') for m in MODELS],'nm'),('去尺寸形狀波動',[gr(m,'shape_repeat_sd_nm') for m in MODELS],'nm'),('最差直徑偏移',[gr(m,'diameter_repeat_absmax_nm') for m in MODELS],'nm'),('SEM 平均直徑差',[sr(m,'mean_absolute_pillar_difference_nm') for m in MODELS],'nm')]
    fig3=conference_bars(FIG/'figure_3_size_contour.png',size_panels,'尺寸與輪廓結果 越低越好',split=4)
    sem_panels=[]
    for cand in (1,2):
        sub=semmap[semmap.mapping_candidate==cand].set_index('model')
        sem_panels += [(f'SEM 全徑向差 方向 {cand}',[float(sub.loc[m,'full_radial_difference_nm']) for m in MODELS],'nm'),(f'SEM 去尺寸形狀差 方向 {cand}',[float(sub.loc[m,'de_size_shape_difference_nm']) for m in MODELS],'nm')]
    fig4=conference_bars(FIG/'figure_4_sem_contour.png',sem_panels,'同九顆 SEM 輪廓一致度 越低越好',split=2)

    doc=Document();configure_doc(doc)
    p=doc.add_paragraph(style='Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.add_run('R140v2 R148v2 R150 混合重建模型設計與量測結果比較')
    p=doc.add_paragraph(style='Subtitle');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.add_run('U-Net PSF 抗混疊 位移 尺寸與輪廓之固定930張實拍比較')
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.add_run('研究實驗紀錄　2026年9月28日').bold=True
    doc.add_heading('摘要',level=1)
    doc.add_paragraph('本報告比較R140v2、R148v2與R150三種混合式單張同尺寸重建模型。三者皆使用U-Net相關的多尺度特徵、固定抗混疊濾波、原圖參考與有界殘差輸出，但反覆修正方式與PSF處理不同。比較採相同30趟、930張實拍與8,370顆圓，分開報告單趟30步波動、短步與長距離位移、直徑重拍、輪廓、同九顆SEM一致度與運算成本。2026年9月30日按使用者指定重新計算單趟波動：R140v2為4.321 nm、R150為4.726 nm、R148v2為4.865 nm；R150相對R148v2的配對區間跨零。R140v2仍是三版短步位移首選；R148v2保有直徑重拍與最新PSF混合架構的優勢，但不是單趟步距波動最低版本。尺寸相對SEM表仍不及原圖。')
    p=doc.add_paragraph();p.add_run('關鍵詞　').bold=True;p.add_run('點擴散函數　U-Net　抗混疊　微位移量測　輪廓重拍　SEM尺寸對照')
    doc.add_heading('1 研究問題與結論',level=1)
    doc.add_paragraph('問題是：在保留可寫入論文的方法特性時，哪個版本最符合短步位移、長距離位移、尺寸穩定與輪廓量測需求。比較後沒有單一版本在所有指標第一。限定使用最新研究版25顆PSF與後期脈絡加原尺寸階段設計時，R148v2是最平衡版本。若把「共享完整U-Net主幹反覆四次」列為必要條件，符合者是R140v2；R148v2與R150的三個原尺寸階段使用獨立參數，不能稱為共享主幹。')
    table(doc,['用途','建議版本','依據'],[
        ['最新PSF混合架構論文主模型','R148v2','直徑重拍13.252 nm最佳；長距離重拍10.156 nm最佳；SEM平均直徑差在三版中最低'],
        ['短步位移主模型','R140v2','單趟30步波動4.321 nm、短步平均差3.640 nm、最大誤差15.374 nm均為三版最低'],
        ['資料與平均PSF政策對照','R150','短步與去尺寸形狀有改善，但尺寸與輪廓退步，適合作為取捨證據'],
    ],widths=[1.6,1.1,4.4],font_size=9)
    caption(doc,'表 1　三版本的建議角色')

    doc.add_heading('2 比較範圍與指標定義',level=1)
    doc.add_paragraph('三模型皆固定使用各自第8,192次從零訓練權重。實拍比較使用同一30趟，每趟31張，共930張；每張固定量測九顆圓，共8,370個輪廓。單趟波動先對每趟30個相鄰步距取標準差，30趟各得到一個值，再扣除各趟平均步距合併變異；30趟用來判斷逐趟改善範圍。原表的跨趟同一步波動另行保留，不能代替單趟波動。位移準度則以影像位移相對PI回授差計算；區間重抽樣完整掃描，不把九顆圓或720個輪廓方向當成獨立樣本。')
    table(doc,['名詞','本報告定義','不能代表'],[
        ['位移準度','影像量測位移相對PI回授的平均絕對差','所有系統或所有樣品的絕對定位能力'],
        ['單趟30步波動','同一趟的30個相鄰影像步距樣本標準差 再以30趟合併','固定同一步跨30趟的波動或絕對準度'],
        ['直徑重拍','相同位置與圓在30趟間的直徑標準差','直徑接近SEM'],
        ['輪廓重拍','720方向半徑在30趟間的平均波動','SEM輪廓準確度'],
        ['去尺寸形狀','每個輪廓扣除自身平均半徑後的重拍波動','整體尺寸正確'],
        ['SEM輪廓一致度','實拍與同九顆SEM輪廓的徑向差','完全獨立的絕對準確度'],
    ],widths=[1.25,3.3,2.55],font_size=8.5)
    caption(doc,'表 2　指標的使用界線')

    doc.add_heading('3 模型設計總覽',level=1);add_figure(doc,arch,'圖 1　三種模型的資料流與反覆修正方式',7.0)
    table(doc,['項目','R140v2','R148v2','R150'],[
        ['參數量','1,446,366','1,194,406','1,194,406'],
        ['主架構','完整U-Net共享四次','U-Net脈絡一次 加三個獨立原尺寸階段','同R148v2'],
        ['U-Net通道','32 64 96 128','24 40 64 輸出16通道脈絡','同R148v2'],
        ['反覆次數','4','3','3'],
        ['原尺寸階段','無獨立階段','64通道 膨脹率1 2 4 2','同R148v2'],
        ['抗混疊','降採樣前與升採樣後固定二項式濾波','脈絡U-Net內固定二項式濾波 原尺寸階段不縮放','同R148v2'],
        ['正規化','逐像素跨通道','逐像素跨通道','逐像素跨通道'],
        ['殘差限制','總殘差±0.35 每次步長≤0.25','同左','同左'],
        ['PSF位置','最後一次 半尺寸解碼層','輸入全解析提示與最終成像一致','同R148v2'],
        ['PSF版本','較早25顆 bank 25cc6c95','最新研究25顆 bank efc9d70d','同R148v2'],
    ],widths=[1.25,1.9,2.25,1.8],font_size=7.6)
    caption(doc,'表 3　模型架構與光學模組比較')

    doc.add_heading('4 各版本的設計理念',level=1)
    doc.add_heading('4.1 R140v2 共享反覆U-Net',level=2)
    doc.add_paragraph('R140v2針對R139早期輸出飽和，加入逐像素通道正規化、較小學習率、較小輸出頭增益與梯度限制。同一個完整U-Net在四次修正中共享權重，透過原圖、目前輸出、殘差、水平與垂直梯度、拉普拉斯與局部平均建立七通道輸入。固定二項式濾波放在每次降採樣之前及雙線性升採樣之後，用來降低相位依賴。')
    doc.add_paragraph('PSF模組位於最後一次修正的半尺寸解碼層，從25顆較早PSF銀行挑八顆候選。930張實拍的八個權重最後全部為0.125；PSF開關造成的輸出差只有約0.0044至0.0054灰階。因此R140v2可支持共享反覆U-Net與抗混疊設計，但不能把其成績主要歸因於逐張PSF選擇。')
    doc.add_heading('4.2 R148v2 一次脈絡與獨立原尺寸邊界階段',level=2)
    doc.add_paragraph('R148v2改用最新研究版25顆PSF。U-Net只執行一次，輸出低強度脈絡特徵；三個原尺寸階段各自擁有參數，負責逐步修改影像邊界。這個分工避免完整U-Net重複執行時依賴範圍累積，也避免縮放路徑直接決定最後銳利邊界。')
    doc.add_paragraph('三階段最終步長為0.07776、0.07399與0.07119。關閉脈絡後14個抽查場景全部變差；關閉PSF提示後10個變差、4個改善。改用生成時的個別PSF取代平均PSF，整體差異接近零。這支持固定PSF物理提示存在，但不支持逐張PSF自適應已成功。')
    doc.add_heading('4.3 R150 實拍尺度圓陣列與平均PSF政策',level=2)
    doc.add_paragraph('R150完全保留R148v2模型，將96個過度擁擠的程序化場景換成半徑6至12像素、中心距24至36像素的圓陣列，並讓模型在訓練與推論都只看到平均PSF。25顆個別PSF仍負責製造訓練模糊。這版同時改變資料幾何與模型端PSF身分政策，因此實拍差異不能唯一歸因於其中一項。')
    doc.add_paragraph('R150在共同生成測試上比R148v2低6.45%，新圓陣列低13.85%，112組未更動場景低5.20%。但完整實拍顯示直徑隨拍攝趟次變化增加，因此生成改善沒有等比例轉移到尺寸量測。')

    doc.add_heading('5 訓練設定與具體參數',level=1)
    table(doc,['設定','R140v2','R148v2','R150'],[
        ['訓練母場景','512 train 128 dev 128 test','同左 每母場景4視圖','同左 其中96組換實拍尺度圓陣列'],
        ['更新與輪數','8,192 16輪','8,192 16輪','8,192 16輪'],
        ['最佳化','AdamW','AdamW','AdamW'],
        ['學習率','3e-4至3e-6','3e-4至3e-6','3e-4至3e-6'],
        ['梯度限制','1.0','1.0','1.0'],
        ['影像 梯度','1.0 0.2','1.0 0.2','1.0 0.2'],
        ['位移一致','0.2','0.2','0.2'],
        ['邊界 成像一致','無 無','0.2 0.01','0.2 0.01'],
        ['階段權重','最終輸出訓練政策','0.25 0.35 0.40','0.25 0.35 0.40'],
        ['訓練PSF身分','八候選門控','25%已知 其餘平均','全部平均'],
        ['精度','FP32 關閉TF32','FP32 關閉TF32','FP32 關閉TF32'],
    ],widths=[1.3,1.85,2.0,2.0],font_size=7.2)
    caption(doc,'表 4　正式訓練設定')

    doc.add_heading('6 PSF模組與論文可用主張',level=1)
    table(doc,['版本','可支持的主張','不應主張'],[
        ['R140v2','共享反覆U-Net 抗混疊與穩定殘差可改善短步位移','最新PSF逐張選擇有效 八候選自適應成功'],
        ['R148v2','最新25顆PSF的全解析物理提示 一次脈絡與原尺寸邊界分工','個別PSF身分可從影像可靠辨認 所有位移第一'],
        ['R150','平均PSF訓練推論一致與實拍尺度資料的受控結果','生成圓改善會自動改善實拍尺寸'],
    ],widths=[1.0,3.2,2.95],font_size=8.2)
    caption(doc,'表 5　PSF與創新主張的證據界線')
    doc.add_paragraph('最新研究版PSF使用實際P類SEM輪廓幾何完成校準，但沒有把SEM直徑值當成神經網路訓練答案。同九顆SEM再用於尺寸比較時，結果屬校準條件下的一致度，不能稱完全獨立的絕對準確度。')

    doc.add_heading('7 位移準度與兩種波動',level=1)
    doc.add_paragraph('使用者主要關心的是每一趟內30個單步位移的波動。表6先報這個指標；同一趟的RAW與模型逐一配對。合併標準差先扣除每趟平均步距，再合併30趟的變異。')
    table(doc,['方法','單趟標準差平均nm','30趟合併標準差nm','單趟最小至最大nm','相對RAW改善'],[
        [label,f"{within_by[label]['mean_scan_sd_nm']:.3f}",f"{within_by[label]['pooled_within_scan_sd_nm']:.3f}",f"{within_by[label]['per_scan_sd_min_nm']:.3f} 至 {within_by[label]['per_scan_sd_max_nm']:.3f}",'基準' if label=='RAW' else f"{within_by[label]['raw_reduction_pooled_percent']:.1f}%"] for label in ('RAW','R140v2','R148v2','R150')
    ],widths=[.8,1.4,1.45,1.7,1.2],font_size=8.3)
    caption(doc,'表 6　單趟30步位移波動與30趟合併結果')
    doc.add_paragraph('R140v2的合併標準差4.321 nm為三版最低，R150為4.726 nm，R148v2為4.865 nm。三者在30/30趟都比同趟RAW低。R150相對R148v2的合併差為0.139 nm，但完整趟次配對區間為負0.075至正0.366 nm，不能稱穩定勝出。更多歷史版本與每趟改善範圍已另作16方法共同重算。')
    add_figure(doc,fig2,'圖 2　短步與長距離準度及跨趟同一步波動',7.0)
    table(doc,['版本','短步平均差','短步偏差','短步重拍','短步最大','長距離平均差','長距離重拍'],[
        ['R140v2',f"{dr(MODELS[0],'adjacent','mae_nm'):.3f}",f"{dr(MODELS[0],'adjacent','bias_nm'):.3f}",f"{dr(MODELS[0],'adjacent','repeatability_nm'):.3f}",f"{dr(MODELS[0],'adjacent','maximum_error_nm'):.3f}",f"{dr(MODELS[0],'start','mae_nm'):.3f}",f"{dr(MODELS[0],'start','repeatability_nm'):.3f}"],
        ['R148v2',f"{dr(MODELS[1],'adjacent','mae_nm'):.3f}",f"{dr(MODELS[1],'adjacent','bias_nm'):.3f}",f"{dr(MODELS[1],'adjacent','repeatability_nm'):.3f}",f"{dr(MODELS[1],'adjacent','maximum_error_nm'):.3f}",f"{dr(MODELS[1],'start','mae_nm'):.3f}",f"{dr(MODELS[1],'start','repeatability_nm'):.3f}"],
        ['R150',f"{dr(MODELS[2],'adjacent','mae_nm'):.3f}",f"{dr(MODELS[2],'adjacent','bias_nm'):.3f}",f"{dr(MODELS[2],'adjacent','repeatability_nm'):.3f}",f"{dr(MODELS[2],'adjacent','maximum_error_nm'):.3f}",f"{dr(MODELS[2],'start','mae_nm'):.3f}",f"{dr(MODELS[2],'start','repeatability_nm'):.3f}"],
    ],widths=[.9,1.05,1.0,1.0,1.0,1.15,1.1],font_size=8)
    caption(doc,'表 6A　原有短步與長距離指標　波動欄為跨趟同一步　單位nm')
    doc.add_paragraph('表6A保留原本有效的不同指標：R140v2短步平均差與跨趟同一步波動均最低；R148v2相對R140v2的短步平均差增加0.363 nm，整趟配對區間為+0.157至+0.572 nm。R150短步平均差較R148v2低0.127 nm，但區間跨零。長距離平均差接近，R148v2的跨趟同一步波動最低。這些數值均不能替代表6的單趟30步波動。')

    doc.add_heading('8 尺寸與輪廓結果',level=1);add_figure(doc,fig3,'圖 3　直徑 輪廓 形狀與SEM尺寸差',7.0)
    table(doc,['版本','平均直徑','直徑重拍','輪廓重拍','去尺寸形狀','最差直徑偏移','SEM平均直徑差'],[
        [SHORT[i],f"{gr(m,'diameter_mean_nm'):.3f}",f"{gr(m,'diameter_repeat_sd_nm'):.3f}",f"{gr(m,'contour_repeat_sd_nm'):.3f}",f"{gr(m,'shape_repeat_sd_nm'):.3f}",f"{gr(m,'diameter_repeat_absmax_nm'):.3f}",f"{sr(m,'mean_absolute_pillar_difference_nm'):.3f}"] for i,m in enumerate(MODELS)
    ],widths=[.85,1.05,1.0,1.0,1.05,1.15,1.25],font_size=7.9)
    caption(doc,'表 7　尺寸與輪廓重拍　單位nm')
    doc.add_paragraph('R148v2的直徑重拍13.252 nm為三版最佳，且相對R140v2低5.329 nm，配對區間完全低於零。R140v2的輪廓重拍18.430 nm與R148v2的18.600 nm差異不明確，但去尺寸形狀15.991 nm明確較好。R150的直徑重拍22.389 nm與輪廓19.897 nm均明確退步；去尺寸形狀16.483 nm則比R148v2好。R150的問題集中在整體尺度隨掃描變動，而不是輪廓形狀全面失穩。')

    doc.add_heading('9 同九顆SEM的輪廓一致度',level=1);add_figure(doc,fig4,'圖 4　兩個方向候選下的SEM輪廓差',7.0)
    table(doc,['方向','指標','R140v2','R148v2','R150','最佳'],[
        [str(cand),'全徑向差',f"{float(semmap[(semmap.model==MODELS[0])&(semmap.mapping_candidate==cand)].full_radial_difference_nm.iloc[0]):.3f}",f"{float(semmap[(semmap.model==MODELS[1])&(semmap.mapping_candidate==cand)].full_radial_difference_nm.iloc[0]):.3f}",f"{float(semmap[(semmap.model==MODELS[2])&(semmap.mapping_candidate==cand)].full_radial_difference_nm.iloc[0]):.3f}",'R148v2'] if metric=='full' else [] for cand in [] for metric in []
    ],font_size=8)
    # Replace the empty helper table above with a populated compact table.
    t=doc.tables[-1];
    # remove empty artifact table and rebuild is intentionally avoided by appending rows directly
    vals=[]
    for cand in (1,2):
        s=semmap[semmap.mapping_candidate==cand].set_index('model')
        full=[float(s.loc[m,'full_radial_difference_nm']) for m in MODELS];shape=[float(s.loc[m,'de_size_shape_difference_nm']) for m in MODELS]
        vals.append([cand,'全徑向差',f'{full[0]:.3f}',f'{full[1]:.3f}',f'{full[2]:.3f}',SHORT[int(np.argmin(full))]])
        vals.append([cand,'去尺寸形狀差',f'{shape[0]:.3f}',f'{shape[1]:.3f}',f'{shape[2]:.3f}',SHORT[int(np.argmin(shape))]])
    # Delete the empty table XML, then insert the real table at current position.
    tbl_el=t._element;tbl_el.getparent().remove(tbl_el)
    table(doc,['方向','指標','R140v2','R148v2','R150','最佳'],vals,widths=[.65,1.35,1.15,1.15,1.15,1.0],font_size=8.2)
    caption(doc,'表 8　SEM輪廓一致度　單位nm')
    doc.add_paragraph('兩個方向候選的結論一致：R148v2具有最低全徑向差，代表尺寸與整體輪廓合併後最接近SEM。去除平均半徑後，方向1以R150略低，方向2以R148v2最低；差異很小且受方向對應影響。R150的SEM平均直徑差220.324 nm為三版最大，不能因去尺寸形狀略好而稱尺寸更準。')

    doc.add_heading('10 推論成本與工程特性',level=1)
    add_figure(doc,EFF/'figures/efficiency_time_memory.png','圖 5　同條件下的重建時間與模型記憶體峰值',7.0)
    eff=pd.read_csv(EFF/'benchmark_summary.csv')
    runt=[]
    for _,r in eff.iterrows():
        diff='整張基準' if pd.isna(r.get('worst_mean_difference_gray_levels')) else f"平均最壞 {r['worst_mean_difference_gray_levels']:.2e} 灰階"
        runt.append([r['display'],f"{r['median_seconds']:.2f}",f"{r['p90_seconds']:.2f}",f"{r['peak_allocated_gib']:.2f}",f"{r['peak_reserved_gib']:.2f}",diff])
    table(doc,['方案','中位秒','P90秒','模型峰值GiB','暫存保留GiB','與整張差異'],runt,widths=[1.5,.8,.8,1.05,1.05,1.7],font_size=7.8);caption(doc,'表 9　三張實拍的同條件效率與分塊驗證')
    doc.add_paragraph('在相同RTX A6000、FP32與1544乘2064影像下，R140v2整張重建中位1.32秒，模型峰值3.42 GiB；R148v2整張為1.42秒與4.41 GiB。R148v2正式512核心加24像素周圍範圍的分塊，中位1.89秒、模型峰值2.46 GiB，三張實拍與整張輸出的最壞平均差只有1.61乘10的負6次方灰階。R140v2若採992核心加128像素周圍範圍，中位2.19秒、模型峰值1.47 GiB；720加128可再降至1.03 GiB，但時間增加到2.73秒。')
    doc.add_paragraph('R148v2先以整張影像計算光學提示與脈絡，只切分三段原尺寸修正，因此分塊與整張幾乎相同。R140v2必須把完整四輪模型逐塊執行；三張實拍沒有接縫加重，但內部頻率處理會受畫面尺寸影響，所以只能主張實測近似一致。測試期間R61仍在同張顯示卡訓練，故相對排序與記憶體結論可用，正式論文秒數仍應在顯示卡空閒後複測。R150未納入本次同條件重跑；原930張紀錄的2.088秒保留為歷史觀察，不與本表直接比較。')

    doc.add_heading('11 論文方法選擇',level=1)
    doc.add_paragraph('若論文主軸要求最新研究版25顆PSF、U-Net脈絡、抗混疊、原圖參考、有界殘差、量測導向位置與邊界要求，以及完整930張驗證，建議使用R148v2。它在短步位移不是第一，但在直徑重拍、長距離重拍與同九顆SEM尺寸差之間最平衡。')
    doc.add_paragraph('R140v2適合作為共享反覆U-Net對照與短步位移上限。它的短步表現最好，也具有抗混疊與穩定正規化；但使用較早PSF銀行，八候選權重最後完全相等，不能當成最新PSF模組成功的證據。')
    doc.add_paragraph('R150應作為受控負結果與機制證據。它說明生成圓陣列與平均PSF政策可以改善生成邊界、短步平均值及去尺寸形狀，卻可能增加實拍尺度對模糊與拍攝條件的敏感度。R150不適合作為論文主模型。')
    table(doc,['論文段落','建議使用','可寫結論'],[
        ['主要方法','R148v2','一次抗混疊U-Net脈絡與三個獨立原尺寸邊界階段結合最新實測PSF提示'],
        ['共享主幹對照','R140v2','共享U-Net四次可得到最佳短步位移 但PSF自適應沒有成立'],
        ['資料與PSF政策消融','R150','生成改善不保證實拍尺寸改善 尺度敏感度需要獨立控制'],
        ['正式基準','COMBO','本報告不改變既有正式基準身分'],
    ],widths=[1.35,1.15,4.2],font_size=8.7);caption(doc,'表 10　建議的論文角色分配')

    doc.add_heading('12 限制與下一步',level=1)
    doc.add_paragraph('第一，R150同時改變資料幾何與模型端PSF身分政策，現有結果不能把尺寸退步唯一歸因於其中一項。若要繼續，應增加兩個單因素條件：新圓陣列加R148v2原PSF政策，以及舊R148v2資料加全程平均PSF。第二，同九顆SEM參與PSF校準，SEM比較不是完全獨立的絕對準確度。第三，三版都只在同一顯微系統與同類樣品完成驗證；跨樣品與跨系統尚未建立。第四，同條件效率測試期間仍有R61訓練共享顯示卡，絕對秒數需在空閒時複測。')
    doc.add_paragraph('現階段不建議再增加模型深度或放大邊界權重。最有價值的工作是用單因素資料與PSF政策拆開R150的尺度敏感來源，並以新的同類樣品與獨立尺寸參考確認R148v2的直徑重拍優勢能否外推。')

    doc.add_page_break();doc.add_heading('附錄 A 完整檢查點與來源',level=1)
    table(doc,['版本','最終權重SHA256','PSF銀行SHA256','結果狀態'],[
        ['R140v2','b96980287f02329b36f2188886462e51cadabad2259c8a13018f68e3b3f2650c',prov140['bank']['sha256'],'8192次 930張 8370圓 稽核通過'],
        ['R148v2','8daddf823166b373d3c3b437ebb9869e3d2260ed83d72613140669d92ee0db22','efc9d70d6427d82ba84f1371f71b6423f1491a815956412f8d6a627b72b1f843','8192次 930張 8370圓 稽核通過'],
        ['R150','1ce02e2c7f25bc88677212d02ee7116bef4dc61c45558f0dc135cee3e2d31e27','efc9d70d6427d82ba84f1371f71b6423f1491a815956412f8d6a627b72b1f843','8192次 930張 8370圓 稽核通過'],
    ],widths=[.8,2.45,2.45,1.4],font_size=6.8);caption(doc,'表 A1　正式權重與PSF身分')
    doc.add_heading('附錄 B 主要來源紀錄',level=1)
    for text in [
        'R140v2完整結果紀錄　Experiments R140v2 StableUNet reports R140v2 RESULTS',
        'R140v2 PSF因果核對　Experiments R140v2 StableUNet reports R140v2 PSF GATE CAUSAL AUDIT',
        'R148v2訓練與930張比較　Thesis MOSR Evidence Data Reports R148v2 Training DeepDive 20260926',
        'R150完整實拍驗證　Experiments R150 MatchedGeometryMeanPSF reports R150 REAL VALIDATION RESULTS',
        '共同量測表　R150 results comparison displacement summary shape size summary SEM comparison',
        '單趟30步位移重算　Thesis MOSR Evidence Model Comparison Reports WithinScan 30Step 16Models 20260930',
        'R140v2與R148v2同條件效率與分塊驗證　Thesis MOSR Evidence Efficiency Validation R140v2 R148v2 20260928',
    ]:doc.add_paragraph(text,style='List Bullet')
    doc.add_paragraph('報告結論只使用上述已完成且通過稽核的正式結果。R149局部邊界方案未通過預設門檻，沒有正式模型，因此不列入三模型性能排名。')
    doc.save(DOCX);print(DOCX)

if __name__=='__main__':main()
