"""Generuje miniatury 7 typów skali Bristol (icons/bristol/type1-7.png)."""
import math
import os
from PIL import Image, ImageDraw

W, H, S = 256, 176, 4
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bristol")

BASE = (138, 90, 51, 255)
DARK = (93, 58, 30, 255)
LIGHT = (176, 122, 78, 255)
SHEEN = (225, 185, 140, 110)


def sc(box):
    return [c * S for c in box]


def render(fn):
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    fn(ImageDraw.Draw(img), img)
    return img.resize((W, H), Image.LANCZOS)


def blend(img, fn):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    fn(ImageDraw.Draw(layer))
    img.alpha_composite(layer)


def type1(d, img):
    for x, y, r, fill in [(58, 62, 15, BASE), (122, 50, 13, LIGHT), (186, 64, 16, BASE),
                          (76, 116, 14, LIGHT), (148, 112, 15, BASE), (206, 118, 12, BASE)]:
        d.ellipse(sc([x - r, y - r, x + r, y + r]), fill=fill)


def type2(d, img):
    for x, y in [(48, 88), (88, 82), (128, 92), (168, 84), (208, 90)]:
        d.ellipse(sc([x - 27, y - 27, x + 27, y + 27]), fill=BASE)


def type3(d, img):
    d.rounded_rectangle(sc([26, 62, 230, 114]), radius=26 * S, fill=BASE)
    for x1, y1, x2, y2 in [(70, 68, 78, 92), (118, 66, 112, 92), (168, 68, 176, 90),
                           (94, 96, 104, 110), (146, 96, 154, 110)]:
        d.line(sc([x1, y1, x2, y2]), fill=DARK, width=4 * S)


def type4(d, img):
    x = 40
    while x <= 216:
        y = 88 + 22 * math.sin(2 * math.pi * (x - 40) / 176)
        d.ellipse(sc([x - 13, y - 13, x + 13, y + 13]), fill=BASE)
        x += 5


def type5(d, img):
    d.rounded_rectangle(sc([28, 52, 98, 112]), radius=20 * S, fill=BASE)
    d.rounded_rectangle(sc([112, 72, 182, 132]), radius=22 * S, fill=LIGHT)
    d.rounded_rectangle(sc([168, 40, 232, 96]), radius=18 * S, fill=BASE)


def type6(d, img):
    for pts, fill in [([(40, 60), (62, 44), (84, 58), (96, 80), (78, 98), (52, 94), (34, 80)], BASE),
                      ([(120, 96), (142, 80), (168, 92), (176, 116), (152, 132), (126, 126)], LIGHT),
                      ([(176, 44), (200, 32), (224, 48), (228, 70), (204, 82), (180, 70)], BASE)]:
        d.polygon(sc([c for p in pts for c in p]), fill=fill)


def type7(d, img):
    d.ellipse(sc([28, 92, 228, 142]), fill=BASE)
    blend(img, lambda ld: ld.ellipse(sc([48, 100, 150, 116]), fill=SHEEN))
    for x, y, r in [(64, 72, 6), (128, 60, 7), (192, 74, 5)]:
        d.ellipse(sc([x - r, y - r, x + r, y + r]), fill=BASE)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for i, fn in enumerate([type1, type2, type3, type4, type5, type6, type7], start=1):
        path = os.path.join(OUT, f"type{i}.png")
        render(fn).save(path)
        print("zapisano", path)