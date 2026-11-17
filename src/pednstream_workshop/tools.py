"""Helper layer for the PedNStream OD-weights workshop.

Students call a handful of friendly functions:

    res = run(od={"0_5": 1, "0_6": 1, "1_5": 1, "1_6": 1})
    res.kpis()            # headline numbers
    res.plot_map()        # network coloured by density at the worst moment
    res.plot_links()      # density over time on every corridor
    res.plot_arrivals()   # who reached which destination, and when
    compare({"A": res1, "B": res2})

Everything underneath is plain PedNStream (NetworkEnvGenerator + Network).
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize

from pednstream.utils.network_env_generator import NetworkEnvGenerator

HERE = Path(__file__).resolve().parent
DEFAULT_NETWORK = HERE / "networks" / "station_square"
AMSTERDAM = HERE / "networks" / "amsterdam"

# plot_map frames the network and lets a wide panel show more street map (adjustable="datalim");
# matplotlib then warns at every draw that it widened the limits, which is exactly what we want
logging.getLogger("matplotlib.axes._base").addFilter(
    lambda record: "to fulfill fixed data aspect" not in record.getMessage())


def _load_names(network_dir) -> dict:
    """names.json next to sim_params.yaml: display names per node (+ short names for KPIs)."""
    path = Path(network_dir) / "names.json"
    if not path.exists():
        return {"names": {}, "short": {}, "streets": {}, "label_side": {}, "minor": set()}
    with open(path) as f:
        raw = json.load(f)
    out = {k: {(int(n) if "_" not in n else n): v for n, v in raw.get(k, {}).items()}
           for k in ("names", "short", "streets", "label_side")}
    out["minor"] = {int(n) for n in raw.get("minor", [])}  # points along a street: number only
    return out


NODE_NAMES = _load_names(DEFAULT_NETWORK)["names"]

CORRIDORS = ["0_2", "1_3", "2_3", "2_4", "3_4", "3_5", "4_6"]


# ----------------------------------------------------------------------------
# Input helpers
# ----------------------------------------------------------------------------
def _parse_key(key) -> tuple:
    if isinstance(key, tuple):
        return tuple(int(k) for k in key)
    o, d = str(key).split("_")
    return int(o), int(d)


def switch(before: float, after: float, at_step: int, steps: int = 300) -> np.ndarray:
    """A time-varying OD weight: `before` until `at_step`, then `after`.

    Example: a concert ends at step 150 and suddenly everyone wants the platform:
        od = {"0_5": switch(1, 5, 150), "0_6": 1, ...}
    """
    arr = np.full(steps + 1, float(before))
    arr[at_step:] = float(after)
    return arr


def ramp(start: float, end: float, steps: int = 300) -> np.ndarray:
    """A time-varying OD weight that changes linearly from `start` to `end`."""
    return np.linspace(float(start), float(end), steps + 1)


def arrival_plan(per_minute: Iterable[float], block_minutes: float = 10, unit_time: float = 10,
                 steps: int = 720) -> np.ndarray:
    """People arriving per time step from a list of 'people per minute', one value per block.

    Example: arrival_plan([300, 300, 0, 300]) -> 300 people/min for minutes 0-10 and 10-20,
    nobody in minutes 20-30, 300/min in minutes 30-40, nobody after that.
    """
    per_block = int(round(block_minutes * 60 / unit_time))
    arr = np.zeros(steps + 1)
    for i, rate in enumerate(per_minute):
        arr[i * per_block:(i + 1) * per_block] = float(rate) * unit_time / 60
    return arr


def diverse_paths(graph, origin, dest, max_paths=8, stretch=1.3, penalty=1.6):
    """Up to `max_paths` routes that really differ, none more than `stretch` x the shortest.

    In a dense street grid the k shortest paths are near-copies (they differ in one alley), so
    people could never spread over parallel streets. Here: take the shortest route, make its
    streets look `penalty` x longer, take the next shortest route, and so on.
    Used instead of PedNStream's k-shortest-paths for networks whose sim_params.yaml sets
    `path_finder: {diverse_paths: true}` (the Amsterdam OSM network).
    """
    import networkx as nx

    length = {(u, v): d["weight"] for u, v, d in graph.edges(data=True)}
    weight = dict(length)
    shortest = nx.shortest_path_length(graph, origin, dest, weight="weight")
    paths = []
    for _ in range(4 * max_paths):
        p = nx.shortest_path(graph, origin, dest, weight=lambda u, v, d: weight[(u, v)])
        if sum(length[e] for e in zip(p, p[1:])) > stretch * shortest:
            break
        if p not in paths:
            paths.append(p)
            if len(paths) == max_paths:
                break
        for u, v in zip(p, p[1:]):
            weight[(u, v)] *= penalty
            if (v, u) in weight:
                weight[(v, u)] *= penalty
    return paths


@contextmanager
def _route_set(params):
    """Use `diverse_paths` instead of PedNStream's k shortest paths while a network is built,
    if its sim_params.yaml asks for it (path_finder: {diverse_paths: true})."""
    import pednstream.ltm.path_finder as pf

    k_shortest = pf.enumerate_shortest_simple_paths
    if params.get("path_finder", {}).get("diverse_paths"):
        pf.enumerate_shortest_simple_paths = diverse_paths   # PedNStream looks it up when it builds routes
    try:
        yield
    finally:
        pf.enumerate_shortest_simple_paths = k_shortest


def widen(street: str, extra: float = 2, network_dir: Path | str = AMSTERDAM) -> Dict[str, Dict]:
    """Link overrides that widen every stretch of a named street, for run(links=...).

    Example: run(network_dir=AMSTERDAM, links=widen("Kalverstraat"), ...)
    """
    import yaml

    streets = _load_names(network_dir)["streets"]
    keys = [k for k, s in streets.items() if s == street]
    if not keys:
        raise ValueError(f"No street called {street!r}. Streets: {sorted(set(streets.values()))}")
    with open(Path(network_dir) / "sim_params.yaml") as f:
        cfg = yaml.safe_load(f)
    default = cfg.get("default_link", {}).get("width", 0)
    return {k: {"width": cfg.get("links", {}).get(k, {}).get("width", default) + extra} for k in keys}


# ----------------------------------------------------------------------------
# Running a scenario
# ----------------------------------------------------------------------------
def run(
    od: Optional[Dict] = None,
    demand: Optional[Dict[int, Dict]] = None,
    route_choice: Optional[Dict] = None,
    links: Optional[Dict[str, Dict]] = None,
    origins: Optional[Iterable[int]] = None,
    arrivals: Optional[Dict[int, Iterable[float]]] = None,
    network_dir: Path | str = DEFAULT_NETWORK,
) -> "Result":
    """Run one scenario and return a `Result`.

    Args:
        od: OD weights, e.g. {"0_5": 3, "0_6": 1, "1_5": 1, "1_6": 1}.
            Values are *relative* per origin. A value can also be an array
            (see `switch` / `ramp`) to make the weight change over time.
            Missing pairs keep the value from sim_params.yaml.
        demand: per-origin demand overrides, e.g. {0: {"peak_lambda": 60}}.
        route_choice: path-finder overrides, e.g. {"beta": 0} (ignore congestion).
        links: link overrides, e.g. {"2_3": {"width": 4}}.
        origins: keep only these gates as origins, e.g. [0] for Gate A alone.
            The other gates and their OD pairs are removed from the model.
        arrivals: your own arrival pattern per origin: people per time step,
            e.g. {0: arrival_plan([300, 300, 0, 300])}. Replaces `demand` for that origin.
        network_dir: which network to load, e.g. AMSTERDAM. Default: Station Square.
    """
    gen = NetworkEnvGenerator()
    gen.network_data = gen.load_network_data(str(network_dir))
    params = gen.config["params"]
    steps = params["simulation_steps"]

    if route_choice:
        params["path_finder"] = {**params.get("path_finder", {}), **route_choice}

    od_flows = dict(gen.config.get("od_flows", {}))
    for key, w in (od or {}).items():
        o, d = _parse_key(key)
        if np.ndim(w) and len(w) != steps + 1:
            raise ValueError(f"OD {key}: time-varying weights need {steps + 1} values, got {len(w)}")
        od_flows[(o, d)] = w

    od_nodes = {}
    if origins is not None:
        origins = [int(o) for o in origins]
        od_flows = {od: w for od, w in od_flows.items() if _parse_key(od)[0] in origins}
        od_nodes = {"origin_nodes": origins}

    demand_overrides = {f"origin_{o}": p for o, p in (demand or {}).items()}
    custom = []
    for o, pattern in (arrivals or {}).items():
        values = np.zeros(steps + 1)
        pattern = np.asarray(pattern, dtype=float)[: steps + 1]
        values[: len(pattern)] = pattern

        def fixed_arrivals(origin_id, params=None, _v=values):
            return _v.copy()

        fixed_arrivals.__name__ = f"workshop_arrivals_{o}"   # PedNStream registers patterns by name
        custom.append(fixed_arrivals)
        demand_overrides[f"origin_{o}"] = {"pattern": fixed_arrivals.__name__}

    if custom:
        # built-in demand patterns reseed numpy themselves; ours don't, so seed here
        # to make every run with the same plan give exactly the same result
        np.random.seed(params.get("seed", 42))
    with _route_set(params):
        net = gen.create_network(
            str(network_dir),
            od_flows=od_flows,
            demand_params_overrides=demand_overrides,
            link_params_overrides=links or {},
            od_nodes_overrides=od_nodes,
            custom_demand_functions=custom,
            verbose=False,
        )
    for t in range(1, steps):
        net.network_loading(t)

    return Result(network=net, steps=steps, unit_time=params["unit_time"], od=od_flows,
                  network_dir=Path(network_dir))


# ----------------------------------------------------------------------------
# Results
# ----------------------------------------------------------------------------
@dataclass
class Result:
    network: object
    steps: int
    unit_time: float
    od: dict
    network_dir: Path = DEFAULT_NETWORK
    _pos: dict = field(default=None, repr=False)
    _names: dict = field(default=None, repr=False)

    # --- network description -------------------------------------------------
    @property
    def corridors(self) -> list:
        """Every two-way corridor as 'u_v' (u < v), virtual origin/destination links left out."""
        if Path(self.network_dir) == DEFAULT_NETWORK:
            return CORRIDORS
        keys = {tuple(sorted(k)) for k, l in self.network.links.items()
                if not str(l.link_id).startswith("virtual")}
        return [f"{u}_{v}" for u, v in sorted(keys)]

    @property
    def names(self) -> dict:
        if self._names is None:
            self._names = _load_names(self.network_dir)
        return self._names

    def name(self, node: int) -> str:
        return self.names["names"].get(node, f"node {node}")

    def short(self, node: int) -> str:
        return self.names["short"].get(node, self.name(node))

    def corridor_label(self, c: str) -> str:
        street = self.names["streets"].get(c)
        return f"{c} {street}" if street else c

    @property
    def k_critical(self) -> float:
        return self.link(self.corridors[0]).k_critical

    # --- raw series ---------------------------------------------------------
    @property
    def t(self) -> np.ndarray:
        return np.arange(self.steps)

    def link(self, key: str):
        return self.network.links[_parse_key(key)]

    def density(self, key: str) -> np.ndarray:
        """Density (ped/m^2) on a corridor, both directions added up."""
        u, v = _parse_key(key)
        d = self.network.links[(u, v)].density[: self.steps].astype(float)
        if (v, u) in self.network.links:
            d = d + self.network.links[(v, u)].density[: self.steps]
        return d

    def turned_away(self, origin: int) -> np.ndarray:
        """Cumulative people who could NOT enter at a gate because the first
        corridor was full (PedNStream drops this demand, it does not queue it)."""
        node = self.network.nodes[origin]
        wanted = np.concatenate([[0.0], np.cumsum(node.demand[: self.steps - 1])])
        return np.maximum(wanted - self.entered(origin), 0)

    def entered(self, origin: int) -> np.ndarray:
        """Cumulative number of people who walked into the network at an origin."""
        node = self.network.nodes[origin]
        out = [l for l in node.outgoing_links if not str(l.link_id).startswith("virtual")]
        return sum(l.cumulative_inflow[: self.steps] for l in out)

    def arrivals(self, dest: int) -> np.ndarray:
        """Cumulative number of people who reached a destination."""
        node = self.network.nodes[dest]
        incoming = [l for l in node.incoming_links if not str(l.link_id).startswith("virtual")]
        return sum(l.cumulative_outflow[: self.steps] for l in incoming)

    # --- headline numbers ----------------------------------------------------
    def kpis(self) -> pd.Series:
        nodes = self.network.nodes
        origins, dests = self.network.origin_nodes, self.network.destination_nodes
        demand = sum(nodes[o].demand[: self.steps - 1].sum() for o in origins)
        blocked = sum(self.turned_away(o)[-1] for o in origins)
        arrived = {d: self.arrivals(d)[-1] for d in dests}
        in_net = sum(l.num_pedestrians[: self.steps] for l in self.network.links.values())
        dens = {c: self.density(c).max() for c in self.corridors}
        worst = max(dens, key=dens.get)
        k_crit = self.k_critical
        congested_minutes = sum((self.density(c) > k_crit).sum() for c in self.corridors) * self.unit_time / 60
        return pd.Series(
            {
                "total demand (people)": round(demand),
                **{f"reached {self.short(d)}": round(arrived[d]) for d in dests},
                "turned away at gates": round(blocked),
                "still inside at end": round(demand - blocked - sum(arrived.values())),
                "worst corridor": self.corridor_label(worst),
                "peak density there (ped/m²)": round(dens[worst], 2),
                "corridor-minutes congested": round(congested_minutes, 1),
                "time spent inside (person-hours)": round(in_net.sum() * self.unit_time / 3600, 1),
            }
        )

    def link_table(self) -> pd.DataFrame:
        rows = []
        for c in self.corridors:
            u, v = _parse_key(c)
            fwd = self.network.links[(u, v)]
            bwd = self.network.links[(v, u)]
            d = self.density(c)
            rows.append(
                {
                    "corridor": self.corridor_label(c),
                    "from → to": f"{self.name(u)} → {self.name(v)}",
                    "width (m)": fwd.width,
                    "length (m)": fwd.length,
                    "people through": round(fwd.cumulative_inflow[self.steps - 1] + bwd.cumulative_inflow[self.steps - 1]),
                    "peak density": round(d.max(), 2),
                    "peak at minute": round(d.argmax() * self.unit_time / 60, 1),
                }
            )
        return pd.DataFrame(rows).set_index("corridor")

    def route_split(self) -> pd.DataFrame:
        """How each OD pair splits over its routes (at the node where they diverge).

        These are the route-choice probabilities PedNStream used in the last step.
        """
        rows = []
        for od, paths in self.network.path_finder.od_paths.items():
            if len(paths) == 1:
                rows.append({"OD": f"{od[0]}_{od[1]}", "route": "-".join(map(str, paths[0])), "share": 1.0})
                continue
            k = next(i for i in range(1, min(map(len, paths))) if len({p[i] for p in paths}) > 1) - 1
            node = self.network.nodes[paths[0][k]]
            turn_p = getattr(node, "node_turn_probs", {}).get(od, {})
            for p in paths:
                up = p[k - 1] if k > 0 else -1
                rows.append({
                    "OD": f"{od[0]}_{od[1]}",
                    "route": "-".join(map(str, p)),
                    "share": round(turn_p.get((up, p[k + 1]), np.nan), 2),
                })
        return pd.DataFrame(rows)

    # --- plots --------------------------------------------------------------
    @property
    def pos(self) -> dict:
        if self._pos is None:
            with open(Path(self.network_dir) / "node_positions.json") as f:
                self._pos = {int(k): v for k, v in json.load(f).items()}
        return self._pos

    @property
    def background(self):
        """(image, extent, attribution) of the street map behind the network, or None."""
        if not hasattr(self, "_background"):
            img_path = Path(self.network_dir) / "background.jpg"
            meta_path = Path(self.network_dir) / "background.json"
            self._background = None
            if img_path.exists() and meta_path.exists():
                with open(meta_path) as f:
                    meta = json.load(f)
                self._background = (plt.imread(img_path), meta["extent"], meta.get("attribution", ""))
        return self._background

    def plot_map(self, step: Optional[int] = None, ax=None, title: Optional[str] = None, vmax: float = 6):
        """Network coloured by density. step=None -> the moment of highest density."""
        if step is None:
            total = sum(self.density(c) for c in self.corridors)
            step = int(total.argmax())
        if ax is None:
            _, ax = plt.subplots(figsize=(6, 6))
        street_map = len(self.corridors) > 100   # a whole street network: thin lines, empty streets grey
        segs, cols, widths, empty = [], [], [], []
        for c in self.corridors:
            u, v = _parse_key(c)
            d = self.density(c)[step]
            w = self.network.links[(u, v)].width
            if street_map and d < 0.02:
                empty.append([self.pos[u], self.pos[v]])
                continue
            segs.append([self.pos[u], self.pos[v]])
            cols.append(d)
            widths.append(w * 3 if Path(self.network_dir) == DEFAULT_NETWORK
                          else 1.5 * np.sqrt(w) if street_map else 4 * np.sqrt(w))
        norm = Normalize(0, vmax)
        bg = self.background
        if empty:
            ax.add_collection(LineCollection(empty, colors="#9e9e9e", linewidths=0.6, alpha=0.7, zorder=1))
        lc = LineCollection(segs, cmap="RdYlGn_r", norm=norm, linewidths=widths, capstyle="round",
                            alpha=0.85 if bg else 1, zorder=2)
        lc.set_array(np.array(cols))
        ax.add_collection(lc)
        label_box = dict(boxstyle="round,pad=0.15", fc="white", alpha=0.75, lw=0) if bg else None
        for n, (x, y) in self.pos.items():
            if n in self.names["minor"]:
                if not street_map:   # points along a street: small grey dot with its number
                    ax.scatter([x], [y], s=70, c="#757575", zorder=3, edgecolor="white", linewidths=0.5)
                    ax.text(x, y, str(n), color="white", fontsize=5, ha="center", va="center", zorder=4)
                continue
            colour = "#2e7d32" if n in self.network.origin_nodes else "#c62828" if n in self.network.destination_nodes else "#424242"
            marker = "s" if n in self.network.origin_nodes else "D" if n in self.network.destination_nodes else "o"
            ax.scatter([x], [y], s=260, c=colour, marker=marker, zorder=3, edgecolor="white")
            ax.text(x, y, str(n), color="white", fontsize=8, fontweight="bold", ha="center", va="center", zorder=4)
            label = self.name(n) if Path(self.network_dir) == DEFAULT_NETWORK else self.name(n).split(" (")[0]
            side = self.names["label_side"].get(n, "right")
            offset, ha, va = {"right": ((10, 8), "left", "bottom"), "left": ((-10, 8), "right", "bottom"),
                              "below": ((0, -12), "center", "top")}[side]
            ax.annotate(label, (x, y), xytext=offset, textcoords="offset points", fontsize=9, zorder=5,
                        ha=ha, va=va, bbox=label_box)
        many = len(self.corridors) > 20   # big network: only label the crowded links
        for c, (u, v) in zip(self.corridors, (_parse_key(c) for c in self.corridors)):
            (x1, y1), (x2, y2) = self.pos[u], self.pos[v]
            if street_map or (many and self.density(c)[step] < 1):
                continue
            ax.text((x1 + x2) / 2, (y1 + y2) / 2, f"{self.density(c)[step]:.1f}", fontsize=8, zorder=4,
                    ha="center", va="center", bbox=dict(boxstyle="round", fc="white", alpha=0.8, lw=0))
        ax.set_aspect("equal")
        if bg:
            img, extent, attribution = bg
            ax.imshow(img, extent=extent, zorder=0, interpolation="bilinear")
            # frame the network; a wide panel shows more of the street map left and right
            xs, ys = [p[0] for p in self.pos.values()], [p[1] for p in self.pos.values()]
            pad = 0.06 * max(max(xs) - min(xs), max(ys) - min(ys))
            ax.set_xlim(max(extent[0], min(xs) - pad), min(extent[1], max(xs) + pad))
            ax.set_ylim(max(extent[2], min(ys) - pad), min(extent[3], max(ys) + pad))
            ax.set_aspect("equal", adjustable="datalim")
            ax.text(0.99, 0.01, attribution, transform=ax.transAxes, fontsize=6, ha="right", va="bottom",
                    color="#555555", zorder=5)
            ax.set_xticks([]); ax.set_yticks([])
        else:
            ax.margins(0.25)
            ax.axis("off")
        ax.figure.colorbar(lc, ax=ax, shrink=0.6, label="density (ped/m²)")
        ax.set_title(title or f"Density at minute {step * self.unit_time / 60:.0f}")
        return ax

    def plot_links(self, corridors: Optional[Iterable[str]] = None, ax=None, title: Optional[str] = None):
        """Density over time on each corridor. Dashed line = critical density."""
        if ax is None:
            _, ax = plt.subplots(figsize=(9, 4))
        minutes = self.t * self.unit_time / 60
        if corridors is None and self.names["streets"] and len(self.corridors) > 20:
            # big network: one line per street (its most crowded link), busy streets only
            by_street = {}
            for c in self.corridors:
                by_street.setdefault(self.names["streets"].get(c, c), []).append(self.density(c))
            worst = {street: np.max(dens, axis=0) for street, dens in by_street.items()}
            busiest = sorted(worst, key=lambda s: -worst[s].max())[:8]   # the 8 most crowded streets
            for street in busiest:
                if worst[street].max() > 0.1 * self.k_critical:
                    ax.plot(minutes, worst[street], label=street)
            corridors = []
        elif corridors is None:
            corridors = self.corridors
        for c in corridors:
            ax.plot(minutes, self.density(c), label=self.corridor_label(c))
        ax.axhline(self.k_critical, ls="--", c="grey", lw=1)
        ax.set_xlabel("minute")
        ax.set_ylabel("density (ped/m²)")
        ax.legend(ncol=4, fontsize=8)
        ax.set_title(title or ("Density on the most crowded streets" if not corridors else "Density per corridor"))
        return ax

    def people_on(self, key: str) -> np.ndarray:
        """Number of people on a corridor, both directions added up."""
        u, v = _parse_key(key)
        n = self.network.links[(u, v)].num_pedestrians[: self.steps].astype(float)
        if (v, u) in self.network.links:
            n = n + self.network.links[(v, u)].num_pedestrians[: self.steps]
        return n

    def plot_flow(self, ax=None, title: Optional[str] = None):
        """People per minute leaving the origin(s) vs arriving at the destination(s),
        with the number of people inside the network on a second axis."""
        if ax is None:
            _, ax = plt.subplots(figsize=(9, 4))
        minutes = self.t * self.unit_time / 60
        scale = 60 / self.unit_time

        def rate(cum):
            return np.diff(cum, prepend=0) * scale

        departures = sum(self.entered(o) for o in self.network.origin_nodes)
        arrivals = sum(self.arrivals(d) for d in self.network.destination_nodes)
        ax.fill_between(minutes, rate(departures), step="pre", alpha=0.35, color="tab:blue", label="leaving the station (your plan)")
        ax.plot(minutes, rate(arrivals), color="tab:red", lw=2, label="arriving at the destination")
        ax.set_xlabel("minute")
        ax.set_ylabel("people per minute")
        ax2 = ax.twinx()
        ax2.plot(minutes, departures - arrivals, color="black", ls="--", lw=1, label="people on the streets")
        ax2.set_ylabel("people on the streets")
        ax2.set_ylim(bottom=0)
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, fontsize=8, loc="upper right")
        ax.set_title(title or "In and out")
        return ax

    def plot_arrivals(self, ax=None, title: Optional[str] = None):
        """Cumulative arrivals at each destination and people turned away at the gates."""
        if ax is None:
            _, ax = plt.subplots(figsize=(9, 4))
        minutes = self.t * self.unit_time / 60
        for d in self.network.destination_nodes:
            ax.plot(minutes, self.arrivals(d), label=f"arrived at {self.name(d)}")
        for o in self.network.origin_nodes:
            ax.plot(minutes, self.turned_away(o), ls=":", label=f"turned away at {self.name(o)}")
        ax.set_xlabel("minute")
        ax.set_ylabel("people")
        ax.legend(fontsize=8)
        ax.set_title(title or "Arrivals and people turned away")
        return ax

    def dashboard(self, title: str = "", flow: bool = False):
        """Map + density over time + arrivals (flow=True: people per minute in and out instead)."""
        fig = plt.figure(figsize=(14, 6))
        gs = fig.add_gridspec(2, 2, width_ratios=[1, 1.4])
        self.plot_map(ax=fig.add_subplot(gs[:, 0]))
        self.plot_links(ax=fig.add_subplot(gs[0, 1]))
        (self.plot_flow if flow else self.plot_arrivals)(ax=fig.add_subplot(gs[1, 1]))
        fig.suptitle(title)
        fig.tight_layout()
        return fig

    def animate(self, every: int = 3, flow: bool = False):
        """Animated map (returns HTML to display in a notebook).

        flow=True adds the 'In and out' plot next to the map, with a line marking the current minute.
        """
        from matplotlib.animation import FuncAnimation
        from IPython.display import HTML

        fig = plt.figure(figsize=(16, 7.5), dpi=65) if flow else plt.figure(figsize=(6, 6))
        frames = range(0, self.steps, every)

        def draw(step):
            fig.clf()
            minute = step * self.unit_time / 60
            if not flow:
                self.plot_map(step=step, ax=fig.add_subplot(111))
                return
            gs = fig.add_gridspec(1, 2, width_ratios=[1.9, 1])   # most of the width for the map
            self.plot_map(step=step, ax=fig.add_subplot(gs[0]), title=f"Density at minute {minute:.0f}")
            ax = fig.add_subplot(gs[1])
            self.plot_flow(ax=ax)
            ax.axvline(minute, color="black", lw=2)
            fig.tight_layout()

        anim = FuncAnimation(fig, draw, frames=frames, interval=120)
        if not flow:
            html = HTML(anim.to_jshtml())
        else:
            # JPEG frames: a street map in every frame makes PNG frames ~4x bigger
            import tempfile
            from matplotlib.animation import HTMLWriter

            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "movie.html"
                writer = HTMLWriter(fps=1000 / 120, embed_frames=True, default_mode="once")
                writer.frame_format = "jpeg"
                anim.save(str(path), writer=writer, dpi=fig.dpi)
                html = HTML(path.read_text())
        plt.close(fig)
        return html


# ----------------------------------------------------------------------------
# Comparing scenarios
# ----------------------------------------------------------------------------
def compare(results: Dict[str, Result]) -> pd.DataFrame:
    """Side-by-side KPI table for several scenarios."""
    return pd.DataFrame({name: r.kpis() for name, r in results.items()})


def compare_maps(results: Dict[str, Result]):
    """One density map per scenario, each at its own worst moment."""
    n = len(results)
    fig, axes = plt.subplots(1, n, figsize=(5.5 * n, 5.5))
    for ax, (name, r) in zip(np.atleast_1d(axes), results.items()):
        r.plot_map(ax=ax, title=name)
    fig.tight_layout()
    return fig


# ----------------------------------------------------------------------------
# Interactive playground (needs ipywidgets)
# ----------------------------------------------------------------------------
def playground():
    """Sliders for OD weights, demand and route choice. Re-runs on every change."""
    import ipywidgets as w
    from IPython.display import display, clear_output

    def slider(desc, value, lo=0, hi=5, step=0.5):
        return w.FloatSlider(value=value, min=lo, max=hi, step=step, description=desc,
                             style={"description_width": "150px"}, layout=w.Layout(width="420px"))

    s = {
        "0_5": slider("A → Platform X", 1),
        "0_6": slider("A → City Exit Y", 1),
        "1_5": slider("B → Platform X", 1),
        "1_6": slider("B → City Exit Y", 1),
        "peakA": slider("Gate A peak (ped/step)", 40, 0, 80, 5),
        "peakB": slider("Gate B peak (ped/step)", 40, 0, 80, 5),
        "beta": slider("Congestion avoidance β", 2, 0, 10, 0.5),
        "w23": slider("Corridor 2_3 width (m)", 2, 1, 6, 0.5),
    }
    out = w.Output()
    status = w.HTML()

    def share(a, b):
        return f"{100 * a / (a + b):.0f}% / {100 * b / (a + b):.0f}%" if a + b else "50% / 50%"

    def update(*_):
        v = {k: x.value for k, x in s.items()}
        status.value = (
            f"Weights ask for <b>Gate A</b> X/Y: {share(v['0_5'], v['0_6'])} &nbsp;|&nbsp; "
            f"<b>Gate B</b> X/Y: {share(v['1_5'], v['1_6'])}"
        )
        res = run(
            od={k: v[k] for k in ("0_5", "0_6", "1_5", "1_6")},
            demand={0: {"peak_lambda": v["peakA"]}, 1: {"peak_lambda": v["peakB"]}},
            route_choice={"beta": v["beta"]},
            links={"2_3": {"width": v["w23"]}},
        )
        with out:
            clear_output(wait=True)
            res.dashboard()
            plt.show()
            display(res.kpis().to_frame("value"))

    for x in s.values():
        x.observe(update, names="value")
    ui = w.VBox([
        w.HTML("<h4>OD weights (relative, per gate)</h4>"),
        w.HBox([w.VBox([s["0_5"], s["0_6"]]), w.VBox([s["1_5"], s["1_6"]])]),
        status,
        w.HTML("<h4>Demand, behaviour, infrastructure</h4>"),
        w.HBox([w.VBox([s["peakA"], s["peakB"]]), w.VBox([s["beta"], s["w23"]])]),
        out,
    ])
    display(ui)
    update()
