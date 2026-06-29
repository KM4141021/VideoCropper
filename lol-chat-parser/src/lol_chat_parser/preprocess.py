from __future__ import annotations

import cv2
import numpy as np


def preprocess_for_ocr(image: np.ndarray, upscale: int = 2) -> np.ndarray:
    """
    Prepare a chat-region frame for OCR.

    LoL chat has light text on a semi-transparent dark background.
    Steps:
      1. Upscale (cubic) to give OCR more pixel data per character
      2. Grayscale conversion
      3. Fast non-local means denoising
      4. Sharpening kernel
      5. CLAHE contrast enhancement
    Returns a grayscale uint8 array ready for either PaddleOCR or Tesseract.
    """
    if upscale > 1:
        h, w = image.shape[:2]
        image = cv2.resize(
            image, (w * upscale, h * upscale), interpolation=cv2.INTER_CUBIC
        )

    # Grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Denoise (h=10 is mild; keeps text edges intact)
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    # Sharpen
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    sharpened = cv2.filter2D(denoised, -1, kernel)

    # CLAHE — adaptive contrast; better than global histogram equalization
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(sharpened)

    return enhanced
