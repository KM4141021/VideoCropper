# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- **Python**: `C:\Python312\python.exe` — the `python` command is not on PATH, use the full path or `.venv\Scripts\python.exe`
- **Venv**: `.venv\` in the project root — activate with `.venv\Scripts\Activate.ps1` before running commands
- **FFmpeg**: must be on PATH separately; used only by `cropper.py` via subprocess

## Common commands

```powershell
# Install / reinstall package
.venv\Scripts\python.exe -m pip install -e .

# Run all tests
.venv\Scripts\python.exe -m pytest

# Run a single test file
.venv\Scripts\python.exe -m pytest tests/test_parser.py

# Run a single test by name
.venv\Scripts\python.exe -m pytest tests/test_dedupe.py::test_best_confidence_retained

# Run with coverage
.venv\Scripts\python.exe -m pytest --cov=lol_chat_parser --cov-report=term-missing
```

## CLI usage

```powershell
# Step 1 — pick chat box (opens OpenCV window, saves coordinates)
.venv\Scripts\python.exe -m lol_chat_parser calibrate --video lol222.mp4 --output crop_config.json

# Step 2 — optional cropped video preview
.venv\Scripts\python.exe -m lol_chat_parser crop --video lol222.mp4 --config crop_config.json --output chat_only.mp4

# Step 3 — extract chat to JSON
.venv\Scripts\python.exe -m lol_chat_parser parse --video lol222.mp4 --config crop_config.json --output chat_messages.json --champions examples/champion_names.example.json --sample-rate 1.0
```

## Architecture

The pipeline flows in one direction: **video frames → preprocessing → OCR → parsing → deduplication → JSON**.

### Data flow in `parse`

```
cli.py::parse
  └─ video.py::iter_frames_at_rate     # OpenCV VideoCapture, yields (timestamp, bgr_frame)
       └─ preprocess.py::preprocess_for_ocr  # upscale → grayscale → denoise → sharpen → CLAHE
            └─ ocr.py::OCREngine.recognize   # returns List[OCRResult(text, confidence)]
                 └─ parser.py::parse_chat_line  # regex → (sender_raw, champion|None, message)
                      └─ dedupe.py::deduplicate  # normalize → suppress within time window
                           └─ models.py::ParseOutput  # pydantic → JSON
```

### Key design decisions

**OCR is swappable** — `ocr.py` defines an `OCREngine` ABC with a single `recognize(image) -> List[OCRResult]` method. `PaddleOCREngine` and `TesseractEngine` both implement it. `get_ocr_engine(name)` is the factory. Adding a new engine means subclassing `OCREngine` and registering it in the factory.

**Coordinates are in original video resolution** — `calibrate` scales the display frame to fit the screen but scales the ROI back before saving to `crop_config.json`. Everything downstream (`crop`, `parse`, `iter_frames_at_rate`) works in original pixel coordinates.

**Champion matching is two-stage** — `champions.py::ChampionMatcher.match()` tries exact case-insensitive lookup first (O(1) via `_lower_map`), then falls back to `rapidfuzz.fuzz.WRatio` fuzzy match. The threshold is configurable at construction time.

**Parser pattern order matters** — `parser.py` tries three regex patterns in specificity order: bracket prefix (`[All]`/`[Ally]`) → parenthetical (`Name (Content):`) → simple (`Name:`). The parenthetical pattern checks `paren_content` against `_ROLE_KEYWORDS` to distinguish `"Jinx (Team): msg"` (sender is the champion) from `"Player (Jinx): msg"` (paren is the champion).

**Dedup operates on normalized keys** — `dedupe.py` lowercases, strips punctuation, collapses whitespace, then groups by `(sender, chat)` key. Within a configurable time window, only the earliest occurrence is kept; the highest confidence score seen across duplicates is retained on that record.

**Preprocessing returns grayscale** — `preprocess_for_ocr` returns a grayscale `uint8` ndarray. `PaddleOCREngine.recognize` converts it back to BGR before passing to PaddleOCR. Tesseract works directly with grayscale.

### Models (`models.py`)

All three pydantic v2 models are used for both validation and JSON serialization via `.model_dump_json()`:
- `CropConfig` — saved/loaded as `crop_config.json`
- `ChatMessage` — one detected chat line
- `ParseOutput` — top-level output wrapping source path, crop, and message list

### Defaults (`config.py`)

All tunable defaults live here. Change them here rather than hardcoding in CLI option defaults.
