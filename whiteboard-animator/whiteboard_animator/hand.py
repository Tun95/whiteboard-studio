"""Optional drawing hand that follows the pen tip while the image is revealed."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

HANDS_DIR = Path(__file__).parent / "hands"
BUILTIN = ("doodle", "brown", "dark", "light")
DEFAULT_TIP = (32, 251)  # pen-tip pixel inside the bundled 480x342 hand PNGs
TIPS = {"doodle": (4, 101)}  # pen-tip pixel inside the 720x476 "doodle" hand


class Hand:
    """An RGBA hand image whose pen tip is drawn at the current ink position."""

    def __init__(self, image: str | Path | None = None, tip: tuple[float, float] | None = None,
                 scale: float = 1.0):
        name = str(image) if image else "doodle"
        if name in BUILTIN:
            path, default_tip = HANDS_DIR / f"hand-{name}.png", TIPS.get(name, DEFAULT_TIP)
        else:
            path, default_tip = Path(name), (0, 0)
            if tip is None:
                raise ValueError("a custom hand image needs --hand-tip X,Y (pen-tip pixel in the image)")
        with Image.open(path) as im:
            self._rgba = im.convert("RGBA")
        self._tip = tuple(tip) if tip is not None else default_tip
        self.scale = scale
        self._cache: dict[int, tuple[np.ndarray, np.ndarray, tuple[int, int]]] = {}

    def _prepared(self, frame_w: int):
        # Hand is about 26% of the frame width at scale 1.0.
        if frame_w in self._cache:
            return self._cache[frame_w]
        target_w = max(40, int(frame_w * 0.26 * self.scale))
        k = target_w / self._rgba.width
        im = self._rgba.resize((target_w, max(1, int(self._rgba.height * k))), Image.LANCZOS)
        arr = np.asarray(im).astype(np.float32)
        rgb, alpha = arr[..., :3], arr[..., 3:4] / 255.0
        tip = (int(self._tip[0] * k), int(self._tip[1] * k))
        self._cache[frame_w] = (rgb, alpha, tip)
        return self._cache[frame_w]

    def paste(self, frame: np.ndarray, x: float, y: float):
        """Blend the hand into frame (in place) with its pen tip at (x, y).

        Returns (slice_y, slice_x, saved_pixels) so the caller can undo it.
        """
        rgb, alpha, (tx, ty) = self._prepared(frame.shape[1])
        hh, ww = rgb.shape[:2]
        x0, y0 = int(round(x)) - tx, int(round(y)) - ty
        fx0, fy0 = max(x0, 0), max(y0, 0)
        fx1, fy1 = min(x0 + ww, frame.shape[1]), min(y0 + hh, frame.shape[0])
        if fx1 <= fx0 or fy1 <= fy0:
            return None
        sy, sx = slice(fy0, fy1), slice(fx0, fx1)
        hy, hx = slice(fy0 - y0, fy1 - y0), slice(fx0 - x0, fx1 - x0)
        saved = frame[sy, sx].copy()
        a = alpha[hy, hx]
        frame[sy, sx] = (saved.astype(np.float32) * (1 - a) + rgb[hy, hx] * a).astype(np.uint8)
        return sy, sx, saved
