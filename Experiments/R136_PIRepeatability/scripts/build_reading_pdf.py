from common import *
import math,html,shutil
import pandas as pd,numpy as np
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT,TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import BaseDocTemplate,PageTemplate,Frame,Paragraph,Spacer,Table,TableStyle,Image,PageBreak,KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents
from PIL import Image as PILImage

BASE=ROOT/'output/R136_LSC_R61_Reading_Package';TMP=ROOT/'tmp/package_build';T=ROOT/'results/lsc/r61_analysis/tables';FIG=ROOT/'reports/lsc_r61_figures'
PDF=ROOT/'output/pdf/R136_LSC_R61_Report.pdf';PDF.parent.mkdir(parents=True,exist_ok=True)
pdfmetrics.registerFont(TTFont('CJK',r'C:\Windows\Fonts\msjh.ttc',subfontIndex=0));pdfmetrics.registerFont(TTFont('CJKB',r'C:\Windows\Fonts\msjhbd.ttc',subfontIndex=0));pdfmetrics.registerFontFamily('CJK',normal='CJK',bold='CJKB')
NAVY=colors.HexColor('#203A52');TEAL=colors.HexColor('#117C99');GRAY=colors.HexColor('#617080');LIGHT=colors.HexColor('#EFF4F7');LINE=colors.HexColor('#D7E0E7')
ST={
 'title':ParagraphStyle('Title',fontName='CJKB',fontSize=28,leading=38,textColor=NAVY,wordWrap='CJK',spaceAfter=18),
 'h':ParagraphStyle('Section',fontName='CJKB',fontSize=19,leading=27,textColor=NAVY,wordWrap='CJK',spaceAfter=14),
 'sub':ParagraphStyle('Sub',fontName='CJKB',fontSize=12,leading=19,textColor=TEAL,wordWrap='CJK',spaceBefore=10,spaceAfter=7),
 'body':ParagraphStyle('Body',fontName='CJK',fontSize=10.5,leading=17,wordWrap='CJK',spaceAfter=10,textColor=NAVY),
 'note':ParagraphStyle('Note',fontName='CJK',fontSize=9,leading=14,wordWrap='CJK',spaceAfter=8,textColor=GRAY),
 'cell':ParagraphStyle('Cell',fontName='CJK',fontSize=9,leading=13,wordWrap='CJK',textColor=NAVY),
 'head':ParagraphStyle('Head',fontName='CJKB',fontSize=9,leading=13,wordWrap='CJK',textColor=colors.white),
}
W,H=A4;CW=W-96
class Doc(BaseDocTemplate):
 def __init__(self,path):
  super().__init__(str(path),pagesize=A4,leftMargin=48,rightMargin=48,topMargin=58,bottomMargin=44,title='R61 LSC圓心位移：30次重拍完整結果',author='MOSR研究紀錄',pageCompression=1)
  self.addPageTemplates(PageTemplate(id='body',frames=[Frame(48,44,CW,H-102,id='normal',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=self.decorate));self.seq=0
 def beforeDocument(self):self.seq=0
 def decorate(self,c,doc):
  c.saveState();c.setStrokeColor(LINE);c.setLineWidth(.5);c.line(48,H-39,W-48,H-39);c.setFillColor(GRAY);c.setFont('CJK',8.2);c.drawString(48,H-29,'MOSR研究紀錄  /  LSC圓心位移  /  原圖與R61');c.drawString(48,25,'完整30次  ·  20倍  ·  9顆圓合併讀值');c.drawRightString(W-48,25,str(doc.page));c.restoreState()
 def afterFlowable(self,f):
  if isinstance(f,Paragraph) and f.style.name=='Section':
   self.seq+=1;key='section'+str(self.seq);text=f.getPlainText();self.canv.bookmarkPage(key);self.canv.addOutlineEntry(text,key,level=0,closed=False);self.notify('TOCEntry',(0,text,self.page,key))

story=[]
def P(text,style='body'):return Paragraph(text,ST[style])
def para(text,style='body'):story.append(P(text,style))
def section(title):
 if story:story.append(PageBreak())
 story.append(P(title,'h'))
def table(headers,rows,widths=None,size=9):
 data=[[P(html.escape(str(v)),'head') for v in headers]]
 for row in rows:data.append([P(html.escape('' if v is None else str(v)),'cell') for v in row])
 tb=Table(data,colWidths=widths or [CW/len(headers)]*len(headers),repeatRows=1,hAlign='LEFT')
 cmds=[('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,0),7),('BOTTOMPADDING',(0,0),(-1,0),7),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,1),(-1,-1),3),('BOTTOMPADDING',(0,1),(-1,-1),3),('LINEBELOW',(0,-1),(-1,-1),.6,LINE)]
 for i in range(1,len(data)):
  if i%2:cmds.append(('BACKGROUND',(0,i),(-1,i),LIGHT))
 tb.setStyle(TableStyle(cmds));story.append(tb);story.append(Spacer(1,10))
def image(path,height=330):
 with PILImage.open(path) as im:w,h=im.size
 scale=min(CW/w,height/h);story.append(Image(str(path),width=w*scale,height=h*scale,hAlign='CENTER'));story.append(Spacer(1,9))
def num(v,n=3):return f'{float(v):.{n}f}'
def reading_charts(positions,scans):
 import subprocess
 subprocess.run(['python',str(ROOT/'scripts/build_pdf_charts.py')],check=True)
def main():
 key=load(ROOT/'results/lsc/r61_analysis/key_results.json');cal=load(T/'calibration.json');summary=pd.read_csv(T/'summary.csv');rep=pd.read_csv(T/'repeatability.csv');scans=pd.read_csv(T/'per_scan.csv');positions=pd.read_csv(T/'per_position.csv');individual=pd.read_csv(T/'individual_circle_summary.csv');pairs=pd.read_csv(T/'paired_comparisons.csv');audit=load(ROOT/'results/lsc/r61_analysis/verification.json')
 snapshot=load(TMP/'package_context.json');reading_charts(positions,scans)
 # 1. Cover and takeaways
 para('原圖與 R61<br/>LSC 圓心位移<br/>30 次重拍完整結果','title')
 para('100MF樣品  /  Basler acA2040-120um  /  20倍','sub')
 para('本版以論文沿用的LSC圓心定位為主，納入全部30次掃描。原圖與R61各930張影像，每張追蹤同一組9顆圓。')
 para('<b>在這批資料與LSC流程下，R61的短步位移更接近PI回授，重拍波動約減半；相對起點的長距離位移也有較小幅度改善。</b>')
 table(['指標（nm）','原圖','R61'],[['每一步平均絕對誤差','8.667','5.160'],['每一步重拍波動','10.452','5.195'],['相對起點平均絕對誤差','17.738','15.267'],['相對起點重拍波動','14.796','11.870']],[CW*.58,CW*.21,CW*.21])
 para('短步：30次全部改善。相對起點：24次改善、6次退步。9顆圓分開分析時，各自的平均誤差也都有下降。')
 para('閱讀版：2026-09-17。拍攝日期：2026-09-03（台北時間）。<br/>本版只納入已完整完成的原圖與R61。R129仍在運算，未列入本版排名。','note')
 para('此處「誤差」是與PI回授的差距。結果適用於本批樣品與指定量法，尚不是完整量測不確定度或所有情境的準確度認證。','note')
 # 2. TOC
 section('目錄與閱讀方式');toc=TableOfContents();toc.levelStyles=[ParagraphStyle('TOC0',fontName='CJK',fontSize=10,leading=20,leftIndent=0,firstLineIndent=0,wordWrap='CJK',textColor=NAVY)];story.append(toc);story.append(Spacer(1,16))
 para('PDF用來閱讀結論、方法與主要圖表；Excel用來篩選與查詢完整數字。CSV保留原始欄位及完整精度。圖檔可單獨放大或放入簡報。','note')
 # 3 Method
 section('01  實驗範圍與量測方式')
 table(['項目','內容'],[['資料','100MF重複位移拍攝，同一樣品與同次工作階段'],['相機與倍率','Basler acA2040-120um，20倍'],['拍攝時間','2026-09-03 00:18至00:52（台北時間）'],['數量','30次完整掃描，每次31張；每方法930張'],['參考位置','使用者確認為拍攝時的PI實際X、Y回授，單位μm'],['名義尺度','3.45μm感光像素 / 20倍 = 0.1725μm/px'],['圓心定位','使用論文既有的取邊與幾何最小平方圓心擬合'],['目標','中央同一組3×3、共9顆圓，全程保留同一身分'],['位移','相鄰影像圓心相減；另直接計算各影格相對起點的圓心差'],['合併讀值','分別取9顆圓X、Y位移的中位數，再投影到主要移動方向']],[120,CW-120])
 para('原圖只提供共同的目標搜尋位置。原圖與R61都在自己的影像上重新取邊、擬合圓心，沒有把原圖圓心套給重建圖，也沒有利用PI答案指定最終圓心。')
 para('20倍取邊設定沿用原流程：64個等弧長輪廓點、13次粗輪廓演化、法線兩側2.4像素搜尋。目標初始大小由本批原圖取得。','note')
 # 4 overlay
 section('02  實際取邊與圓心定位')
 image(FIG/'01_circle_fit_check.png',560)
 para('圖1｜黃色點為實際取邊點，青色為擬合圓與圓心。上排是第一次掃描的首張，下排是最後一次掃描的末張；左右分別為原圖、R61。9顆圓的編號在整批資料中保持一致。','note')
 para('每方法共8,370筆圓心。位移由圓心座標相減得到，並非整個影像區域的圖案比對。')
 # 5 main
 section('03  主要結果與改善範圍')
 rows=[]
 for x in key['tables']:
  if x['view']=='nominal_all30':rows.append(['每一步' if x['kind']=='adjacent' else '相對起點','原圖' if x['model']=='Raw' else 'R61',num(x['mae_nm']),num(x['repeatability_nm']),num(x['maximum_error_nm'])])
 table(['位移方式','方法','平均絕對誤差 nm','重拍波動 nm','最大誤差 nm'],rows,[95,55,117,117,CW-384])
 para('上表是9顆圓合併後的讀值，不是單顆圓的定位能力。所有數值均納入完整30次；沒有挑选較好影格或剔除不利結果。','note')
 rows=[]
 for c in key['comparisons']:
  if c['view']=='nominal_all30':rows.append(['每一步' if c['kind']=='adjacent' else '相對起點',f"{c['mae_reduction_percent']:.2f}%",f"{c['repeatability_reduction_percent']:.2f}%",f"{c['improved_scans']} / 30",f"{c['mae_improvement_ci95'][0]:.3f}至{c['mae_improvement_ci95'][1]:.3f}"])
 table(['位移方式','平均誤差降低','重拍波動降低','改善次數','平均改善量95%範圍 nm'],rows,[88,92,92,74,CW-346])
 para('改善量為「原圖誤差減R61誤差」，正值代表改善。95%範圍以完整掃描為重抽單位，重抽10,000次；相鄰位移共用影格，不當作900個獨立實驗。')
 para('將連續3次掃描成組重抽後，短步改善量範圍為2.581至4.468nm；相對起點為1.323至3.655nm。兩者仍支持本批資料的平均改善。')
 # 6 errors
 section('04  各位置的平均誤差')
 image(TMP/'pdf_chart_position.png',500)
 para('圖2｜線為同一位置30次誤差的平均，陰影為上下各1個重拍標準差。灰色是原圖，藍色是R61。左圖比較相鄰步距，右圖比較相對起點的位移。','note')
 para('短步平均誤差有正有負，R61的重拍範圍較窄。相對起點則可見兩種方法都有隨位置改變的偏差，因此不能只看「更穩」就認定所有位置都完全正確。')
 para('位置序號1至30，代表每次掃描由起點往後的30個位置；不是30次掃描的次序。相對起點是直接由兩個圓心位置相減，沒有把每一步相加當作替代。')
 # 7 repeat
 section('05  同一位置重拍的波動')
 image(TMP/'pdf_chart_repeatability.png',500)
 para('圖3｜每個位置各自以30次誤差計算標準差。此圖回答的是「重做一次，讀值會變動多少」，不等同於30次取平均後的不確定度。','note')
 para('短步重拍波動由10.452nm降至5.195nm，約降低50.30%；相對起點由14.796nm降至11.870nm，約降低19.78%。')
 para('波動同時包含本次拍攝時間變化、影像與讀值變化、PI參考的波動。它是這次實驗的實測散布，不能直接當作整套系統的全部誤差來源。')
 # 8 run plot
 section('06  30次掃描逐次比較')
 image(TMP/'pdf_chart_captures.png',500)
 para('圖4｜每個點是一整次掃描的平均絕對誤差，虛線分隔前6次與後24次。左圖30次都改善；右圖24次改善、6次退步。','note')
 para('前6次掃描每次約20.5秒，後24次約26.4秒，中間約有11分鐘空檔。圖中沒有把這個時間差隱藏為同樣的拍攝節奏；分段結果另列於第11節。')
 # 9 full30
 section('07  全部30次的數值表')
 ss=scans[scans.view=='nominal_all30'];rows=[]
 for i in range(1,31):
  g=ss[ss.run_index==i].set_index(['kind','model']);a,b=g.loc[('adjacent','Raw'),'mae_nm'],g.loc[('adjacent','R61'),'mae_nm'];c,d=g.loc[('start','Raw'),'mae_nm'],g.loc[('start','R61'),'mae_nm'];rows.append([str(i),num(a),num(b),num(a-b),num(c),num(d),num(c-d)])
 table(['掃描','短步 原圖','短步 R61','短步 改善','起點 原圖','起點 R61','起點 改善'],rows,[43]+[(CW-43)/6]*6)
 para('單位：nm。改善 = 原圖平均絕對誤差 - R61平均絕對誤差。負值是退步。對應每次掃描的完整識別與其他指標，見Excel「每次掃描」。','note')
 # 10,11 position tables
 for kind,title in [('adjacent','08  各位置明細：相鄰每一步'),('start','09  各位置明細：相對起點')]:
  section(title);g=positions[(positions.view=='nominal_all30')&(positions.kind==kind)].set_index(['position_index','model']);rows=[]
  for j in range(1,31):
   a,b=g.loc[(j,'Raw')],g.loc[(j,'R61')];rows.append([str(j),num(a.bias_nm),num(b.bias_nm),num(a.repeatability_sd_nm),num(b.repeatability_sd_nm),num(a.mae_nm),num(b.mae_nm)])
  table(['位置','偏差 原圖','偏差 R61','重拍波動 原圖','重拍波動 R61','誤差大小 原圖','誤差大小 R61'],rows,[43]+[(CW-43)/6]*6)
  para('單位：nm。偏差保留正負，誤差大小使用絕對值；重拍波動為同一位置30次的標準差。最小值、最大值及側向資料完整保留於「各位置波動」工作表。','note')
 # 12 individual
 section('10  每顆圓分開看，也有改善')
 image(FIG/'05_individual_circles.png',200)
 g=individual.pivot(index=['kind','pillar_id'],columns='model',values='mae_nm');rows=[]
 for pid in range(1,10):rows.append([str(pid),num(g.loc[('adjacent',pid),'Raw']),num(g.loc[('adjacent',pid),'R61']),num(g.loc[('start',pid),'Raw']),num(g.loc[('start',pid),'R61'])])
 table(['圓編號','短步 原圖','短步 R61','起點 原圖','起點 R61'],rows,[65]+[(CW-65)/4]*4)
 para('圖5及表｜單顆圓的平均絕對誤差，單位nm。9顆圓在短步與相對起點兩種讀法中，平均誤差都下降，因此改善不是只靠少數圓或9圓合併後的效果。','note')
 para('這9顆圓共享同一張影像與相同拍攝條件，不能當成9倍的獨立實驗數。')
 # 13 calibration
 section('11  前6次校正，後24次檢驗')
 para(f'只使用前6次原圖的LSC位移與PI回授估計尺度及方向。得到每像素{cal["estimated_um_per_px"]:.9f}μm，固定套用到兩種方法後24次的資料。R61結果沒有參與尺度校正。')
 rows=[]
 for x in key['tables']:
  if x['view']=='calibrated_late24':rows.append(['每一步' if x['kind']=='adjacent' else '相對起點','原圖' if x['model']=='Raw' else 'R61',num(x['mae_nm']),num(x['repeatability_nm']),num(x['maximum_error_nm'])])
 table(['位移','方法','平均誤差 nm','重拍波動 nm','最大誤差 nm'],rows,[94,55,117,117,CW-383])
 para('拍攝時段比較（以下沿用全30次名義尺度）','sub');b=pd.read_csv(T/'time_blocks.csv');b=b[b.view=='nominal_all30'];rows=[]
 for _,x in b.iterrows():rows.append(['前6次' if x.time_block=='early6' else '後24次','每一步' if x.kind=='adjacent' else '相對起點','原圖' if x.model=='Raw' else 'R61',num(x.mae_nm)])
 table(['時段','位移','方法','平均絕對誤差 nm'],rows,[100,110,85,CW-295])
 para('後24次的檢驗仍顯示短步與相對起點平均誤差改善。這是以同一PI為參照的操作校正，並不是獨立的倍率校正證書。','note')
 # 14 ranges
 section('12  主要指標的95%範圍')
 metrics={'bias_nm':'有向偏差','mae_nm':'平均絕對誤差','rmse_nm':'平方平均根誤差','error_sd_nm':'掃描內波動'};rows=[]
 for kind in ['adjacent','start']:
  for model in ['Raw','R61']:
   x=summary[(summary.view=='nominal_all30')&(summary.kind==kind)&(summary.model==model)].iloc[0]
   for k,label in metrics.items():rows.append(['每一步' if kind=='adjacent' else '相對起點','原圖' if model=='Raw' else model,label,num(x[k+'_mean']),f"{x[k+'_ci95_low']:.3f}至{x[k+'_ci95_high']:.3f}"])
 table(['位移','方法','指標（nm）','30次平均','平均值95%範圍'],rows,[77,48,125,82,CW-332])
 para('「掃描內波動」是單次掃描中不同步距誤差的標準差，與第5節跨30次的重拍波動不同。「平均值95%範圍」也不是下一次量測落點的保證範圍。')
 para('完整指標、次間標準差、最大誤差與側向資料見Excel「各指標範圍」及原始summary.csv。所有區間以固定的尺度估計為條件，尚未合併PI等校正來源的不確定度。','note')
 # 15 worst
 section('13  最差情況與9顆圓的一致性')
 worst=pd.read_csv(T/'largest_errors.csv');worst=worst[worst.view=='nominal_all30'].groupby(['model','kind'],sort=False).head(3);rows=[]
 for _,x in worst.iterrows():rows.append(['原圖' if x.model=='Raw' else x.model,'每一步' if x.kind=='adjacent' else '相對起點',str(int(x.run_index)),f'{int(x.i)}到{int(x.j)}',num(abs(x.error_nm))])
 table(['方法','位移','掃描序號','影格索引','絕對誤差 nm'],rows,[65,105,90,95,CW-355])
 para('影格索引從0開始。每種方法、每種位移列出最大的3筆，完整最差清單包含在資料包。最大值是本批觀察到的結果，不是未來誤差上限。','note')
 within=pd.read_csv(T/'within_grid_variation.csv');rows=[]
 for (m,k),g in within.groupby(['model','kind']):rows.append(['原圖' if m=='Raw' else m,'每一步' if k=='adjacent' else '相對起點',num(g.within_grid_sd_nm.median()),num(g.within_grid_sd_nm.max())])
 table(['方法','位移','9圓不一致程度中位數 nm','觀察最大值 nm'],rows,[70,105,180,CW-355])
 para('圓間不一致是同一段位移中9顆圓讀值的分散，不能直接當作與PI的真實誤差。')
 #16 scope
 section('14  已核對的內容與適用範圍')
 table(['核對內容','結果'],[['資料完整性','兩方法各930張、8370筆圓心；所有30次均納入'],['圓心重新求解',f'全部16,740組邊界點獨立重算；最大圓心差{audit["max_independent_center_difference_px"]:.3g}px'],['位移計算','逐顆座標相減、9圓合併、PI單位換算均已重算核對'],['實際影像','首末拍攝的取邊與圓心標記已查看；同一組9顆圓持續追蹤'],['來源','原始照片與固定R61模型保留；重建結果直接沿用']],[130,CW-130])
 para('可以支持的結論','sub');para('在本批20倍、同一樣品、指定9顆圓與LSC流程下，R61改善與PI回授的差距及重拍穩定程度。短步改善較明顯，長距離仍有退步案例。')
 para('尚未由這批資料證明的事情','sub');para('不同樣品、不同倍率、不同天的普遍表現；圓的真實直徑或形狀；完整二維的尺度與方向；整套量測的總不確定度。')
 para('本資料主要沿PI Y方向移動。PI校正證書、有效光學倍率的獨立不確定度與殘餘同步時間差尚未提供，因此不能把重拍波動當作全部量測不確定度。')
 para('參考資料','sub');para('<link href="https://www.baslerweb.com/en/shop/aca2040-120um/" color="#117C99">Basler相機規格</link>　<link href="https://physics.nist.gov/cuu/Uncertainty/typea.html" color="#117C99">NIST：重複觀測</link>　<link href="https://physics.nist.gov/cuu/Uncertainty/typeb.html" color="#117C99">NIST：其他不確定度來源</link>','note')
 #17 supplementary
 section('15  補充：影像區域比對（非LSC）')
 para('<b>本節使用另一種量測方式，不能與前面的LSC數字混用。</b>前一輪是比對整個影像區域的移動，沒有逐顆擬合圓心。本包保留這段結果作方法比較。')
 table(['非LSC讀法','原圖每步誤差 nm','R61每步誤差 nm','30次比較'],[['細節加權區域比對','7.957','4.777','R61全30次較小'],['直接亮度區域比對','2.696','4.041','原圖全30次較小']],[150,110,110,CW-370])
 image(ROOT/'reports/r61_figures/05_sensitivity.png',260)
 para('補充圖｜非LSC讀法改變時，模型比較的方向會改變。這說明影像重建和量測方式必須一起驗證。論文採用LSC，因此主結論以前面完整LSC分析為準；也保留其他讀法的結果，不隱藏相反證據。','note')
 para('完整非LSC統計表與7張圖在「04_補充_非LSC影像比對」資料夾。')
 #18 package
 section('16  在其他電腦如何閱讀')
 table(['內容','用途'],[['01_報告','本PDF及可用文字編輯器閱讀的說明'],['02_統計表','Excel總表和完整CSV；可篩選掃描、位置、圓編號與方法'],['03_LSC圖表','主結果的原尺寸PNG圖檔，統計圖另附PDF'],['04_補充_非LSC影像比對','另一讀法的獨立結果與圖表，避免混入LSC主結論'],['05_定位與分析紀錄','16,740筆圓心的邊界點、PI原始位置紀錄、來源清單、設定與程式存檔']],[175,CW-175])
 para('建議順序','sub');para('先讀本PDF，再開Excel的「閱讀指南」與「主要結果」。需要追查單一位置時，查看「每次掃描」「各位置波動」「全部圓心」及「逐顆圓位移」。圖片都能獨立開啟，不依賴原電腦的路徑。')
 para('本包依使用者選擇，不含全量930張原圖、930張重建圖或模型權重。它是完整的閱讀與統計成果包；不等於可直接重新訓練或重建模型的完整實驗環境。')
 para('統計來源與重算','sub');para('主要數值直接取自已核對的CSV，沒有在排版時重新挑選資料。包內附完整性清單與輕量核對程式；分析程式存檔供追溯，歷史來源路徑只作來源說明。')
 para('版本範圍：原圖與R61，完整30次LSC。R129完成後應產生新的三方法比較版本，不把本版說成已包含R129。','note')
 Doc(PDF).multiBuild(story);shutil.copy2(PDF,BASE/'01_報告'/PDF.name);save(TMP/'pdf_created.json',dict(path=str(PDF),created_utc=now(),expected_pages=18,method='LSC primary,nonLSC supplementary'))
 print('Created',str(PDF),flush=True)
if __name__=='__main__':main()
