"""v1.0.0.2: fill the black background around the UV islands of the skin textures with the island colour
(push-pull), so faces/limbs whose UVs touch an island edge (and mip-mapped distant figures) never pick up black."""
import sys, numpy as np
from PIL import Image, ImageFilter

def pushpull(img, mask):
    if min(mask.shape) <= 1:
        w = mask.sum(); return np.broadcast_to((img * mask[..., None]).sum((0, 1)) / max(w, 1e-6), img.shape).copy()
    h, w = mask.shape; h2, w2 = (h + 1) // 2, (w + 1) // 2
    pi = np.zeros((h2 * 2, w2 * 2, img.shape[2])); pm = np.zeros((h2 * 2, w2 * 2))
    pi[:h, :w] = img * mask[..., None]; pm[:h, :w] = mask
    si = pi.reshape(h2, 2, w2, 2, -1).sum((1, 3)); sm = pm.reshape(h2, 2, w2, 2).sum((1, 3))
    low = pushpull(si / np.maximum(sm, 1e-6)[..., None], (sm > 0).astype(float))
    up = np.repeat(np.repeat(low, 2, 0), 2, 1)[:h, :w]
    return np.where(mask[..., None] > 0, img, up)

for p in sys.argv[1:]:
    im = Image.open(p).convert("RGB"); a = np.asarray(im).astype(float)
    m = Image.fromarray(((a.sum(2) > 60) * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(5))  # drop dark edge fringe
    mask = (np.asarray(m) > 0).astype(float)
    out = pushpull(a, mask)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(p)
    print(p, "filled %.0f%%" % (100 * (1 - mask.mean())))
