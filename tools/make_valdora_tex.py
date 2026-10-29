"""THE ANULMENT: procedural textures for Valdora (facades, shopfronts, sky, flags, placards, badge, phone, evidence cards).
All designs are original and fictional. Run: python3 tools/make_valdora_tex.py"""
import os, random, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "tex"); os.makedirs(OUT, exist_ok=True)
FB = os.path.join(os.path.dirname(__file__), "..", "assets", "ui_font.ttf")
FP = os.path.join(os.path.dirname(__file__), "..", "assets", "ui_plain.ttf")
def F(sz, bold=True): return ImageFont.truetype(FB if bold else FP, sz)
R = random.Random(7)

def noise(img, amt=18, blur=1):
    px = img.load(); w, h = img.size
    for _ in range(w * h // 3):
        x, y = R.randrange(w), R.randrange(h); c = px[x, y]; d = R.randint(-amt, amt)
        px[x, y] = tuple(max(0, min(255, v + d)) for v in c[:3]) + tuple(c[3:])
    return img.filter(ImageFilter.GaussianBlur(blur)) if blur else img

def facade(name, base, floors, cols, lit, style, day=False):
    """1024 px = 32 m wide, 28 m tall (matches the world UVs). Night: some windows lit warm / TV blue."""
    W, H = 1024, 896
    im = Image.new("RGB", (W, H), base); d = ImageDraw.Draw(im)
    fh = H / floors; cw = W / cols
    for f in range(floors):
        y0 = H - (f + 1) * fh
        d.line([(0, y0), (W, y0)], fill=tuple(int(c * 0.78) for c in base), width=3)   # panel joints
        for c in range(cols):
            x0 = c * cw
            if style == "panel":
                d.line([(x0, y0), (x0, y0 + fh)], fill=tuple(int(c_ * 0.85) for c_ in base), width=2)
                wx0, wy0, wx1, wy1 = x0 + cw * 0.18, y0 + fh * 0.25, x0 + cw * 0.82, y0 + fh * 0.78
                if R.random() < 0.18:   # enclosed balcony
                    d.rectangle([x0 + cw * 0.08, y0 + fh * 0.45, x0 + cw * 0.92, y0 + fh * 0.98], fill=tuple(int(c_ * 0.9) for c_ in base))
            elif style == "gov":
                wx0, wy0, wx1, wy1 = x0 + cw * 0.3, y0 + fh * 0.12, x0 + cw * 0.7, y0 + fh * 0.88
                d.rectangle([x0, y0, x0 + cw * 0.14, y0 + fh], fill=tuple(min(255, int(c_ * 1.08)) for c_ in base))  # pilasters
            else:   # old block (pre-war): tall windows with cornices
                wx0, wy0, wx1, wy1 = x0 + cw * 0.25, y0 + fh * 0.18, x0 + cw * 0.75, y0 + fh * 0.85
                d.rectangle([wx0 - 6, wy0 - 10, wx1 + 6, wy0 - 4], fill=tuple(min(255, int(c_ * 1.15)) for c_ in base))
            r = R.random()
            if day: col = (int(70 + 40 * R.random()), int(85 + 40 * R.random()), int(100 + 40 * R.random()))
            elif r < lit: col = R.choice([(255, 196, 120), (250, 214, 150), (255, 180, 100), (235, 225, 200)])
            elif r < lit + 0.05: col = (120, 160, 255)
            else: col = (int(18 + 14 * R.random()), int(20 + 14 * R.random()), int(26 + 14 * R.random()))
            d.rectangle([wx0, wy0, wx1, wy1], fill=col)
            if r < lit and R.random() < 0.6:   # curtains
                d.rectangle([wx0, wy0, wx0 + (wx1 - wx0) * 0.3, wy1], fill=tuple(int(v * 0.7) for v in col))
            d.line([((wx0 + wx1) / 2, wy0), ((wx0 + wx1) / 2, wy1)], fill=(40, 40, 44), width=3)
    # rain streaks / grime
    for _ in range(140):
        x = R.randrange(W); y = R.randrange(H); L = R.randint(40, 220)
        d.line([(x, y), (x + R.randint(-3, 3), y + L)], fill=tuple(int(c * 0.82) for c in base), width=R.randint(2, 6))
    noise(im, 10, 1).save(os.path.join(OUT, name + (".png")))

for k, (base, fl, cl, lit, st) in enumerate([((132, 132, 128), 10, 10, 0.28, "panel"), ((118, 120, 122), 10, 8, 0.22, "panel"),
                                             ((150, 140, 124), 7, 7, 0.32, "old"), ((140, 138, 134), 8, 9, 0.18, "gov"),
                                             ((105, 108, 112), 10, 12, 0.25, "panel"), ((160, 150, 136), 6, 6, 0.35, "old")]):
    R.seed(100 + k); facade("vfac%d" % k, base, fl, cl, lit, st)
    R.seed(100 + k); facade("vfac%d_day" % k, base, fl, cl, lit, st, day=True)

# shopfront strip: 1024 = 32 m, 0.15-4 m tall
SHOPS = ["BRUTĂRIA DOINA", "FARMACIA VERDE", "ALIMENTARA 24", "CAFENEA LUNA", "LIBRĂRIA NOUA", "CROITORIE", "POȘTA VALDORA",
         "BANCA CIVICĂ", "FLORĂRIE", "CHIOȘC ZIARE", "PATISERIA AMIRA", "BISTRO PIAȚA"]
im = Image.new("RGB", (2048, 256), (40, 40, 44)); d = ImageDraw.Draw(im)
for k in range(8):
    x0 = k * 256; open_ = k % 3 != 2
    d.rectangle([x0 + 6, 70, x0 + 250, 256], fill=(230, 190, 120) if open_ else (70, 72, 76))
    if open_:
        for s in range(4): d.rectangle([x0 + 20 + s * 58, 100, x0 + 60 + s * 58, 230], fill=(200, 160, 100))
    else:
        for y in range(80, 256, 10): d.line([(x0 + 6, y), (x0 + 250, y)], fill=(95, 97, 100), width=3)
    d.rectangle([x0 + 6, 10, x0 + 250, 62], fill=R.choice([(30, 60, 50), (60, 30, 36), (30, 40, 70), (50, 46, 40)]))
    t = SHOPS[k % len(SHOPS)]; f = F(26)
    while d.textlength(t, font=f) > 230: f = F(f.size - 2)
    d.text((x0 + 128, 36), t, font=f, fill=(245, 235, 210), anchor="mm")
im.save(os.path.join(OUT, "vshop.png"))

# overcast rainy night sky (equirect strip), low clouds lit orange from the city
W, H = 2048, 512; im = Image.new("RGB", (W, H)); px = im.load()
import random as _r
cl = Image.effect_noise((W // 8, H // 8), 64).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(6))
cp = cl.load()
for y in range(H):
    t = y / H   # 0 = top (zenith side of the v range), 1 = horizon
    for x in range(W):
        n = (cp[x, y] - 128) / 128.0
        r_ = 14 + 40 * t ** 2 + 10 * n; g_ = 16 + 30 * t ** 2 + 9 * n; b_ = 24 + 22 * t ** 2 + 8 * n
        px[x, y] = (int(max(0, r_)), int(max(0, g_)), int(max(0, b_)))
im = im.transpose(Image.FLIP_TOP_BOTTOM); im.save(os.path.join(OUT, "sky_valdora.jpg"), quality=90)

# Valdoran flag (invented): teal / white / burgundy bands with a gold ring of oak leaves
def flag(path, w=600, h=400):
    im = Image.new("RGB", (w, h)); d = ImageDraw.Draw(im)
    for k, c in enumerate([(18, 110, 120), (240, 240, 232), (120, 26, 44)]):
        d.rectangle([0, k * h // 3, w, (k + 1) * h // 3], fill=c)
    cx, cy, r = w * 0.32, h / 2, h * 0.26
    for a in range(0, 360, 30):
        x, y = cx + math.cos(math.radians(a)) * r, cy + math.sin(math.radians(a)) * r
        d.ellipse([x - 16, y - 9, x + 16, y + 9], fill=(214, 170, 40))
    d.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], fill=(214, 170, 40))
    im.save(path)
flag(os.path.join(OUT, "flag_valdora.png"))

# placards atlas (4 x 1), white boards with hand-painted text
TXT = ["FREE CLN", "GIVE US BACK\nOUR VOTE", "CLN\nPREȘEDINTE!", "TURUL DOI\nÎNAPOI!"]
im = Image.new("RGB", (2048, 512), (240, 238, 228)); d = ImageDraw.Draw(im)
for k, t in enumerate(TXT):
    x0 = k * 512
    d.rectangle([x0 + 8, 8, x0 + 504, 504], outline=(40, 40, 40), width=10, fill=(244, 240, 228) if k % 2 == 0 else (250, 232, 120))
    d.multiline_text((x0 + 256, 256), t, font=F(68 if "\n" in t else 100), fill=(160, 20, 30) if k != 1 else (20, 30, 110), anchor="mm", align="center", spacing=8)
im.save(os.path.join(OUT, "placards.png"))

# police badge + livery text (invented, no real crest)
im = Image.new("RGBA", (256, 256), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
pts = [(128 + 110 * math.cos(math.radians(a)) * (1 if k % 2 == 0 else 0.62), 128 + 110 * math.sin(math.radians(a)) * (1 if k % 2 == 0 else 0.62)) for k, a in enumerate(range(-90, 270, 30))]
d.polygon(pts, fill=(205, 175, 70)); d.ellipse([70, 70, 186, 186], fill=(20, 32, 70))
d.text((128, 118), "POLIȚIA", font=F(22), fill=(240, 230, 190), anchor="mm"); d.text((128, 144), "VALDOREI", font=F(20), fill=(240, 230, 190), anchor="mm")
im.save(os.path.join(OUT, "police_badge.png"))
im = Image.new("RGBA", (1024, 128), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.text((512, 64), "POLIȚIA VALDOREI", font=F(92), fill=(20, 40, 120, 255), anchor="mm"); im.save(os.path.join(OUT, "livery_police.png"))
im = Image.new("RGBA", (1024, 128), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.text((512, 64), "TAXI VALDORA", font=F(96), fill=(30, 30, 30, 255), anchor="mm"); im.save(os.path.join(OUT, "livery_taxi.png"))
im = Image.new("RGBA", (1024, 128), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.text((512, 64), "TRANSVAL  12", font=F(96), fill=(240, 240, 240, 255), anchor="mm"); im.save(os.path.join(OUT, "livery_bus.png"))
im = Image.new("RGBA", (1024, 128), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.text((512, 64), "CURIER RAPID", font=F(96), fill=(200, 40, 30, 255), anchor="mm"); im.save(os.path.join(OUT, "livery_van.png"))

# EX IX G10 phone body (585 x 1170 px, screen at (43,43) 479 x 1054 - same layout as the earlier EX IX phone art)
S = 2; im = Image.new("RGBA", (585 * S, 1170 * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.rounded_rectangle([4 * S, 4 * S, 581 * S, 1166 * S], radius=70 * S, fill=(26, 28, 34, 255), outline=(120, 124, 134, 255), width=5 * S)
d.rounded_rectangle([14 * S, 14 * S, 571 * S, 1156 * S], radius=60 * S, fill=(8, 8, 10, 255))
d.rounded_rectangle([43 * S, 43 * S, 522 * S, 1097 * S], radius=34 * S, fill=(0, 0, 0, 0))
d.ellipse([280 * S, 22 * S, 304 * S, 36 * S], fill=(30, 30, 40, 255))
f = ImageFont.truetype(FB, 26 * S); d.text((292 * S, 1130 * S), "EX IX G10", font=f, fill=(190, 196, 210, 255), anchor="mm")
im = im.resize((585, 1170), Image.LANCZOS); im.save(os.path.join(OUT, "phone_g10.png"))
im = Image.new("RGB", (479, 1054), (6, 8, 14)); d = ImageDraw.Draw(im)
d.text((240, 470), "EX", font=F(150), fill=(230, 232, 240), anchor="mm"); d.text((240, 590), "IX G10", font=F(64), fill=(120, 170, 255), anchor="mm")
d.text((240, 990), "EX Inc.", font=F(28, False), fill=(140, 140, 150), anchor="mm"); im.save(os.path.join(OUT, "phone_boot.png"))
im = Image.new("RGB", (479, 1054)); d = ImageDraw.Draw(im)
for y in range(1054): d.line([(0, y), (479, y)], fill=(int(14 + 20 * y / 1054), int(22 + 18 * y / 1054), int(40 + 30 * y / 1054)))
im.save(os.path.join(OUT, "phone_wall.png"))

# app icons (simple flat glyphs)
def icon(name, col, glyph):
    im = Image.new("RGBA", (128, 128), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([4, 4, 124, 124], radius=28, fill=col)
    d.text((64, 66), glyph, font=F(60 if len(glyph) < 2 else 40), fill=(255, 255, 255), anchor="mm"); im.save(os.path.join(OUT, "app_%s.png" % name))
for n, c, g in (("camera", (40, 44, 52), "◉" if False else "CAM"), ("messages", (40, 160, 90), "MSG"), ("news", (190, 60, 50), "NEWS"),
                ("map", (50, 110, 190), "MAP"), ("evidence", (170, 120, 30), "EVI"), ("recorder", (150, 40, 90), "REC"), ("settings", (90, 92, 100), "SET")):
    icon(n, c, g)

# evidence cards (what a photographed / recovered clue looks like in the gallery and on the board)
CARDS = {
    "ev_memo": ("MEMO - CONFIDENTIAL", ["To: Court Registry", "Re: 'Round one' file", "Annulment ruling drafted", "BEFORE the hearing.", "Dated 3 days early.", "- Office of the Chief Clerk"]),
    "ev_email": ("RECOVERED EMAIL", ["From: liaison@valmont-office", "To: alliance.secretariat", "Subj: the result", "'The Union expects the", "vote to be set aside.", "Funds follow compliance.'"]),
    "ev_ledger": ("LEDGER PAGE", ["Transfers - Reform Alliance", "Consultancy 'R.A. Media'", "  400,000 VAL", "Coalition 'Civic Fund'", "  250,000 VAL", "Source: Valmont account"]),
    "ev_photo": ("PHOTO - COURT CAR PARK", ["Judge's car beside a", "black van, 02:14.", "Plates: VAL-UNION-07", "Intelligence service", "pass on the dashboard.", ""]),
    "ev_script": ("STATE TV AUTOCUE", ["'CLN is a danger to", "the nation...'", "Approved 2 days before", "the court ruling.", "Signed: News Director", ""]),
    "ev_ballots": ("TALLY SHEETS", ["Polling stations 1-412", "CLN: 61.4%", "Reform Alliance: 18.2%", "Coalition: 11.9%", "Patriots' Front backs CLN", "All sheets stamped valid."]),
    "ev_recording": ("RECORDED INTERVIEW", ["Prosecutor's aide:", "'We were told the charge", "before there was a case.'", "Recorder app, 4m 12s", "", ""]),
}
for k, (title, lines) in CARDS.items():
    im = Image.new("RGB", (512, 384), (236, 230, 214)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 512, 56], fill=(120, 30, 34)); d.text((256, 28), title, font=F(28), fill=(255, 245, 230), anchor="mm")
    for i, l in enumerate(lines): d.text((24, 76 + i * 46), l, font=F(28, False), fill=(30, 30, 34))
    for _ in range(30): d.line([(R.randrange(512), R.randrange(60, 384)), (R.randrange(512), R.randrange(60, 384))], fill=(226, 220, 204), width=1)
    im.save(os.path.join(OUT, k + ".png"))

# cork board
im = Image.new("RGB", (1024, 640), (150, 110, 70)); im = noise(im, 30, 0).filter(ImageFilter.GaussianBlur(0.8)); im.save(os.path.join(OUT, "board_cork.jpg"), quality=88)
print("textures done")
