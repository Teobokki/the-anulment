"""Offline text-to-speech: Piper (MIT) with the Romanian voice ro_RO-mihai-medium (CC0). Runs piper as a child process,
text on stdin, WAV out to a temp folder. No network, no admin."""
import os, sys, subprocess, tempfile, time, threading


class TTS:
    def __init__(self, base, log=None):
        self.base = base; self.log = log or (lambda e: None); self.n = 0; self.lock = threading.Lock()
        exe = "piper.exe" if os.name == "nt" else "piper"
        cands = [os.environ.get("AN_PIPER", ""), os.path.join(base, "piper", exe), os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "piper", exe),
                 "/workspace/an_dl/piper/piper/piper"]
        self.exe = next((c for c in cands if c and os.path.exists(c)), None)
        self.model = os.path.join(base, "assets", "voice", "ro_RO-mihai-medium.onnx")
        self.out = os.path.join(tempfile.gettempdir(), "the_anulment_tts_%d" % os.getpid()); os.makedirs(self.out, exist_ok=True)
        self.ok = bool(self.exe and os.path.exists(self.model))

    def synth(self, text, length=1.0):
        if not self.ok: return None
        text = " ".join(str(text).replace("\n", " ").split())[:200]
        if not text: return None
        with self.lock: self.n += 1; k = self.n
        wav = os.path.join(self.out, "line_%04d.wav" % (k % 64))
        flags = 0x08000000 if os.name == "nt" else 0          # CREATE_NO_WINDOW
        p = subprocess.run([self.exe, "-m", self.model, "-f", wav, "--length_scale", "%.2f" % length, "-q"], input=text.encode("utf-8"),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=os.path.dirname(self.exe), timeout=30, creationflags=flags)
        return wav if os.path.exists(wav) and os.path.getsize(wav) > 1000 else None
