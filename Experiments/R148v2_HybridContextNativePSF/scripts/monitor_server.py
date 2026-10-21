"""Local read-only dashboard for R148v2 training and real validation."""
from __future__ import annotations
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import ctypes,hashlib,json,os,shutil
ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs/formal_8192';LOGS=ROOT/'runs/launcher_logs';PORT=8149
HASH_CACHE={}
def load(path):
 try:return json.loads(Path(path).read_text(encoding='utf-8-sig'))
 except:return None
def alive(pid):
 if not pid:return False
 handle=ctypes.windll.kernel32.OpenProcess(0x1000,False,int(pid))
 if handle:ctypes.windll.kernel32.CloseHandle(handle);return True
 return False
def file_hash(path):
 p=Path(path)
 if not p.is_file():return None
 key=(str(p),p.stat().st_mtime_ns,p.stat().st_size)
 if key in HASH_CACHE:return HASH_CACHE[key]
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 HASH_CACHE.clear();HASH_CACHE[key]=h.hexdigest();return HASH_CACHE[key]
def tail_json(path,n=40):
 p=Path(path)
 if not p.is_file():return []
 lines=p.read_text(encoding='utf-8').splitlines()[-n:];out=[]
 for line in lines:
  try:out.append(json.loads(line))
  except:pass
 return out
def tail_text(path,n=20):
 p=Path(path)
 if not p.is_file():return []
 return p.read_text(encoding='utf-8',errors='replace').splitlines()[-n:]
def window_rate(rows):
 if len(rows)<2:return 0
 values=[]
 for left,right in zip(rows,rows[1:]):
  try:dt=(datetime.fromisoformat(right['utc'])-datetime.fromisoformat(left['utc'])).total_seconds()
  except:continue
  if 0<dt<10:values.append(dt)
 return 1/(sum(values)/len(values)) if values else 0
