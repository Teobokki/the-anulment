"""THE ANULMENT original score: dramatic, melancholic minor-key tracks (~104 BPM), pulsing staccato strings, piano,
violins/cellos, big drums at climaxes. Rendered offline with FluidSynth + FluidR3_GM (MIT). Crowd choir chants are
rendered from the offline Romanian Piper voice (ro_RO-mihai-medium, CC0) and layered (pitch shifts, octaves, offsets,
stereo spread, reverb) on the beat. No 'ooh/aah' pads. All melodies/progressions are generated originals."""
import os, sys, struct, random, subprocess, wave, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "..", "assets", "music"); os.makedirs(OUT, exist_ok=True)
TMP = "/workspace/an_music"; SF2 = "/usr/share/sounds/sf2/FluidR3_GM.sf2"; SR = 44100
PIPER = "/workspace/an_dl/piper/piper/piper"; VOICE = "/workspace/an_dl/piper/ro_RO-mihai-medium.onnx"

def vlq(n):
    b = [n & 0x7F]; n >>= 7
    while n: b.append((n & 0x7F) | 0x80); n >>= 7
    return bytes(reversed(b))
def write_midi(path, events, bpm):
    """events: (beat, chan, kind, a, b) kind: on/off/prog/cc"""
    tpq = 480; ev = []
    for t, ch, k, a, b in events:
        tick = int(round(t * tpq))
        if k == "on": ev.append((tick, 1, bytes([0x90 | ch, a, b])))
        elif k == "off": ev.append((tick, 0, bytes([0x80 | ch, a, 0])))
        elif k == "prog": ev.append((tick, -1, bytes([0xC0 | ch, a])))
        elif k == "cc": ev.append((tick, -1, bytes([0xB0 | ch, a, b])))
    ev.sort(key=lambda e: (e[0], e[1]))
    trk = b"\x00\xFF\x51\x03" + struct.pack(">I", int(60e6 / bpm))[1:]; last = 0
    for tick, _, data in ev: trk += vlq(tick - last) + data; last = tick
    trk += b"\x00\xFF\x2F\x00"
    open(path, "wb").write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, tpq) + b"MTrk" + struct.pack(">I", len(trk)) + trk)

class Song:
    def __init__(self, bpm): self.e = []; self.bpm = bpm
    def prog(self, ch, p, vol=100, pan=64, rev=50):
        self.e += [(0, ch, "prog", p, 0), (0, ch, "cc", 7, vol), (0, ch, "cc", 10, pan), (0, ch, "cc", 91, rev)]
    def note(self, t, ch, n, d, v):
        self.e += [(t, ch, "on", n, max(1, min(127, int(v)))), (t + d, ch, "off", n, 0)]

ROOT = 57  # A
# original progressions (scale degrees as semitone offsets from A, minor triads/major triads)
PROGS = {"A": [(0, "m"), (5, "m"), (10, "M"), (3, "M"), (8, "M"), (2, "d"), (7, "M"), (7, "M")],      # i iv VII III VI ii° V V
         "B": [(0, "m"), (7, "m"), (8, "M"), (5, "m"), (0, "m"), (10, "M"), (3, "M"), (7, "M")],
         "C": [(0, "m"), (3, "M"), (5, "m"), (7, "M")]}
def triad(r, q):
    return [r, r + (3 if q in "md" else 4), r + (6 if q == "d" else 7)]
SCALE = [0, 2, 3, 5, 7, 8, 10, 11]   # harmonic-ish minor colour

