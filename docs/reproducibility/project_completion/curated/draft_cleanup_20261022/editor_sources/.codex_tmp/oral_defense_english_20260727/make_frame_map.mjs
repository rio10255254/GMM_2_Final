import fs from "node:fs/promises";
import path from "node:path";

const root = "D:/GMM_2_Final/PSF_Fitting/.codex_tmp/oral_defense_english_20260727";
const inspectPath = path.join(root, "template-inspect", "template-inspect.ndjson");
const outPath = path.join(root, "template-frame-map.json");

const lines = (await fs.readFile(inspectPath, "utf8"))
  .split(/\r?\n/)
  .filter(Boolean)
  .map((line) => JSON.parse(line));

const placeholderTargets = new Map();
for (const record of lines) {
  if (!record.slide || !record.id || !record.placeholder) continue;
  if (!placeholderTargets.has(record.slide)) placeholderTargets.set(record.slide, []);
  placeholderTargets.get(record.slide).push({
    action: "rewrite",
    sourceElementId: record.id,
    reason: "Preserve the populated inherited placeholder exactly.",
  });
}

const replacements = new Map([
  [26, ["im/03y9gj6t", "im/147q947e"]],
  [28, ["im/tovq5sna", "im/mp07yt4f", "im/nq98ry50", "im/ru54zuls"]],
  [29, ["im/wr6h4bup", "im/nmdgrmd8"]],
  [30, ["im/p0rux0zq", "im/ozitovi5"]],
  [32, ["im/wbap8zah", "im/xcjq14r2"]],
  [34, ["im/10vyh4j6"]],
  [36, ["im/ret8ru94"]],
  [37, ["im/76983i5s"]],
  [39, ["im/orq54ryp"]],
  [40, ["im/kjqtg3uh", "im/behcjyd0"]],
  [41, ["im/i5cbmho3"]],
  [45, ["im/vatoj6hs", "im/zy1cn2xw"]],
  [47, ["im/l0zqx0na", "im/0zq94vmp"]],
  [49, ["im/ydcnipsf"]],
  [51, ["im/b61sz25s"]],
]);

const outputSlides = [];
for (let slide = 1; slide <= 63; slide += 1) {
  const editTargets = [...(placeholderTargets.get(slide) ?? [])];
  for (const sourceElementId of replacements.get(slide) ?? []) {
    editTargets.push({
      action: "replace",
      sourceElementId,
      reason: "Replace the Chinese figure with its source-backed English redraw.",
    });
  }
  if (slide === 63) {
    editTargets.push({
      action: "replace",
      sourceElementId: "sh/83e9o7yx",
      reason: "Replace the Chinese derivation with an English rendering of the same equations.",
    });
  }
  outputSlides.push({
    outputSlide: slide,
    sourceSlide: slide,
    narrativeRole: replacements.has(slide) || slide === 63
      ? "English figure conversion"
      : "preserve-only same slide",
    reuseMode: "duplicate-slide",
    editTargets,
  });
}

await fs.writeFile(outPath, JSON.stringify({ outputSlides, omittedSourceSlides: [] }, null, 2));
console.log(outPath);
