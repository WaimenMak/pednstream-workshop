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

NODE_NAMES = {
    0: "West Gate (A)",
    1: "South Gate (B)",
    2: "Plaza",
    3: "Hall",
    4: "Mall Jct",
    5: "Platform (X)",
    6: "City Exit (Y)",
}

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


# ----------------------------------------------------------------------------
# Running a scenario
# ----------------------------------------------------------------------------
def run(
    od: Optional[Dict] = None,
    demand: Optional[Dict[int, Dict]] = None,
    route_choice: Optional[Dict] = None,
    links: Optional[Dict[str, Dict]] = None,
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

    net = gen.create_network(
        str(network_dir),
        od_flows=od_flows,
        demand_params_overrides={f"origin_{o}": p for o, p in (demand or {}).items()},
        link_params_overrides=links or {},
        verbose=False,
    )
    for t in range(1, steps):
        net.network_loading(t)

    return Result(network=net, steps=steps, unit_time=params["unit_time"], od=od_flows)


# ----------------------------------------------------------------------------
# Results
# ----------------------------------------------------------------------------
@dataclass
class Result:
    network: object
    steps: int
    unit_time: float
    od: dict
    _pos: dict = field(default=None, repr=False)

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
        out = next(l for l in node.outgoing_links if not str(l.link_id).startswith("virtual"))
        wanted = np.concatenate([[0.0], np.cumsum(node.demand[: self.steps - 1])])
        entered = out.cumulative_inflow[: self.steps]
        return np.maximum(wanted - entered, 0)

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
        dens = {c: self.density(c).max() for c in CORRIDORS}
        worst = max(dens, key=dens.get)
        k_crit = self.network.links[(2, 3)].k_critical
        congested_minutes = sum((self.density(c) > k_crit).sum() for c in CORRIDORS) * self.unit_time / 60
        return pd.Series(
            {
                "total demand (people)": round(demand),
                "reached Platform X": round(arrived.get(5, 0)),
                "reached City Exit Y": round(arrived.get(6, 0)),
                "turned away at gates": round(blocked),
                "still inside at end": round(demand - blocked - sum(arrived.values())),
                "worst corridor": worst,
                "peak density there (ped/m²)": round(dens[worst], 2),
                "corridor-minutes congested": round(congested_minutes, 1),
                "time spent inside (person-hours)": round(in_net.sum() * self.unit_time / 3600, 1),
            }
        )

    def link_table(self) -> pd.DataFrame:
        rows = []
        for c in CORRIDORS:
            u, v = _parse_key(c)
            fwd = self.network.links[(u, v)]
            bwd = self.network.links[(v, u)]
            d = self.density(c)
            rows.append(
                {
                    "corridor": c,
                    "from → to": f"{NODE_NAMES[u]} → {NODE_NAMES[v]}",
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
            with open(DEFAULT_NETWORK / "node_positions.json") as f:
                self._pos = {int(k): v for k, v in json.load(f).items()}
        return self._pos

    def plot_map(self, step: Optional[int] = None, ax=None, title: Optional[str] = None, vmax: float = 6):
        """Network coloured by density. step=None -> the moment of highest density."""
        if step is None:
            total = sum(self.density(c) for c in CORRIDORS)
            step = int(total.argmax())
        if ax is None:
            _, ax = plt.subplots(figsize=(6, 6))
        segs, cols, widths = [], [], []
        for c in CORRIDORS:
            u, v = _parse_key(c)
            segs.append([self.pos[u], self.pos[v]])
            cols.append(self.density(c)[step])
            widths.append(self.network.links[(u, v)].width * 3)
        norm = Normalize(0, vmax)
        lc = LineCollection(segs, cmap="RdYlGn_r", norm=norm, linewidths=widths, capstyle="round")
        lc.set_array(np.array(cols))
        ax.add_collection(lc)
        for n, (x, y) in self.pos.items():
            colour = "#2e7d32" if n in self.network.origin_nodes else "#c62828" if n in self.network.destination_nodes else "#424242"
            marker = "s" if n in self.network.origin_nodes else "D" if n in self.network.destination_nodes else "o"
            ax.scatter([x], [y], s=160, c=colour, marker=marker, zorder=3, edgecolor="white")
            ax.annotate(NODE_NAMES[n], (x, y), xytext=(8, 8), textcoords="offset points", fontsize=9)
        for c, (u, v) in zip(CORRIDORS, (_parse_key(c) for c in CORRIDORS)):
            (x1, y1), (x2, y2) = self.pos[u], self.pos[v]
            ax.text((x1 + x2) / 2, (y1 + y2) / 2, f"{self.density(c)[step]:.1f}", fontsize=8,
                    ha="center", va="center", bbox=dict(boxstyle="round", fc="white", alpha=0.8, lw=0))
        ax.set_aspect("equal")
        ax.margins(0.25)
        ax.axis("off")
        plt.colorbar(lc, ax=ax, shrink=0.6, label="density (ped/m²)")
        ax.set_title(title or f"Density at minute {step * self.unit_time / 60:.0f}")
        return ax

    def plot_links(self, corridors: Optional[Iterable[str]] = None, ax=None, title: Optional[str] = None):
        """Density over time on each corridor. Dashed line = critical density."""
        if ax is None:
            _, ax = plt.subplots(figsize=(9, 4))
        minutes = self.t * self.unit_time / 60
        for c in corridors or CORRIDORS:
            ax.plot(minutes, self.density(c), label=c)
        ax.axhline(self.network.links[(2, 3)].k_critical, ls="--", c="grey", lw=1)
        ax.set_xlabel("minute")
        ax.set_ylabel("density (ped/m²)")
        ax.legend(ncol=4, fontsize=8)
        ax.set_title(title or "Density per corridor")
        return ax

    def plot_arrivals(self, ax=None, title: Optional[str] = None):
        """Cumulative arrivals at each destination and people turned away at the gates."""
        if ax is None:
            _, ax = plt.subplots(figsize=(9, 4))
        minutes = self.t * self.unit_time / 60
        for d in self.network.destination_nodes:
            ax.plot(minutes, self.arrivals(d), label=f"arrived at {NODE_NAMES[d]}")
        for o in self.network.origin_nodes:
            ax.plot(minutes, self.turned_away(o), ls=":", label=f"turned away at {NODE_NAMES[o]}")
        ax.set_xlabel("minute")
        ax.set_ylabel("people")
        ax.legend(fontsize=8)
        ax.set_title(title or "Arrivals and people turned away")
        return ax

    def dashboard(self, title: str = ""):
        fig = plt.figure(figsize=(14, 6))
        gs = fig.add_gridspec(2, 2, width_ratios=[1, 1.4])
        self.plot_map(ax=fig.add_subplot(gs[:, 0]))
        self.plot_links(ax=fig.add_subplot(gs[0, 1]))
        self.plot_arrivals(ax=fig.add_subplot(gs[1, 1]))
        fig.suptitle(title)
        fig.tight_layout()
        return fig

    def animate(self, every: int = 3):
        """Animated map (returns HTML to display in a notebook)."""
        from matplotlib.animation import FuncAnimation
        from IPython.display import HTML

        fig, ax = plt.subplots(figsize=(6, 6))
        frames = range(0, self.steps, every)

        def draw(step):
            fig.clf()
            self.plot_map(step=step, ax=fig.add_subplot(111))

        anim = FuncAnimation(fig, draw, frames=frames, interval=120)
        html = HTML(anim.to_jshtml())
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
        return f"{100 * a / (a + b):.0f}% / {100 * b / (a + b):.0f}%" if a + b else "no flow"

    def update(*_):
        v = {k: x.value for k, x in s.items()}
        status.value = (
            f"<b>Gate A</b> X/Y split: {share(v['0_5'], v['0_6'])} &nbsp;|&nbsp; "
            f"<b>Gate B</b> X/Y split: {share(v['1_5'], v['1_6'])}"
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
