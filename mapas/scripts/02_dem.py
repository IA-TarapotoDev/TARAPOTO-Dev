# Descarga AWS Terrain Tiles (terrarium) y arma un GeoTIFF en EPSG:3857
import sys, math, os, io, urllib.request, numpy as np, rasterio
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from rasterio.transform import from_origin
Z = int(sys.argv[1]); W, E, S, N = map(float, sys.argv[2:6]); out = sys.argv[6]
cache = f"/home/user/data_base/tiles{Z}"; os.makedirs(cache, exist_ok=True)
n = 2 ** Z
tx = lambda lon: int((lon + 180) / 360 * n)
ty = lambda lat: int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
x0, x1, y0, y1 = tx(W), tx(E), ty(N), ty(S)
print("tiles", (x1 - x0 + 1) * (y1 - y0 + 1), flush=True)
def get(xy):
    x, y = xy; f = f"{cache}/{x}_{y}.png"
    if not os.path.exists(f):
        for k in range(5):
            try:
                d = urllib.request.urlopen(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{x}/{y}.png", timeout=60).read()
                open(f, "wb").write(d); break
            except Exception as e:
                if k == 4: raise
    a = np.asarray(Image.open(f).convert("RGB")).astype(np.float32)
    return x, y, a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
big = np.zeros(((y1 - y0 + 1) * 256, (x1 - x0 + 1) * 256), np.float32)
with ThreadPoolExecutor(16) as ex:
    for x, y, a in ex.map(get, [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]):
        big[(y - y0) * 256:(y - y0 + 1) * 256, (x - x0) * 256:(x - x0 + 1) * 256] = a
R = 6378137.0; size = 2 * math.pi * R / n
tr = from_origin(-math.pi * R + x0 * size, math.pi * R - y0 * size, size / 256, size / 256)
with rasterio.open(out, "w", driver="GTiff", height=big.shape[0], width=big.shape[1], count=1, dtype="float32",
                   crs="EPSG:3857", transform=tr, compress="deflate", tiled=True, predictor=3, BIGTIFF="YES") as d:
    d.write(big, 1)
print(out, big.shape, float(big.min()), float(big.max()))
