"""Make the explicitly authored integer axis format independent of workbook cell formatting."""
import sys,zipfile
from pathlib import Path
from lxml import etree
p=Path(sys.argv[1]);ns={'c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
with zipfile.ZipFile(p) as z: entries=[(i,z.read(i.filename)) for i in z.infolist()]
temp=p.with_name(p.stem+'_axis.pptx')
with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED) as out:
 for info,data in entries:
  if '/charts/' in info.filename and info.filename.endswith('.xml'):
   root=etree.fromstring(data)
   for fmt in root.findall('.//c:valAx/c:numFmt',ns):fmt.set('sourceLinked','0')
   data=etree.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
  out.writestr(info,data)
temp.replace(p)
