import fs from "node:fs/promises";

const inspectPath = "D:/GMM_2_Final/PSF_Fitting/.codex_tmp/oral_defense_with_notes_20260728/template-inspect/template-inspect.ndjson";
const outPath = "D:/GMM_2_Final/PSF_Fitting/.codex_tmp/oral_defense_table_only_20260728/template-frame-map.json";
const records = (await fs.readFile(inspectPath, "utf8"))
  .split(/\r?\n/)
  .filter(Boolean)
  .map((line) => JSON.parse(line));

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

const tables = records.filter((record) => record.kind === "table" && record.slide === 59 && record.name === "表格 1");
if (tables.length !== 1) throw new Error(`Expected one slide 59 performance table, found ${tables.length}`);
addEdit(59, {
  action: "rewrite",
  sourceElementId: tables[0].id,
  reason: "Replace only the multi-model performance table with the locked thesis-v17 values.",
});

const outputSlides = Array.from({ length: 63 }, (_, index) => {
  const slide = index + 1;
  return {
    outputSlide: slide,
    sourceSlide: slide,
    narrativeRole: slide === 59 ? "v17 performance table correction only" : "preserve-only same slide",
    reuseMode: "duplicate-slide",
    editTargets: edits.get(slide) ?? [],
  };
});

await fs.writeFile(outPath, `${JSON.stringify({ outputSlides, omittedSourceSlides: [] }, null, 2)}\n`, "utf8");
console.log(outPath);
