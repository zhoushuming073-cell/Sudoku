"""Grid rectification and printed-digit OCR for photographed/screenshotted Sudoku."""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageDraw, ImageFont


@dataclass
class OCRResult:
    board: list[int]
    confidence: list[float]
    warped: np.ndarray
    uncertain: list[int]


def configure_tesseract() -> None:
    explicit = os.environ.get("TESSERACT_CMD")
    if explicit:
        pytesseract.pytesseract.tesseract_cmd = explicit
    elif getattr(sys, "frozen", False) and (bundled := Path(sys._MEIPASS) / "tesseract" / "tesseract.exe").exists():
        pytesseract.pytesseract.tesseract_cmd = str(bundled)
        os.environ["TESSDATA_PREFIX"] = str(bundled.parent / "tessdata")
    elif shutil.which("tesseract"):
        pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract")
    elif os.name == "nt":
        usual = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if usual.exists():
            pytesseract.pytesseract.tesseract_cmd = str(usual)
    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        raise RuntimeError(
            "找不到Tesseract OCR。请先安装Tesseract，并将其加入PATH，"
            "或设置环境变量 TESSERACT_CMD 指向tesseract.exe。"
        ) from exc


def _order_corners(points: np.ndarray) -> np.ndarray:
    p = points.astype(np.float32).reshape(4, 2)
    s = p.sum(axis=1)
    d = np.diff(p, axis=1).ravel()
    return np.array([p[np.argmin(s)], p[np.argmin(d)],
                     p[np.argmax(s)], p[np.argmax(d)]], dtype=np.float32)


