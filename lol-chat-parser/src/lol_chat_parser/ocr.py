from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    text: str
    confidence: float


class OCREngine(ABC):
    """Abstract base — swap engines without changing callers."""

    @abstractmethod
    def recognize(self, image: np.ndarray) -> List[OCRResult]:
        """
        Run OCR on a preprocessed image (grayscale or BGR uint8 ndarray).
        Returns a list of detected text lines with confidence scores.
        """
        ...


# ── PaddleOCR ─────────────────────────────────────────────────────────────────

class PaddleOCREngine(OCREngine):
    def __init__(self) -> None:
        try:
            from paddleocr import PaddleOCR  # type: ignore[import]
        except ImportError:
            raise RuntimeError(
                "PaddleOCR is not installed.\n"
                "Run: pip install paddleocr paddlepaddle"
            )
        # use_angle_cls=True handles upside-down text; lang='en' for English chat
        self._ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        logger.info("PaddleOCR engine ready")

    def recognize(self, image: np.ndarray) -> List[OCRResult]:
        # PaddleOCR expects BGR — convert grayscale if needed
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        raw = self._ocr.ocr(image, cls=True)
        results: List[OCRResult] = []
        if raw and raw[0]:
            for line in raw[0]:
                if line and len(line) >= 2:
                    text = str(line[1][0]).strip()
                    conf = float(line[1][1])
                    if text:
                        results.append(OCRResult(text=text, confidence=conf))
        return results


# ── Tesseract ─────────────────────────────────────────────────────────────────

class TesseractEngine(OCREngine):
    def __init__(self) -> None:
        try:
            import pytesseract  # type: ignore[import]
            self._pt = pytesseract
        except ImportError:
            raise RuntimeError(
                "pytesseract is not installed.\n"
                "Run: pip install pytesseract\n"
                "Also install the Tesseract binary: "
                "https://github.com/UB-Mannheim/tesseract/wiki"
            )
        logger.info("Tesseract engine ready")

    def recognize(self, image: np.ndarray) -> List[OCRResult]:
        data = self._pt.image_to_data(
            image, output_type=self._pt.Output.DICT, lang="eng"
        )
        lines: dict = {}
        for i, word in enumerate(data["text"]):
            word = word.strip()
            if not word:
                continue
            conf = max(0.0, float(data["conf"][i])) / 100.0
            key = (
                data["page_num"][i],
                data["block_num"][i],
                data["par_num"][i],
                data["line_num"][i],
            )
            if key not in lines:
                lines[key] = {"words": [], "confs": []}
            lines[key]["words"].append(word)
            lines[key]["confs"].append(conf)

        results: List[OCRResult] = []
        for key in sorted(lines):
            text = " ".join(lines[key]["words"])
            avg_conf = sum(lines[key]["confs"]) / len(lines[key]["confs"])
            if text.strip():
                results.append(OCRResult(text=text, confidence=avg_conf))
        return results


# ── Factory ───────────────────────────────────────────────────────────────────

def get_ocr_engine(name: str) -> OCREngine:
    if name == "paddleocr":
        return PaddleOCREngine()
    elif name == "tesseract":
        return TesseractEngine()
    else:
        raise ValueError(f"Unknown OCR engine '{name}'. Choose 'paddleocr' or 'tesseract'.")
