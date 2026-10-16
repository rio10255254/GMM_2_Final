from pathlib import Path

from docx import Document


DOCX = Path(
    r"D:\GMM_2_Final\Experiments\R63_CausalBoundaryMotionAblation\results"
    r"\thesis_v8_language_cleanup\thesis_v8_language_working.docx"
)


def main() -> None:
    document = Document(DOCX)
    replacements = {
        "並依資料角色、樣品來源、倍率與結構類型固定分組為":
            "並依資料用途、樣品來源、倍率與結構類型固定分組為",
        "種資料角色，每類": "類資料，每類",
    }
    changed = 0
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            for old, new in replacements.items():
                if old in run.text:
                    run.text = run.text.replace(old, new)
                    changed += 1
    if changed != len(replacements):
        raise RuntimeError(f"Expected {len(replacements)} wording replacements, found {changed}")
    document.save(DOCX)
    print(f"Applied {changed} final wording replacements to {DOCX}")


if __name__ == "__main__":
    main()
