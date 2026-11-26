"""Render crisp, compact TrueColor pixel-art AWS cloud logo from image 2.png."""

from collections import deque
from pathlib import Path

_FALLBACK_LOGO = (
    "\n      \x1b[38;5;208m▄████████▄\x1b[0m\n"
    "    \x1b[38;5;208m▄████████████▄\x1b[0m\n"
    "  \x1b[38;5;208m▄███\x1b[97;1;48;5;208m  aws  \x1b[0;38;5;208m██████▄\x1b[0m\n"
    " \x1b[38;5;208m█████\x1b[97;1;48;5;208m ╰───╯ \x1b[0;38;5;208m████████\x1b[0m\n"
    " \x1b[38;5;208m▀██████████████████▀\x1b[0m\n"
)


def _flood_outer_transparent(img, width: int, height: int) -> set[tuple[int, int]]:
    """Find all outer background pixels connected to image borders."""
    visited: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()

    def is_bg(x: int, y: int) -> bool:
        r, g, b, a = img.getpixel((x, y))
        return a < 128 or (r > 195 and g > 195 and b > 195)

    for x in range(width):
        for y in (0, height - 1):
            if is_bg(x, y):
                queue.append((x, y))
                visited.add((x, y))
    for y in range(height):
        for x in (0, width - 1):
            if (x, y) not in visited and is_bg(x, y):
                queue.append((x, y))
                visited.add((x, y))

    while queue:
        cx, cy = queue.popleft()
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited and is_bg(nx, ny):
                visited.add((nx, ny))
                queue.append((nx, ny))
    return visited


def _snap_pixel(r: int, g: int, b: int) -> tuple[int, int, int]:
    """Snap anti-aliased pixels to crisp AWS orange, white, or dark outline."""
    if r > 205 and g > 205 and b > 205:
        return (255, 255, 255)
    if r > 175 and g > 85 and b < 90:
        return (255, 153, 0)
    if r < 95 and g < 115 and b < 140:
        return (16, 42, 72)
    return (r, g, b)


def render_aws_logo(image_path: str | Path = "image 2.png", width: int = 44) -> str:
    """Convert image 2.png into crisp, compact TrueColor half-block pixel art."""
    path = Path(image_path)
    if not path.exists():
        return _FALLBACK_LOGO
    try:
        from PIL import Image
    except ImportError:
        return _FALLBACK_LOGO

    img = Image.open(path).convert("RGBA")
    height = round(img.height * (width / img.width))
    if height % 2 != 0:
        height += 1
    img = img.resize((width, height), Image.LANCZOS)
    outer_bg = _flood_outer_transparent(img, width, height)

    lines: list[str] = [""]
    for y in range(0, height, 2):
        row = [" "]
        for x in range(width):
            t1 = (x, y) in outer_bg
            t2 = (x, y + 1) in outer_bg
            r1, g1, b1, _ = img.getpixel((x, y))
            r2, g2, b2, _ = img.getpixel((x, y + 1))
            if not t1:
                r1, g1, b1 = _snap_pixel(r1, g1, b1)
            if not t2:
                r2, g2, b2 = _snap_pixel(r2, g2, b2)

            if t1 and t2:
                row.append("\x1b[0m ")
            elif not t1 and t2:
                row.append(f"\x1b[0m\x1b[38;2;{r1};{g1};{b1}m▀")
            elif t1 and not t2:
                row.append(f"\x1b[0m\x1b[38;2;{r2};{g2};{b2}m▄")
            else:
                row.append(f"\x1b[38;2;{r1};{g1};{b1};48;2;{r2};{g2};{b2}m▀")
        row.append("\x1b[0m")
        lines.append("".join(row))
    lines.append("")
    return "\n".join(lines)
