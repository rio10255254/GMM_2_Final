"""Normalize only the two new report files to Traditional Chinese on Windows."""
import ctypes
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
f=ctypes.windll.kernel32.LCMapStringEx
f.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_wchar_p,ctypes.c_int,ctypes.c_wchar_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_longlong]
for name in ('R147_INTERNAL_AUDIT.md','R147_OPTIMIZATION_PLAN.md'):
 p=ROOT/'reports'/name;s=p.read_text(encoding='utf-8');n=f('zh-CN',0x04000000,s,len(s),None,0,None,None,0);b=ctypes.create_unicode_buffer(n);result=f('zh-CN',0x04000000,s,len(s),b,n,None,None,0);assert result>0;t=b.value
 for a,z in {'網絡':'網路','數組':'陣列','中繼資料':'中繼資料','噪聲':'雜訊','圖像':'影像','數據':'資料','模型測量':'模型量測'}.items():t=t.replace(a,z)
 p.write_text(t,encoding='utf-8')
print('Traditional Chinese reports saved')
