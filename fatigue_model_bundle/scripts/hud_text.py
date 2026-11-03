"""Draw readable mixed Chinese/English HUD text onto OpenCV BGR frames."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HUD_FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
)


@lru_cache(maxsize=8)
def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in HUD_FONT_CANDIDATES:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    raise RuntimeError(
        "No font with Chinese glyph support found. "
        "Install Microsoft YaHei, SimHei, Noto Sans CJK, or WenQuanYi."
    )


def draw_hud_panel(
    frame: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    *,
    panel_alpha: float = 0.45,
) -> None:
    """Darken a rectangular HUD region to match the text backing panel."""
    h, w = frame.shape[:2]
    x1 = max(0, min(int(x1), w))
    y1 = max(0, min(int(y1), h))
    x2 = max(x1, min(int(x2), w))
    y2 = max(y1, min(int(y2), h))
    if x1 == x2 or y1 == y2:
        return

    panel = frame[y1:y2, x1:x2]
    cv2.convertScaleAbs(panel, alpha=panel_alpha, dst=panel)


def put_cjk_lines(
    frame: np.ndarray,
    lines: list[tuple[str, tuple[int, int, int]]],
    *,
    x: int = 12,
    y: int = 8,
    line_height: int = 18,
    font_size: int = 15,
    panel_alpha: float = 0.45,
) -> None:
    """Draw text lines with a dark backing panel, using BGR input colors."""
    if not lines:
        return

    font = _load_font(font_size)
    measuring_image = Image.new("RGB", (1, 1))
    measuring_draw = ImageDraw.Draw(measuring_image)
    text_width = max(
        (measuring_draw.textlength(text, font=font) for text, _ in lines),
        default=0,
    )
    panel_width = min(int(text_width) + x * 2, frame.shape[1])
    panel_height = min(line_height * len(lines) + y, frame.shape[0])
    draw_hud_panel(
        frame,
        0,
        0,
        panel_width,
        panel_height,
        panel_alpha=panel_alpha,
    )

    image = Image.fromarray(frame[:panel_height, :panel_width])
    draw = ImageDraw.Draw(image)
    text_y = y
    for text, color in lines:
        if text:
            rgb = (color[2], color[1], color[0])
            draw.text((x, text_y), text, font=font, fill=rgb)
        text_y += line_height
    frame[:panel_height, :panel_width] = np.asarray(image)


def put_cjk_texts(
    frame: np.ndarray,
    items: list[
        tuple[str, tuple[int, int], int, tuple[int, int, int], str]
    ],
) -> None:
    """Draw independently positioned CJK labels in one image conversion."""
    if not items:
        return

    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    anchors = {"left": "la", "center": "ma", "right": "ra"}

    for text, (x, y), font_size, color, align in items:
        if not text:
            continue
        font = _load_font(font_size)
        rgb = (color[2], color[1], color[0])
        draw.text(
            (x, y),
            text,
            font=font,
            fill=rgb,
            anchor=anchors.get(align, "la"),
        )

    frame[:] = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
