from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
p=Path(str(PROJECT_ROOT / 'Experiments/R130_Clean/results/build_web_documents.py'))
s=p.read_text(encoding='utf-8-sig')
s=s.replace("st=self.doc.styles['Normal'];", "\n  for border in self.doc.styles.element.xpath('.//w:pBdr'):border.getparent().remove(border)\n  st=self.doc.styles['Normal'];")
s=s.replace("df=df.copy();self.p(title)","df=df.copy();self.p(title);self.doc.paragraphs[-1].paragraph_format.keep_with_next=True")
s=s.replace("w,h=Image.open(figs[key]).size;width=min(6.9,7.4*w/h)","w,h=Image.open(figs[key]).size;width=min(6.2 if key=='selected' else 6.9,7.4*w/h)")
s=s.replace("['初始開發',5.724764379,None,None,None]","['初始開發',5.724764379,4.642031369,3.745995140,1.667669470]")
s=s.replace('初始開發分項未在本表引用，留空不是零；全部原始開發記錄附於完整數據。','初始與最終分項均取自實際評估；全部原始開發記錄附於完整數據。')
s=s.replace("v=pd.read_csv(R/'results/independent_review/time_block_sensitivity.csv');x.table(v,", "v=pd.read_csv(R/'results/independent_review/time_block_sensitivity.csv').rename(columns={'kind':'位移種類','reference':'參考方法','mean_difference_nm':'平均差值','block3_separate_6_24_low_nm':'95%下界','block3_separate_6_24_high_nm':'95%上界'});x.table(v,")
p.write_text(s,encoding='utf-8')
