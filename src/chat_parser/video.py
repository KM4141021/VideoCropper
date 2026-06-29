from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def get_video_info(video_path: Path) -> Tuple[float, int]:
    """Return (fps, total_frame_count) for a video file."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return fps, total


def get_frame_at(video_path: Path, timestamp: float = 0.0) -> np.ndarray:
    """Return the BGR frame closest to the given timestamp (seconds)."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError(f"Could not read frame at {timestamp}s from {video_path}")
    return frame


def iter_frames_at_rate(
    video_path: Path,
    sample_rate: float,
    x: int,
    y: int,
    w: int,
    h: int,
) -> Iterator[Tuple[float, np.ndarray]]:
    """
    Yield (timestamp_seconds, cropped_bgr_frame) sampled every sample_rate seconds.

    The region (x, y, w, h) is cropped from each frame before yielding,
    so callers receive only the chat box area for further processing.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_step = max(1, int(round(fps * sample_rate)))
    frame_idx = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_step == 0:
                timestamp = frame_idx / fps
                fh, fw = frame.shape[:2]
                x1 = max(0, x)
                y1 = max(0, y)
                x2 = min(fw, x + w)
                y2 = min(fh, y + h)
                cropped = frame[y1:y2, x1:x2]
                if cropped.size > 0:
                    yield timestamp, cropped
            frame_idx += 1
    finally:
        cap.release()
