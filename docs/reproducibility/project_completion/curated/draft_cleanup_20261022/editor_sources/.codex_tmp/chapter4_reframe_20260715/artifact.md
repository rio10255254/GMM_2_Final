# Chapter 4 reference template distillation

## Source and scope

- Source document: `Thesis_v3.1_MOSR_revised.docx`.
- Relevant source range: printed PDF pages 67–96 (Chapter 4).
- New artifact: a standalone, replacement-ready Chapter 4 draft. The source document is not overwritten.

## Page geometry

- A4 portrait (21.0 × 29.7 cm).
- Chapter-body margins: top/bottom 2.54 cm; left/right 3.17 cm.
- Header distance 1.5 cm; footer distance 1.75 cm.
- Header centered, short chapter label; page number centered in footer.

## Typography and paragraph behavior

- Chinese body: 標楷體; Latin text and numbers: Times New Roman.
- Body size: 12 pt; line spacing: 1.5; justified.
- Chapter title: centered, bold, 18 pt.
- Level-2 heading: left aligned, bold, 14 pt, 1.5 spacing, small space before/after.
- Level-3 heading: left aligned, bold, 12 pt, small space before/after.
- Captions: centered, 10 pt; figure placed before caption.
- Body paragraphs use a two-character first-line indent; list-like design points use a hanging layout without excessive bullets.

## Visual language

- Figures occupy the usable text width and are centered.
- Diagrams use a white background, restrained blue/teal/orange accents, thin arrows, and English labels.
- Each concept is a separate figure; no crowded multi-panel collage.
- Tables use a light blue header, thin gray grid lines, and compact 10–11 pt text.

## Structural pattern

- Open with chapter-level research question and verification logic.
- Move from optical prior → model architecture → data/supervision → training → evaluation protocol → claim boundaries.
- Each section explains purpose before implementation details.
- Include a final claim-to-evidence mapping table so Chapter 6 follows the same logic.

## Content guardrails derived from verified artifacts

- V42 uses a fixed mean of 25 normalized 101 × 101 PSFs in its physical preprocessor.
- The adaptive four-candidate PSF branch is present but bypassed in the formal V42 run because its effective scale is zero; it must not be described as active.
- V42 is initialized from a V41 checkpoint and fine-tunes selected output-side modules; it is not a full-network training-from-scratch claim.
- The model keeps raw low-frequency position, adds bounded high-frequency detail, applies orientation-aware boundary correction, and scales the final residual with an input-quality gate.
- Current evaluation sequences are represented in the target-domain training package; Chapter 6 results are target-domain functional validation, not unseen-sample generalization.
- Separate July 20×/50× fitted PSFs are optical validation assets and Wiener controls; they are not the same object as the checkpoint PSF stack.

