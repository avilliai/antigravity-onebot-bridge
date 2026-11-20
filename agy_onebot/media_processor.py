# -*- coding: utf-8 -*-
"""Media Processor for QQ / OneBot Images and Multi-modal inputs.

Processes inbound QQ images:
- Size validation & boundary checking.
- Resizing long edges to keep token cost bounded and avoid buffer overflows.
- Animated GIF tiling (e.g. 3x2 frame grid) for models that only inspect single frames.
- Fallback gracefully when Pillow (PIL) is not installed.
"""

import base64
import io
import os
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageSequence
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# Default limits
DEFAULT_MAX_BYTES = 2 * 1024 * 1024  # 2 MiB
DEFAULT_MAX_LONG_EDGE = 1280
DEFAULT_GIF_FRAMES = 6


def detect_image_format(data: bytes) -> Optional[str]:
    """Detect image format from header bytes."""
    if not data or len(data) < 12:
        return None
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    return None


def normalize_image_bytes(
    raw_data: bytes,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_long_edge: int = DEFAULT_MAX_LONG_EDGE,
    gif_frames: int = DEFAULT_GIF_FRAMES,
) -> Tuple[bytes, str]:
    """Normalize image bytes for multimodal AI consumption.

    Returns (processed_bytes, mime_type).
    """
    if not raw_data:
        return b"", "image/jpeg"

    fmt = detect_image_format(raw_data) or "jpeg"
    mime = f"image/{fmt}"

    if not HAS_PIL:
        # Without PIL, return raw bytes if under limit
        return raw_data[:max_bytes], mime

    try:
        with Image.open(io.BytesIO(raw_data)) as img:
            # Handle animated GIF: tile selected frames into a composite grid
            if getattr(img, "is_animated", False) and img.n_frames > 1:
                return _tile_animated_gif(img, target_frames=gif_frames, tile_size=240)

            # Convert RGBA/P to RGB for JPEG compatibility if needed
            work_img = img
            if work_img.mode in ("RGBA", "LA") and fmt == "jpeg":
                background = Image.new("RGB", work_img.size, (255, 255, 255))
                background.paste(work_img, mask=work_img.split()[-1])
                work_img = background
            elif work_img.mode not in ("RGB", "RGBA"):
                work_img = work_img.convert("RGB")

            # Check dimensions and resize if long edge exceeds limit
            width, height = work_img.size
            long_edge = max(width, height)
            if long_edge > max_long_edge:
                scale = max_long_edge / float(long_edge)
                new_w = max(1, int(width * scale))
                new_h = max(1, int(height * scale))
                work_img = work_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Save to buffer
            buf = io.BytesIO()
            save_format = "JPEG" if fmt in ("jpeg", "jpg") else "PNG"
            work_img.save(buf, format=save_format, quality=85)
            result_bytes = buf.getvalue()

            out_mime = "image/jpeg" if save_format == "JPEG" else "image/png"
            return result_bytes, out_mime
    except Exception:
        # On processing error, fallback to raw data
        return raw_data[:max_bytes], mime


def _tile_animated_gif(
    img: "Image.Image",
    target_frames: int = 6,
    tile_size: int = 240,
) -> Tuple[bytes, str]:
    """Extract key frames from an animated GIF and tile them into a single contact grid."""
    total_frames = getattr(img, "n_frames", 1)
    frames_to_sample = min(target_frames, total_frames)

    indices = [
        int(i * (total_frames - 1) / max(1, frames_to_sample - 1))
        for i in range(frames_to_sample)
    ]

    sampled: List["Image.Image"] = []
    for idx in indices:
        img.seek(idx)
        frame = img.convert("RGB")
        frame.thumbnail((tile_size, tile_size), Image.Resampling.BILINEAR)
        sampled.append(frame)

    # 3 columns layout
    cols = min(3, len(sampled))
    rows = (len(sampled) + cols - 1) // cols
    w, h = sampled[0].size
    grid_img = Image.new("RGB", (cols * w, rows * h), (240, 240, 240))

    for idx, f in enumerate(sampled):
        c = idx % cols
        r = idx // cols
        grid_img.paste(f, (c * w, r * h))

    buf = io.BytesIO()
    grid_img.save(buf, format="JPEG", quality=80)
    return buf.getvalue(), "image/jpeg"


def bytes_to_data_uri(data: bytes, mime: str = "image/jpeg") -> str:
    """Encode image bytes into data URI string."""
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"
