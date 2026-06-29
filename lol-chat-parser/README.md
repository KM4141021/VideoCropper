# lol-chat-parser

A local CLI tool that extracts chat messages from League of Legends screen recordings.  
Runs entirely on your PC — no cloud, no game-client interaction, no gameplay automation.

---

## What it does

1. **calibrate** — lets you drag a rectangle around the chat box in a video frame and saves the coordinates.
2. **crop** — uses FFmpeg to cut the video down to just the chat-box area.
3. **parse** — samples frames, runs OCR (PaddleOCR or Tesseract), parses chat lines, matches champion names, deduplicates, and writes a JSON file.

---

## Requirements

- Python 3.11 or newer
- FFmpeg on your PATH
- (Optional) Tesseract binary if you want the Tesseract fallback

---

## Installation

### 1 — Install FFmpeg

Download the Windows build from <https://ffmpeg.org/download.html> (e.g. `ffmpeg-release-essentials.zip`).  
Extract it and add the `bin/` folder to your system PATH, or place `ffmpeg.exe` alongside the project.

Verify:
```
ffmpeg -version
```

### 2 — Create a virtual environment and install Python dependencies

```powershell
cd lol-chat-parser
python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
```

Or without editable install:
```powershell
pip install -r requirements.txt
```

### 3 — Install PaddleOCR (primary OCR engine)

PaddleOCR requires the PaddlePaddle framework.  
For CPU-only (most users):

```powershell
pip install paddlepaddle paddleocr
```

For GPU (CUDA):
```powershell
pip install paddlepaddle-gpu paddleocr
```

First run will download model weights (~200 MB) automatically.

### 4 — Install Tesseract (optional fallback)

Download the installer from <https://github.com/UB-Mannheim/tesseract/wiki>.  
The default install path is `C:\Program Files\Tesseract-OCR\tesseract.exe`.  
Add that directory to your PATH, then:

```powershell
pip install pytesseract
```

---

## Usage

### Step 1 — Calibrate (pick the chat box)

```powershell
python -m lol_chat_parser calibrate --video game_recording.mp4 --output crop_config.json
```

An OpenCV window opens showing a frame from the video.  
Click and drag to draw a rectangle around the League chat area.  
Press **ENTER** to confirm. The coordinates are saved to `crop_config.json`.

Options:
| Flag | Default | Description |
|---|---|---|
| `--video` | required | Path to source video |
| `--output` | `crop_config.json` | Where to save the crop config |
| `--timestamp` | `0.0` | Seconds into the video to display for selection |

---

### Step 2 — Crop the video (optional)

Generates a small MP4 containing only the chat box — useful for review.

```powershell
python -m lol_chat_parser crop \
  --video game_recording.mp4 \
  --config crop_config.json \
  --output chat_only.mp4
```

---

### Step 3 — Parse chat messages

```powershell
python -m lol_chat_parser parse \
  --video game_recording.mp4 \
  --config crop_config.json \
  --output chat_messages.json \
  --ocr paddleocr \
  --sample-rate 0.5 \
  --champions examples/champion_names.example.json \
  --player-map examples/player_to_champion.example.json
```

All options:

| Flag | Default | Description |
|---|---|---|
| `--video` | required | Source video |
| `--config` | required | Crop config JSON |
| `--output` | required | Output JSON path |
| `--ocr` | `paddleocr` | OCR engine: `paddleocr` or `tesseract` |
| `--sample-rate` | `0.5` | Seconds between sampled frames |
| `--champions` | none | Path to `champion_names.json` |
| `--player-map` | none | Path to `player_to_champion.json` |
| `--fuzzy-threshold` | `80.0` | rapidfuzz min score for champion matching (0–100) |
| `--dedup-window` | `5.0` | Seconds; identical messages within window are merged |
| `--upscale` | `2` | Integer upscale factor applied before OCR |
| `--min-confidence` | `0.3` | Minimum OCR confidence to keep a result (0–1) |
| `--verbose` | off | Enable debug logging |

---

## Output JSON format

```json
{
  "source_video": "game_recording.mp4",
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

### Field reference

| Field | Description |
|---|---|
| `timestamp_seconds` | Time in the source video where the message was detected |
| `champion` | Resolved champion name, or `null` if uncertain |
| `sender_raw` | Exact sender text as OCR read it |
| `chat` | The message body |
| `confidence` | OCR engine confidence (0–1) |
| `raw_ocr` | Full raw OCR string before parsing |

---

## Supported chat formats

The parser handles:

```
Jinx: group mid
[All] Jinx: gg
[Ally] Caitlyn: push bot
Jinx (Team): group
PlayerName (Jinx): group mid
```

---

## Champion name files

Copy `examples/champion_names.example.json` and pass it via `--champions`.  
The file can be a JSON array of strings or a dict whose values are champion names.

```json
["Jinx", "Caitlyn", "Thresh", "LeBlanc", "Miss Fortune"]
```

Champion matching uses exact lookup first, then rapidfuzz fuzzy matching to handle common OCR errors (`l`/`I`, `0`/`O`, missing apostrophes, merged spaces).

---

## Player-to-champion mapping

If you know which summoner played which champion, create a JSON object:

```json
{
  "SummonerOne": "Jinx",
  "SummonerTwo": "Caitlyn"
}
```

Pass it with `--player-map`. When the parser cannot match the sender name directly to a champion, it looks the summoner name up in this map.

---

## Running tests

```powershell
pytest
```

Or with coverage:
```powershell
pytest --cov=lol_chat_parser --cov-report=term-missing
```

---

## Project structure

```
lol-chat-parser/
├── src/lol_chat_parser/
│   ├── cli.py          # typer CLI (calibrate / crop / parse)
│   ├── video.py        # OpenCV frame extraction
│   ├── cropper.py      # FFmpeg subprocess wrapper
│   ├── preprocess.py   # image upscale / denoise / sharpen / CLAHE
│   ├── ocr.py          # PaddleOCR and Tesseract engines
│   ├── parser.py       # regex chat-line parser
│   ├── dedupe.py       # duplicate suppression
│   ├── champions.py    # exact + fuzzy champion matching
│   ├── models.py       # pydantic output models
│   └── config.py       # default constants
├── tests/
│   ├── test_parser.py
│   ├── test_dedupe.py
│   └── test_champions.py
├── examples/
│   ├── crop_config.example.json
│   ├── champion_names.example.json
│   └── player_to_champion.example.json
├── requirements.txt
└── pyproject.toml
```

---

## Troubleshooting

**`ffmpeg` not found** — Make sure FFmpeg is on your PATH. Run `ffmpeg -version` to confirm.

**PaddleOCR downloads models on first run** — This is expected. It downloads ~200 MB of model weights to `~/.paddleocr/`. Subsequent runs use the cache.

**Low OCR accuracy** — Try increasing `--upscale 3` and lowering `--min-confidence 0.2`. Ensure the crop region is tight around the chat box.

**Wrong champion names** — Lower `--fuzzy-threshold` (e.g. `70`) or add the player mapping file.
