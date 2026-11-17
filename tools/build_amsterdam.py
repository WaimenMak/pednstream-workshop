"""Build the Amsterdam challenge network directly from the OpenStreetMap walking network.

Every walkable street, square and footpath between Centraal Station and Museumplein becomes
part of the PedNStream network: no hand-picked corridors. The steps follow the
build-pedestrian-dataset workflow:

  1. download the OSM walk network for the area (cached in tools/.cache/, git-ignored);
  2. keep a band of BAND metres around the straight line Stationsplein -> Museumplein;
  3. merge the nodes of one intersection (osmnx consolidate_intersections, in metres);
  4. merge parallel ways between the same two junctions (street + sidewalks = one corridor,
     widths added up) and drop dead ends, which no route can use;
  5. give every corridor its OSM length, and a width from the OSM `width` tag or from the
     street type (WIDTH below); Damrak is set very wide on purpose (DAMRAK_WIDTH);
  6. add the station itself (node 0) with a short, wide hall to Stationsplein, so the
     station has exactly one exit.

Writes, in src/pednstream_workshop/networks/amsterdam/:
  adj_matrix.npy        binary adjacency matrix (PedNStream loads it when the YAML has none)
  edge_distances.pkl    {(u, v): length in m}, both directions
  sim_params.yaml       simulation settings, corridor widths, demand and OD
  node_positions.json   node -> [x, y] in Web Mercator metres (EPSG:3857), for the plots
  names.json            names of the main places and the street name of every corridor
  background.jpg/.json  faded OpenStreetMap background (only with --refresh-map or if missing)

Needs `pip install osmnx contextily` (facilitators only; students never run this):
    python tools/build_amsterdam.py [--refresh-map]
"""

import json
import math
import pickle
import re
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import osmnx as ox
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "pednstream_workshop" / "networks" / "amsterdam"
CACHE = ROOT / "tools" / ".cache" / "amsterdam_walk.graphml"
BBOX = (4.876, 52.354, 4.908, 52.382)  # left, bottom, right, top
USER_AGENT = "pednstream-workshop-network-builder/1.0"

BAND = 650        # m on each side of the line Stationsplein -> Museumplein
MERGE = 20        # m, nodes closer than this form one intersection
DROP = {"busway", "elevator", "service"}  # bus lanes, lifts and service alleys are not walking routes
WIDTH = {         # effective walking width (m) per OSM highway type, when the way has no width tag
    "pedestrian": 6, "living_street": 4, "footway": 2.5, "steps": 2, "path": 2, "cycleway": 1.5,
    "residential": 2.5, "unclassified": 2.5, "tertiary": 3.5, "tertiary_link": 3.5,
    "secondary": 4, "primary": 4,
}
MAX_WIDTH = 12    # cap for streets with many parallel ways (except Damrak)
DAMRAK_WIDTH = 20
SQUARE_WIDTH = 10  # Museumplein is an open square: its paths into the destination are at least this wide

# Main places (latitude, longitude): they get the low node numbers and a label on the map.
PLACES = [
    ("Centraal Station", (52.3800, 4.9015)),   # 0: the station itself (origin), drawn inside the building
    ("Stationsplein", (52.3787, 4.8998)),      # 1: in front of the station, where Damrak starts
    ("Dam (Madame Tussauds)", (52.3730, 4.8932)),
    ("Spui", (52.3685, 4.8897)),
    ("Muntplein", (52.3667, 4.8936)),
    ("Leidseplein", (52.3642, 4.8826)),
    ("Rembrandtplein", (52.3661, 4.8966)),
    ("Weteringcircuit", (52.3597, 4.8905)),
    ("Rijksmuseum", (52.3604, 4.8853)),
    ("Museumplein", (52.3577, 4.8830)),        # destination
]
DESTINATION = len(PLACES) - 1
LABEL_SIDE = {"1": "left", "3": "left", "8": "left"}


def mercator(lat, lon):
    r = 6378137.0
    return r * math.radians(lon), r * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def as_set(value):
    if isinstance(value, list):
        return set(value)
    return {value} if isinstance(value, str) and value else set()


FOOT = {"footway", "pedestrian", "path", "steps", "cycleway", "living_street"}


