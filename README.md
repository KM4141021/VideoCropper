# Video Chat Parser

A local CLI tool that extracts chat messages from game screen recordings using OCR.
Runs entirely on your PC — no cloud, no internet required during processing.

---

## What it does

1. **calibrate** — open a frame from your video and drag a rectangle around the chat box to save its coordinates.
2. **crop** — use FFmpeg to cut the video down to just the chat-box area (optional preview step).
3. **parse** — sample frames at a set interval, run OCR, parse chat lines, match sender names, deduplicate, and write a JSON file.

---

## Requirements

- Python 3.11 or newer
- FFmpeg installed and on your system PATH
- Tesseract binary (optional — only needed if using the Tesseract OCR engine)

---

## Installation

### 1 — Install FFmpeg

Download the Windows build from the [FFmpeg official site](https://ffmpeg.org/download.html) (e.g. `ffmpeg-release-essentials.zip`).
Extract it and add the `bin/` folder to your system PATH.

Verify it works:
```powershell
ffmpeg -version
```

---

### 2 — Create a virtual environment

Open PowerShell in the project folder and run:

```powershell
C:\Python312\python.exe -m venv .venv
.venv\Scripts\Activate.ps1
```

You should see `(.venv)` appear at the start of your prompt.

---

### 3 — Install Python dependencies

```powershell
.venv\Scripts\python.exe -m pip install -e .
```

This installs all required packages and registers the `chat-parser` CLI command.

---

### 4 — Install PaddleOCR (primary OCR engine)

PaddleOCR is included in the dependencies above. On first run it will automatically download its model weights (~200 MB) to `~/.paddleocr/`. This only happens once.

If you want GPU acceleration (Nvidia only):
```powershell
.venv\Scripts\python.exe -m pip install paddlepaddle-gpu
```

---

### 5 — Install Tesseract (optional fallback OCR engine)

Download and install the Tesseract binary from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki). Add the install directory (`C:\Program Files\Tesseract-OCR\`) to your PATH.

---

## Every new terminal session

Before running any command, navigate to the project and activate the venv:

```powershell
cd "D:\VideoCropper\VideoCropper"
.venv\Scripts\Activate.ps1
```

---

## Commands

### calibrate — select the chat box region

Run this once per video layout to tell the tool where the chat box is on screen.

```powershell
.venv\Scripts\python.exe -m chat_parser calibrate --video recording.mp4 --output crop_config.json
```

An OpenCV window opens showing a frame from the middle of the video. Click and drag to draw a rectangle around the chat area, then press **ENTER** to confirm. The coordinates are saved to `crop_config.json`.

| Flag | Default | Description |
|---|---|---|
| `--video` | required | Path to the source video file |
| `--output` | `crop_config.json` | Where to save the crop config |
| `--timestamp` | mid-video | Specific timestamp in seconds to show (default is the middle of the video) |

---

### crop — export a cropped video (optional)

Generates a small MP4 containing only the chat box region. Useful for visually verifying the crop before running OCR.

```powershell
.venv\Scripts\python.exe -m chat_parser crop --video recording.mp4 --config crop_config.json --output chat_only.mp4
```

| Flag | Default | Description |
|---|---|---|
| `--video` | required | Path to the source video file |
| `--config` | required | Path to the crop config JSON |
| `--output` | required | Output path for the cropped MP4 |

---

### parse — extract chat messages to JSON

Processes the video frame by frame, runs OCR on the chat box, parses each detected line, deduplicates across frames, and writes a JSON file.

```powershell
.venv\Scripts\python.exe -m chat_parser parse `
  --video recording.mp4 `
  --config crop_config.json `
  --output chat_messages.json `
  --champions examples/champion_names.example.json `
  --sample-rate 1.0
```

| Flag | Default | Description |
|---|---|---|
| `--video` | required | Path to the source video file |
| `--config` | required | Path to the crop config JSON |
| `--output` | required | Output path for the JSON results |
| `--sample-rate` | `0.5` | Seconds between sampled frames — `1.0` is faster with similar accuracy |
| `--ocr` | `paddleocr` | OCR engine: `paddleocr` or `tesseract` |
| `--champions` | none | Path to a JSON file of known sender names for matching |
| `--player-map` | none | Path to a JSON mapping of player names to display names |
| `--fuzzy-threshold` | `80.0` | Minimum fuzzy match score to accept a name match (0–100) |
| `--dedup-window` | `5.0` | Seconds — identical messages within this window are merged into one |
| `--upscale` | `2` | Upscale factor applied to frames before OCR (try `3` for small text) |
| `--min-confidence` | `0.3` | Minimum OCR confidence (0–1) to include a result |
| `--verbose` | off | Enable debug-level logging |

---

## Output JSON format

```json
{
  "source_video": "recording.mp4",
  "crop": {
    "x": 10,
    "y": 730,
    "width": 380,
    "height": 250
  },
  "messages": [
    {
      "timestamp_seconds": 123.5,
      "champion": "Jinx",
      "sender_raw": "Jinx",
      "chat": "group mid",
      "confidence": 0.91,
      "raw_ocr": "Jinx: group mid"
    }
  ]
}
```

| Field | Description |
|---|---|
| `timestamp_seconds` | When in the video this message was detected |
| `champion` | Matched name from your names file, or `null` if not matched |
| `sender_raw` | Exact sender text as OCR read it |
| `chat` | The message body |
| `confidence` | OCR confidence score (0–1, higher is better) |
| `raw_ocr` | Full raw OCR string before parsing |

---

## Supported chat formats

The parser recognises these line formats:

```
Name: message text
[All] Name: message text
[Ally] Name: message text
Name (Team): message text
PlayerName (DisplayName): message text
```

---

## Name matching files

### Champion / sender names (`--champions`)

A JSON array or dict of known names used for matching senders:

```json
["Alice", "Bob", "Charlie"]
```

Matching tries exact lookup first, then fuzzy matching via rapidfuzz to handle OCR errors like merged spaces, wrong capitalisation, or substituted characters.

Copy and edit `examples/champion_names.example.json` as a starting point.

### Player-to-name mapping (`--player-map`)

Maps a player's account name to their display name when they differ:

```json
{
  "AccountName1": "DisplayName1",
  "AccountName2": "DisplayName2"
}
```

Copy and edit `examples/player_to_champion.example.json` as a starting point.

---

## Running tests

```powershell
.venv\Scripts\python.exe -m pytest
```

With coverage report:
```powershell
.venv\Scripts\python.exe -m pytest --cov=chat_parser --cov-report=term-missing
```

---

## Troubleshooting

**`ffmpeg` not found** — Confirm FFmpeg is on your PATH with `ffmpeg -version`.

**PaddleOCR downloads on first run** — Expected. Model weights (~200 MB) download to `~/.paddleocr/` once and are cached for all future runs.

**Low OCR accuracy** — Try `--upscale 3` and `--min-confidence 0.2`. Make sure the crop region is tight around the chat area with no extra padding.

**Name not matched** — Lower `--fuzzy-threshold` (e.g. `65`) or add the name to your `--player-map` file.

**`pip` not recognised** — Use `.venv\Scripts\python.exe -m pip` instead of `pip` directly.
