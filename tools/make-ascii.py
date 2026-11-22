import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "assets" / "ascii-art.png"
TEXT = ROOT / "assets" / "ascii.txt"

CELL_W, CELL_H = 5, 9
SUPERSAMPLE = 4
POOL = "".join(chr(c) for c in range(33, 127))
FONT_SETS = (("consola.ttf", "consolab.ttf"), ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf"))
MIN_COVERAGE = 0.1
MAX_STROKE = 0.11
MAX_TILT = 0.16
TWIN_RANGE = 0.02
GLYPH_GAMMA = 0.8
TONE_GAMMA = 1.0
STROKE_BOOST = 1.6
INK = np.array([0xF4, 0xF6, 0xF8], np.float32) / 255


def load_fonts(size):
    for names in FONT_SETS:
        try:
            return [ImageFont.truetype(n, size) for n in names]
        except OSError:
            continue
    raise SystemExit("no monospace font found: install Consolas or DejaVu Sans Mono")


def glyph_tiles():
    tw, th = CELL_W * SUPERSAMPLE, CELL_H * SUPERSAMPLE
    glyphs = []
    for font in load_fonts(240):
        advance = int(np.ceil(font.getlength("M")))
        cap = -font.getbbox("H", anchor="ls")[1]
        base = int(cap * 1.4)
        for ch in POOL:
            im = Image.new("L", (advance, int(cap * 1.8)), 0)
            ImageDraw.Draw(im).text((0, base), ch, font=font, fill=255, anchor="ls")
            a = np.asarray(im.crop((0, base - cap, advance, base)).resize((tw, th), Image.LANCZOS), np.float32) / 255
            a = 1 - (1 - a) ** STROKE_BOOST
            profile = a.mean(axis=1)
            cov = float(profile.mean())
            if cov < MIN_COVERAGE:
                continue
            spectrum = np.abs(np.fft.rfft(profile - cov)) / len(profile) / cov
            if np.sqrt((spectrum[2:] ** 2).sum()) > MAX_STROKE or spectrum[1] > MAX_TILT:
                continue
            glyphs.append((cov, ch, a))
    glyphs.sort(key=lambda g: g[0])
    return glyphs


def largest_region(mask):
    w, h = mask.size
    px = mask.load()
    seen = bytearray(w * h)
    best = []
    for sy in range(h):
        for sx in range(w):
            if px[sx, sy] and not seen[sy * w + sx]:
                stack, blob = [(sx, sy)], []
                seen[sy * w + sx] = 1
                while stack:
                    x, y = stack.pop()
                    blob.append((x, y))
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if 0 <= nx < w and 0 <= ny < h and px[nx, ny] and not seen[ny * w + nx]:
                            seen[ny * w + nx] = 1
                            stack.append((nx, ny))
                if len(blob) > len(best):
                    best = blob
    out = Image.new("L", mask.size, 0)
    op = out.load()
    for x, y in best:
        op[x, y] = 255
    return out


def blur(a, radius):
    im = Image.fromarray(np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius))
    return np.asarray(im, np.float32) / 255


def photo_subject(path):
    src = Image.open(path).convert("RGBA")
    if src.getextrema()[3][0] == 255:
        mask = Image.new("L", src.size, 255)
    else:
        a = src.getchannel("A").point(lambda p: 255 if p > 110 else 0)
        a = a.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))
        mask = largest_region(a).filter(ImageFilter.GaussianBlur(1.2))
    box = mask.point(lambda p: 255 if p > 20 else 0).getbbox() or (0, 0, *src.size)
    src, mask = src.crop(box), mask.crop(box)

    scale = 4
    size = (src.width * scale, src.height * scale)
    gray = src.convert("RGB").convert("L").filter(ImageFilter.MedianFilter(3))
    g = np.asarray(gray.resize(size, Image.LANCZOS), np.float32) / 255
    m = np.asarray(mask.resize(size, Image.LANCZOS), np.float32) / 255

    lo, hi = np.percentile(g[m > 0.5], [1.0, 99.6])
    g = np.clip((g - lo) / max(hi - lo, 1e-3), 0, 1)
    g = np.clip(g + 0.55 * (g - blur(g, 7 * scale)), 0, 1)
    g = np.clip(g + 0.9 * (blur(g, 0.7 * scale) - blur(g, 2.2 * scale)), 0, 1)
    g = 0.14 + 0.86 * g ** 0.85
    return g, m


