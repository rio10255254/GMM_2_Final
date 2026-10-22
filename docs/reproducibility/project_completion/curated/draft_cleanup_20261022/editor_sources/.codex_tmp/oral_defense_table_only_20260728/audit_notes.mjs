import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const sourcePath = "C:/Users/Rio/OneDrive/學業/碩班/論文/可用/江彥諠_口試簡報_附講稿.pptx";
const finalPath = "C:/Users/Rio/OneDrive/學業/碩班/論文/可用/江彥諠_口試簡報_附講稿_v17效能表格修正.pptx";
function parse(text) { return text.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line)); }
async function notes(file) {
  const presentation = await PresentationFile.importPptx(await FileBlob.load(file));
  const result = await presentation.inspect({ kind: "notes", maxChars: 300000 });
  return parse(result.ndjson).filter((record) => record.kind === "notes");
}
const before = await notes(sourcePath);
const after = await notes(finalPath);
const beforeMap = new Map(before.map((record) => [record.slide, record.text ?? ""]));
const afterMap = new Map(after.map((record) => [record.slide, record.text ?? ""]));
const changed = [];
for (let slide = 1; slide <= 63; slide += 1) {
  if ((beforeMap.get(slide) ?? "") !== (afterMap.get(slide) ?? "")) changed.push(slide);
}
const result = { sourceNoteSlides: before.length, finalNoteSlides: after.length, changedNoteSlides: changed };
await fs.writeFile("D:/GMM_2_Final/PSF_Fitting/.codex_tmp/oral_defense_table_only_20260728/notes-audit.json", `${JSON.stringify(result, null, 2)}\n`, "utf8");
console.log(JSON.stringify(result, null, 2));
if (changed.length || before.length !== after.length) process.exitCode = 1;
