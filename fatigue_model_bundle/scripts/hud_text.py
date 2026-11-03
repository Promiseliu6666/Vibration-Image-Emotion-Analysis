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
    panel = frame[:panel_height, :panel_width]
    cv2.convertScaleAbs(panel, alpha=panel_alpha, dst=panel)

    image = Image.fromarray(panel)
    draw = ImageDraw.Draw(image)
    text_y = y
    for text, color in lines:
        if text:
            rgb = (color[2], color[1], color[0])
            draw.text((x, text_y), text, font=font, fill=rgb)
        text_y += line_height
    panel[:] = np.asarray(image)
