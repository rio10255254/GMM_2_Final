"""Native journal-style table rules and independent chart axis formats."""
import sys,zipfile
from pathlib import Path
from lxml import etree
p=Path(sys.argv[1]);ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
with zipfile.ZipFile(p) as z:entries=[(i,z.read(i.filename)) for i in z.infolist()]
tmp=p.with_name(p.stem+'_journal.pptx')
def rule(tcpr,side,color=None,width=0):
    tag='{'+ns['a']+'}ln'+side
    for e in tcpr.findall(tag):tcpr.remove(e)
    line=etree.Element(tag,w=str(width or 12700))
    # DrawingML requires table-cell border elements before the cell fill.
    order=['lnL','lnR','lnT','lnB','lnTlToBr','lnBlToTr']
    idx=0
    while idx<len(tcpr) and etree.QName(tcpr[idx]).localname in order and order.index(etree.QName(tcpr[idx]).localname)<order.index('ln'+side):idx+=1
    tcpr.insert(idx,line)
    if color:
        fill=etree.SubElement(line,'{'+ns['a']+'}solidFill');etree.SubElement(fill,'{'+ns['a']+'}srgbClr',val=color)
    else:etree.SubElement(line,'{'+ns['a']+'}noFill')
with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
    for info,data in entries:
        if info.filename.startswith('ppt/slides/slide') and info.filename.endswith('.xml'):
            root=etree.fromstring(data)
            for table in root.findall('.//a:tbl',ns):
                rows=table.findall('a:tr',ns)
                for i,row in enumerate(rows):
                    for cell in row.findall('a:tc',ns):
                        pr=cell.find('a:tcPr',ns)
                        if pr is None:pr=etree.SubElement(cell,'{'+ns['a']+'}tcPr')
                        rule(pr,'L');rule(pr,'R')
                        rule(pr,'T','000000' if i==0 else None,19050 if i==0 else 0)
                        rule(pr,'B','000000' if i in [0,len(rows)-1] else None,19050 if i==len(rows)-1 else 12700)
            data=etree.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
        if '/charts/' in info.filename and info.filename.endswith('.xml'):
            root=etree.fromstring(data)
            for fmt in root.findall('.//c:valAx/c:numFmt',ns):fmt.set('sourceLinked','0')
            for axis in root.findall('.//c:valAx',ns):
                minimum=axis.find('c:scaling/c:min',ns)
                if minimum is not None and float(minimum.get('val'))<0:
                    for old in axis.findall('c:crossesAt',ns):axis.remove(old)
                    crosses=axis.find('c:crosses',ns)
                    if crosses is None:crosses=etree.SubElement(axis,'{'+ns['c']+'}crosses')
                    crosses.set('val','min')
                    for cat in root.findall('.//c:catAx',ns):
                        lbl=cat.find('c:tickLblPos',ns)
                        if lbl is None:lbl=etree.SubElement(cat,'{'+ns['c']+'}tickLblPos')
                        lbl.set('val','low')
            for i,series in enumerate(root.findall('.//c:lineChart/c:ser',ns)):
                marker=series.find('c:marker',ns)
                if marker is not None:
                    old=marker.find('c:spPr',ns)
                    if old is not None:marker.remove(old)
                    pr=etree.SubElement(marker,'{'+ns['c']+'}spPr')
                    fill=etree.SubElement(pr,'{'+ns['a']+'}solidFill')
                    etree.SubElement(fill,'{'+ns['a']+'}srgbClr',val=['999999','555555','111111'][i%3])
                    ln=etree.SubElement(pr,'{'+ns['a']+'}ln',w='9525')
                    fill=etree.SubElement(ln,'{'+ns['a']+'}solidFill')
                    etree.SubElement(fill,'{'+ns['a']+'}srgbClr',val=['999999','555555','111111'][i%3])
            bar=root.find('.//c:barChart',ns)
            if bar is not None and len(bar.findall('c:ser/c:cat//c:pt',ns))==3:
                for axis in root.findall('.//c:catAx',ns):
                    lbl=axis.find('c:tickLblPos',ns)
                    if lbl is None:lbl=etree.SubElement(axis,'{'+ns['c']+'}tickLblPos')
                    lbl.set('val','none')
            data=etree.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
        z.writestr(info,data)
tmp.replace(p)
