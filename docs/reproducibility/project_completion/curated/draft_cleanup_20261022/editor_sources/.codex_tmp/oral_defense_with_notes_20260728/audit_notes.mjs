import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const root = "D:/GMM_2_Final/PSF_Fitting/.codex_tmp/oral_defense_with_notes_20260728";
const sourcePath = "C:/Users/Rio/OneDrive/學業/碩班/論文/可用/江彥諠_口試簡報_附講稿.pptx";
const finalPath = "C:/Users/Rio/OneDrive/學業/碩班/論文/可用/江彥諠_口試簡報_附講稿_英文圖表_v17效能修正.pptx";

function parseNdjson(text) {
  return text.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
}

async function inspectNotes(filePath) {
  const presentation = await PresentationFile.importPptx(await FileBlob.load(filePath));
  const inspected = await presentation.inspect({ kind: "notes", maxChars: 300000 });
  return parseNdjson(inspected.ndjson).filter((record) => record.kind === "notes");
}

const source = await inspectNotes(sourcePath);
const final = await inspectNotes(finalPath);
const sourceBySlide = new Map(source.map((record) => [record.slide, record.text ?? ""]));
const finalBySlide = new Map(final.map((record) => [record.slide, record.text ?? ""]));
const mismatches = [];

for (let slide = 1; slide <= 63; slide += 1) {
  const before = sourceBySlide.get(slide) ?? "";
  const after = finalBySlide.get(slide) ?? "";
  if (slide === 59 || slide === 60) {
    if (!after.startsWith(before)) mismatches.push({ slide, issue: "original notes are not preserved as a prefix" });
    if (!after.includes("[Sources]") || !after.includes("[/Sources]")) mismatches.push({ slide, issue: "source block missing" });
  } else if (before !== after) {
    mismatches.push({ slide, issue: "speaker notes changed", beforeChars: before.length, afterChars: after.length });
  }
}

const result = {
  sourceNoteSlides: source.length,
  finalNoteSlides: final.length,
  mismatchCount: mismatches.length,
  mismatches,
  slide59OriginalChars: (sourceBySlide.get(59) ?? "").length,
  slide59FinalChars: (finalBySlide.get(59) ?? "").length,
  slide60OriginalChars: (sourceBySlide.get(60) ?? "").length,
  slide60FinalChars: (finalBySlide.get(60) ?? "").length,
};
await fs.writeFile(path.join(root, "notes-audit.json"), `${JSON.stringify(result, null, 2)}\n`, "utf8");
console.log(JSON.stringify(result, null, 2));
if (mismatches.length) process.exitCode = 1;
