"""Build the Amsterdam challenge network from the OpenStreetMap walking network.

Each corridor of the challenge (e.g. Damrak from Stationsplein to the Dam) is routed over
the real OSM walking network, preferring the named street(s), and split into pieces of
about SEGMENT metres. Every split point becomes a PedNStream node, so the network follows
the streets and a queue can be seen growing back along a street.

Writes, in src/pednstream_workshop/networks/amsterdam/:
  sim_params.yaml       the PedNStream network (adjacency, link lengths/widths, settings)
  node_positions.json   node -> [x, y] in Web Mercator metres (EPSG:3857)
  names.json            node and street names for the plots
  background.jpg/.json  faded OpenStreetMap background (only with --refresh-map or if missing)

Needs `pip install osmnx contextily` (facilitators only; students never run this):
    python tools/build_amsterdam.py [--refresh-map]
The OSM walking network is cached in tools/.cache/ (git-ignored).
"""

import json
import math
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import osmnx as ox

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "pednstream_workshop" / "networks" / "amsterdam"
CACHE = ROOT / "tools" / ".cache" / "amsterdam_walk.graphml"
BBOX = (4.876, 52.354, 4.908, 52.382)  # left, bottom, right, top
USER_AGENT = "pednstream-workshop-network-builder/1.0"
SEGMENT = 300  # m, target length of one link
PREFER = 0.5   # edges on the named street count as this fraction of their length

# Main places (latitude, longitude). Snapped to the nearest walkable OSM node.
PLACES = {
    0: ("Centraal Station", (52.3789, 4.9001)),
    9: ("Stationsplein", (52.3772, 4.8985)),
    1: ("Dam (Madame Tussauds)", (52.3730, 4.8932)),
    2: ("Westermarkt (Anne Frank)", (52.3750, 4.8837)),
    3: ("Nieuwmarkt", (52.3727, 4.9005)),
    4: ("Muntplein", (52.3667, 4.8936)),
    5: ("Waterlooplein (Rembrandthuis)", (52.3678, 4.9026)),
    6: ("Leidseplein", (52.3642, 4.8826)),
    7: ("Rijksmuseum", (52.3604, 4.8853)),  # north end of the passage
    8: ("Museumplein", (52.3577, 4.8830)),
    10: ("Weteringcircuit", (52.3597, 4.8905)),
}
ORIGIN, DESTINATION = 0, 8

# (from, to, street label, OSM street names to prefer, effective width in m[, via (lat, lon) points])
CORRIDORS = [
    (9, 1, "Damrak", ["Damrak"], 20),
    (9, 2, "Nieuwendijk / Leliegracht", [], 3, [(52.3759, 4.8900), (52.3756, 4.8862)]),  # via Torensluis
    (9, 3, "Zeedijk", ["Zeedijk"], 3),
    (1, 2, "Raadhuisstraat", ["Raadhuisstraat"], 3),  # trams in the middle, narrow pavements
    (1, 4, "Kalverstraat", ["Kalverstraat"], 3),
    (2, 6, "Prinsengracht", ["Prinsengracht"], 4),
    (3, 5, "Jodenbreestraat", ["Sint Antoniesbreestraat", "Jodenbreestraat"], 5),
    (4, 5, "Amstel", ["Amstel"], 5),
    (4, 6, "Leidsestraat", ["Heiligeweg", "Koningsplein", "Leidsestraat"], 2.5),
    (4, 10, "Vijzelstraat", ["Vijzelstraat", "Vijzelgracht"], 4),
    (5, 10, "Utrechtsestraat / Weteringschans", ["Utrechtsestraat", "Weteringschans"], 4,
     [(52.3612, 4.8993)]),  # via Frederiksplein
    (10, 7, "Stadhouderskade", ["Stadhouderskade", "Weteringschans"], 5),
    (6, 8, "Hobbemastraat", ["Hobbemastraat", "Stadhouderskade"], 6),
    (7, 8, "Rijksmuseum passage", [], 5),
]
STATION_HALL = (0, 9, "station hall", 100, 30)  # not routed: inside the station
LABEL_SIDE = {"9": "left", "4": "left", "5": "left", "3": "below"}