def compose(name, bpm, bars, prog, layers, seed, intensity):
    rnd = random.Random(seed); s = Song(bpm)
    s.prog(0, 48, 96, 50, 60); s.prog(1, 0, 104, 70, 45); s.prog(2, 40, 92, 40, 70); s.prog(3, 42, 100, 84, 60)
    s.prog(4, 45, 90, 76, 40); s.prog(5, 60, 80, 56, 60); s.prog(6, 47, 100, 64, 50); s.prog(7, 49, 88, 90, 70)
    P = PROGS[prog]; mel_prev = 12
    for bar in range(bars):
        r, q = P[bar % len(P)]; ch = triad(ROOT + r - 12, q); t0 = bar * 4
        sect = bar / bars; big = intensity * (0.4 + 0.6 * sect)
        if "stac" in layers:   # pulsing staccato strings (8ths)
            for k in range(8):
                for n in ch: s.note(t0 + k * 0.5, 0, n + 12, 0.22, 52 + 30 * big + (8 if k % 2 == 0 else 0))
        if "pizz" in layers:
            for k in range(4): s.note(t0 + k, 4, ch[k % 3] + 12, 0.4, 60 + 20 * big)
        if "cello" in layers:   # long cello roots
            s.note(t0, 3, ch[0] - 12, 3.9, 70 + 25 * big); s.note(t0, 3, ch[0], 3.9, 50 + 20 * big)
        if "piano" in layers:   # arpeggiated piano + melody
            for k, n in enumerate([ch[0], ch[1], ch[2], ch[1] + 12, ch[2], ch[1], ch[0] + 12, ch[2]]):
                s.note(t0 + k * 0.5, 1, n + 12, 0.6, 48 + 18 * big)
        if "melody" in layers and (bar % 8) >= (0 if intensity > 0.5 else 2):
            # motif: chord-tone anchored phrases with stepwise passing notes (generated)
            rhythm = rnd.choice([[1.5, 0.5, 1, 1], [1, 0.5, 0.5, 2], [0.5, 0.5, 1, 1.5, 0.5], [2, 1, 1]])
            t = t0
            for d in rhythm:
                tones = [x - ROOT for x in ch]
                if rnd.random() < 0.6: tgt = rnd.choice(tones) % 12 + 12
                else: tgt = SCALE[rnd.randrange(len(SCALE))] + 12
                if abs(tgt - mel_prev) > 7: tgt += -12 if tgt > mel_prev else 12
                tgt = max(5, min(24, tgt)); mel_prev = tgt
                inst = 2 if "violin" in layers else 1
                s.note(t, inst, ROOT + tgt + (0 if inst == 2 else 12), d * 0.95, 78 + 25 * big); t += d
        if "violin" in layers and "melody" not in layers:
            s.note(t0, 2, ch[2] + 12, 3.8, 66 + 20 * big)
        if "horn" in layers and sect > 0.4:
            s.note(t0, 5, ch[0], 1.9, 70 * big + 30); s.note(t0 + 2, 5, ch[1], 1.9, 70 * big + 30)
        if "strings2" in layers:
            for n in ch: s.note(t0, 7, n, 3.9, 50 + 30 * big)
        if "drums" in layers and (sect > 0.35 or intensity > 0.8):
            for k in range(4):
                s.note(t0 + k, 9, 36, 0.2, 100 if k in (0, 2) else 70)
                if k in (1, 3): s.note(t0 + k, 9, 38, 0.2, 90 + 20 * big)
                s.note(t0 + k + 0.5, 9, 42, 0.1, 50)
            if bar % 4 == 3:
                for k, n in enumerate((45, 43, 41, 41)): s.note(t0 + 2 + k * 0.5, 9, n, 0.2, 105)
            if bar % 8 == 0: s.note(t0, 9, 49, 1, 110); s.note(t0, 6, ch[0] - 24 + 12, 1.0, 110)
        if "timp" in layers and bar % 2 == 0: s.note(t0, 6, ch[0] - 12, 1.5, 70 + 40 * big)
    mid = os.path.join(TMP, name + ".mid"); write_midi(mid, s.e, bpm)
    wav = os.path.join(TMP, name + ".wav")
    subprocess.run(["fluidsynth", "-ni", "-g", "0.6", "-r", str(SR), "-F", wav, SF2, mid], check=True, capture_output=True)
    return wav, bars * 4 * 60.0 / bpm

def read_wav(p):
    w = wave.open(p); n = w.getnframes(); ch = w.getnchannels(); sr = w.getframerate()
    a = np.frombuffer(w.readframes(n), np.int16).astype(np.float32) / 32768.0
    a = a.reshape(-1, ch)
    if ch == 1: a = np.repeat(a, 2, axis=1)
    return a, sr
