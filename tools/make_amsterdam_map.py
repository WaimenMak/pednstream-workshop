"""Place the Amsterdam nodes at their real location and render a background map.

Writes, in src/pednstream_workshop/networks/amsterdam/:
  node_positions.json   node -> [x, y] in Web Mercator metres (EPSG:3857)
  background.jpg        street map behind the network
  background.json       its extent [xmin, xmax, ymin, ymax] and attribution

Map tiles: OpenStreetMap standard tiles, faded so the density colours stand out.
Only needed when the nodes or the map change (needs `pip install contextily`):
    python tools/make_amsterdam_map.py
"""

import json
import math
from pathlib import Path

import contextily as cx
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent.parent / "src" / "pednstream_workshop" / "networks" / "amsterdam"

# node: (latitude, longitude), approximate
NODES = {
    0: (52.3789, 4.9001),  # Centraal Station
    9: (52.3772, 4.8985),  # Stationsplein
    1: (52.3730, 4.8932),  # Dam (Madame Tussauds)
    2: (52.3750, 4.8837),  # Westermarkt (Anne Frank Huis)
    3: (52.3727, 4.9005),  # Nieuwmarkt
    4: (52.3667, 4.8936),  # Muntplein
    5: (52.3678, 4.9026),  # Waterlooplein (Rembrandthuis)
    6: (52.3642, 4.8826),  # Leidseplein
    7: (52.3602, 4.8870),  # Rijksmuseum
    8: (52.3572, 4.8813),  # Museumplein
}
MARGIN = 0.0025  # degrees around the nodes
ZOOM = 16
ATTRIBUTION = "© OpenStreetMap contributors"
FADE = 0.45  # 0 = original colours, 1 = white


def mercator(lat, lon):
    r = 6378137.0
    return [r * math.radians(lon), r * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))]


positions = {str(n): [round(v, 1) for v in mercator(*ll)] for n, ll in NODES.items()}
(OUT / "node_positions.json").write_text(json.dumps(positions) + "\n")

lats = [ll[0] for ll in NODES.values()]
lons = [ll[1] for ll in NODES.values()]
img, extent = cx.bounds2img(min(lons) - MARGIN, min(lats) - MARGIN, max(lons) + MARGIN, max(lats) + MARGIN,
                            zoom=ZOOM, source=cx.providers.OpenStreetMap.Mapnik, ll=True, use_cache=False,
                            # the OSM tile policy asks every app to identify itself
                            headers={"User-Agent": "pednstream-workshop-map-builder/1.0 (one-off render)"})
rgb = img[..., :3].astype(float) / 255
grey = rgb.mean(axis=2, keepdims=True)
rgb = 0.5 * rgb + 0.5 * grey                      # half desaturated
rgb = (1 - FADE) * rgb + FADE                      # faded towards white
rgb = rgb[::2, ::2]                                # half resolution is plenty
plt.imsave(OUT / "background.jpg", np.clip(rgb, 0, 1), pil_kwargs={"quality": 85})
(OUT / "background.json").write_text(json.dumps(
    {"extent": [round(float(e), 1) for e in extent], "attribution": ATTRIBUTION}, indent=1) + "\n")
print("image", img.shape, "extent", extent)