def mercator(lat, lon):
    r = 6378137.0
    return [r * math.radians(lon), r * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))]


def load_graph():
    if not CACHE.exists():
        ox.settings.http_user_agent = USER_AGENT
        ox.settings.requests_timeout = 300
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        ox.save_graphml(ox.graph_from_bbox(BBOX, network_type="walk"), CACHE)
    return nx.Graph(ox.load_graphml(CACHE))  # undirected: people walk both ways


def edge_names(data):
    name = data.get("name", "")
    return set(name) if isinstance(name, list) else {name}


def route(G, stops, prefer):
    def weight(u, v, d):
        return d["length"] * (PREFER if edge_names(d) & set(prefer) else 1.0)
    path = [stops[0]]
    for a, b in zip(stops, stops[1:]):
        path += nx.shortest_path(G, a, b, weight=weight)[1:]
    cum = np.concatenate([[0], np.cumsum([G.edges[u, v]["length"] for u, v in zip(path, path[1:])])])
    return path, cum


def main():
    G = load_graph()
    xs = [G.nodes[n]["x"] for n in G.nodes]
    ys = [G.nodes[n]["y"] for n in G.nodes]
    ids = list(G.nodes)

    def nearest(lat, lon):
        return ids[int(np.argmin((np.array(xs) - lon) ** 2 + (np.array(ys) - lat) ** 2))]

    osm_of = {n: nearest(*ll) for n, (_, ll) in PLACES.items()}
    lonlat = {n: (G.nodes[o]["x"], G.nodes[o]["y"]) for n, o in osm_of.items()}
    names = {n: name for n, (name, _) in PLACES.items()}
    links, streets, minor = [], {}, []
    next_id = max(PLACES) + 1

    for u, v, label, prefer, width, *via in CORRIDORS:
        stops = [osm_of[u]] + [nearest(*ll) for ll in (via[0] if via else [])] + [osm_of[v]]
        path, cum = route(G, stops, prefer)
        total = cum[-1]
        pieces = max(1, int(round(total / SEGMENT)))
        chain, cuts = [u], [0.0]
        for k in range(1, pieces):
            i = int(np.argmin(np.abs(cum - k * total / pieces)))
            if 0 < i < len(path) - 1 and cum[i] > cuts[-1] + 50:
                n = next_id
                next_id += 1
                lonlat[n] = (G.nodes[path[i]]["x"], G.nodes[path[i]]["y"])
                names[n] = f"{label} ({len(chain)})"
                minor.append(n)
                chain.append(n)
                cuts.append(cum[i])
        chain.append(v)
        cuts.append(total)
        for (a, b), length in zip(zip(chain, chain[1:]), np.diff(cuts)):
            key = f"{min(a, b)}_{max(a, b)}"
            links.append((key, round(float(length)), width, label))
            streets[key] = label
        print(f"{label:22s} {u}->{v}: {total:5.0f} m in {len(chain) - 1} links via {chain}")

    a, b, label, length, width = STATION_HALL
    links.insert(0, (f"{a}_{b}", length, width, label))
    streets[f"{a}_{b}"] = label
    lonlat[0] = PLACES[0][1][::-1]  # the station itself is not on the walking network

    n_nodes = next_id
    adj = np.zeros((n_nodes, n_nodes), dtype=int)
    for key, *_ in links:
        a, b = map(int, key.split("_"))
        adj[a, b] = adj[b, a] = 1

    rows = "\n".join(f"    [{', '.join(map(str, adj[i]))}],  # {i} {names[i]}" for i in range(n_nodes))
    link_lines = "\n".join(f'  "{k}": {{length: {l}, width: {w}}}  # {s}' for k, l, w, s in links)
    yaml = f"""# =====================================================================
#  "Amsterdam: Centraal to Museumplein": challenge network for PedNStream
#  GENERATED by tools/build_amsterdam.py from the OpenStreetMap walking
#  network (© OpenStreetMap contributors). Edit that script, not this file.
# =====================================================================
#
#  Main places (the other nodes are points along the streets, ~{SEGMENT} m apart):
#    0 Centraal Station (ORIGIN)   9 Stationsplein       1 Dam (Madame Tussauds)
#    2 Westermarkt (Anne Frank)    3 Nieuwmarkt          4 Muntplein
#    5 Waterlooplein               6 Leidseplein         7 Rijksmuseum
#    8 Museumplein (DESTINATION)
#
#  Damrak (Stationsplein -> Dam, past Madame Tussauds) is very wide (20 m) and is
#  the obvious way out of the station, but everything that goes that way has to
#  squeeze through the narrow Kalverstraat (3 m) south of the Dam.
#  Lengths are measured along the OSM walking routes; widths are 'effective'
#  widths (what is left after terraces, bikes and trams).
# =====================================================================

network:
  adjacency_matrix: [
{rows}
  ]
  origin_nodes: [{ORIGIN}]
  destination_nodes: [{DESTINATION}]

simulation:
  seed: 42
  simulation_steps: 720  # 720 x 10 s = 2 hours
  unit_time: 10
  assign_flows_type: "classic"
  od_tracking: true      # each person keeps their destination (OD pair) all the way
  path_finder:
    k_paths: 6
    temp: 5
    alpha: 1
    beta: 2
    omega: 1
    std_dev: 0

default_link:
  length: 300
  width: 4
  free_flow_speed: 1.2
  k_critical: 2
  k_jam: 6
  gamma: 0.01

links:
{link_lines}

# Students replace this with their own arrival pattern.
demand:
  origin_0:
    pattern: "constant"
    base_lambda: 50

od_flows:
  "{ORIGIN}_{DESTINATION}": 1
"""
    (OUT / "sim_params.yaml").write_text(yaml)
    positions = {str(n): [round(c, 1) for c in mercator(lat, lon)] for n, (lon, lat) in sorted(lonlat.items())}
    (OUT / "node_positions.json").write_text(json.dumps(positions) + "\n")
    (OUT / "names.json").write_text(json.dumps({
        "names": {str(n): names[n] for n in sorted(names)},
        "short": {str(DESTINATION): "Museumplein"},
        "streets": streets,
        "label_side": LABEL_SIDE,
        "minor": minor,
    }, ensure_ascii=False, indent=1) + "\n")
    print(f"{n_nodes} nodes, {len(links)} corridors")

    if "--refresh-map" in sys.argv or not (OUT / "background.jpg").exists():
        make_background([ll[1] for ll in lonlat.values()], [ll[0] for ll in lonlat.values()])


def make_background(lats, lons, margin=0.0025, zoom=16, fade=0.45):
    import contextily as cx
    import matplotlib.pyplot as plt

    img, extent = cx.bounds2img(min(lons) - margin, min(lats) - margin, max(lons) + margin, max(lats) + margin,
                                zoom=zoom, source=cx.providers.OpenStreetMap.Mapnik, ll=True, use_cache=False,
                                headers={"User-Agent": USER_AGENT})  # the OSM tile policy asks apps to identify
    rgb = img[..., :3].astype(float) / 255
    rgb = 0.5 * rgb + 0.5 * rgb.mean(axis=2, keepdims=True)  # half desaturated
    rgb = ((1 - fade) * rgb + fade)[::2, ::2]                  # faded, half resolution
    plt.imsave(OUT / "background.jpg", np.clip(rgb, 0, 1), pil_kwargs={"quality": 85})
    (OUT / "background.json").write_text(json.dumps(
        {"extent": [round(float(e), 1) for e in extent], "attribution": "© OpenStreetMap contributors"},
        indent=1) + "\n")


if __name__ == "__main__":
    main()
