import fs from "node:fs/promises";
import path from "node:path";

const root = "D:/GMM_2_Final/PSF_Fitting/.codex_tmp/oral_defense_with_notes_20260728";
const inspectPath = path.join(root, "template-inspect", "template-inspect.ndjson");
const outPath = path.join(root, "template-frame-map.json");

const records = (await fs.readFile(inspectPath, "utf8"))
  .split(/\r?\n/)
  .filter(Boolean)
  .map((line) => JSON.parse(line));

const replacementPositions = new Map([
  [26, [[554.94, 341.36], [880.20, 343.59]]],
  [28, [[88.00, 177.50], [66.86, 444.91], [623.37, 177.50], [647.95, 455.75]]],
  [29, [[855.33, 6.97], [829.42, 372.38]]],
  [30, [[75.54, 177.50], [75.54, 441.60]]],
  [32, [[64.30, 233.07], [664.55, 233.07]]],
  [34, [[562.10, 177.50]]],
  [36, [[562.10, 177.50]]],
  [37, [[534.12, 204.91]]],
  [39, [[640.00, 28.80]]],
  [40, [[160.67, 415.01], [702.00, 414.91]]],
  [41, [[424.67, 415.16]]],
  [45, [[656.77, 197.97], [48.00, 197.97]]],
  [47, [[656.77, 197.97], [48.00, 197.97]]],
  [49, [[766.67, 73.73]]],
  [51, [[52.02, 177.50]]],
]);

function findOne(predicate, label) {
  const matches = records.filter(predicate);
  if (matches.length !== 1) throw new Error(`${label}: expected 1 match, found ${matches.length}`);
  return matches[0];
}

function nearestImage(slide, x, y) {
  const candidates = records.filter((record) => record.kind === "image" && record.slide === slide);
  const ranked = candidates
    .map((record) => ({ record, distance: Math.hypot(record.bbox[0] - x, record.bbox[1] - y) }))
    .sort((a, b) => a.distance - b.distance);
  if (!ranked.length || ranked[0].distance > 1) {
    throw new Error(`Slide ${slide}: no image at (${x}, ${y}); nearest distance=${ranked[0]?.distance}`);
  }
  return ranked[0].record;
}

const edits = new Map();
function addEdit(slide, edit) {
  if (!edits.has(slide)) edits.set(slide, []);
  edits.get(slide).push(edit);
}

for (const record of records) {
  if (!record.slide || !record.id || !record.placeholder) continue;
  addEdit(record.slide, {
    action: "rewrite",
    sourceElementId: record.id,
    reason: "Preserve the populated inherited placeholder exactly.",
  });
}

for (const [slide, positions] of replacementPositions) {
  for (const [x, y] of positions) {
    const image = nearestImage(slide, x, y);
    addEdit(slide, {
      action: "replace",
      sourceElementId: image.id,
      reason: "Replace the Chinese figure with its verified English redraw while preserving the inherited image frame.",
    });
  }
}

const perfTable = findOne((r) => r.kind === "table" && r.slide === 59 && r.name === "表格 1", "slide 59 performance table");
const perfSubtitle = findOne((r) => r.kind === "textbox" && r.slide === 59 && r.name === "文字方塊 5", "slide 59 protocol label");
const perfSummary = findOne((r) => r.kind === "textbox" && r.slide === 59 && r.name === "文字方塊 3", "slide 59 summary");
addEdit(59, { action: "rewrite", sourceElementId: perfTable.id, reason: "Use the locked thesis-v17 same-protocol benchmark." });
addEdit(59, { action: "rewrite-and-reposition", sourceElementId: perfSubtitle.id, reason: "State the common full-frame benchmark condition." });
addEdit(59, { action: "rewrite", sourceElementId: perfSummary.id, reason: "Correct the model ranking and performance interpretation." });

const authorNotes = records.filter((r) => r.kind === "textbox" && r.textPreview === "需補進論文");
if (authorNotes.length !== 7) throw new Error(`Expected 7 obsolete authoring reminders, found ${authorNotes.length}`);
for (const note of authorNotes) {
  addEdit(note.slide, {
    action: "delete",
    sourceElementId: note.id,
    reason: "Remove the obsolete Chinese authoring reminder from the defense-ready deck.",
  });
}

const conclusion = findOne((r) => r.kind === "textbox" && r.slide === 60 && r.name === "文字方塊 12", "slide 60 performance conclusion");
addEdit(60, { action: "rewrite", sourceElementId: conclusion.id, reason: "Synchronize the repeated MOSR latency with thesis v17." });

const derivation = findOne((r) => r.kind === "textbox" && r.slide === 63 && r.name === "文字方塊 2", "slide 63 derivation");
addEdit(63, { action: "replace", sourceElementId: derivation.id, reason: "Replace the Chinese derivation with its verified English rendering." });

const outputSlides = Array.from({ length: 63 }, (_, index) => {
  const slide = index + 1;
  return {
    outputSlide: slide,
    sourceSlide: slide,
    narrativeRole: edits.has(slide) ? "focused English figure/data correction" : "preserve-only same slide",
    reuseMode: "duplicate-slide",
    editTargets: edits.get(slide) ?? [],
  };
});

await fs.writeFile(outPath, `${JSON.stringify({ outputSlides, omittedSourceSlides: [] }, null, 2)}\n`, "utf8");
console.log(outPath);
