"""
CLI entry point for lol-chat-parser.

Commands:
  calibrate  — pick the chat-box rectangle interactively
  crop       — export a cropped video with FFmpeg
  parse      — run OCR and emit a JSON file of chat messages
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import cv2
import typer
from tqdm import tqdm

from .champions import ChampionMatcher
from .config import (
    DEFAULT_DEDUP_WINDOW,
    DEFAULT_FUZZY_THRESHOLD,
    DEFAULT_MIN_OCR_CONFIDENCE,
    DEFAULT_OCR_ENGINE,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_UPSCALE_FACTOR,
)
from .cropper import crop_video
from .dedupe import deduplicate
from .models import ChatMessage, CropConfig, ParseOutput
from .ocr import get_ocr_engine
from .parser import parse_chat_line
from .preprocess import preprocess_for_ocr
from .video import get_frame_at, get_video_info, iter_frames_at_rate

app = typer.Typer(
    name="lol-chat-parser",
    help="Extract and parse chat messages from League of Legends screen recordings.",
    add_completion=False,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _require_file(path: Path, label: str) -> None:
    if not path.exists():
        typer.echo(f"Error: {label} not found: {path}", err=True)
        raise typer.Exit(1)


def _load_crop_config(config_path: Path) -> CropConfig:
    try:
        return CropConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        typer.echo(f"Error reading crop config: {exc}", err=True)
        raise typer.Exit(1)


# ── calibrate ─────────────────────────────────────────────────────────────────

@app.command()
def calibrate(
    video: Path = typer.Option(..., "--video", "-v", help="Path to the source video file"),
    output: Path = typer.Option(
        "crop_config.json", "--output", "-o", help="Path to save the crop config JSON"
    ),
    timestamp: float = typer.Option(
        -1.0, "--timestamp", "-t",
        help="Timestamp in seconds to display (-1 = middle of video)",
    ),
) -> None:
    """
    Interactively select the chat box rectangle from a video frame.

    An OpenCV window opens showing the full frame scaled to fit your screen.
    Click and drag to draw a rectangle around the League chat area, then
    press ENTER or SPACE to confirm. Press ESC to abort without saving.
    """
    _require_file(video, "video")

    fps, total_frames = get_video_info(video)
    if timestamp < 0:
        timestamp = (total_frames / fps) / 2
        typer.echo(f"Using mid-video frame at {timestamp:.1f}s …")
    else:
        typer.echo(f"Loading frame at {timestamp:.1f}s …")

    try:
        frame = get_frame_at(video, timestamp)
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    # Scale frame down so it fits on screen while keeping the full image visible
    orig_h, orig_w = frame.shape[:2]
    try:
        import ctypes
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
    except Exception:
        screen_w, screen_h = 1920, 1080

    max_w = int(screen_w * 0.92)
    max_h = int(screen_h * 0.88)
    scale = min(max_w / orig_w, max_h / orig_h, 1.0)

    if scale < 1.0:
        display_w = int(orig_w * scale)
        display_h = int(orig_h * scale)
        display_frame = cv2.resize(frame, (display_w, display_h), interpolation=cv2.INTER_AREA)
        typer.echo(f"Frame scaled {orig_w}x{orig_h} → {display_w}x{display_h} to fit screen")
    else:
        display_frame = frame
        scale = 1.0

    typer.echo(
        "\nInstructions:\n"
        "  • Click and drag to select the chat box rectangle.\n"
        "  • Press ENTER or SPACE to confirm.\n"
        "  • Press C to cancel the current selection and redraw.\n"
        "  • Press ESC to abort without saving.\n"
    )

    window_title = "Select Chat Box — ENTER to confirm | ESC to abort"
    cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_title, display_frame.shape[1], display_frame.shape[0])
    roi = cv2.selectROI(window_title, display_frame, fromCenter=False, showCrosshair=True)
    cv2.destroyAllWindows()

    rx, ry, rw, rh = roi
    if rw == 0 or rh == 0:
        typer.echo("No region selected — aborting.", err=True)
        raise typer.Exit(1)

    # Scale ROI coordinates back to original video resolution
    x = int(rx / scale)
    y = int(ry / scale)
    w = int(rw / scale)
    h = int(rh / scale)

    config = CropConfig(x=x, y=y, width=w, height=h)
    output.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"\nSaved: {output}")
    typer.echo(f"  x={x}  y={y}  width={w}  height={h}")


# ── crop ──────────────────────────────────────────────────────────────────────

@app.command()
def crop(
    video: Path = typer.Option(..., "--video", "-v", help="Path to the source video file"),
    config: Path = typer.Option(..., "--config", "-c", help="Path to the crop config JSON"),
    output: Path = typer.Option(..., "--output", "-o", help="Output path for the cropped MP4"),
) -> None:
    """
    Crop the video to the chat box region and save an MP4 using FFmpeg.
    """
    _require_file(video, "video")
    _require_file(config, "crop config")

    crop_cfg = _load_crop_config(config)
    typer.echo(
        f"Cropping {video.name} "
        f"[x={crop_cfg.x} y={crop_cfg.y} w={crop_cfg.width} h={crop_cfg.height}] …"
    )
    try:
        crop_video(video, crop_cfg, output)
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Done → {output}")


# ── parse ─────────────────────────────────────────────────────────────────────

@app.command()
def parse(
    video: Path = typer.Option(..., "--video", "-v", help="Path to the source video file"),
    config: Path = typer.Option(..., "--config", "-c", help="Path to the crop config JSON"),
    output: Path = typer.Option(..., "--output", "-o", help="Output path for the JSON results"),
    sample_rate: float = typer.Option(
        DEFAULT_SAMPLE_RATE, "--sample-rate", "-s",
        help="Seconds between sampled frames (default 0.5)",
    ),
    ocr: str = typer.Option(
        DEFAULT_OCR_ENGINE, "--ocr",
        help="OCR engine to use: 'paddleocr' (default) or 'tesseract'",
    ),
    champions_file: Optional[Path] = typer.Option(
        None, "--champions", help="Path to champion_names.json for name matching"
    ),
    player_map_file: Optional[Path] = typer.Option(
        None, "--player-map", help="Path to player_to_champion.json mapping file"
    ),
    fuzzy_threshold: float = typer.Option(
        DEFAULT_FUZZY_THRESHOLD, "--fuzzy-threshold",
        help="Minimum rapidfuzz match score to accept a champion name (0–100)",
    ),
    dedup_window: float = typer.Option(
        DEFAULT_DEDUP_WINDOW, "--dedup-window",
        help="Seconds within which identical messages are considered duplicates",
    ),
    upscale: int = typer.Option(
        DEFAULT_UPSCALE_FACTOR, "--upscale",
        help="Integer upscale factor applied to frames before OCR (1–4)",
    ),
    min_confidence: float = typer.Option(
        DEFAULT_MIN_OCR_CONFIDENCE, "--min-confidence",
        help="Minimum OCR confidence (0–1) required to include a result",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-V", help="Enable debug-level logging"),
) -> None:
    """
    Extract and parse all chat messages from a video, writing a JSON file.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    _require_file(video, "video")
    _require_file(config, "crop config")

    crop_cfg = _load_crop_config(config)

    # Optional champion matcher
    champion_matcher: Optional[ChampionMatcher] = None
    if champions_file is not None:
        _require_file(champions_file, "champions file")
        champion_matcher = ChampionMatcher.from_file(champions_file, threshold=fuzzy_threshold)

    # Optional player → champion mapping
    player_map: Optional[dict] = None
    if player_map_file is not None:
        _require_file(player_map_file, "player map file")
        with open(player_map_file, encoding="utf-8") as fh:
            player_map = json.load(fh)
        logger.info("Loaded player map with %d entries", len(player_map))

    # Boot OCR engine (imports happen here so startup errors are reported early)
    typer.echo(f"Initialising OCR engine: {ocr} …")
    try:
        ocr_engine = get_ocr_engine(ocr)
    except (RuntimeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    # Estimate progress
    fps, total_frames = get_video_info(video)
    frame_step = max(1, int(round(fps * sample_rate)))
    estimated_samples = max(1, total_frames // frame_step)

    typer.echo(
        f"Video: {video.name}  fps={fps:.1f}  "
        f"sample every {sample_rate}s  ~{estimated_samples} frames"
    )

    raw_messages: list[ChatMessage] = []

    with tqdm(total=estimated_samples, desc="Parsing", unit="frame", ncols=80) as pbar:
        for timestamp, frame in iter_frames_at_rate(
            video, sample_rate,
            crop_cfg.x, crop_cfg.y, crop_cfg.width, crop_cfg.height,
        ):
            pbar.update(1)

            processed = preprocess_for_ocr(frame, upscale=upscale)
            ocr_results = ocr_engine.recognize(processed)

            for result in ocr_results:
                if result.confidence < min_confidence:
                    continue
                parsed = parse_chat_line(
                    result.text,
                    champion_matcher=champion_matcher,
                    player_map=player_map,
                )
                if parsed is None:
                    continue
                sender_raw, champion, chat_text = parsed
                raw_messages.append(
                    ChatMessage(
                        timestamp_seconds=round(timestamp, 3),
                        champion=champion,
                        sender_raw=sender_raw,
                        chat=chat_text,
                        confidence=round(result.confidence, 4),
                        raw_ocr=result.text,
                    )
                )

    unique = deduplicate(raw_messages, time_window=dedup_window)
    typer.echo(f"Messages: {len(raw_messages)} raw → {len(unique)} after dedup")

    result_obj = ParseOutput(
        source_video=str(video),
        crop=crop_cfg,
        messages=unique,
    )
    output.write_text(result_obj.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"Output → {output}")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app()


if __name__ == "__main__":
    main()