def rectify_grid(image: np.ndarray, size: int = 900) -> np.ndarray:
    """Use large, nearly-square quadrilateral; fall back to the image bounds."""
    if image is None or image.size == 0:
        raise ValueError("无法读取图片，请选择PNG、JPG或BMP图片。")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    inverted = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY_INV, 31, 9)
    contours, _ = cv2.findContours(inverted, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape
    quadrilaterals = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 0.15 * h * w:
            continue
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.024 * perimeter, True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue
        x, y, bw, bh = cv2.boundingRect(polygon)
        if not 0.68 < bw / max(bh, 1) < 1.45:
            continue
        quadrilaterals.append((area, polygon.reshape(4, 2)))

    if quadrilaterals:
        corners = _order_corners(max(quadrilaterals, key=lambda x: x[0])[1])
    else:
        # Straight-on screenshots frequently occupy virtually the entire frame.
        # The fallback deliberately stays conservative for arbitrary photos.
        margin = round(min(h, w) * 0.012)
        side = min(h, w) - 2 * margin
        left, top = (w - side) // 2, (h - side) // 2
        corners = np.array([[left, top], [left+side, top],
                            [left+side, top+side], [left, top+side]], dtype=np.float32)

    target = np.array([[0, 0], [size - 1, 0],
                       [size - 1, size - 1], [0, size - 1]], dtype=np.float32)
    transform = cv2.getPerspectiveTransform(corners, target)
    return cv2.warpPerspective(image, transform, (size, size), flags=cv2.INTER_CUBIC)


def _digit_patch(cell: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    margin = int(min(h, w) * 0.15)
    interior = gray[margin:h-margin, margin:w-margin]
    if interior.size == 0:
        return None
    _, binary = cv2.threshold(interior, 0, 255,
                              cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    components = []
    for idx in range(1, n):
        x, y, cw, ch, area = stats[idx]
        if (area >= interior.size * 0.006 and
                ch > interior.shape[0] * 0.25 and
                cw < interior.shape[1] * 0.85):
            components.append((area, (x, y, cw, ch)))
    if not components:
        return None
    _, (x, y, cw, ch) = max(components)
    patch = binary[y:y+ch, x:x+cw]
    # Tesseract is much more stable with a centered, high-resolution glyph.
    ratio = min(100 / max(cw, 1), 116 / max(ch, 1))
    patch = cv2.resize(patch, (max(1, round(cw*ratio)), max(1, round(ch*ratio))),
                       interpolation=cv2.INTER_CUBIC)
    canvas = np.zeros((144, 144), dtype=np.uint8)
    py = (144 - patch.shape[0]) // 2
    px = (144 - patch.shape[1]) // 2
    canvas[py:py+patch.shape[0], px:px+patch.shape[1]] = patch
    return 255 - canvas


def _normalize_glyph(image: np.ndarray) -> np.ndarray:
    """Normalize a single black-on-white glyph to a common 64x88 canvas."""
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, foreground = cv2.threshold(image, 150, 255, cv2.THRESH_BINARY_INV)
    ys, xs = np.where(foreground > 0)
    if not len(xs):
        return np.zeros((88, 64), dtype=np.uint8)
    crop = foreground[ys.min():ys.max()+1, xs.min():xs.max()+1]
    target_w, target_h = 52, 76
    scale = min(target_w/crop.shape[1], target_h/crop.shape[0])
    new_w, new_h = max(1, round(crop.shape[1]*scale)), max(1, round(crop.shape[0]*scale))
    scaled = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_AREA)
    _, scaled = cv2.threshold(scaled, 120, 255, cv2.THRESH_BINARY)
    canvas = np.zeros((88, 64), dtype=np.uint8)
    x, y = (64-new_w)//2, (88-new_h)//2
    canvas[y:y+new_h, x:x+new_w] = scaled
    return canvas


_TEMPLATE_CACHE: list[tuple[int, np.ndarray]] | None = None


def _templates() -> list[tuple[int, np.ndarray]]:
    """Generate printed digits locally; no model downloads or online API."""
    global _TEMPLATE_CACHE
    if _TEMPLATE_CACHE is not None:
        return _TEMPLATE_CACHE
    fonts = [
        "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
        "/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    available = [font for font in fonts if Path(font).exists()]
    generated = []
    for path in available:
        font = ImageFont.truetype(path, 110)
        for digit in range(1, 10):
            tile = Image.new("L", (160, 160), 255)
            drawer = ImageDraw.Draw(tile)
            drawer.text((20, -1), str(digit), fill=0, font=font)
            normalized = _normalize_glyph(np.array(tile))
            for delta in (-1, 0, 1):
                kernel = np.ones((2, 2), np.uint8)
                variant = (cv2.dilate(normalized, kernel, iterations=1) if delta == 1 else
                           cv2.erode(normalized, kernel, iterations=1) if delta == -1 else normalized)
                generated.append((digit, variant))
    _TEMPLATE_CACHE = generated
    return generated


def _match_printed_digit(patch: np.ndarray) -> tuple[int, float]:
    """Nearest template by ink mask overlap; best for crisp printed screens."""
    sample = _normalize_glyph(patch) > 0
    best_digit, best_score = 0, -1.0
    for digit, template in _templates():
        other = template > 0
        intersection = np.count_nonzero(sample & other)
        union = np.count_nonzero(sample | other)
        score = intersection / max(union, 1)
        if score > best_score:
            best_digit, best_score = digit, score
    return best_digit, best_score


def _read_digit(patch: np.ndarray) -> tuple[int, float]:
    config = "--oem 3 --psm 10 -c tessedit_char_whitelist=123456789"
    data = pytesseract.image_to_data(patch, config=config,
                                    output_type=pytesseract.Output.DICT)
    possibilities = []
    for text, conf in zip(data["text"], data["conf"]):
        match = re.search(r"[1-9]", str(text))
        if match:
            possibilities.append((int(match.group()), max(0.0, float(conf))))
    tesseract_digit, tesseract_conf = max(possibilities, key=lambda pair: pair[1]) if possibilities else (0, 0.0)
    template_digit, similarity = _match_printed_digit(patch)

    # Robust printed-font matching generally beats Tesseract on isolated thin
    # digits (especially 4/5/6/9). Keep a high-confidence OCR result when the
    # template similarity is weak; mark disagreements for manual inspection.
    if similarity >= 0.43:
        if tesseract_digit and tesseract_digit != template_digit and tesseract_conf >= 85:
            return tesseract_digit, min(tesseract_conf, 50.0)
        return template_digit, 90.0 if similarity >= 0.63 else 60.0
    if tesseract_digit:
        return tesseract_digit, min(tesseract_conf, 54.0)
    return 0, 0.0


def recognize_image(path: str) -> OCRResult:
    raw = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    return recognize_frame(image)


def recognize_pil_image(image: Image.Image) -> OCRResult:
    frame = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    return recognize_frame(frame)


def recognize_frame(image: np.ndarray) -> OCRResult:
    configure_tesseract()
    warped = rectify_grid(image)
    board, confidence, uncertain = [], [], []
    cell_size = warped.shape[0] // 9
    for row in range(9):
        for col in range(9):
            cell = warped[row*cell_size:(row+1)*cell_size,
                          col*cell_size:(col+1)*cell_size]
            patch = _digit_patch(cell)
            if patch is None:
                board.append(0)
                confidence.append(100.0)
                continue
            number, score = _read_digit(patch)
            board.append(number)
            confidence.append(score)
            if score < 55.0:
                uncertain.append(row*9+col)
    return OCRResult(board, confidence, warped, uncertain)
