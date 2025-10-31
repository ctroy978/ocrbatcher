from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


def _ensure_unique_path(base_dir: Path, stem: str) -> Path:
    counter = 1
    candidate = base_dir / f"{stem}.pdf"
    while candidate.exists():
        counter += 1
        candidate = base_dir / f"{stem}_{counter}.pdf"
    return candidate


def _wrap_text(text: str, width: int = 85) -> list[str]:
    import textwrap

    wrapped_lines: list[str] = []
    for line in text.splitlines() or [""]:
        if not line:
            wrapped_lines.append("")
            continue
        wrapped = textwrap.wrap(line, width=width, replace_whitespace=False, drop_whitespace=False)
        if not wrapped:
            wrapped_lines.append("")
        else:
            wrapped_lines.extend(wrapped)
    return wrapped_lines


def write_pdf(
    text: str,
    *,
    base_dir: Path,
    filename_stem: str,
    timestamp: str,
    page_number: int,
    header: bool = True,
) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    target_path = _ensure_unique_path(base_dir, filename_stem)
    content = text or "[No OCR text detected]"

    pdf = canvas.Canvas(str(target_path), pagesize=letter)
    _, height = letter
    left_margin = 0.75 * inch
    top_margin = height - 0.75 * inch
    leading = 12

    header_text = None
    if header:
        pdf.setFont("Courier", 8)
        header_text = f"Restored page • {timestamp} • source page {page_number}"
        pdf.drawString(left_margin, top_margin, header_text)
        text_y = top_margin - leading * 1.5
    else:
        text_y = top_margin

    pdf.setFont("Courier", 11)
    for line in _wrap_text(content):
        if text_y < 0.75 * inch:
            pdf.showPage()
            text_y = top_margin
            if header:
                pdf.setFont("Courier", 8)
                pdf.drawString(left_margin, top_margin, header_text)
                text_y = top_margin - leading * 1.5
            pdf.setFont("Courier", 11)
        pdf.drawString(left_margin, text_y, line)
        text_y -= leading

    pdf.save()
    return target_path