def way_width(d):
    """Width of one OSM way: the width tag of a footpath, else the default of its type.
    (On a road the width tag is the carriageway, not the space for walking.)"""
    for w in as_set(d.get("width")) if as_set(d.get("highway")) <= FOOT else ():
        m = re.match(r"\s*([\d.]+)", w)
        if m and 0.5 <= float(m.group(1)) <= 30:
            return float(m.group(1))
    return max((WIDTH.get(h, 2.5) for h in as_set(d.get("highway"))), default=2.5)


def load_graph():
    if not CACHE.exists():
        ox.settings.http_user_agent = USER_AGENT
        ox.settings.requests_timeout = 300
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        ox.save_graphml(ox.graph_from_bbox(BBOX, network_type="walk"), CACHE)
    return ox.load_graphml(CACHE)


def main():
    G = load_graph()
    print(f"OSM walk network: {G.number_of_nodes()} nodes, {G.number_of_edges()} directed ways")

    # 1. walking ways only, projected to metres (UTM)
    G = G.edge_subgraph([(u, v, k) for u, v, k, d in G.edges(keys=True, data=True)
                         if not as_set(d.get("highway")) & DROP]).copy()
    P = ox.project_graph(G)
    crs = P.graph["crs"]

    def to_utm(lat, lon):
        return ox.projection.project_geometry(Point(lon, lat), to_crs=crs)[0].coords[0]

    def to_latlon(x, y):
        lon, lat = ox.projection.project_geometry(Point(x, y), crs=crs, to_latlong=True)[0].coords[0]
        return lat, lon

    # 2. the band around the line Stationsplein -> Museumplein
    a, b = np.array(to_utm(*PLACES[1][1])), np.array(to_utm(*PLACES[DESTINATION][1]))

    def dist_to_line(x, y):
        p, ab = np.array([x, y]) - a, b - a
        t = np.clip(p @ ab / (ab @ ab), 0, 1)
        return np.linalg.norm(p - t * ab)
    P = P.subgraph([n for n, d in P.nodes(data=True) if dist_to_line(d["x"], d["y"]) <= BAND]).copy()

    # 3. one node per intersection
    C = ox.consolidate_intersections(P, tolerance=MERGE, rebuild_graph=True, dead_ends=False,
                                     reconnect_edges=True)

    # 4. one corridor per pair of junctions: parallel ways (street + sidewalks) add their widths
    U = nx.Graph()
    for u, v, d in ox.convert.to_undirected(C).edges(data=True):
        if u == v:
            continue
        w, names = way_width(d), as_set(d.get("name"))
        if U.has_edge(u, v):
            e = U.edges[u, v]
            e["length"] = min(e["length"], float(d["length"]))
            e["width"] += w
            e["names"] |= names
        else:
            U.add_edge(u, v, length=float(d["length"]), width=w, names=set(names))
    for n in U.nodes:
        U.nodes[n].update(x=C.nodes[n]["x"], y=C.nodes[n]["y"])
    U = U.subgraph(max(nx.connected_components(U), key=len)).copy()

    def nearest(lat, lon):
        x, y = to_utm(lat, lon)
        return min(U.nodes, key=lambda n: (U.nodes[n]["x"] - x) ** 2 + (U.nodes[n]["y"] - y) ** 2)
    place_node = {i: nearest(*ll) for i, (_, ll) in enumerate(PLACES) if i > 0}
    assert len(set(place_node.values())) == len(place_node), "two places snapped to the same node"

    # dead ends can never be on a route between the station and Museumplein
    keep = set(place_node.values())
    while dead := [n for n in U.nodes if U.degree(n) <= 1 and n not in keep]:
        U.remove_nodes_from(dead)

    # 5. number the nodes: main places first, then the rest from north to south
    rest = sorted((n for n in U.nodes if n not in keep), key=lambda n: (-U.nodes[n]["y"], U.nodes[n]["x"]))
    order = [None] + [place_node[i] for i in range(1, len(PLACES))] + rest
    idx = {n: i for i, n in enumerate(order) if n is not None}
    N = len(order)

    adj = np.zeros((N, N), dtype=np.int8)
    dist, widths, streets = {}, {}, {}

    def add(i, j, length, width, street):
        key = f"{min(i, j)}_{max(i, j)}"
        adj[i, j] = adj[j, i] = 1
        dist[(i, j)] = dist[(j, i)] = round(max(length, 5.0), 1)
        widths[key] = round(width, 1)
        streets[key] = street

    add(0, 1, 100, 30, "station hall")  # 6. inside the station: not on the walking network
    for u, v, d in U.edges(data=True):
        names = sorted(d["names"])
        street, width = (names[0] if names else "footpath"), min(d["width"], MAX_WIDTH)
        if "Damrak" in d["names"]:
            street, width = "Damrak", DAMRAK_WIDTH
        if place_node[DESTINATION] in (u, v):
            street, width = "Museumplein", max(width, SQUARE_WIDTH)
        add(idx[u], idx[v], d["length"], width, street)

    np.save(OUT / "adj_matrix.npy", adj)
    with open(OUT / "edge_distances.pkl", "wb") as f:
        pickle.dump(dist, f)

    latlon = {0: PLACES[0][1]}
    latlon.update({i: to_latlon(U.nodes[n]["x"], U.nodes[n]["y"]) for n, i in idx.items()})
    positions = {str(i): [round(c, 1) for c in mercator(*ll)] for i, ll in sorted(latlon.items())}
    (OUT / "node_positions.json").write_text(json.dumps(positions) + "\n")
    (OUT / "names.json").write_text(json.dumps({
        "names": {str(i): name for i, (name, _) in enumerate(PLACES)},
        "short": {str(DESTINATION): "Museumplein"},
        "streets": streets,
        "label_side": LABEL_SIDE,
        "minor": list(range(len(PLACES), N)),
    }, ensure_ascii=False, indent=1) + "\n")

    link_lines = "\n".join(f'  "{k}": {{width: {w}}}  # {streets[k]}' for k, w in widths.items())
    places = "\n".join(f"#    {i:2d} {name}" for i, (name, _) in enumerate(PLACES))
    yaml = f"""# =====================================================================
#  "Amsterdam: Centraal to Museumplein": challenge network for PedNStream
#  GENERATED by tools/build_amsterdam.py straight from the OpenStreetMap
#  walking network (© OpenStreetMap contributors). Edit that script, not this file.
# =====================================================================
#
#  {N} nodes and {len(widths)} corridors: every walkable street within {BAND} m of the line
#  Stationsplein - Museumplein. The adjacency matrix is in adj_matrix.npy and the corridor
#  lengths (measured along OSM) are in edge_distances.pkl. Main places:
{places}
#
#  Widths are 'effective' walking widths: the OSM width tag, or a default per street type,
#  with the street and its sidewalks between the same two junctions added up. Damrak
#  (past Madame Tussauds) is set to {DAMRAK_WIDTH} m on purpose.
#  The paths into Museumplein (an open square) are at least {SQUARE_WIDTH} m.
# =====================================================================

network:
  origin_nodes: [0]
  destination_nodes: [{DESTINATION}]

simulation:
  seed: 42
  simulation_steps: 720  # 720 x 10 s = 2 hours
  unit_time: 10
  assign_flows_type: "classic"
  od_tracking: true      # each person keeps their destination (OD pair) all the way
  path_finder:
    k_paths: 8             # up to 8 routes ...
    diverse_paths: true    # ... that really differ (see diverse_paths in the workshop package)
    temp: 5
    alpha: 1
    beta: 2
    omega: 1
    std_dev: 0

default_link:
  length: 50
  width: 3
  free_flow_speed: 1.34   # m/s, a typical free walking speed
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
  "0_{DESTINATION}": 1
"""
    (OUT / "sim_params.yaml").write_text(yaml)
    walk = nx.shortest_path_length(U, place_node[1], place_node[DESTINATION], weight="length")
    print(f"{N} nodes, {len(widths)} corridors; shortest walk Stationsplein -> Museumplein {walk:.0f} m")

    if "--refresh-map" in sys.argv or not (OUT / "background.jpg").exists():
        make_background([ll[0] for ll in latlon.values()], [ll[1] for ll in latlon.values()])


def make_background(lats, lons, margin=0.0015, aspect=1.8, zoom=16, fade=0.45):
    """Street map around the network, at least `aspect` times as wide as it is high, so a wide
    plot (the animation) shows more of the city on both sides instead of white space."""
    import contextily as cx
    import matplotlib.pyplot as plt

    (x0, y0), (x1, y1) = mercator(min(lats) - margin, min(lons) - margin), mercator(max(lats) + margin, max(lons) + margin)
    extra = max(0.0, aspect * (y1 - y0) - (x1 - x0)) / 2
    img, extent = cx.bounds2img(x0 - extra, y0, x1 + extra, y1, zoom=zoom, source=cx.providers.OpenStreetMap.Mapnik,
                                ll=False, use_cache=False,
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
