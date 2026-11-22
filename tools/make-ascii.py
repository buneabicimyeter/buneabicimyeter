import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

OUT = Path(__file__).resolve().parent.parent / "assets" / "ascii.txt"
SHADE_OUT = OUT.with_name("ascii-shade.txt")
SHADES = 10
CELL_ASPECT = 0.55

RAMP = " .'`,:;-~+=*?%#&$@"


def find_font(size):
    for name in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def word_image(cols, rows):
    w, h = cols * 10, int(rows * 10 / CELL_ASPECT)
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    font = find_font(int(h * 0.5))
    boxes = [d.textbbox((0, 0), part, font=font) for part in ("AS", "IL")]
    gap = h * 0.05
    y = (h - sum(b[3] - b[1] for b in boxes) - gap) / 2
    for part, box in zip(("AS", "IL"), boxes):
        d.text(((w - (box[2] - box[0])) / 2 - box[0], y - box[1]), part, font=font, fill=255)
        y += box[3] - box[1] + gap
    light = Image.linear_gradient("L").rotate(-35).resize((w, h))
    light = ImageOps.autocontrast(light).point(lambda p: 110 + p * 145 // 255)
    return Image.composite(light, Image.new("L", (w, h)), img)


def subject_mask(img):
    if img.mode != "RGBA" or img.getextrema()[3][0] == 255:
        return Image.new("L", img.size, 255)
    a = img.getchannel("A").point(lambda p: 255 if p > 110 else 0)
    a = a.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))
    return largest_region(a).filter(ImageFilter.GaussianBlur(1.2))


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


def photo_image(path, cols):
    src = Image.open(path)
    src = src.convert("RGBA") if "A" in src.getbands() else src.convert("RGB")
    mask = subject_mask(src)
    box = mask.point(lambda p: 255 if p > 20 else 0).getbbox() or (0, 0, *src.size)
    src, mask = src.crop(box), mask.crop(box)

    scale = max(1, 1400 // max(src.size))
    size = (src.width * scale, src.height * scale)
    gray = src.convert("RGB").convert("L").resize(size, Image.LANCZOS)
    mask = mask.resize(size, Image.LANCZOS)

    tone = ImageOps.autocontrast(gray, cutoff=1, mask=mask)
    tone = Image.blend(ImageOps.equalize(tone, mask=mask), tone, 0.6).point(lambda p: int(255 * (p / 255) ** 0.95))

    soft = gray.filter(ImageFilter.GaussianBlur(1.5 * scale))
    edges = ImageChops.add(
        soft.filter(ImageFilter.FIND_EDGES), soft.filter(ImageFilter.Kernel((3, 3), [-1, -1, -1, -1, 8, -1, -1, -1, -1], 1))
    )
    edges = ImageOps.autocontrast(edges, cutoff=2, mask=mask).point(lambda p: int(p * 0.35))
    outline = ImageOps.autocontrast(mask.filter(ImageFilter.FIND_EDGES)).point(lambda p: int(p * 0.5))

    detail = ImageChops.add(ImageChops.add(tone.point(lambda p: int(p * 0.9)), edges), outline)
    detail = detail.point(lambda p: max(18, p))
    detail = Image.composite(detail, Image.new("L", size, 0), mask)
    detail = detail.filter(ImageFilter.UnsharpMask(radius=2 * scale, percent=140, threshold=2))

    rows = round(cols * size[1] / size[0] * CELL_ASPECT)
    return detail, rows


def to_ascii(img, cols, rows):
    small = img.resize((cols, rows), Image.BOX)
    px = small.load()
    n = len(RAMP) - 1
    glyphs, shades = [], []
    for y in range(rows):
        g = "".join(RAMP[round(px[x, y] * n / 255)] for x in range(cols)).rstrip()
        glyphs.append(g)
        shades.append("".join(str(min(SHADES - 1, px[x, y] * SHADES // 256)) for x in range(len(g))))
    while glyphs and not glyphs[-1].strip():
        glyphs.pop(), shades.pop()
    while glyphs and not glyphs[0].strip():
        glyphs.pop(0), shades.pop(0)
    pad = min(len(l) - len(l.lstrip()) for l in glyphs if l.strip())
    return [l[pad:] for l in glyphs], [l[pad:] for l in shades]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("photo", nargs="?")
    ap.add_argument("--cols", type=int, default=150)
    args = ap.parse_args()

    if args.photo:
        img, rows = photo_image(args.photo, args.cols)
        glyphs, shades = to_ascii(img, args.cols, rows)
    else:
        cols = 78
        rows = round(cols * CELL_ASPECT)
        glyphs, shades = to_ascii(word_image(cols, rows), cols, rows)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(glyphs) + "\n", encoding="utf-8", newline="\n")
    SHADE_OUT.write_text("\n".join(shades) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(glyphs)} lines x {max(map(len, glyphs))} cols -> {OUT}")