def write_wav(p, a):
    a = np.clip(a, -1, 1); w = wave.open(p, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((a * 32767).astype(np.int16).tobytes()); w.close()

def tts(text, path, scale=1.0):
    subprocess.run([PIPER, "-m", VOICE, "-f", path, "--length_scale", str(scale)], input=text.encode("utf-8"), check=True, capture_output=True)

def ff(src, dst, af):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", af, "-ar", str(SR), "-ac", "2", dst], check=True)

def chant_phrase(text, beats, bpm, key):
    """one chant phrase stretched to exactly `beats`, then 14 layered voices (pitch +-, octave down, offsets, pan, reverb)"""
    raw = os.path.join(TMP, "ch_%s_raw.wav" % key); tts(text, raw, 0.9)
    a, sr = read_wav(raw); dur = len(a) / sr; target = beats * 60.0 / bpm * 0.92
    fit = os.path.join(TMP, "ch_%s_fit.wav" % key)
    ff(raw, fit, "rubberband=tempo=%.4f,loudnorm=I=-16" % (dur / target))
    base, _ = read_wav(fit); L = int(beats * 60.0 / bpm * SR); mix = np.zeros((L + SR, 2), np.float32)
    rnd = random.Random(hash(key) & 0xFFFF)
    for k in range(14):
        semi = rnd.choice([-12, -12, -5, -3, -2, -1, 0, 0, 0, 1, 2, 3, -7, 0])
        v = os.path.join(TMP, "ch_%s_%d.wav" % (key, k))
        ff(fit, v, "rubberband=pitch=%.4f:formant=preserved" % (2 ** (semi / 12.0)))
        x, _ = read_wav(v); off = int(rnd.uniform(0, 0.035) * SR); pan = rnd.uniform(-0.85, 0.85)
        g = rnd.uniform(0.5, 0.9) * (0.8 if semi == -12 else 1.0)
        n = min(len(x), L + SR - off)
        mix[off:off + n, 0] += x[:n, 0] * g * (1 - max(0, pan)); mix[off:off + n, 1] += x[:n, 1] * g * (1 + min(0, pan))
    # reverb: exponentially decaying noise impulse (1.6 s)
    ir_len = int(1.6 * SR); ir = np.random.RandomState(3).randn(ir_len).astype(np.float32) * np.exp(-np.linspace(0, 7, ir_len)).astype(np.float32)
    ir /= np.abs(ir).sum() / 6
    wet = np.stack([np.convolve(mix[:, c], ir)[:len(mix)] for c in range(2)], 1)
    out = mix * 0.75 + wet * 0.35
    return out / (np.abs(out).max() + 1e-6)

def crowd_bed(seconds, seed=1):
    rs = np.random.RandomState(seed); n = int(seconds * SR)
    x = rs.randn(n, 2).astype(np.float32)
    k = np.ones(40) / 40; x = np.stack([np.convolve(x[:, c], k, "same") for c in range(2)], 1)      # murmur (low-passed noise)
    env = 0.6 + 0.4 * np.sin(np.linspace(0, seconds * 0.7, n))[:, None]
    return x * env * 0.5

def lay_chants(music, bpm, start_bar, every_bars, phrases, gain=0.55):
    bar = 4 * 60.0 / bpm; t = start_bar * bar; i = 0
    while t + 2 * bar < len(music) / SR:
        ph = phrases[i % len(phrases)]; s = int(t * SR); n = min(len(ph), len(music) - s)
        music[s:s + n] += ph[:n] * gain; t += every_bars * bar; i += 1
    return music

def finish(name, a):
    tmp = os.path.join(TMP, name + "_mix.wav"); write_wav(tmp, a / (np.abs(a).max() + 1e-6) * 0.9)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), "-c:a", "libvorbis", "-q:a", "4",
                    os.path.join(OUT, name + ".ogg")], check=True)
    print("TRACK", name, round(len(a) / SR, 1), "s", flush=True)

