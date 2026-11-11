"""Generuje propozycje ikon aplikacji BM Reporter (PNG 1024x1024)."""
import os
import numpy as np
from PIL import Image, ImageDraw

SIZE = 1024
MARGIN = 51
TILE = SIZE - 2 * MARGIN
RADIUS = 220
OUT = os.path.dirname(os.path.abspath(__file__))


def gradient_tile(c1, c2):
    t = np.linspace(0, 1, TILE)[:, None, None]
    arr = np.array(c1)[None, None, :] * (1 - t) + np.array(c2)[None, None, :] * t
    arr = np.broadcast_to(arr, (TILE, TILE, 3))
    img = Image.fromarray(arr.astype("uint8")).convert("RGBA")
    mask = Image.new("L", (TILE, TILE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, TILE - 1, TILE - 1], radius=RADIUS, fill=255)
    img.putalpha(mask)
    return img


def canvas(c1, c2):
    base = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    base.alpha_composite(gradient_tile(c1, c2), (MARGIN, MARGIN))
    return base, ImageDraw.Draw(base)


def cap(d, xy, r, fill):
    d.ellipse([xy[0] - r, xy[1] - r, xy[0] + r, xy[1] + r], fill=fill)


def blend(img, fn):
    """ImageDraw nie miesza alfa — polprzezroczyste ksztalty rysujemy na osobnej warstwie."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    fn(ImageDraw.Draw(layer))
    img.alpha_composite(layer)


def icon_medyczna():
    img, d = canvas((20, 184, 166), (13, 148, 136))
    w, white = 70, (255, 255, 255, 255)
    d.line([(320, 340), (704, 340)], fill=white, width=w)
    d.arc([583, 305, 825, 547], -90, 90, fill=white, width=w)
    d.line([(704, 512), (320, 512)], fill=white, width=w)
    d.arc([199, 477, 441, 719], 90, 270, fill=white, width=w)
    d.line([(320, 684), (704, 684)], fill=white, width=w)
    cap(d, (320, 340), w // 2, white)
    cap(d, (704, 684), w // 2, white)
    return img


def swirl_layers(img, d, shaded):
    layers = [(512, 640, 260, 110), (512, 520, 190, 95), (512, 415, 120, 80), (540, 322, 52, 42)]
    if shaded:
        blend(img, lambda ld: ld.ellipse([232, 720, 792, 800], fill=(60, 40, 30, 60)))
    for cx, cy, rx, ry in layers:
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(169, 113, 75, 255))
        if shaded:
            d.ellipse([cx - rx * 0.72, cy - ry * 0.95, cx + rx * 0.45, cy - ry * 0.05],
                      fill=(201, 154, 107, 255))
            blend(img, lambda ld: ld.ellipse([cx - rx * 0.45, cy - ry * 0.8, cx - rx * 0.05, cy - ry * 0.35],
                                             fill=(255, 235, 210, 110)))


def icon_maskotka():
    img, d = canvas((253, 243, 216), (250, 236, 195))
    swirl_layers(img, d, shaded=False)
    dark = (60, 40, 30, 255)
    cap(d, (430, 620), 22, dark)
    cap(d, (594, 620), 22, dark)
    d.arc([462, 600, 562, 680], 20, 160, fill=dark, width=14)
    blend(img, lambda ld: cap(ld, (366, 662), 26, (244, 160, 160, 160)))
    blend(img, lambda ld: cap(ld, (658, 662), 26, (244, 160, 160, 160)))
    return img


def icon_wykres():
    img, d = canvas((30, 41, 59), (15, 23, 42))
    bars = [(232, 220, (59, 142, 208)), (382, 340, (56, 163, 165)),
            (532, 460, (47, 165, 114)), (682, 400, (122, 199, 79))]
    for x, h, color in bars:
        d.rounded_rectangle([x, 760 - h, x + 110, 760], radius=45, fill=color + (255,))
    white = (255, 255, 255, 255)
    d.line([(560, 230), (600, 270), (668, 185)], fill=white, width=26, joint="curve")
    cap(d, (560, 230), 13, white)
    cap(d, (668, 185), 13, white)
    return img


def icon_3d():
    img, d = canvas((253, 232, 215), (230, 224, 248))
    swirl_layers(img, d, shaded=True)
    return img


if __name__ == "__main__":
    for name, fn in [("propozycja-1-medyczna", icon_medyczna),
                     ("propozycja-2-maskotka", icon_maskotka),
                     ("propozycja-3-wykres", icon_wykres),
                     ("propozycja-4-3d", icon_3d)]:
        img = fn()
        preview = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 255))
        preview.alpha_composite(img)
        path = os.path.join(OUT, name + ".png")
        preview.convert("RGB").save(path)
        print("zapisano", path)
        if name == "propozycja-2-maskotka":
            ico = os.path.join(OUT, "app.ico")
            img.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            print("zapisano", ico)