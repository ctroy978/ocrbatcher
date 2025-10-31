from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich import print as rich_print

from . import ai_cleanup, ocr
from .clients.google_vision_client import GoogleVisionClient
from .clients.xai_client import XAIClient
from .config import get_settings
from .export import write_pdf
from .logging_utils import get_logger
from .naming import extract_first_name
from .pdf_utils import convert_to_images

PROVIDER_NAME = "google-vision"

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)


def _resolve_bool(value: Optional[bool], default: bool) -> bool:
    return default if value is None else value


def _parse_bool_option(name: str, value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    raise typer.BadParameter(f"{name} must be one of: true, false, yes, no, on, off, 1, 0")


def _validate_dependencies(*, credentials_path: Path, xai_key: Optional[str]) -> None:
    if not credentials_path.exists():
        raise typer.BadParameter(f"Google credentials file not found: {credentials_path}")
    if not xai_key:
        raise typer.BadParameter("XAI_API_KEY is required for cleanup.")


def _write_artifacts(artifacts_dir: Path, page_index: int, artifacts: dict[str, str]) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    for name, content in artifacts.items():
        target = artifacts_dir / f"page_{page_index + 1:03d}_{name}.txt"
        target.write_text(content or "", encoding="utf-8")


async def _process_pages(
    *,
    images: list[Path],
    threshold: int,
    semaphore: asyncio.Semaphore,
    run_dir: Path,
    timestamp: str,
    dry_run: bool,
    keep_images: bool,
    fallback: Optional[str],
    logger,
    xai_client: XAIClient,
    vision_client: GoogleVisionClient,
) -> tuple[list[dict], list[Path]]:
    results: list[dict] = []
    generated_files: list[Path] = []
    artifacts_dir = run_dir / "artifacts"

    async def worker(page_index: int, image_path: Path) -> dict:
        nonlocal generated_files
        async with semaphore:
            page_label = page_index + 1
            logger.info("[bold]Processing page %s with Google Vision OCR[/]", page_label)
            ocr_result = None
            cleanup_result = None
            try:
                ocr_result = await ocr.ocr_google_vision(
                    image_path,
                    client=vision_client,
                    threshold=threshold,
                )
                cleanup_result = await ai_cleanup.restore(ocr_result.masked_text, client=xai_client, logger=logger)
                restored_text = cleanup_result.restored_text
                name_result = extract_first_name(restored_text, fallback, page_index)

                if dry_run:
                    output_path = run_dir / f"{name_result.filename_stem}.pdf"
                else:
                    output_path = write_pdf(
                        restored_text,
                        base_dir=run_dir,
                        filename_stem=name_result.filename_stem,
                        timestamp=timestamp,
                        page_number=page_label,
                        header=True,
                    )
                    generated_files.append(output_path)

                logger.info(
                    "Page %s processed: masked_tokens=%s, total_tokens=%s, name=%s, output=%s",
                    page_label,
                    ocr_result.stats.masked_tokens,
                    ocr_result.stats.total_tokens,
                    name_result.display_name,
                    output_path,
                )

                if cleanup_result.guardrail_violated:
                    logger.warning(
                        "Page %s cleanup guardrail violated after retry; review output manually.",
                        page_label,
                    )

                return {
                    "status": "success",
                    "page": page_label,
                    "output": output_path,
                    "name": name_result.display_name,
                    "guardrail_triggered": cleanup_result.guardrail_triggered,
                    "guardrail_violated": cleanup_result.guardrail_violated,
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception("Page %s failed: %s", page_label, exc)
                artifacts: dict[str, str] = {}
                if ocr_result:
                    artifacts.update(ocr_result.artifacts)
                if cleanup_result:
                    artifacts["restored"] = cleanup_result.restored_text
                else:
                    artifacts.setdefault("restored", "")
                _write_artifacts(artifacts_dir, page_index, artifacts)
                return {
                    "status": "failed",
                    "page": page_label,
                    "error": str(exc),
                }
            finally:
                if not keep_images and image_path.exists():
                    try:
                        image_path.unlink()
                    except OSError:
                        logger.debug("Could not remove temp image %s", image_path)

    tasks = [asyncio.create_task(worker(idx, image)) for idx, image in enumerate(images)]
    page_results = await asyncio.gather(*tasks)
    results.extend(page_results)
    return results, generated_files


@app.command()
def main(
    input: Path = typer.Option(..., "--input", "-i", help="Path to input PDF"),
    outdir: Optional[Path] = typer.Option(None, "--outdir", "-o", help="Base output directory"),
    unk_threshold: Optional[int] = typer.Option(None, "--unk-threshold", help="Confidence threshold for masking"),
    max_concurrency: Optional[int] = typer.Option(None, "--max-concurrency", help="Max concurrent API calls"),
    dry_run: Optional[str] = typer.Option(None, "--dry-run", help="Enable dry-run mode (true/false)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging", is_flag=True),
    quiet: bool = typer.Option(False, "--quiet", help="Silence verbose logging", is_flag=True),
    keep_images: Optional[str] = typer.Option(None, "--keep-images", help="Keep intermediate images (true/false)"),
    name_fallback: Optional[str] = typer.Option(None, "--name-fallback", help="Fallback first name"),
) -> None:
    settings = get_settings()

    resolved_threshold = unk_threshold or settings.unk_threshold
    resolved_outdir = (outdir or settings.output_dir).resolve()
    resolved_concurrency = max_concurrency or settings.max_concurrency
    dry_run_bool = _parse_bool_option("dry-run", dry_run)
    keep_images_bool = _parse_bool_option("keep-images", keep_images)

    if verbose and quiet:
        raise typer.BadParameter("Cannot use --verbose and --quiet together.")

    resolved_dry_run = _resolve_bool(dry_run_bool, settings.dry_run)
    if verbose:
        resolved_verbose = True
    elif quiet:
        resolved_verbose = False
    else:
        resolved_verbose = settings.verbose
    resolved_keep_images = _resolve_bool(keep_images_bool, settings.keep_images)
    resolved_fallback = name_fallback or settings.name_fallback

    if resolved_concurrency < 1:
        raise typer.BadParameter("max_concurrency must be >= 1")

    input_path = input.expanduser().resolve()
    if not input_path.exists():
        raise typer.BadParameter(f"Input PDF not found: {input_path}")

    _validate_dependencies(
        credentials_path=settings.google.credentials_path,
        xai_key=settings.xai.api_key,
    )

    logger = get_logger(verbose=resolved_verbose)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = resolved_outdir / timestamp
    images_dir = run_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting OCR batch: input=%s provider=%s", input_path, PROVIDER_NAME)
    images = convert_to_images(
        input_path,
        images_dir,
        dpi=220,
        image_format="jpeg",
        jpeg_quality=70,
    )
    logger.info("Rasterized %s pages to %s", len(images), images_dir)

    semaphore = asyncio.Semaphore(resolved_concurrency)

    async def runner():
        async with XAIClient(settings.xai) as xai_client:
            async with GoogleVisionClient(settings.google) as vision_client:
                return await _process_pages(
                    images=images,
                    threshold=resolved_threshold,
                    semaphore=semaphore,
                    run_dir=run_dir,
                    timestamp=timestamp,
                    dry_run=resolved_dry_run,
                    keep_images=resolved_keep_images,
                    fallback=resolved_fallback,
                    logger=logger,
                    xai_client=xai_client,
                    vision_client=vision_client,
                )

    results, generated_files = asyncio.run(runner())

    success = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]
    guardrail_flags = [r for r in success if r.get("guardrail_violated")]

    logger.info("Run completed: %s succeeded, %s failed.", len(success), len(failed))
    if resolved_dry_run:
        logger.info("Dry-run mode was enabled; no PDFs were written.")
    else:
        for path in generated_files:
            logger.info("Generated %s", path)

    if guardrail_flags:
        logger.warning(
            "Guardrail warnings: %s pages require review (%s).",
            len(guardrail_flags),
            ", ".join(str(flag["page"]) for flag in guardrail_flags),
        )

    if failed:
        rich_print("[red]Some pages failed. See logs and artifacts for details.[/]")

