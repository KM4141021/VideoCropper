from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .models import CropConfig

logger = logging.getLogger(__name__)


def crop_video(source: Path, config: CropConfig, output: Path) -> None:
    """
    Use FFmpeg to produce a video containing only the chat box rectangle.

    FFmpeg crop filter syntax: crop=w:h:x:y
    Output uses H.264 at CRF 18 (visually lossless) with fast preset.
    """
    crop_filter = f"crop={config.width}:{config.height}:{config.x}:{config.y}"
    cmd = [
        "ffmpeg",
        "-i", str(source),
        "-vf", crop_filter,
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-c:a", "copy",
        "-movflags", "+faststart",
        "-y",
        str(output),
    ]
    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg exited with code {result.returncode}.\n"
            f"stderr:\n{result.stderr}"
        )
    logger.info("Cropped video written to: %s", output)
