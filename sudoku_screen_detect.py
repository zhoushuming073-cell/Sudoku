"""Locate a visible 9×9 Sudoku grid in a full-screen screenshot."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class GridDetection:
    box: tuple[int, int, int, int]
    score: float


def _line_score(ink: np.ndarray, box: tuple[int, int, int, int]) -> float:
    x0, y0, x1, y1 = box
    width, height = x1 - x0, y1 - y0
    margin = max(2, min(width, height) // 45)
    horizontal, vertical = [], []
    for index in range(10):
        y = round(y0 + index * (height - 1) / 9)
        x = round(x0 + index * (width - 1) / 9)
        rows = ink[max(0, y-margin):min(ink.shape[0], y+margin+1), x0:x1]
        cols = ink[y0:y1, max(0, x-margin):min(ink.shape[1], x+margin+1)]
        horizontal.append(float(np.max(np.mean(rows > 0, axis=1))))
        vertical.append(float(np.max(np.mean(cols > 0, axis=0))))
    if (sum(value >= .55 for value in horizontal) < 8 or
            sum(value >= .55 for value in vertical) < 8):
        return 0.0
    return (sum(horizontal) + sum(vertical)) / 20


def detect_grid(image: Image.Image,
                preferred_box: tuple[int, int, int, int] | None = None) -> GridDetection | None:
    """Find regular ten-line grids; coordinates are physical screenshot pixels."""
    raw = np.asarray(image.convert("RGB"))
    height, width = raw.shape[:2]
    if min(width, height) < 400:
        return None
    scale = min(1.0, 1600 / max(width, height))
    reduced = cv2.resize(raw, (round(width * scale), round(height * scale)),
                         interpolation=cv2.INTER_AREA) if scale < 1 else raw
    gray = cv2.cvtColor(reduced, cv2.COLOR_RGB2GRAY)
    ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY_INV, 31, 8)
    kernel_size = max(18, min(gray.shape) // 38)
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                                  cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, 1)))
    vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (1, kernel_size)))
    lines = cv2.dilate(cv2.bitwise_or(horizontal, vertical), np.ones((3, 3), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(lines, 8)
    candidates = []
    for x, y, bw, bh, area in stats[1:count]:
        side = min(bw, bh)
        if (side < 180 or side > min(gray.shape) * .96 or
                not .78 <= bw / bh <= 1.28 or area < side * 2):
            continue
        box = (int(x), int(y), int(x + bw), int(y + bh))
        score = _line_score(ink, box)
        if score < .68:
            continue
        physical_box = tuple(round(value / scale) for value in box)
        bonus = 0.0
        if preferred_box:
            cx = (physical_box[0] + physical_box[2]) / 2
            cy = (physical_box[1] + physical_box[3]) / 2
            px = (preferred_box[0] + preferred_box[2]) / 2
            py = (preferred_box[1] + preferred_box[3]) / 2
            distance = ((cx-px)**2 + (cy-py)**2)**.5
            bonus = .08 * max(0.0, 1 - distance / max(width, height))
        candidates.append(GridDetection(physical_box, score + bonus))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item.score, (item.box[2]-item.box[0]) *
                                             (item.box[3]-item.box[1])), reverse=True)
    if (not preferred_box and len(candidates) > 1 and
            candidates[0].score - candidates[1].score < .04):
        return None
    return candidates[0]

