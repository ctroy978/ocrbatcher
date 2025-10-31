# OCR Batcher CLI

OCR Batcher transforms a scanned PDF of handwritten student tests into cleaned, text-first PDFs per student. Each page is rasterized, OCR'd with **Google Cloud Vision**, scrubbed with XAI Grok to fill `[[UNK]]` tokens, named via extracted first names, and exported to `out/<timestamp>/student_name.pdf`. Pages are rendered to 220 DPI JPEG before OCR to keep payload sizes comfortably within API limits.

## Quick Start

1. **Create a virtual environment (Python 3.11+)**  
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   python -m pip install --upgrade pip
   pip install -e .
   ```
2. **Install native tools**
   - **Poppler (for pdf2image)**
     - macOS: `brew install poppler`
     - Ubuntu/Debian: `sudo apt install poppler-utils`
     - Windows: install [Poppler for Windows](https://blog.alivate.com.au/poppler-windows/) and add `bin/` to `PATH`
3. **Configure Google & environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual XAI key and Vision settings.
   ```
   Place your Google service-account JSON (e.g. `gen-lang-client.json`) in the project root or point `GOOGLE_APPLICATION_CREDENTIALS` to it.
4. **Run the CLI**
   ```bash
   python -m grader --input medusa.pdf --dry-run true --verbose
   ```

> The repository includes `medusa.pdf`, a sample two-page handwritten essay you can use while iterating.

## Environment Variables

The app loads configuration from `.env` (see `scripts/sample_env.env` for a template). Key entries:

```
GOOGLE_APPLICATION_CREDENTIALS=gen-lang-client.json
VISION_LANGUAGE_HINTS=en,es      # optional
VISION_MIME_TYPE=image/jpeg
XAI_API_KEY=...
XAI_CLEANUP_MODEL=grok-4-fast-reasoning
UNK_THRESHOLD=65
MAX_CONCURRENCY=3
NAME_FALLBACK=Student
OUTPUT_DIR=out
```

## CLI Usage

```
python -m grader --help
```

Typical run:

```bash
python -m grader \
  --input medusa.pdf \
  --unk-threshold 65 \
  --max-concurrency 3 \
  --dry-run true \
  --verbose
```

Outputs land in `out/<YYYY-MM-DD_HH-mm-ss>/` alongside any artifacts for failures.

## Development Workflow

- Format & lint: `ruff check .` and `black .`
- Tests: `pytest`
- Regenerate virtualenv dependencies with `pip install -e .`

## Troubleshooting

- **Google credentials not found**: ensure the service-account JSON exists and `GOOGLE_APPLICATION_CREDENTIALS` points to it (absolute or project-relative path).
- **Poppler missing**: `pdf2image` needs `pdftoppm`. Install Poppler and ensure the `bin/` directory is on `PATH`.
- **Vision rate limits / quota**: lower `--max-concurrency`, verify project quotas, and review Vision usage in Google Cloud console. Failed requests leave logs under `out/<timestamp>/artifacts/`.
- **XAI timeouts**: rerun with lower concurrency or retry once network stabilizes. Guardrail warnings appear in logs; flagged pages should be reviewed manually.
- **Low-confidence OCR**: adjust `--unk-threshold` (higher masks more text) or review the run artifacts to inspect masked regions.

For manual inspection, the run folder retains intermediate images when `--keep-images` is enabled and always preserves artifacts for failed pages.
