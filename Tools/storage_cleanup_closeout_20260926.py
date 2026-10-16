
import json,pathlib,datetime,shutil,hashlib,re,psutil
ROOT=pathlib.Path(r"D:\GMM_2_Final")
LAB=ROOT/"Thesis_MOSR_Evidence/LabSystem_MOSR"
OLD=pathlib.Path(r"H:\GMM_2_Final_Archive\operation_logs\Storage_Migration_20260926")
OUT=ROOT/"docs/operations/storage_execution_20260926"
DOCS=ROOT/"docs/operations"
result=json.loads((OUT/"post_cleanup_verification.json").read_text(encoding="utf-8"))
execution=json.loads((OUT/"native_cleanup_execution.json").read_text(encoding="utf-8-sig"))
assert result["removed_directories"]==19 and execution["finished"]
measured=result["measured_free_bytes_delta"]/2**30
free=result["d_free_bytes_at_final_check"]/2**30
logical=result["removed_logical_bytes"]/2**30
plans={}
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
for short,identifier in [("R53","R53_RealisticDatasetCalibration"),("R56","R56_LabelCoreRepairTraining")]:
 plan=json.loads((OLD/(short+"_cleanup_plan.json")).read_text(encoding="utf-8"));plans[short]=plan
 v=result["batches"][short];assert v["full_archive_sha256"]=="PASS" and v["retained_sha256"]=="PASS"
 for item in plan["targets"]:assert not pathlib.Path(item["target"]).exists()
 exp=LAB/"Experiments"/identifier
 note=f"""## 2026-09-26 最新狀態：封存與 D 槽清理完成

{v['removed_directories']} 個已核對的歷史目錄已透過使用者正式核准，以原生 PowerShell 移除。
H 槽完整歷史 {v['archive_files']:,} 檔在移除後再次逐檔核對，全部一致。
D 槽保留內容 {v['retained_files']} 檔及 {v['preserved_original_files_rehashed']} 個原成果／程式／驗證檔再次核對通過。
正式訓練成果及原報告留在原位置；研究判決沒有改變。
兩批合計的當下 D 可用空間增加約 {measured:.4f} GiB，清理完成時約 {free:.3f} GiB。
此為兩批合計量測，沒有單獨歸算每輪回收量。其他訓練持續執行，檔案標示容量與真正占用不同。

恢復時由 H 的 payload 按 LabSystem 相對路徑複製回原位置，再按 source_manifest.csv 核對。
要重做歷史訓練，需先恢復資料，或在啟動程式明確指定封存資料位置。
完整副本：{v['archive']}
本次實際移除與核對：D:/GMM_2_Final/docs/operations/storage_execution_20260926/native_cleanup_execution.json、post_cleanup_verification.json。
"""
 for name in [short+"_STORAGE_CLOSEOUT_20260926.md"]:
  p=DOCS/name;s=p.read_text(encoding="utf-8")
  first,rest=s.split("\n",1)
  p.write_text(first+"\n\n"+note+"\n## 先前封存與拒絕紀錄（歷史狀態）\n"+rest,encoding="utf-8")
 pointer=exp/("ARCHIVE_POINTER_"+short+"_20260926.md")
 pointer.write_text("# "+short+" 完整歷史封存入口\n\n"+note,encoding="utf-8")
 for name in ["README.md","MANIFEST.md"]:
  p=exp/name;p.write_text(p.read_text(encoding="utf-8")+"\n\n"+note,encoding="utf-8")
 manual=DOCS/(short+"_MANUAL_CLEANUP_PATHS_20260926.txt")
 manual.write_text("2026-09-26：以下目錄已由正式核准流程清理完成，不需再手動移除。\n這是歷史清理範圍，不是可執行程式。\n\n"+"\n".join(x["target"] for x in plan["targets"])+"\n",encoding="utf-8")
 archive=pathlib.Path(plan["archive"])
 closing={"utc":now,"cleanup_complete":True,"removed_directories":v["removed_directories"],"removed_logical_bytes":v["removed_logical_bytes"],"archive_full_sha256_after_removal":"PASS","retained_sha256_after_removal":"PASS","joint_measured_D_delta_bytes":result["measured_free_bytes_delta"],"measurement_scope":"joint R53+R56; do not sum per-round entries","evidence":str(OUT/"post_cleanup_verification.json")}
 (archive/"cleanup_complete_20260926.json").write_text(json.dumps(closing,ensure_ascii=False,indent=2),encoding="utf-8")
 ctx=archive/"post_cleanup_context_20260926";ctx.mkdir(exist_ok=True)
 for metadata_name in ["ARCHIVE_RECORD.md","ARCHIVE_CLOSEOUT.md"]:
  old_metadata=archive/metadata_name
  if old_metadata.exists():shutil.copy2(old_metadata,ctx/("previous_"+metadata_name))
  shutil.copy2(DOCS/(short+"_STORAGE_CLOSEOUT_20260926.md"),old_metadata)
 for p in [pointer,DOCS/(short+"_STORAGE_CLOSEOUT_20260926.md"),manual,OUT/"native_cleanup_execution.json",OUT/"post_cleanup_verification.json"]:
  shutil.copy2(p,ctx/p.name)
 ctxmanifest=[{"name":p.name,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(ctx.iterdir()) if p.is_file() and p.name!="context_manifest.json"]
 (ctx/"context_manifest.json").write_text(json.dumps(ctxmanifest,ensure_ascii=False,indent=2),encoding="utf-8")
registry=DOCS/"PROJECT_STORAGE_REGISTRY.json"
j=json.loads(registry.read_text(encoding="utf-8"))
shutil.copy2(registry,OUT/"registry_before_cleanup_closeout.json")
for e in j["entries"]:
 for short in ["R53","R56"]:
  if e.get("id")==("lab_"+short.lower()+"_archive_20260926"):
   e["state"]="full_H_snapshot_verified_D_compact_core_cleanup_complete"
   e["blocked_by"]=[]
   e["d_cleanup_reclaimed_bytes"]=None
   e["d_removed_logical_bytes"]=result["batches"][short]["removed_logical_bytes"]
   e["joint_cleanup_measurement_record"]=str(OUT/"post_cleanup_verification.json")
   e["cleanup_complete"]=True
   e["post_cleanup_full_archive_hash_check"]="PASS"
   e["keep"]="Canonical experiment, full formal run, validation and hash-verified metadata/representative images remain on D. All planned large history targets removed with formal user approval. Full H snapshot rehashed after removal."
j["updated_at"]="2026-09-26"
j["snapshot"]["d_free_gib"]=free
j["snapshot"]["archive_free_gib"]=shutil.disk_usage("H:\\").free/2**30
j["snapshot"]["note"]+=" R53/R56 cleanup completed with explicit approvals on 2026-09-26; joint D free-space delta "+f"{measured:.4f}"+" GiB, all full archives and kept originals reverified. Current live jobs may change free space."
assert len({e["id"] for e in j["entries"]})==len(j["entries"])
registry.write_text(json.dumps(j,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
summary=f"2026-09-26 正式核准清理完成：R53/R56 共 19 個指定歷史目錄已移除；移除後 H 槽完整封存 79,160 檔及 D 保留成果再次逐檔核對通過。兩批當下 D 可用空間增加 {measured:.4f} GiB，清理後约 {free:.3f} GiB。人工核准與正式 require_escalated 流程成功，沒有關閉安全保護，原始完整存取模式不會提出此類核准請求。現行訓練與 R148/R148v2 來源未操作；原正式模型、報告及驗證成果保留。[完整執行紀錄](docs/operations/PROJECT_STORAGE_MIGRATION_EXECUTION_20260926.md)"
p=ROOT/"PROJECT_STATE.md";s=p.read_text(encoding="utf-8")
s=s.replace("### Storage / Historical Archive\n","### Storage / Historical Archive\n"+summary.replace("约","約")+"\n",1)
p.write_text(s,encoding="utf-8")
p=DOCS/"PROJECT_STORAGE_MIGRATION_EXECUTION_20260926.md";s=p.read_text(encoding="utf-8")
s=re.sub(r"(?m)^狀態：.*$","狀態：R53/R56 封存、正式核准清理與移除後完整核對完成；其餘規劃仍待後續分批執行。",s,count=1)
s+=f"""\n\n## 2026-09-26 正式核准後的完整清理

使用者切換 Ask for approval 後，新一輪已具備正式核准途徑。普通隔離環境的前置核對未完成，正式請求一般 Windows 環境核對後通過；原生 R53 移除命令亦在正式核准後成功。其餘 18 個目錄經一次明確核准逐項移除。沒有換用 Python、其他 shell 或移除安全保護來繞過拒絕。

合計移除 19 個精確目錄，檔案標示容量 {logical:.4f} GiB。D 槽當下可用空間增加 {measured:.4f} GiB；移除後完整封存共 79,160 檔、兩批 D 保留內容與原正式成果逐檔重核全部通過。當時 D 可用約 {free:.3f} GiB。當下容量差含活動程序寫入影響，不將檔案標示容量當成實際回收量。

完整執行與核對：
- storage_execution_20260926/native_cleanup_execution.json
- storage_execution_20260926/post_cleanup_verification.json

R53、R56 的資料已按封存政策移往 H；D 保留完整正式 run、報告、程式、資料清單、代表影像與恢復入口。Git 有效歷史及其他待清理區域未操作。本紀錄只表示首兩批及核准問題已完成，不表示三區總規劃全部完成。
"""
p.write_text(s,encoding="utf-8")
p=DOCS/"LABSYSTEM_ARCHIVE_QUEUE.md";s=p.read_text(encoding="utf-8")
s=s.replace("## 目前狀態\n","## 目前狀態\n\nR53/R56 已於 2026-09-26 透過正式核准完成 D 清理；19 個指定目錄已移除，H 完整封存與 D 保留內容重核通過。兩批當下實測增加 "+f"{measured:.4f}"+" GiB。下方未清理描述為先前歷史狀態，最新以各輪收尾紀錄為準。\n",1)
for short in ["R53","R56"]:
 s=re.sub(r"(?m)^\| "+short+r" \|.*$",f"| {short} | 已完成但未採用的歷史實驗 | 完整 H 快照 {result['batches'][short]['archive_bytes']/2**30:.4f} GiB | 封存及 D 精簡完成 | 正式成果、程式、原正式 run、驗證與代表證據保留 | 2026-09-26：移除 {result['batches'][short]['removed_directories']} 目錄，移除後完整核對 PASS；回收量列入兩批合計 |",s,count=1)
p.write_text(s,encoding="utf-8")
p=DOCS/"PROJECT_ARCHIVE_INDEX.md";s=p.read_text(encoding="utf-8")
s=s.replace("## 2026-09-26 Lab R56 完整封存（D 槽精簡待執行）","## 2026-09-26 Lab R56 完整封存（D 槽精簡已完成）",1)
s=s.replace("## 2026-09-26 Lab R53 完整封存（D 槽精簡待執行）","## 2026-09-26 Lab R53 完整封存（D 槽精簡已完成）",1)
anchor="## 2026-09-26 Lab R56"
s=s.replace(anchor,"## 2026-09-26 R53/R56 正式核准清理收尾\n\n19 個指定歷史目錄已移除。兩份完整 H 封存共 79,160 檔與 D 保留內容在移除後重核通過；D 當下可用空間增加 "+f"{measured:.4f}"+" GiB。下方未清理說明為先前狀態，最新以各輪收尾記錄為準。[實際執行](PROJECT_STORAGE_MIGRATION_EXECUTION_20260926.md)\n\n"+anchor,1)
p.write_text(s,encoding="utf-8")
for filename in ["STORAGE_APPROVAL_ROUTING_FIX_20260926.md","STORAGE_TOOL_POLICY_DIAGNOSIS_20260926.md"]:
 p=DOCS/filename;s=p.read_text(encoding="utf-8")
 s+="\n\n## 最終實際解決結果\n\n新一輪已切換可人工核准模式；正式 require_escalated 請求獲使用者核准後，與先前相同的 R53 原生移除命令成功。剩餘 18 個目錄亦按正式核准移除。這證明先前拒絕不是任何情況下都不可刪除的絕對禁止；可以透過正式核准途徑完成。沒有停用保護或新增寬泛刪除免審规则。此前對具體內部分支的推斷仍不作程式內部已證明的主張。\n\nR53/R56 本批封存與精簡完成。完整移除後核對記錄見 storage_execution_20260926/post_cleanup_verification.json。\n"
 p.write_text(s.replace("规则","規則"),encoding="utf-8")
closing={"utc":now,"approval_problem_resolved_for_verified_cleanup":True,"formal_approval_used":True,"same_native_R53_command_succeeded":True,"builtin_safety_disabled":False,"removed_directories":19,"post_cleanup_verification":"PASS","measured_D_free_delta_gib":measured,"D_free_gib_at_final_check":free}
(OUT/"permission_and_cleanup_resolved.json").write_text(json.dumps(closing,ensure_ascii=False,indent=2),encoding="utf-8")
(OLD/"permission_and_cleanup_resolved_20260926.json").write_text(json.dumps(closing,ensure_ascii=False,indent=2),encoding="utf-8")
shutil.copy2(OUT/"post_cleanup_verification.json",OLD/"post_cleanup_verification_20260926.json")
shutil.copy2(OUT/"native_cleanup_execution.json",OLD/"native_cleanup_execution_20260926.json")
for p in [ROOT/"PROJECT_STATE.md",DOCS/"PROJECT_STORAGE_MIGRATION_EXECUTION_20260926.md",DOCS/"PROJECT_STORAGE_REGISTRY.json",DOCS/"STORAGE_APPROVAL_ROUTING_FIX_20260926.md"]:
 shutil.copy2(p,OLD/("final_cleanup_"+p.name))
print(json.dumps(closing,ensure_ascii=False,indent=2))

