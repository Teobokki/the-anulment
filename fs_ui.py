"""UI kit (from THE ANULMENT, DirectGUI) for THE ANULMENT."""
from direct.gui.DirectGui import DirectFrame, DirectButton, DGG, DirectLabel
from direct.gui.OnscreenText import OnscreenText
from direct.gui.OnscreenImage import OnscreenImage
from panda3d.core import TextNode, Vec4, TransparencyAttrib

FONT = None; FONT_PLAIN = None; JP = None; SYM = None; SFX = None
PINK = (0.86, 0.62, 0.22, 1); CYAN = (0.62, 0.78, 0.95, 1); GOLD = (1.0, 0.82, 0.25, 1); WHITE = (1, 1, 1, 1)   # Valdora: brass + steel blue
PANEL = (0.04, 0.045, 0.06, 0.9)


def init_fonts(loader, path, plain, jp):
    global FONT, FONT_PLAIN, JP, SYM
    from panda3d.core import Filename
    def lf(p, ppu, outline):
        f = loader.load_font(Filename.from_os_specific(p).get_fullpath())
        f.set_pixels_per_unit(ppu)
        if outline: f.set_outline(Vec4(0, 0, 0, 0.85), 0.25, 0.25)
        return f
    try:
        FONT = lf(path, 80, True); FONT_PLAIN = lf(plain, 64, False); JP = SYM = lf(jp, 64, True)
        from panda3d.core import TextProperties, TextPropertiesManager
        tp = TextProperties(); tp.set_font(JP); TextPropertiesManager.get_global_ptr().set_properties("jp", tp)   # inline "\1jp\1...\2" Japanese runs
    except Exception:
        FONT = FONT_PLAIN = JP = None
    return JP


def text(parent, t, pos, scale=0.05, fg=WHITE, align=TextNode.A_center, font=None, wrap=None, shadow=None):
    return OnscreenText(parent=parent, text=t, pos=pos, scale=scale, fg=fg, align=align, mayChange=True,
                        font=font or FONT, wordwrap=wrap, shadow=shadow)


def panel(parent, l, r, b, t, col=PANEL, edge=PINK, pos=(0, 0), ew=0.006):
    o = DirectFrame(parent=parent, frameColor=edge, frameSize=(l - ew, r + ew, b - ew, t + ew), pos=(pos[0], 0, pos[1]), relief=DGG.FLAT)
    o.inner = DirectFrame(parent=o, frameColor=col, frameSize=(l, r, b, t), relief=DGG.FLAT)
    return o


def button(parent, label, pos, cmd, w=0.3, h=0.055, col=(0.08, 0.09, 0.12, 0.92), edge=PINK, scale=0.048, fg=WHITE,
           extra=None, enabled=True, hint=None, font=None, press=None, release=None):
    b = 0.006
    outer = DirectFrame(parent=parent, frameColor=edge, frameSize=(-w - b, w + b, -h - b, h + b), pos=(pos[0], 0, pos[1]), relief=DGG.FLAT)
    c = Vec4(*col)
    hi = Vec4(min(1, c[0] + 0.25), min(1, c[1] + 0.08), min(1, c[2] + 0.22), 0.97)
    dn = Vec4(c[0] * 0.6, c[1] * 0.6, c[2] * 0.6, 1)
    dis = Vec4(0.2, 0.2, 0.22, 0.8)

    def clicked(*a):
        if SFX: SFX("click")
        if cmd: cmd(*(extra or []))
    btn = DirectButton(parent=outer, text=label, text_scale=scale, text_fg=fg, text_font=font or FONT,
                       text_pos=(0, -scale * 0.33), frameSize=(-w, w, -h, h), frameColor=(c, dn, hi, dis),
                       relief=DGG.FLAT, command=clicked if cmd else None, pressEffect=1, rolloverSound=None, clickSound=None)
    if press:
        btn.bind(DGG.B1PRESS, lambda e: press()); btn.bind(DGG.B1RELEASE, lambda e: release() if release else None)
    if hint:
        OnscreenText(parent=outer, text=hint, pos=(w - 0.012, h - 0.032), scale=0.028, fg=(1, 1, 1, 0.65), align=TextNode.A_right, font=FONT_PLAIN)
    if not enabled:
        btn["state"] = DGG.DISABLED
    outer.btn = btn
    return outer


def bar(parent, pos, w, h, frac, col=CYAN, bg=(0.1, 0.1, 0.15, 0.8)):
    outer = DirectFrame(parent=parent, frameColor=bg, frameSize=(0, w, -h, h), pos=(pos[0], 0, pos[1]))
    fill = DirectFrame(parent=outer, frameColor=col, frameSize=(0, w, -h, h))
    fill.set_sx(max(0.001, frac))
    return outer, fill


# ---- v1.0.4 Japanese line breaking (kinsoku shori) -------------------------------------------------------------
NO_START = set("。、，．・：；？！ー\uff5e…‥」』）］｝〕〉》】ゝゞヽヾぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ々!?,.:;)]}'\"%")
NO_END = set("「『（［｛〔〈《【([{")


def _em(ch):
    return 0.6 if ord(ch) < 0x2E80 else 1.0


def jwrap(s, em=16.0):
    """wrap a Japanese / mixed line into <= em-wide rows: break between any CJK characters (or at spaces for ASCII
    words), but never start a row with closing punctuation / small kana (。、！？」 ...) or end one with an opening
    bracket - the punctuation is pulled back onto the previous row instead (burasage)."""
    out = []
    for para in s.split("\n"):
        # tokens: ASCII words stay whole, every CJK character is its own token
        toks, buf = [], ""
        for ch in para:
            if ord(ch) < 0x2E80 and ch != " ": buf += ch
            else:
                if buf: toks.append(buf); buf = ""
                toks.append(ch)
        if buf: toks.append(buf)
        rows, cur, w = [], "", 0.0
        for t in toks:
            tw = sum(_em(c) for c in t)
            if cur and w + tw > em and t != " " and t[0] not in NO_START:
                cut = max(cur.rfind(q) for q in "、。！？」 ")
                if cut >= len(cur) * 0.55 and cut < len(cur) - 1:      # nicer: break right after punctuation / a space
                    rows.append(cur[:cut + 1].rstrip()); cur = cur[cut + 1:].lstrip(); w = sum(_em(c) for c in cur)
                elif cur[-1] in NO_END: rows.append(cur[:-1]); cur, w = cur[-1], _em(cur[-1])
                else: rows.append(cur.rstrip()); cur, w = "", 0.0
                if t == " ": continue
            cur += t; w += tw
        if cur: rows.append(cur.rstrip())
        out.append("\n".join(r.lstrip() for r in rows))
    return "\n".join(out)