if __name__ == "__main__":
    BPM = 104
    T = {  # name: (bpm, bars, prog, layers, seed, intensity, chants)
        "title":    (104, 24, "A", {"stac", "cello", "piano", "melody", "violin", "drums", "timp"}, 11, 0.7, False),
        "city":     (100, 16, "C", {"pizz", "cello", "piano", "strings2"}, 22, 0.3, False),
        "investigation": (106, 16, "B", {"stac", "cello", "pizz", "melody"}, 33, 0.45, False),
        "protest":  (104, 24, "A", {"stac", "cello", "strings2", "horn", "drums", "timp", "violin"}, 44, 1.0, True),
        "family":   (100, 16, "C", {"piano", "melody", "cello", "strings2"}, 55, 0.25, False),
        "finale":   (108, 24, "B", {"stac", "cello", "melody", "violin", "horn", "drums", "timp"}, 66, 1.0, True),
        "credits":  (104, 32, "A", {"stac", "cello", "piano", "melody", "violin", "horn", "drums"}, 77, 0.85, True),
    }
    ch1 = chant_phrase("C. L. N. președinte!", 4, BPM, "cln"); ch2 = chant_phrase("Turul doi înapoi!", 4, BPM, "turul")
    for name, (bpm, bars, prog, layers, seed, inten, chants) in T.items():
        wav, dur = compose(name, bpm, bars, prog, layers, seed, inten)
        a, _ = read_wav(wav); a = a[:int(dur * SR)]
        if chants:
            c1 = ch1 if bpm == BPM else chant_phrase("C. L. N. președinte!", 4, bpm, "cln%d" % bpm)
            c2 = ch2 if bpm == BPM else chant_phrase("Turul doi înapoi!", 4, bpm, "turul%d" % bpm)
            a = a + crowd_bed(len(a) / SR, seed)[:len(a)] * 0.08
            a = lay_chants(a, bpm, 4 if name != "credits" else 8, 2, [c1, c2], 0.5)
        n = int(0.05 * SR); a[:n] *= np.linspace(0, 1, n)[:, None]; a[-n:] *= np.linspace(1, 0, n)[:, None]
        finish(name, a)
    # live crowd chant loop for the protest zones (spatial in game): 8 bars of chants over murmur, plus a cheer
    bar = 4 * 60.0 / BPM; L = int(8 * bar * SR); c = crowd_bed(L / SR, 9)[:L] * 0.35
    clap = np.zeros((L, 2), np.float32); rs = np.random.RandomState(5)
    for b in range(32):
        s = int(b * bar / 4 * SR * 1.0) if False else int(b * 60.0 / BPM * SR)
        for k in range(30):
            o = s + rs.randint(0, 900); m = min(L - o, 600)
            if m > 0: clap[o:o + m] += rs.randn(m, 2).astype(np.float32) * np.exp(-np.linspace(0, 9, m))[:, None] * 0.05
    c = c + clap
    c = lay_chants(c, BPM, 0, 2, [ch1, ch2], 0.9)
    write_wav(os.path.join(TMP, "chant_live.wav"), c / np.abs(c).max() * 0.9)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(TMP, "chant_live.wav"), "-af", "loudnorm=I=-16", "-c:a", "libvorbis", "-q:a", "4",
                    os.path.join(HERE, "..", "assets", "sfx", "chant_live.ogg")], check=True)
    n = int(3.0 * SR); rs = np.random.RandomState(8); x = rs.randn(n, 2).astype(np.float32)
    x = np.stack([np.convolve(x[:, cc], np.ones(12) / 12, "same") for cc in range(2)], 1)
    env = np.minimum(1, np.linspace(0, 6, n)) * np.exp(-np.linspace(0, 2.5, n)); x *= env[:, None]
    for k in range(60):
        o = rs.randint(0, n - 700); x[o:o + 700] += rs.randn(700, 2).astype(np.float32) * np.exp(-np.linspace(0, 9, 700))[:, None] * 0.6
    write_wav(os.path.join(HERE, "..", "assets", "sfx", "cheer.wav"), x / np.abs(x).max() * 0.85)
    print("MUSIC DONE", flush=True)
