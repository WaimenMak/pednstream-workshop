"""PedNStream OD-weights workshop.

    from pednstream_workshop import run, compare
    res = run(od={"0_5": 3, "0_6": 1, "1_5": 1, "1_6": 1})
    res.dashboard()
"""

from .tools import (
    AMSTERDAM,
    CORRIDORS,
    DEFAULT_NETWORK,
    NODE_NAMES,
    Result,
    arrival_plan,
    compare,
    compare_maps,
    playground,
    ramp,
    run,
    switch,
    widen,
)

__version__ = "1.6.1"

__all__ = [
    "AMSTERDAM",
    "CORRIDORS",
    "DEFAULT_NETWORK",
    "NODE_NAMES",
    "Result",
    "arrival_plan",
    "compare",
    "compare_maps",
    "playground",
    "ramp",
    "run",
    "switch",
    "widen",
]
