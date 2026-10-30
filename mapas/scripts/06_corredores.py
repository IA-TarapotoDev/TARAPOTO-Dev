# Calcula rutas de los corredores (OSRM) y el punto exacto de salida de la ZTE (cruce de la vía con el límite ZTE)
import json, time, urllib.request, geopandas as gpd, pandas as pd, numpy as np, warnings
from shapely.geometry import LineString, Point
from shapely.ops import substring
warnings.filterwarnings("ignore")
B = "/home/user/data_base"
CORR = {
  "OESTE":     [("Corral Quemado", -78.6902691, -5.7534684), ("Puente Boliche", -79.6880993, -5.9832564), ("Chiclayo", -79.8409, -6.7714)],
  "SUROESTE":  [("Chachapoyas", -77.8692, -6.2317), ("Leymebamba", -77.803, -6.709), ("Balsas", -78.0217, -6.8369), ("Celendín", -78.1456, -6.8658), ("Cajamarca", -78.5170, -7.1617)],
  "SUR":       [("Tocache", -76.5133, -8.1886), ("Tingo María", -75.9975, -9.2953), ("Huánuco", -76.2422, -9.9306), ("Ambo", -76.2047, -10.1306), ("Cerro de Pasco", -76.2567, -10.6828)],
}
def osrm(pts):
    u = "https://router.project-osrm.org/route/v1/driving/" + ";".join(f"{x},{y}" for _, x, y in pts) + "?overview=full&geometries=geojson&steps=true&annotations=false"
    for k in range(5):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "ia-tarapoto-mapas/1.0"}), timeout=90))
        except Exception as e:
            print("retry", e); time.sleep(3 + 3 * k)
reg = gpd.read_file(f"{B}/regimen.gpkg").to_crs(32718)
zte = reg[reg.regimen == "ZTE"].geometry.iloc[0]
dist = gpd.read_file(f"{B}/distritos_tematico.gpkg").to_crs(32718)
out = {}
for name, pts in CORR.items():
    d = osrm(pts); r = d["routes"][0]
    line = gpd.GeoSeries([LineString(r["geometry"]["coordinates"])], crs=4326).to_crs(32718).iloc[0]
    L = line.length
    scale = r["distance"] / L  # OSRM km vs. longitud UTM (factor de escala)
    # tramos ZTE / ZTC
    inter = line.intersection(zte.boundary)
    cuts = sorted({line.project(p) for p in getattr(inter, "geoms", [inter]) if not p.is_empty})
    segs = []; prev = 0
    for c in cuts + [L]:
        if c - prev < 1: continue
        s = substring(line, prev, c); mid = s.interpolate(0.5, normalized=True)
        segs.append({"desde_km": prev * scale / 1000, "hasta_km": c * scale / 1000, "regimen": "ZTE" if zte.contains(mid) else "ZTC"}); prev = c
    # puntos de salida (transición ZTE -> ZTC)
    exits = []
    for a, b in zip(segs, segs[1:]):
        if a["regimen"] == "ZTE" and b["regimen"] == "ZTC":
            p = line.interpolate(a["hasta_km"] * 1000 / scale)
            ll = gpd.GeoSeries([p], crs=32718).to_crs(4326).iloc[0]
            near = dist[dist.distance(p) < 50]
            exits.append({"km": a["hasta_km"], "lon": ll.x, "lat": ll.y,
                          "limite": " / ".join(f"{x.distrito.title()} ({x.provincia.title()}, {x.departamento.title()}) {x.regimen}" for x in near.itertuples())})
    # km de cada parada
    legs = np.cumsum([0] + [l["distance"] for l in r["legs"]]) / 1000
    stops = [{"nombre": n, "km": float(k)} for (n, _, _), k in zip(pts, legs)]
    refs = []
    for l in r["legs"]:
        for s in l["steps"]:
            if s.get("ref") and s["distance"] > 1500 and s["ref"] not in refs: refs.append(s["ref"])
    km_zte = sum(s["hasta_km"] - s["desde_km"] for s in segs if s["regimen"] == "ZTE")
    out[name] = {"km_total": r["distance"] / 1000, "horas": r["duration"] / 3600, "km_zte": km_zte, "segmentos": segs,
                 "salidas": exits, "paradas": stops, "vias": refs, "coords": r["geometry"]["coordinates"]}
    print(f"\n{name}: {r['distance']/1000:.1f} km, ZTE {km_zte:.1f} km, vías {refs}")
    for s in segs: print(f"   {s['desde_km']:7.1f}-{s['hasta_km']:7.1f} {s['regimen']}")
    for e in exits: print(f"   SALIDA km {e['km']:.1f} ({e['lat']:.5f}, {e['lon']:.5f}) {e['limite']}")
    for s in stops: print(f"   {s['nombre']}: km {s['km']:.1f}")
    time.sleep(1.5)
json.dump(out, open(f"{B}/corredores.json", "w"), ensure_ascii=False)
