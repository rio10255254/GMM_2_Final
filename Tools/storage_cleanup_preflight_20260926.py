import csv,json,pathlib,os,hashlib,datetime,psutil
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT=pathlib.Path(str(PROJECT_ROOT))
OLD=pathlib.Path(r"H:\GMM_2_Final_Archive\operation_logs\Storage_Migration_20260926")
OUT=ROOT/"docs/operations/storage_execution_20260926"
OUT.mkdir(exist_ok=True)
LAB=ROOT/"LabSystem_MOSR"
def ext(p):return pathlib.Path("\\\\?\\"+str(p))
def digest(p):
 h=hashlib.sha256()
 with ext(p).open("rb") as f:
  for chunk in iter(lambda:f.read(4194304),b""):h.update(chunk)
 return h.hexdigest()
live=[]
for p in psutil.process_iter(["pid","name","cmdline"]):
 try:
  if (p.info["name"] or "").lower().startswith("python"):
   live.append({"pid":p.pid,"cwd":p.cwd(),"cmdline":p.info["cmdline"]})
 except (psutil.NoSuchProcess,psutil.AccessDenied):pass
record={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"live_processes":live,"batches":{},"deletion_executed":False}
for short in ["R53","R56"]:
 plan=json.loads((OLD/(short+"_cleanup_plan.json")).read_text(encoding="utf-8"))
 archive=pathlib.Path(plan["archive"])
 verify=json.loads((archive/"verification.json").read_text(encoding="utf-8"))
 assert verify["verified"] and verify["source_unchanged"]
 rows=list(csv.DictReader((archive/"source_manifest.csv").open(encoding="utf-8")))
 expected={r["relative_path"]:r for r in rows}
 targets=[]
 for t in plan["targets"]:
  path=pathlib.Path(t["target"])
  assert path.is_dir() and path.resolve()==path and path.is_relative_to(LAB)
  assert not any(str(path).casefold() in (str(x["cwd"])+" "+" ".join(x["cmdline"] or [])).casefold() for x in live)
  prefix=path.relative_to(LAB).as_posix()+"/"
  selected={k:r for k,r in expected.items() if k.startswith(prefix)}
  assert len(selected)==t["files"] and sum(int(r["size_bytes"]) for r in selected.values())==t["bytes"]
  actual=set()
  for base,dirs,files in os.walk(ext(path),followlinks=False):
   for name in dirs:
    d=pathlib.Path(base)/name
    assert not (d.stat(follow_symlinks=False).st_file_attributes&0x400)
   for name in files:
    p=pathlib.Path(base)/name;rel=p.relative_to(ext(LAB)).as_posix()
    r=selected[rel];st=p.stat()
    assert st.st_size==int(r["size_bytes"]) and st.st_mtime_ns==int(r["mtime_ns"]),rel
    hp=ext(archive/"payload"/rel);hs=hp.stat()
    assert hs.st_size==int(r["size_bytes"]) and hs.st_mtime_ns==int(r["mtime_ns"]),rel
    actual.add(rel)
  assert actual==set(selected)
  targets.append({"target":str(path),"files":len(actual),"bytes":t["bytes"],"source_and_archive_metadata_unchanged":True})
 kept=list(csv.DictReader((OLD/(short+"_retained_manifest.csv")).open(encoding="utf-8")))
 for r in kept:
  p=pathlib.Path(plan["retained_copy_root"])/r["relative_path"]
  assert p.stat().st_size==int(r["size_bytes"]) and digest(p)==r["sha256"]
 record["batches"][short]={"full_archive_previously_SHA256_verified":True,"targets":targets,"retained_rehash":"PASS","retained_files":len(kept)}
 print(short,"preflight PASS",len(targets),"targets",len(kept),"retained files",flush=True)
(OUT/"cleanup_preflight_after_permission_switch.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
print("Live Python cwd:",json.dumps([{"pid":x["pid"],"cwd":x["cwd"]} for x in live],ensure_ascii=False),flush=True)
