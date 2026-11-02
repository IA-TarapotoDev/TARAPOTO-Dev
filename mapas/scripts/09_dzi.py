# Genera teselas Deep Zoom (DZI) a partir del PNG de 300 dpi para el visor web (OpenSeadragon)
import sys, os, math
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
src, out_dir, name = sys.argv[1], sys.argv[2], sys.argv[3]
TS, OV, Q = 254, 1, 86
im = Image.open(src).convert("RGB")
W, H = im.size
maxlev = math.ceil(math.log2(max(W, H)))
os.makedirs(f"{out_dir}/{name}_files", exist_ok=True)
n = 0
cur = im
for lev in range(maxlev, -1, -1):
    s = 2 ** (maxlev - lev)
    w, h = max(1, math.ceil(W / s)), max(1, math.ceil(H / s))
    if cur.size != (w, h):
        cur = cur.resize((w, h), Image.LANCZOS)
    d = f"{out_dir}/{name}_files/{lev}"
    os.makedirs(d, exist_ok=True)
    for c in range(math.ceil(w / TS)):
        for r in range(math.ceil(h / TS)):
            x0 = c * TS - (OV if c else 0); y0 = r * TS - (OV if r else 0)
            x1 = min((c + 1) * TS + OV, w); y1 = min((r + 1) * TS + OV, h)
            cur.crop((x0, y0, x1, y1)).save(f"{d}/{c}_{r}.jpg", quality=Q, optimize=True, progressive=False, subsampling=0)
            n += 1
with open(f"{out_dir}/{name}.dzi", "w") as f:
    f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<Image xmlns="http://schemas.microsoft.com/deepzoom/2008" Format="jpg" Overlap="{OV}" TileSize="{TS}"><Size Width="{W}" Height="{H}"/></Image>\n')
print("teselas", n, "niveles", maxlev + 1, (W, H))