def word_subject():
    w, h = 900, 1000
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    font = load_fonts(420)[1]
    for i, part in enumerate(("AS", "IL")):
        d.text((w / 2, h * (0.27 + i * 0.48)), part, font=font, fill=255, anchor="mm")
    m = np.asarray(img, np.float32) / 255
    shade = np.linspace(1.0, 0.55, h, dtype=np.float32)[:, None]
    return m * shade, m


def tone_grid(g, m, cols):
    rows = round(cols * g.shape[0] / g.shape[1] * CELL_W / CELL_H)
    num = np.asarray(Image.fromarray((g * m).astype(np.float32)).resize((cols, rows), Image.BOX))
    cover = np.asarray(Image.fromarray(m.astype(np.float32)).resize((cols, rows), Image.BOX))
    tone = np.where(cover > 1e-3, num / np.maximum(cover, 1e-3), 0)
    return np.clip(tone, 0, 1), np.clip(cover, 0, 1)


def render(tone, cover):
    glyphs = glyph_tiles()
    covs = np.array([g[0] for g in glyphs], np.float32)
    lo, hi = float(covs[0]), float(covs[-1])
    rows, cols = tone.shape
    tw, th = CELL_W * SUPERSAMPLE, CELL_H * SUPERSAMPLE
    rgba = np.zeros((rows * CELL_H, cols * CELL_W, 4), np.float32)
    lines = []
    for y in range(rows):
        alpha = np.zeros((th, cols * tw), np.float32)
        light = np.zeros((th, cols * tw), np.float32)
        line = []
        for x in range(cols):
            k, t = cover[y, x], tone[y, x]
            if k < 0.25:
                line.append(" ")
                continue
            target = lo + (hi - lo) * t ** GLYPH_GAMMA
            twins = np.flatnonzero(np.abs(covs - target) <= TWIN_RANGE)
            if twins.size == 0:
                twins = [int(np.abs(covs - target).argmin())]
            cov, ch, tile = glyphs[twins[(x * 7 + y * 13) % len(twins)]]
            line.append(ch)
            ink = min(1.0, hi * t ** TONE_GAMMA / cov)
            a = tile * min(1.0, (k - 0.25) / 0.5)
            alpha[:, x * tw:(x + 1) * tw] = a
            light[:, x * tw:(x + 1) * tw] = a * ink
        lines.append("".join(line).rstrip())
        a_small = alpha.reshape(CELL_H, SUPERSAMPLE, cols * CELL_W, SUPERSAMPLE).mean(axis=(1, 3))
        l_small = light.reshape(CELL_H, SUPERSAMPLE, cols * CELL_W, SUPERSAMPLE).mean(axis=(1, 3))
        band = slice(y * CELL_H, (y + 1) * CELL_H)
        rgba[band, :, 3] = a_small
        shade = np.where(a_small > 1e-4, l_small / np.maximum(a_small, 1e-4), 0)
        rgba[band, :, :3] = shade[..., None] * INK

    used_rows = [i for i, l in enumerate(lines) if l.strip()]
    lead = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
    width = max(len(l) for l in lines)
    r0, r1 = used_rows[0], used_rows[-1] + 1
    rgba = rgba[r0 * CELL_H:r1 * CELL_H, lead * CELL_W:width * CELL_W]
    text = [l[lead:] for l in lines[r0:r1]]
    img = Image.fromarray(np.clip(rgba * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA")
    return img, text


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("photo", nargs="?")
    ap.add_argument("--cols", type=int, default=150)
    args = ap.parse_args()

    g, m = photo_subject(args.photo) if args.photo else word_subject()
    tone, cover = tone_grid(g, m, args.cols)
    img, text = render(tone, cover)
    ART.parent.mkdir(exist_ok=True)
    img.save(ART, optimize=True)
    TEXT.write_text("\n".join(text) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(text)} rows x {max(map(len, text))} cols, {img.width}x{img.height}px -> {ART}")
