from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pdf2image import convert_from_path


def convert_to_images(
    input_pdf: Path,
    work_dir: Path,
    dpi: int = 300,
    image_format: str = "png",
    jpeg_quality: Optional[int] = None,
) -> List[Path]:
    work_dir.mkdir(parents=True, exist_ok=True)
    fmt = "png" if image_format.lower() != "jpeg" else "jpeg"
    images = convert_from_path(str(input_pdf), dpi=dpi, fmt=fmt)
    output_paths: List[Path] = []
    for index, image in enumerate(images):
        if image_format.lower() in {"jpeg", "jpg"}:
            page_path = work_dir / f"page_{index + 1:03d}.jpg"
            rgb_image = image.convert("RGB")
            save_kwargs = {"quality": jpeg_quality or 85, "optimize": True}
            rgb_image.save(page_path, "JPEG", **save_kwargs)
        else:
            page_path = work_dir / f"page_{index + 1:03d}.png"
            image.save(page_path, "PNG")
        output_paths.append(page_path)
    return output_paths