def snapshot():
 marker=load(LOGS/'active_formal_run.json') or {};latest=load(RUN/'latest.json') or {};status=load(RUN/'status.json') or {};history=tail_json(RUN/'updates.jsonl',600);rows=history[-60:];last=rows[-1] if rows else {};pid=int(marker.get('process_id') or 0);step=int(last.get('step') or status.get('step') or 0);total=8192
 dev_initial=load(RUN/'dev_initial.json');dev_files=sorted(p for p in RUN.glob('dev_*.json') if p.name!='dev_initial.json');dev=[]
 if dev_initial:dev.append({'name':'initial','step':0,'loss':dev_initial.get('mean_loss')})
 for p in dev_files:
  x=load(p)
  if x:dev.append({'name':p.name,'step':int(p.stem.split('_')[-1]),'loss':x.get('mean_loss')})
 started=marker.get('started_utc');elapsed=0
 if started:
  try:elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(started)).total_seconds()
  except:pass
 overall_rate=step/elapsed if elapsed>0 else 0;recent_rate=window_rate(history[-101:]);previous_rate=window_rate(history[-201:-100]);remaining=(total-step)/recent_rate if recent_rate>0 else None;speedup=(recent_rate/previous_rate-1)*100 if previous_rate>0 else None
 checkpoint_ok=False
 if latest.get('path') and latest.get('sha256'):checkpoint_ok=file_hash(latest['path'])==latest['sha256']
 validation_marker=load(LOGS/'active_real_validation.json') or {};validation_status=load(ROOT/'runs/real_validation_status.json') or {};reconstruction=load(ROOT/'results/reconstruction_status.json') or {};validation_pid=int(validation_marker.get('ProcessId') or 0);validation_completed=int(reconstruction.get('completed') or (930 if validation_status.get('state')=='complete' else 0));validation_elapsed=float(reconstruction.get('elapsed_seconds') or 0);validation_rate=validation_completed/validation_elapsed if validation_elapsed>0 else 0;validation_remaining=(930-validation_completed)/validation_rate if validation_rate>0 and validation_completed<930 else 0 if validation_completed>=930 else None
 disks={d:round(shutil.disk_usage(d+':\\').free/1024**3,2) for d in ('D','H')}
 return {'now':datetime.now().astimezone().isoformat(timespec='seconds'),'model':marker.get('model'),'status':marker.get('status'),'pid':pid,'alive':alive(pid),'step':step,'total':total,'percent':100*step/total,'epoch':max(0,(step-1)//512),'elapsed_seconds':elapsed,'rate':recent_rate,'recent_rate':recent_rate,'previous_rate':previous_rate,'overall_rate':overall_rate,'speedup_percent':speedup,'remaining_seconds':remaining,'last':last,'recent':rows[-20:],'dev':dev,'latest_checkpoint':latest,'checkpoint_ok':checkpoint_ok,'stdout':tail_text(LOGS/'formal_stdout.log',12),'stderr':tail_text(LOGS/'formal_stderr.log',20),'stderr_bytes':(LOGS/'formal_stderr.log').stat().st_size if (LOGS/'formal_stderr.log').exists() else 0,'disk_free_gib':disks,'data_manifest':marker.get('data_manifest_sha256'),'geometry_manifest':marker.get('geometry_manifest_sha256'),'validation':{'pid':validation_pid,'alive':alive(validation_pid),'state':validation_status.get('state') or 'not_started','phase':validation_status.get('phase') or '—','completed':validation_completed,'total':930,'percent':100*validation_completed/930,'elapsed_seconds':validation_elapsed,'rate':validation_rate,'remaining_seconds':validation_remaining,'stdout':tail_text(LOGS/'real_validation_stdout.log',12),'stderr':tail_text(LOGS/'real_validation_stderr.log',20),'stderr_bytes':(LOGS/'real_validation_stderr.log').stat().st_size if (LOGS/'real_validation_stderr.log').exists() else 0}}
HTML=r'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>R148v2 訓練監控</title><style>
:root{color-scheme:dark;--bg:#0a0f18;--panel:#111a27;--line:#223149;--cyan:#55d8ff;--green:#50e3a4;--yellow:#ffd166;--red:#ff6b78;--text:#e7eef8;--muted:#93a4ba}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 20% 0,#13243d 0,#0a0f18 42%);color:var(--text);font:14px/1.45 system-ui,"Microsoft JhengHei",sans-serif}.wrap{max-width:1500px;margin:auto;padding:22px}header{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:18px}h1{margin:0;font-size:25px}#clock,.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card{background:rgba(17,26,39,.94);border:1px solid var(--line);border-radius:12px;padding:15px;box-shadow:0 12px 30px #0004}.label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em}.value{font-size:24px;font-weight:700;margin-top:4px}.good{color:var(--green)}.warn{color:var(--yellow)}.bad{color:var(--red)}.wide{grid-column:span 2}.full{grid-column:1/-1}.bar{height:13px;border-radius:8px;background:#07101d;overflow:hidden;margin:12px 0}.bar>div{height:100%;background:linear-gradient(90deg,#34a8ff,#50e3a4);transition:width .4s}.validation>div{background:linear-gradient(90deg,#9b5cff,#55d8ff)}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{text-align:right;padding:7px 8px;border-bottom:1px solid #1c2a3e}th:first-child,td:first-child{text-align:left}th{color:var(--muted);font-weight:500}.logs{display:grid;grid-template-columns:1fr 1fr;gap:12px}pre{white-space:pre-wrap;max-height:260px;overflow:auto;margin:8px 0 0;color:#c8d5e6;font:12px/1.45 Consolas,monospace}.spark{height:120px;width:100%;display:block}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;background:var(--red)}.dot.on{background:var(--green);box-shadow:0 0 12px var(--green)}@media(max-width:900px){.grid{grid-template-columns:1fr 1fr}.wide{grid-column:span 2}.logs{grid-template-columns:1fr}} </style></head><body><div class="wrap"><header><div><h1>R148v2 訓練與實拍驗證監控</h1><div class="muted" id="model"></div></div><div id="clock"></div></header><main class="grid">
<section class="card"><div class="label">程序</div><div class="value" id="alive"></div><div id="pid" class="muted"></div></section><section class="card"><div class="label">進度</div><div class="value" id="progress"></div><div id="epoch" class="muted"></div></section><section class="card"><div class="label">速度</div><div class="value" id="rate"></div><div id="eta" class="muted"></div></section><section class="card"><div class="label">保存點</div><div class="value" id="checkpoint"></div><div id="hash" class="muted"></div></section>
<section class="card full"><div class="bar"><div id="bar"></div></div><div class="muted" id="time"></div></section>
<section class="card"><div class="label">實拍驗證程序</div><div class="value" id="valive"></div><div id="vpid" class="muted"></div></section><section class="card"><div class="label">驗證階段</div><div class="value" id="vphase"></div><div id="vstate" class="muted"></div></section><section class="card"><div class="label">實拍進度</div><div class="value" id="vprogress"></div><div id="vrate" class="muted"></div></section><section class="card"><div class="label">預估剩餘</div><div class="value" id="veta"></div><div class="muted">930 張後接 8,370 圓量測與稽核</div></section>
<section class="card full"><div class="bar validation"><div id="vbar"></div></div></section>
<section class="card wide"><div class="label">最新訓練數值</div><table><tbody id="metrics"></tbody></table></section><section class="card wide"><div class="label">開發資料</div><canvas id="chart" class="spark"></canvas><table><tbody id="dev"></tbody></table></section>
<section class="card full"><div class="label">最近更新</div><table><thead><tr><th>Step</th><th>Loss</th><th>Image</th><th>Gradient</th><th>Pair</th><th>Boundary</th><th>Observation</th><th>Category</th></tr></thead><tbody id="recent"></tbody></table></section>
<section class="card"><div class="label">磁碟剩餘</div><div class="value" id="disk"></div></section><section class="card"><div class="label">錯誤輸出</div><div class="value" id="errors"></div></section><section class="card wide"><div class="label">資料身分</div><pre id="identity"></pre></section>
<section class="card full logs"><div><div class="label">標準輸出</div><pre id="stdout"></pre></div><div><div class="label">錯誤輸出內容</div><pre id="stderr"></pre></div></section></main></div><script>
const f=(v,n=5)=>v==null?'—':Number(v).toFixed(n),dur=s=>{if(s==null)return'—';let h=Math.floor(s/3600),m=Math.floor(s%3600/60),q=Math.floor(s%60);return `${h}h ${m}m ${q}s`};function draw(dev){const c=document.querySelector('#chart'),dpr=devicePixelRatio||1,w=c.clientWidth,h=c.clientHeight;c.width=w*dpr;c.height=h*dpr;let x=c.getContext('2d');x.scale(dpr,dpr);x.clearRect(0,0,w,h);if(dev.length<2)return;let ys=dev.map(z=>z.loss),mn=Math.min(...ys),mx=Math.max(...ys),pad=14;x.strokeStyle='#55d8ff';x.lineWidth=2;x.beginPath();dev.forEach((z,i)=>{let px=pad+(w-2*pad)*i/(dev.length-1),py=pad+(h-2*pad)*(mx-z.loss)/(mx-mn||1);i?x.lineTo(px,py):x.moveTo(px,py)});x.stroke();x.fillStyle='#50e3a4';dev.forEach((z,i)=>{let px=pad+(w-2*pad)*i/(dev.length-1),py=pad+(h-2*pad)*(mx-z.loss)/(mx-mn||1);x.beginPath();x.arc(px,py,3,0,7);x.fill()})}
async function refresh(){try{let r=await fetch('/api/status',{cache:'no-store'}),s=await r.json(),v=s.validation||{};clock.textContent=`頁面更新 ${s.now}`;model.textContent=s.model||'';alive.innerHTML=`<span class="dot ${s.alive?'on':''}"></span>${s.alive?'運行中':'已完成'}`;alive.className=`value ${s.alive?'good':'good'}`;pid.textContent=`PID ${s.pid} · ${s.status}`;progress.textContent=`${s.step.toLocaleString()} / ${s.total.toLocaleString()}`;epoch.textContent=`${f(s.percent,2)}% · Epoch ${s.epoch}/15`;bar.style.width=`${s.percent}%`;rate.textContent=`${f(s.recent_rate,3)} update/s`;eta.textContent=`前100次 ${f(s.previous_rate,3)} · 全程 ${f(s.overall_rate,3)} · ${s.speedup_percent==null?'':`近期 ${s.speedup_percent>=0?'+':''}${f(s.speedup_percent,1)}%`}`;checkpoint.textContent=`Step ${s.latest_checkpoint.step||0}`;checkpoint.className=`value ${s.checkpoint_ok?'good':'warn'}`;hash.textContent=`SHA-256 ${s.checkpoint_ok?'通過':'尚未通過'}`;time.textContent=`已耗時 ${dur(s.elapsed_seconds)} · 依最近速度預估剩餘 ${dur(s.remaining_seconds)}`;valive.innerHTML=`<span class="dot ${v.alive?'on':''}"></span>${v.alive?'運行中':v.state==='complete'?'已完成':'未運行'}`;valive.className=`value ${v.alive||v.state==='complete'?'good':'warn'}`;vpid.textContent=`PID ${v.pid||'—'}`;vphase.textContent=v.phase||'—';vstate.textContent=v.state||'—';vprogress.textContent=`${Number(v.completed||0).toLocaleString()} / ${Number(v.total||930).toLocaleString()}`;vrate.textContent=`${f(v.rate,3)} image/s · ${f(v.percent,2)}%`;veta.textContent=dur(v.remaining_seconds);vbar.style.width=`${v.percent||0}%`;let l=s.last||{};metrics.innerHTML=[['Loss',l.loss],['Image',l.image],['Gradient',l.gradient],['Pair',l.pair_output],['Boundary',l.boundary],['Observation',l.observation],['Learning rate',l.learning_rate],['Category',l.category],['Parent',l.parent_id]].map(([a,b])=>`<tr><td>${a}</td><td>${typeof b==='number'?f(b,6):(b??'—')}</td></tr>`).join('');dev.innerHTML=s.dev.map(z=>`<tr><td>${z.name}</td><td>step ${z.step}</td><td>${f(z.loss,6)}</td></tr>`).join('');draw(s.dev);recent.innerHTML=s.recent.slice(-12).reverse().map(z=>`<tr><td>${z.step}</td><td>${f(z.loss)}</td><td>${f(z.image,4)}</td><td>${f(z.gradient,4)}</td><td>${f(z.pair_output,4)}</td><td>${f(z.boundary,4)}</td><td>${f(z.observation,4)}</td><td>${z.category}</td></tr>`).join('');disk.textContent=`D ${s.disk_free_gib.D} GiB · H ${s.disk_free_gib.H} GiB`;errors.textContent=`訓練 ${s.stderr_bytes} · 驗證 ${v.stderr_bytes||0} bytes`;errors.className=`value ${s.stderr_bytes||v.stderr_bytes?'warn':'good'}`;identity.textContent=`Data ${s.data_manifest}\nGeometry ${s.geometry_manifest}`;stdout.textContent=(v.stdout&&v.stdout.length?v.stdout:s.stdout).join('\n');stderr.textContent=v.stderr&&v.stderr.length?v.stderr.join('\n'):s.stderr.length?s.stderr.join('\n'):'無';}catch(e){alive.textContent='監控頁連線失敗';alive.className='value bad'}}refresh();setInterval(refresh,5000);</script></body></html>'''
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path.startswith('/api/status'):data=json.dumps(snapshot(),ensure_ascii=False).encode();ctype='application/json; charset=utf-8'
  else:data=HTML.encode();ctype='text/html; charset=utf-8'
  self.send_response(200);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
 def log_message(self,*args):pass
if __name__=='__main__':
 server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler);print(f'R148v2 monitor http://127.0.0.1:{PORT}',flush=True);server.serve_forever()
