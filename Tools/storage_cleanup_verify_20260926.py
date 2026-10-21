import csv,json,pathlib,os,hashlib,datetime,shutil
ROOT=pathlib.Path(r"D:\GMM_2_Final")
LAB=ROOT/"Thesis_MOSR_Evidence/LabSystem_MOSR"
OLD=pathlib.Path(r"H:\GMM_2_Final_Archive\operation_logs\Storage_Migration_20260926")
OUT=ROOT/"docs/operations/storage_execution_20260926"
def ext(p):return pathlib.Path("\\\\?\\"+str(p))
def digest(p):
 h=hashlib.sha256()
 with ext(p).open("rb") as f:
  for block in iter(lambda:f.read(4194304),b""):h.update(block)
 return h.hexdigest()
execution=json.loads((OUT/"native_cleanup_execution.json").read_text(encoding="utf-8-sig"))
assert execution["finished"] and len(execution["completed"])==18
result={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"native_removal_finished":True,"batches":{},"removed_directories":19,"removed_logical_bytes":0,"measured_free_bytes_delta":execution["free_bytes_delta_total"],"d_free_bytes_after_removal":execution["free_bytes_after_remaining"]}
for name in ["R53","R56"]:
 plan=json.loads((OLD/(name+"_cleanup_plan.json")).read_text(encoding="utf-8"))
 archive=pathlib.Path(plan["archive"])
 rows=list(csv.DictReader((archive/"source_manifest.csv").open(encoding="utf-8")))
 expected={r["relative_path"]:r for r in rows}
 actual=set()
 for base,dirs,files in os.walk(ext(archive/"payload"),followlinks=False):
  for item in files:
   p=pathlib.Path(base)/item;actual.add(p.relative_to(ext(archive/"payload")).as_posix())
 assert actual==set(expected),"Archive file set mismatch"
 for index,r in enumerate(rows,1):
  p=archive/"payload"/r["relative_path"]
  assert ext(p).stat().st_size==int(r["size_bytes"]) and digest(p)==r["sha256"],r["relative_path"]
  if index%5000==0:print(name,"H SHA256",index,"/",len(rows),flush=True)
 deleted=[pathlib.Path(t["target"]).relative_to(LAB).as_posix()+"/" for t in plan["targets"]]
 for target in plan["targets"]:assert not pathlib.Path(target["target"]).exists(),target["target"]
 kept=list(csv.DictReader((OLD/(name+"_retained_manifest.csv")).open(encoding="utf-8")))
 for r in kept:
  p=pathlib.Path(plan["retained_copy_root"])/r["relative_path"]
  assert ext(p).stat().st_size==int(r["size_bytes"]) and digest(p)==r["sha256"],r["relative_path"]
 preserved=0
 for r in rows:
  rel=r["relative_path"]
  if any(rel.startswith(prefix) for prefix in deleted):continue
  p=LAB/rel
  assert p.exists(),rel
  if rel.startswith("Experiments/") and p.name in ["README.md","MANIFEST.md"]:continue
  assert ext(p).stat().st_size==int(r["size_bytes"]) and digest(p)==r["sha256"],rel
  preserved+=1
 result["batches"][name]={"full_archive_sha256":"PASS","archive":str(archive),"archive_files":len(rows),"archive_bytes":sum(int(r["size_bytes"]) for r in rows),"retained_sha256":"PASS","retained_files":len(kept),"preserved_original_files_rehashed":preserved,"removed_directories":len(plan["targets"]),"removed_logical_bytes":plan["target_bytes"]}
 result["removed_logical_bytes"]+=plan["target_bytes"]
 print(name,"POST CLEANUP PASS",len(rows),"archive files",preserved,"original files",flush=True)
result["verified_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
result["d_free_bytes_at_final_check"]=shutil.disk_usage("D:\\").free
(OUT/"post_cleanup_verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
